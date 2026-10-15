#!/usr/bin/env python3
"""Print selected ELF symbols and MIPS instructions for offline port research.

Annotations identify direct targets and GP-relative GOT loads, not a recovered
control-flow graph. This tool never runs the input binary or patches firmware.
"""
import argparse
import re
import struct
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN


def disassemble(path, pattern):
    with open(path, 'rb') as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 32 or not elf.little_endian or elf.header.e_machine != 'EM_MIPS':
            raise ValueError('Expected ELF32 little-endian MIPS')
        symbols = {}
        for section_name in ('.symtab', '.dynsym'):
            section = elf.get_section_by_name(section_name)
            if section:
                for symbol in section.iter_symbols():
                    if symbol.name and symbol.entry.st_shndx != 'SHN_UNDEF':
                        symbols[symbol.name] = symbol.entry
        addresses = {s.st_value: name for name, s in symbols.items()}

        def read(address, size):
            for segment in elf.iter_segments():
                h = segment.header
                if h.p_type == 'PT_LOAD' and h.p_vaddr <= address and address + size <= h.p_vaddr + h.p_filesz:
                    stream.seek(h.p_offset + address - h.p_vaddr)
                    return stream.read(size)
            raise ValueError('Address not file-backed: ' + hex(address))

        reginfo = elf.get_section_by_name('.reginfo')
        gp = struct.unpack('<6I', reginfo.data())[5] if reginfo else None
        engine = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN)
        # Some vendor instructions are not decoded by Capstone. Keep their raw
        # bytes visible instead of silently ending a function at the first one.
        engine.skipdata = True
        for name, symbol in sorted(symbols.items(), key=lambda item: item[1].st_value):
            if not re.search(pattern, name) or symbol.st_info.type != 'STT_FUNC' or not symbol.st_size:
                continue
            print(f'\n{name} @ {symbol.st_value:#x}, {symbol.st_size} bytes; GP={hex(gp) if gp is not None else "unknown"}')
            for ins in engine.disasm(read(symbol.st_value, symbol.st_size), symbol.st_value):
                note = ''
                operand = ins.op_str
                target = re.fullmatch(r'0x([0-9a-f]+)', operand)
                if ins.mnemonic in ('jal', 'j', 'bal', 'b') and target:
                    note = addresses.get(int(target[1], 16), '')
                got = re.search(r', (-?0x[0-9a-f]+|-?\d+)\(\$gp\)', operand)
                if ins.mnemonic == 'lw' and got and gp is not None:
                    try:
                        value = struct.unpack('<I', read(gp + int(got[1], 0), 4))[0]
                        note = f'GOT -> {value:#x} {addresses.get(value, "")}'
                    except ValueError:
                        pass
                print(f'  {ins.address:08x}  {ins.bytes.hex()}  {ins.mnemonic:8s} {operand}' +
                      (f'  ; {note}' if note else ''))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf')
    parser.add_argument('symbol_pattern', help='regular expression matched against symbol names')
    args = parser.parse_args()
    disassemble(args.elf, args.symbol_pattern)
