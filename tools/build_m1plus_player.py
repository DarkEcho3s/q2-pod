#!/usr/bin/env python3
"""Build the M1 V2.1 audio payload from the shared Q2 Pod DSP sources.

Produces a local derived hciplayer, not an installable update by itself. The
full executable hash, audited regions and each replaced word are checked.
"""
import argparse
import io
import json
import os
from pathlib import Path
import struct
import subprocess

from elftools.elf.elffile import ELFFile

from build_m1plus import FLAGS, ROOT, checked, offset, payload_image, sha
from peq import LIBC

TARGET = ROOT/'targets/m1plus/player-v2.1.json'


def source_digest():
    paths = ['patch/peq.c', 'patch/peq.h', 'patch/peq_player.c', 'patch/player_abi.h',
             'tools/build_m1plus_player.py', 'tools/build_m1plus.py', 'tools/peq.py',
             'targets/m1plus/player-v2.1.json']
    return sha(b''.join(p.encode()+b'\0'+(ROOT/p).read_bytes().replace(b'\r\n', b'\n')+b'\0' for p in paths))


def validate_stock(raw, target):
    checked(sha(raw) == target['stock_sha256'], 'Not the pinned M1 Plus V2.1 hciplayer')
    e = ELFFile(io.BytesIO(raw))
    checked(e.elfclass == 32 and e.little_endian and e['e_machine'] == 'EM_MIPS' and
            e['e_flags'] == target['elf_flags'], 'Unexpected player architecture/ABI')
    checked(struct.unpack('<6I', e.get_section_by_name('.reginfo').data())[-1] == target['gp'],
            'Unexpected player GP')
    for region in target['audits']:
        off = offset(e, region['address'], region['size'])
        checked(sha(raw[off:off+region['size']]) == region['sha256'],
                'Player audit mismatch: '+region['name'])
    for p in target['patches']:
        checked(struct.unpack_from('<I', raw, offset(e, p['address'], 4))[0] == p['expected'],
                'Player patch mismatch: '+p['name'])
    return e


def imports(e, gp, out):
    dynamic = {t.entry.d_tag: t.entry.d_val for t in e.get_section_by_name('.dynamic').iter_tags()}
    first, local = dynamic['DT_MIPS_GOTSYM'], dynamic['DT_MIPS_LOCAL_GOTNO']
    got = e.get_section_by_name('.got')
    syms = list(e.get_section_by_name('.dynsym').iter_symbols())
    slots = {s.name: got['sh_addr']+4*(local+i-first) for i, s in enumerate(syms)
             if i >= first and s['st_shndx'] == 'SHN_UNDEF'}
    # The non-PIC player also imports through the separate PLT GOT. Before
    # lazy binding, its resolver expects t8 to contain the slot address.
    plt = e.get_section_by_name('.rel.plt')
    if plt:
        for r in plt.iter_relocations():
            checked(r['r_info_type'] == 127, 'Unexpected MIPS PLT relocation')
            slots[syms[r['r_info_sym']].name] = r['r_offset']
    header = ['struct dirent;']
    asm = ['.module fp=64', '.module oddspreg', '.set noreorder', '.text']
    used = {}
    for name, (ret, args) in LIBC.items():
        alias = {'fopen': 'fopen64', 'readdir': 'readdir64', 'pow': '__pow_finite'}.get(name, name)
        if alias not in slots:
            # Unused declarations are eliminated; a used missing import fails linking.
            header.append(f'extern {ret} {name}({args});')
            continue
        a = slots[alias]
        checked(any(s and s['sh_addr'] <= a < s['sh_addr']+s['sh_size']
                    for s in (got, e.get_section_by_name('.got.plt'))), 'Import outside GOT')
        used[name] = dict(symbol=alias, address=a)
        header += [f'extern {ret} peq_lib_{name}({args});', f'#define {name} peq_lib_{name}']
        asm += [f'.section .text.peq_lib_{name},"ax",@progbits', f'.globl peq_lib_{name}',
                f'peq_lib_{name}:', f'lui $gp, {gp >> 16}', f'ori $gp, $gp, {gp & 65535}',
                f'lui $t8, {a >> 16}', f'ori $t8, $t8, {a & 65535}', 'lw $t9, 0($t8)', 'jr $t9', 'nop']
        if name in ('memcpy', 'memset'):
            asm += [f'.globl {name}', f'.set {name}, peq_lib_{name}']
    (out/'peq_platform.h').write_text('\n'.join(header)+'\n')
    (out/'imports.S').write_text('\n'.join(asm)+'\n')
    return used


def patch(raw, payload, syms, target):
    e = validate_stock(raw, target)
    base = target['payload_base']
    segments = list(e.iter_segments())
    nulls = [i for i, s in enumerate(segments) if s['p_type'] == 'PT_NULL']
    checked(nulls == [len(segments)-1], 'No single final PT_NULL for audio payload')
    checked(base % 65536 == 0 and all(s['p_vaddr']+s['p_memsz'] <= base
            for s in segments if s['p_type'] == 'PT_LOAD'), 'Audio payload overlaps stock')
    checked(0 < len(payload) <= 0x100000, 'Invalid audio payload size')
    data, changes = bytearray(raw), []
    for p in target['patches']:
        value = p['replacement']
        if isinstance(value, str):
            value = syms[value]
            checked(base <= value < base+len(payload) and value % 4 == 0,
                    'Invalid audio hook destination')
            if p['kind'] == 'jal':
                checked(value >> 28 == (p['address']+4) >> 28, 'JAL out of range')
                value = 0x0c000000 | value >> 2
        off = offset(e, p['address'], 4)
        struct.pack_into('<I', data, off, value)
        changes.append(dict(name=p['name'], address=p['address'], file_offset=off,
                            before=p['expected'], after=value))
    off = (len(data)+65535) & ~65535
    data.extend(bytes(off-len(data)))
    data.extend(payload)
    phoff = e['e_phoff']+nulls[0]*e['e_phentsize']
    struct.pack_into('<8I', data, phoff, 1, off, base, base, len(payload), len(payload), 7, 65536)
    allowed = {i for c in changes for i in range(c['file_offset'], c['file_offset']+4)}
    allowed.update(range(phoff, phoff+32))
    checked(all(a == b or i in allowed for i, (a, b) in enumerate(zip(raw, data))),
            'Unexpected modification outside player allowlist')
    return bytes(data), changes


def build(stock, out, zig):
    target = json.loads(TARGET.read_text())
    raw = stock.read_bytes()
    e = validate_stock(raw, target)
    out = out.resolve()
    checked(out.is_relative_to(ROOT/'work') and out != ROOT/'work' and not out.exists(),
            'Output must be a fresh directory inside ignored work/')
    checked(subprocess.check_output([str(zig), 'version'], text=True).strip() == '0.15.2',
            'Use Zig 0.15.2')
    out.mkdir(parents=True)
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'), ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    imp = imports(e, target['gp'], out)
    (out/'m1_player_abi.h').write_text('\n'.join(f'#define {n} 0x{a:x}u'
                                               for n, a in target['addresses'].items())+'\n')
    roots = ['peq_open', 'mp3_seek', 'id3_gain']
    link = out/'link.ld'
    link.write_text('EXTERN('+' '.join(roots)+')\n'
                   f'SECTIONS {{ . = 0x{target["payload_base"]:x}; .text : {{ *(.text*) }} '
                   '.rodata : { *(.rodata*) } .data : { *(.data*) *(.sdata*) *(.got*) } '
                   '.bss : { *(.bss*) *(.sbss*) } /DISCARD/ : { *(.comment) *(.note*) '
                   '*(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) } }')
    flags = [*FLAGS, '-DM1PLUS=1', '-fno-math-errno']
    objs = []
    for src in [ROOT/'patch/peq.c', ROOT/'patch/peq_player.c', out/'imports.S']:
        obj = out/(src.stem+'.o')
        subprocess.run([str(zig), 'cc', *flags, '-I', str(out), '-c', str(src), '-o', str(obj)],
                       env=env, check=True)
        compiled = ELFFile(io.BytesIO(obj.read_bytes()))
        # hciplayer declares ISA revision 5, demo revision 2. The injected r2
        # instructions are a subset; both use O32, 64-bit FP registers, FP ABI
        # 6 and NAN2008. Do not compare the ISA revision byte as an ABI field.
        stock_abi = bytearray(e.get_section_by_name('.MIPS.abiflags').data())
        checked(stock_abi.hex() == '000020050102000600000000000000000100000000000000',
                'Unexpected original player ISA/FPU declaration')
        stock_abi[3] = 2
        checked(compiled['e_flags'] == 0x70001401 and
                compiled.get_section_by_name('.MIPS.abiflags').data() == bytes(stock_abi),
                'Audio object ABI mismatch: '+src.name)
        objs.append(str(obj))
    subprocess.run([str(zig), 'cc', *flags, '-g', '-nostdlib', '-static', '-Wl,--build-id=none',
                    '-Wl,--gc-sections', '-Wl,-T,'+str(link), '-Wl,-e,peq_open',
                    *objs, '-o', str(out/'payload.elf')], env=env, check=True)
    payload, syms = payload_image(out/'payload.elf', target['payload_base'])
    patched, changes = patch(raw, payload, syms, target)
    (out/'hciplayer').write_bytes(patched)
    manifest = dict(target=target['name'], status='built-not-device-tested',
                    stock_sha256=sha(raw), sha256=sha(patched), payload_sha256=sha(payload),
                    source_sha256=source_digest(), compiler='zig 0.15.2',
                    payload_bytes=len(payload), patches=changes, imports=imp,
                    features=['30-band-PEQ', '3-band-EQ', 'channel-balance', 'DSD-passthrough',
                              'crossfade', 'visualizer-PCM-tap', 'MP3-Xing-seek', 'MP3-ReplayGain'],
                    firmware_update=False, ui_integration=False)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k: v for k, v in manifest.items() if k not in ('imports', 'patches')}, indent=2))
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock-player', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--zig', type=Path, required=True)
    a = p.parse_args()
    build(a.stock_player.resolve(), a.out, a.zig.resolve())
