#!/usr/bin/env python3
"""Compile shared UI modules and execute their actual EQ paint code at both sizes.

All toolkit calls use test addresses. No resulting file is a firmware payload.
The checks cover geometry, not M1 toolkit compatibility or theme integration.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
import unicorn.mips_const as r

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build import FUNCTIONS, GLOBALS, CONTEXT_DATA, RING_STEP
from ipod import SETTINGS_ICONS
from peq import LIBC
from build_m1plus import FLAGS, checked, payload_image

MODULES = ['navigation.c', 'peq_ui.c', 'coverflow.c', 'photos.c', 'books.c',
           'visualizer.c', 'playback.c', 'crossfade.c', 'headset.c', 'lockscreen.c', 'scrobble.c']


def headers(out):
    prototypes = {**FUNCTIONS, **LIBC}
    slots = {name: 0x2000000+i*16 for i, name in enumerate(prototypes)}
    h = ['struct dirent { unsigned ino, off; unsigned short reclen; unsigned char d_type; char d_name[256]; };']
    h += [f'#define {n} (({ret} (*)({args}))0x{slots[n]:x}u)' for n, (ret, args) in FUNCTIONS.items()]
    for n, (ret, args) in LIBC.items():
        h += [f'extern {ret} test_lib_{n}({args});', f'#define {n} test_lib_{n}']
    h += [f'#define {n} (*(volatile unsigned char *)0x{0x2100000+i*4:x}u)' for i, n in enumerate(GLOBALS)]
    h += ['extern void *m1_bt_pairs;'] # M1 headset adapter; not part of this paint fixture
    (out/'peq_platform.h').write_text('\n'.join(h)+'\n')
    stock = [f'#define RING_STEP {RING_STEP}', '#define STOCK_VERSION "test"',
             '#define Q2POD_VERSION "test"', '#define ROCKBOX_FLAG "/test/never"']
    stock += [f'#define {n} ((const unsigned char *)0x{0x2200000+i*4096:x}u)' for i, n in enumerate(CONTEXT_DATA)]
    names = ''.join(n.removesuffix('.png')+'\\0' for n in SETTINGS_ICONS)
    stock.append(f'#define SETTINGS_ICON_NAMES "{names}"')
    (out/'stock.h').write_text('\n'.join(stock)+'\n')
    return slots


def compile_variant(out, zig, m1):
    out.mkdir()
    slots = headers(out)
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'), ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    flags = [*FLAGS, '-DIPOD=1', *(['-DM1PLUS=1'] if m1 else [])]
    for module in MODULES:
        subprocess.run([str(zig), 'cc', *flags, '-I', str(out), '-c', str(ROOT/'patch'/module),
                        '-o', str(out/(module+'.o'))], env=env, check=True)
    src = out/'layout.c'
    src.write_text('''#include "peq_ui.c"
void test_render(void *canvas, int tab, int focus) {
    e3.h = POD_CLIENT_H; e3.on = 1; e3.focus = focus;
    ui.tab = tab; ui.tabs = 1;
    e3_paint(canvas); tabs_paint(canvas);
}
void test_dimensions(int *out) {
    out[0] = POD_SCREEN_W; out[1] = POD_CLIENT_H;
    out[2] = PH_COLS; out[3] = PH_TILE_W; out[4] = PH_THUMB_W;
    out[5] = CF_VIEW_W; out[6] = CF_VIEW_H;
    out[7] = CF_TEXT_Y; out[8] = CF_NAME_H + CF_ARTIST_H;
}
''')
    slots.update(caption=0x2003000, rgba=0x2003010, accent_tone=0x2003020)
    link = out/'link.ld'
    link.write_text('EXTERN(test_render test_dimensions)\n'+''.join(f'test_lib_{n} = 0x{slots[n]:x};\n' for n in LIBC)+''.join(f'{n} = 0x{slots[n]:x};\n'
                    for n in ('caption', 'rgba', 'accent_tone'))+
                    'SECTIONS { . = 0xb00000; .text : { *(.text*) } .rodata : { *(.rodata*) } '
                    '.data : { *(.data*) *(.sdata*) *(.got*) } .bss : { *(.bss*) *(.sbss*) } '
                    '/DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) } }')
    subprocess.run([str(zig), 'cc', *flags, '-g', '-I', str(out), '-I', str(ROOT/'patch'),
                    '-nostdlib', '-static', '-Wl,--build-id=none', '-Wl,--gc-sections',
                    '-Wl,-T,'+str(link), '-Wl,-e,test_render', str(src), '-o', str(out/'layout.elf')],
                   env=env, check=True)
    return slots


def exercise(out, slots, width, height):
    u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    u.ctl_set_cpu_model(r.UC_CPU_MIPS32_P5600)
    u.reg_write(r.UC_MIPS_REG_CP0_STATUS, u.reg_read(r.UC_MIPS_REG_CP0_STATUS) | 0x24000000)
    u.mem_map(0xb00000, 0x100000)
    u.mem_map(0x1000000, 0x20000)
    u.mem_map(0x2000000, 0x10000)
    data, syms = payload_image(out/'layout.elf', 0xb00000)
    u.mem_write(0xb00000, data)
    canvas, lcd, stack, stop = 0x1000000, 0x1001000, 0x101f000, 0x101e000
    u.mem_write(canvas+0x38, struct.pack('<I', lcd))
    by_address, boxes = {a: n for n, a in slots.items()}, []

    def read_string(a):
        b = bytearray()
        while (v := u.mem_read(a, 1)[0]):
            b.append(v)
            a += 1
        return b.decode('utf-8')

    def intercept(u, address, size, _):
        name = by_address.get(address)
        if not name:
            return
        args = [u.reg_read(reg) for reg in (r.UC_MIPS_REG_A0, r.UC_MIPS_REG_A1, r.UC_MIPS_REG_A2, r.UC_MIPS_REG_A3)]
        args += list(struct.unpack('<6I', u.mem_read(u.reg_read(r.UC_MIPS_REG_SP)+16, 24)))
        value = 0
        if name == 'canvas_fill_rect':
            boxes.append(dict(kind='fill', box=args[1:5]))
        elif name == 'caption':
            boxes.append(dict(kind='text', text=read_string(args[1]), box=args[2:6]))
        elif name in ('canvas_set_fill_color',):
            pass
        elif name == 'rgba':
            value = (args[1] << 24) | (args[0] & 255) << 16 | (args[0] & 0xff00) | args[0] >> 16
        elif name == 'accent_tone':
            value = 0x6e6e6e
        elif name == 'snprintf':
            u.mem_write(args[0], b'0 dB\0')
            value = 4
        else:
            raise AssertionError('Unexpected paint dependency: '+name)
        u.reg_write(r.UC_MIPS_REG_V0, value)
        u.reg_write(r.UC_MIPS_REG_PC, u.reg_read(r.UC_MIPS_REG_RA))

    u.hook_add(UC_HOOK_CODE, intercept)

    def call(name, *args):
        u.reg_write(r.UC_MIPS_REG_SP, stack)
        u.reg_write(r.UC_MIPS_REG_RA, stop)
        for reg, value in zip((r.UC_MIPS_REG_A0, r.UC_MIPS_REG_A1, r.UC_MIPS_REG_A2, r.UC_MIPS_REG_A3), args):
            u.reg_write(reg, value)
        u.emu_start(syms[name], stop, count=200000)
        assert u.reg_read(r.UC_MIPS_REG_PC) == stop and u.reg_read(r.UC_MIPS_REG_SP) == stack

    call('test_dimensions', canvas+0x100)
    w, h, cols, tile, thumb, cfw, cfh, texty, texth = struct.unpack('<9i', u.mem_read(canvas+0x100, 36))
    assert (w, h) == (width, height)
    assert cols*tile+2 <= w and 0 < thumb < tile
    assert cfw == w and cfh <= texty and texty+texth <= h
    for tab in (0, 1):
        for focus in range(6):
            call('test_render', canvas, tab, focus)
    for b in boxes:
        x, y, bw, bh = b['box']
        assert 0 <= x < w and 0 <= y < h and 0 < bw <= w-x and 0 < bh <= h-y, b
    # Every simple-EQ control and both tabs must have painted, not merely an
    # empty or clipped view that trivially satisfies the bounds check.
    assert {'Low', 'Mid', 'High', 'Reset', 'Simple On', 'Simple', 'Advanced'} <= {
        b.get('text') for b in boxes}
    result = dict(width=w, height=h, compiled_modules=MODULES, painted_boxes=len(boxes),
                  photo_columns=cols, photo_tile_width=tile, coverflow_height=cfh)
    (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--zig', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    checked(out.is_relative_to(ROOT/'work') and out != ROOT/'work' and not out.exists(),
            'Use a fresh output directory under ignored work/')
    out.mkdir(parents=True)
    for name, m1, w, h in [('q2', False, 375, 290), ('m1', True, 320, 450)]:
        dest = out/name
        slots = compile_variant(dest, a.zig.resolve(), m1)
        print(json.dumps(exercise(dest, slots, w, h)))
