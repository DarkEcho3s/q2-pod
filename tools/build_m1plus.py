#!/usr/bin/env python3
"""Build the experimental M1 Plus UI/input payload; never makes an update image.

Only the pinned M1 V2.1 demo is accepted. Outputs are ignored, locally derived
vendor executables, for emulator validation and future staged device bring-up.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import subprocess

from elftools.elf.elffile import ELFFile

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'targets/m1plus/v2.1.json'
FLAGS = ['-target', 'mipsel-linux-musl', '-mcpu=mips32r2+noabicalls+fp64+nan2008', '-mabi=32',
         '-static', '-mno-abicalls', '-mfp64', '-mnan=2008', '-fno-pic', '-G0', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
         '-Oz', '-Wall', '-Wextra', '-Werror', '-ffunction-sections', '-fdata-sections']
# Toolkit structures stay opaque. No Q2 definitions or addresses are imported.
API = {
    'window_manager': ('void *', 'void'),
    'window_manager_get_top_window': ('void *', 'void *'),
    'window_manager_is_animating': ('int', 'void *'),
    **{n: ('void *', 'void *, int, int, int, int') for n in
       ['window_create', 'button_create', 'label_create', 'view_create']},
    'widget_lookup': ('void *', 'void *, const char *, int'),
    'widget_on': ('unsigned', 'void *, unsigned, int (*)(void *, void *), void *'),
    'widget_set_name': ('int', 'void *, const char *'),
    'widget_set_text_utf8': ('int', 'void *, const char *'),
    'widget_set_prop_str': ('int', 'void *, const char *, const char *'),
    'widget_get_prop_str': ('const char *', 'void *, const char *, const char *'),
    'widget_get_prop_int': ('int', 'void *, const char *, int'),
    'widget_set_prop_int': ('int', 'void *, const char *, int'),
    'widget_set_state': ('int', 'void *, const char *'),
    'widget_destroy': ('int', 'void *'),
    'widget_count_children': ('int', 'void *'),
    'slide_indicator_set_max': ('int', 'void *, unsigned'),
    'window_close': ('int', 'void *'),
    'timer_add': ('unsigned', 'int (*)(const void *), void *, unsigned'),
    'navigator_to': ('int', 'const char *'),
    'on_backtoplayer_onclick': ('int', 'void *, void *'),
    'reset_poweroptions_timer': ('void', 'int, int, int'),
}
GLOBALS = {'backlight_status': 'unsigned char', 'keylock_flag': 'unsigned char',
           **{n: 'int' for n in ['standby_mode', 'lockscreen_pageflag', 'rotate_mode',
                                'volume', 'boot_guidestep']}}
LIBC = {
    'fopen': ('void *', 'const char *, const char *'),
    'fread': ('unsigned', 'void *, unsigned, unsigned, void *'),
    'fwrite': ('unsigned', 'const void *, unsigned, unsigned, void *'),
    'fclose': ('int', 'void *'), 'fflush': ('int', 'void *'),
    'fileno': ('int', 'void *'), 'fsync': ('int', 'int'),
    'rename': ('int', 'const char *, const char *'),
    'snprintf': ('int', 'char *, unsigned, const char *, ...'),
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def offset(elf, address, size):
    for s in elf.iter_segments():
        if (s['p_type'] == 'PT_LOAD' and s['p_vaddr'] <= address and
                address + size <= s['p_vaddr'] + s['p_filesz']):
            return s['p_offset'] + address - s['p_vaddr']
    raise ValueError(f'Address is not file-backed: {address:#x}')


def validate_stock(raw, target):
    checked(sha(raw) == target['demo_sha256'], 'Not the pinned M1 Plus V2.1 demo')
    elf = ELFFile(io.BytesIO(raw))
    checked(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_MIPS',
            'Unexpected ELF architecture')
    checked(elf['e_flags'] == target['elf_flags'], 'Unexpected MIPS ABI flags')
    gp = struct.unpack('<6I', elf.get_section_by_name('.reginfo').data())[-1]
    checked(gp == target['stock_gp'], 'Unexpected stock GP')
    symbols = {s.name: s for s in elf.get_section_by_name('.dynsym').iter_symbols()}
    for name, spec in target['symbols'].items():
        s = symbols.get(name)
        checked(s is not None and s['st_shndx'] != 'SHN_UNDEF' and
                s['st_value'] == spec['address'] and s['st_size'] == spec['size'],
                'M1 symbol mismatch: ' + name)
    for name, hook in target['hooks'].items():
        address = target['symbols'][name]['address']
        off = offset(elf, address, 12)
        checked(raw[off:off+12].hex() == hook['prologue'], 'Hook prologue mismatch: ' + name)
        # Only relocate a standard three-word PIC GP setup, never arbitrary code.
        a, b, c = struct.unpack_from('<3I', raw, off)
        checked(a >> 16 == 0x3c1c and b >> 16 == 0x279c and c == 0x0399e021,
                'Hook has no supported PIC prologue: ' + name)
    return elf


def generate_imports(elf, target, out):
    gp = target['stock_gp']
    header = ['/* Generated only after validating the pinned M1 executable. */']
    asm = ['.module fp=64', '.module oddspreg', '.set noreorder', '.text']
    for name, (ret, args) in API.items():
        address = target['symbols'][name]['address']
        header.append(f'#define {name} (({ret} (*)({args}))0x{address:x}u)')
    for name, ctype in GLOBALS.items():
        address = target['symbols'][name]['address']
        header.append(f'#define stock_{name} (*(volatile {ctype} *)0x{address:x}u)')
    for name in target['hooks']:
        address = target['symbols'][name]['address']
        asm += [f'.section .text.stock_{name},"ax",@progbits', f'.globl stock_{name}',
                f'stock_{name}:', f'lui $gp, {gp >> 16}', f'ori $gp, $gp, {gp & 65535}',
                f'j 0x{address + 12:x}', 'nop']
    dynamic = {t.entry.d_tag: t.entry.d_val for t in elf.get_section_by_name('.dynamic').iter_tags()}
    first, local = dynamic['DT_MIPS_GOTSYM'], dynamic['DT_MIPS_LOCAL_GOTNO']
    got = elf.get_section_by_name('.got')
    syms = list(elf.get_section_by_name('.dynsym').iter_symbols())
    for name, (ret, args) in LIBC.items():
        matches = [i for i, s in enumerate(syms) if s.name == name and s['st_shndx'] == 'SHN_UNDEF']
        checked(len(matches) == 1 and matches[0] >= first, 'Missing M1 GOT import: ' + name)
        index = local + matches[0] - first
        checked(4 * (index + 1) <= got['sh_size'], 'GOT import outside table')
        address = got['sh_addr'] + 4 * index
        header.append(f'extern {ret} m1_lib_{name}({args});')
        header.append(f'#define {name} m1_lib_{name}')
        asm += [f'.section .text.m1_lib_{name},"ax",@progbits', f'.globl m1_lib_{name}',
                f'm1_lib_{name}:', f'lui $gp, {gp >> 16}', f'ori $gp, $gp, {gp & 65535}',
                f'lui $t8, {address >> 16}', f'ori $t8, $t8, {address & 65535}',
                'lw $t9, 0($t8)', 'jr $t9', 'nop']
    (out / 'm1_platform.h').write_text('\n'.join(header) + '\n')
    (out / 'imports.S').write_text('\n'.join(asm) + '\n')


def payload_image(path, base):
    elf = ELFFile(io.BytesIO(path.read_bytes()))
    checked(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_MIPS',
            'Payload architecture mismatch')
    checked(elf['e_flags'] == 0x70001401, 'Payload must use MIPS32r2 O32 NAN2008, non-PIC')
    syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols()}
    sections = [s for s in elf.iter_sections() if s['sh_flags'] & 2 and s['sh_size']]
    checked(sections and min(s['sh_addr'] for s in sections) == base, 'Unexpected payload base')
    end = max(s['sh_addr'] + s['sh_size'] for s in sections)
    checked(base < end <= base + 0x100000, 'Unexpected payload size')
    data = bytearray(end-base)  # include zeroed BSS for reproducible bytes
    for s in sections:
        checked(s['sh_type'] not in ('SHT_REL', 'SHT_RELA'), 'Unresolved relocation')
        if s['sh_type'] != 'SHT_NOBITS':
            start = s['sh_addr']-base
            data[start:start+s['sh_size']] = s.data()
    return bytes(data), syms


def patch(raw, payload, syms, target):
    elf = validate_stock(raw, target)
    base = target['payload_base']
    segments = list(elf.iter_segments())
    nulls = [i for i, s in enumerate(segments) if s['p_type'] == 'PT_NULL']
    checked(nulls == [len(segments)-1], 'No single final PT_NULL for payload')
    checked(base % 65536 == 0 and all(s['p_vaddr'] + s['p_memsz'] <= base
            for s in segments if s['p_type'] == 'PT_LOAD'), 'Payload overlaps stock mapping')
    checked(0 < len(payload) <= 0x100000, 'Payload too large or empty')
    data = bytearray(raw)
    changes = []
    for name, hook in target['hooks'].items():
        address, dest = target['symbols'][name]['address'], syms[hook['replacement']]
        checked(base <= dest < base+len(payload) and dest % 4 == 0 and
                (address+4) >> 28 == dest >> 28, 'Invalid MIPS hook destination')
        off = offset(elf, address, 12)
        data[off:off+12] = struct.pack('<3I', 0x08000000 | (dest >> 2), 0, 0)
        changes.append(dict(name=name, address=address, destination=dest, file_offset=off))
    off = (len(data)+65535) & ~65535
    data.extend(bytes(off-len(data)))
    data.extend(payload)
    phoff = elf['e_phoff'] + nulls[0]*elf['e_phentsize']
    struct.pack_into('<8I', data, phoff, 1, off, base, base, len(payload), len(payload), 7, 65536)
    # A byte-level allowlist ensures no silent changes outside four hooks/header.
    allowed = {i for change in changes for i in range(change['file_offset'], change['file_offset']+12)}
    allowed.update(range(phoff, phoff+32))
    checked(all(a == b or i in allowed for i, (a, b) in enumerate(zip(raw, data))),
            'Unexpected modification outside allowlist')
    return bytes(data), changes


def build(stock, out, zig):
    target = json.loads(TARGET.read_text())
    raw = stock.read_bytes()
    elf = validate_stock(raw, target)  # fail before creating output or compiling
    out = out.resolve()
    checked(out.is_relative_to(ROOT / 'work') and out != ROOT / 'work',
            'Output must be a new subdirectory of ignored work/')
    checked(not out.exists(), 'Output already exists; use a fresh directory')
    version = subprocess.check_output([str(zig), 'version'], text=True).strip()
    checked(version == '0.15.2', 'This target is validated with Zig 0.15.2')
    out.mkdir(parents=True)
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'),
               ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    generate_imports(elf, target, out)
    base = target['payload_base']
    link = out/'link.ld'
    link.write_text('EXTERN(' + ' '.join(h['replacement'] for h in target['hooks'].values()) + ')\n'
                    f'SECTIONS {{ . = 0x{base:x}; .text : {{ *(.text*) }} '
                    '.rodata : { *(.rodata*) } .data : { *(.data*) *(.sdata*) *(.got*) } '
                    '.bss : { *(.bss*) *(.sbss*) } /DISCARD/ : { *(.comment) *(.note*) '
                    '*(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) } }')
    objects = []
    for src in [ROOT/'patch/m1plus/input.c', ROOT/'patch/m1plus/shell.c', out/'imports.S']:
        obj = out/(src.stem+'.o')
        subprocess.run([str(zig), 'cc', *FLAGS, '-I', str(out), '-c', str(src), '-o', str(obj)],
                       env=env, check=True)
        compiled = ELFFile(io.BytesIO(obj.read_bytes()))
        checked(compiled['e_flags'] == 0x70001401 and
                compiled.get_section_by_name('.MIPS.abiflags').data() ==
                elf.get_section_by_name('.MIPS.abiflags').data(),
                'Compiled object does not match stock MIPS/FPU ABI: ' + src.name)
        objects.append(str(obj))
    subprocess.run([str(zig), 'cc', *FLAGS, '-g', '-nostdlib', '-static', '-Wl,--build-id=none',
                    '-Wl,--gc-sections', '-Wl,-T,'+str(link), '-Wl,-e,m1_application_init',
                    *objects, '-o', str(out/'payload.elf')], env=env, check=True)
    payload, syms = payload_image(out/'payload.elf', base)
    patched, changes = patch(raw, payload, syms, target)
    (out/'demo.m1pod').write_bytes(patched)
    manifest = dict(target=target['name'], status='experimental-not-device-tested',
                    stock_sha256=sha(raw), demo_sha256=sha(patched), payload_sha256=sha(payload),
                    payload_bytes=len(payload), compiler='zig '+version, hooks=changes,
                    features=['portrait-prototype', 'wheel-navigation-on-prototype-menu', 'bounded-input-log'],
                    firmware_update=False, audio_player_patched=False)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock-demo', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--zig', type=Path, required=True)
    a = p.parse_args()
    build(a.stock_demo.resolve(), a.out, a.zig.resolve())
