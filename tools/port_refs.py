#!/usr/bin/env python3
"""Compact constant/call reference report for offline MIPS ABI review."""
import argparse
import re
from port_correspond import Image


def report(image, start, size, title):
    names = {v[0]: k for k, v in image.symbols.items()}
    print(f'\n{title} {start:#x}:{size:#x}')
    for _, address, refs in image.instructions(start, size):
        for kind, target in refs:
            if not 0x400000 <= target < 0xb00000: continue
            note = names.get(target, '')
            if not note:
                try:
                    data = image.read(target, 256).split(b'\0')[0]
                    if data and all(32 <= x < 127 or x in (9, 10, 13) for x in data): note = repr(data.decode())
                except ValueError: pass
            print(f'  {address:08x} {kind:6s} {target:08x} {note}')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('elf'); p.add_argument('pattern', nargs='?', default='^$')
    p.add_argument('--range')
    args = p.parse_args(); image = Image(args.elf)
    if args.range:
        address, size = [int(s, 0) for s in args.range.split(':')]
        report(image, address, size, 'range')
    else:
        functions={s.name for s in image.elf.get_section_by_name('.dynsym').iter_symbols()
                   if s['st_info']['type']=='STT_FUNC'}
        for name, (address, size) in sorted(image.symbols.items(), key=lambda pair: pair[1][0]):
            if name in functions and size and re.search(args.pattern, name): report(image, address, size, name)
