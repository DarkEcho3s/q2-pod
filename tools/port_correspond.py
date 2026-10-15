#!/usr/bin/env python3
"""Find address correspondences in paired MIPS functions (research, never patching).

Instruction alignment is only a search aid. Every candidate retains its source
function and instruction addresses so a target manifest can cite reviewed code.
"""
import argparse
from collections import defaultdict
import difflib
import io
import json
from pathlib import Path
import re
import struct

from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile


class Image:
    def __init__(self, path):
        self.raw = Path(path).read_bytes()
        self.elf = ELFFile(io.BytesIO(self.raw))
        self.symbols = {s.name: (s['st_value'], s['st_size']) for s in
                        self.elf.get_section_by_name('.dynsym').iter_symbols()
                        if s['st_shndx'] != 'SHN_UNDEF'}
        self.gp = struct.unpack('<6I', self.elf.get_section_by_name('.reginfo').data())[-1]
        self.cs = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
        self.cs.skipdata = True

    def read(self, address, size):
        for s in self.elf.iter_segments():
            if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= address and address+size <= s['p_vaddr']+s['p_filesz']:
                off = s['p_offset']+address-s['p_vaddr']
                return self.raw[off:off+size]
        raise ValueError(hex(address))

    def instructions(self, address, size):
        regs = {'$gp': self.gp, '$zero': 0}
        result = []
        for ins in self.cs.disasm(self.read(address, size), address):
            ops = ins.op_str.split(', ')
            refs = []
            if ins.mnemonic in ('j', 'jal', 'b', 'bal') and len(ops) == 1:
                refs.append(('call', int(ops[0], 0)))
            elif ins.mnemonic == 'lui':
                regs[ops[0]] = int(ops[1], 0) << 16
            elif ins.mnemonic in ('addiu', 'ori') and ops[1] in regs:
                value = regs[ops[1]] + int(ops[2], 0) if ins.mnemonic == 'addiu' else regs[ops[1]] | int(ops[2], 0)
                regs[ops[0]] = value & 0xffffffff
                refs.append(('value', regs[ops[0]]))
            elif ins.mnemonic == 'move':
                if ops[1] in regs: regs[ops[0]] = regs[ops[1]]
                else: regs.pop(ops[0], None)
            elif ins.mnemonic in ('lw', 'sw', 'lb', 'lbu', 'sb', 'lh', 'lhu', 'sh'):
                m = re.fullmatch(r'(-?0x[0-9a-f]+|-?\d+)?\((\$\w+)\)', ops[1])
                base = regs.get(m[2]) if m else None
                if base is not None:
                    addr = base + int(m[1] or '0', 0)
                    refs.append(('memory', addr))
                    if ins.mnemonic == 'lw':
                        try:
                            regs[ops[0]] = struct.unpack('<I', self.read(addr, 4))[0]
                            refs.append(('value', regs[ops[0]]))
                        except ValueError: regs.pop(ops[0], None)
                elif ins.mnemonic.startswith('l'): regs.pop(ops[0], None)
            elif ops and ops[0].startswith('$') and ins.mnemonic not in ('jr', 'jalr', 'beq', 'bne', 'beqz', 'bnez', 'bgez', 'bltz', 'bgtz', 'blez'):
                regs.pop(ops[0], None)
            # Branches and calls invalidate volatile values, except the GOT base.
            # Keep the delay slot in the linear pass; candidates still need review.
            regs['$gp'] = self.gp
            key = ins.mnemonic + ' ' + re.sub(r'-?0x[0-9a-f]+|(?<!\w)-?\d+', '#', ins.op_str)
            result.append((key, ins.address, refs))
        return result


def compare(source, target, aliases=None):
    output = defaultdict(lambda: defaultdict(list))
    for name, (address, size) in source.symbols.items():
        other = target.symbols.get((aliases or {}).get(name, name))
        if not other or not size or size > 20000: continue
        try:
            left, right = source.instructions(address, size), target.instructions(*other)
        except ValueError: continue
        matcher = difflib.SequenceMatcher(None, [x[0] for x in left], [x[0] for x in right], autojunk=False)
        for block in matcher.get_matching_blocks():
            if block.size < 3: continue
            for a, b in zip(left[block.a:block.a+block.size], right[block.b:block.b+block.size]):
                for kind, old in a[2]:
                    if not 0x400000 <= old < 0xb00000: continue
                    for kind2, new in b[2]:
                        if kind != kind2 or not 0x400000 <= new < 0xb00000: continue
                        output[f'{old:x}'][f'{new:x}'].append(dict(function=name, source=hex(a[1]), target=hex(b[1]), kind=kind))
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source'); p.add_argument('target'); p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    args.out.write_text(json.dumps(compare(Image(args.source), Image(args.target)), indent=2)+'\n')
