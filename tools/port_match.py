#!/usr/bin/env python3
"""Find relocation-insensitive MIPS function candidates for manual port audits.

This is a research tool, not permission to patch a candidate. Register operands,
stack offsets and branch displacements remain significant. GOT offsets and PIC
function addresses do not. The original bytes and all masked instructions must
still be checked against the destination ABI before using a match in a target.
"""
import argparse
import difflib
import hashlib
import io
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile


class Binary:
    def __init__(self, path, pic_only=False):
        self.raw = Path(path).read_bytes()
        self.elf = ELFFile(io.BytesIO(self.raw))
        if (self.elf.elfclass != 32 or not self.elf.little_endian or
                self.elf['e_machine'] != 'EM_MIPS'):
            raise ValueError('Expected ELF32 little-endian MIPS')
        self.gp = struct.unpack('<6I', self.elf.get_section_by_name('.reginfo').data())[-1]
        self.symbols = {}
        for section in ('.dynsym', '.symtab'):
            table = self.elf.get_section_by_name(section)
            if table:
                self.symbols.update({s.name: (s['st_value'], s['st_size']) for s in table.iter_symbols()
                                     if s.name and s['st_shndx'] != 'SHN_UNDEF'})
        text = self.elf.get_section_by_name('.text')
        self.start, self.end = text['sh_addr'], text['sh_addr'] + text['sh_size']
        words = struct.unpack('<' + 'I' * (text['sh_size'] // 4), text.data())
        starts = {a for a, size in self.symbols.values() if self.start <= a < self.end and size}
        for i in range(len(words)-2):
            a, b, c = words[i:i+3]
            if a >> 16 == 0x3c1c and b >> 16 == 0x279c and c == 0x0399e021:
                starts.add(self.start + i*4)
            if a >> 26 == 3:
                target = (a & 0x3ffffff) * 4 | (self.start & 0xf0000000)
                if self.start <= target < self.end:
                    starts.add(target)
            if not pic_only and a >> 16 == 0x27bd and a & 0x8000 and not (i >= 3 and words[i-3] >> 16 == 0x3c1c):
                starts.add(self.start + i*4)
        starts = sorted(starts | {self.end})
        self.functions = dict(zip(starts, [b-a for a, b in zip(starts, starts[1:])]))
        self.names = {a: n for n, (a, _) in self.symbols.items()}

    def read(self, address, size):
        for s in self.elf.iter_segments():
            if s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= address and address+size <= s['p_vaddr']+s['p_filesz']:
                off = s['p_offset'] + address - s['p_vaddr']
                return self.raw[off:off+size]
        raise ValueError(f'Not file-backed: {address:#x}+{size:#x}')

    def signature(self, address, size=None):
        size = self.functions[address] if size is None else size
        words = list(struct.unpack('<' + 'I' * (size // 4), self.read(address, size)))
        for i, w in enumerate(words):
            op, rs, rt, imm = w >> 26, (w >> 21) & 31, (w >> 16) & 31, w & 65535
            if ((op == 15 and rt == 28) or (rs == 28 and op in (9, 13, 32, 33, 35, 36, 37, 40, 41, 43)) or
                    (op == 9 and rs == 25 and rt == 25)):
                words[i] = w & 0xffff0000
            elif op in (2, 3):
                words[i] = w & 0xfc000000
        return tuple(words)

    def candidates(self, source, address, limit=5):
        sig = source.signature(address)
        results = []
        for a, size in self.functions.items():
            ratio = size / (len(sig)*4)
            if not 0.65 <= ratio <= 1.5:
                continue
            other = self.signature(a)
            score = difflib.SequenceMatcher(None, sig, other, autojunk=False).ratio()
            results.append((score, a, size))
        return [{'address': hex(a), 'size': size, 'similarity': round(score, 6),
                 'symbol': self.names.get(a), 'sha256': hashlib.sha256(self.read(a, size)).hexdigest()}
                for score, a, size in sorted(results, reverse=True)[:limit]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('destination', type=Path)
    p.add_argument('addresses', nargs='+', type=lambda x: int(x, 0))
    p.add_argument('--out', type=Path)
    p.add_argument('--pic-only', action='store_true', help='Do not split PIC functions at delayed stack allocation')
    args = p.parse_args()
    source, dest = Binary(args.source, args.pic_only), Binary(args.destination, args.pic_only)
    result = {hex(a): dest.candidates(source, a) for a in args.addresses}
    output = json.dumps(result, indent=2)+'\n'
    if args.out:
        args.out.write_text(output)
    else:
        print(output, end='')


if __name__ == '__main__':
    main()
