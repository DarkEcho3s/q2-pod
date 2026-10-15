#!/usr/bin/env python3
"""Compile the shared non-streaming frontend against the M1 Plus V2.1 ABI.

An unresolved adapter is a link error, never a guessed Q2 address or a stub.
This compilation stage deliberately cannot emit an update container.
"""
import argparse
import io
import json
import os
import re
from pathlib import Path
import struct
import subprocess

from elftools.elf.elffile import ELFFile
import build as q2
from peq import LIBC
from ipod import SETTINGS_ICONS
from build_m1plus import FLAGS, ROOT, checked, sha, offset

STOCK_SHA = '29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1'
GP = 0xa03ed0
ALIASES = {
    'mclSetBtVol': 'mclSetVol',
    'player_play_pause': 'play_pause_music', 'player_next_music': 'next_music',
    'player_prev_music': 'prev_music', 'player_stop': 'stop_player',
    'player_save_start': 'save_start_player', 'player_start': 'start_player',
    'playing_timer_start': 'player_timer_start', 'playing_timer_clear': 'player_timer_clear',
    'player_seek_time': 'seek_time', 'player_playtime_and_length': 'get_playtimeandlength',
    'folder_reload_data': 'folder_reload', 'folder_reinit_navbarname': 'folder_nagvation_title',
    'device_set_volume': 'set_devicevolume', 'config_outputchannel': 'set_outputchannel',
    'batch_init_selectrecord': 'select_recordinit', 'batch_set_selectitem': 'set_selectindex',
    'switch_charge_enable': 'toolsSetChargeSwitch',
}
DATA_ALIASES = {
    'g_time24h_flag': 'time24hflag', 'g_guideflag': 'first_guideflag',
    'g_poweroff_state': 'standby_mode', 'bt__recv_pageflag': 'btrecv_pageflag',
    'g_navbar_status': 'navigation_status', 'g_maxvolume': 'max_volume', 'g_carmode': 'car_mode',
    'g_memory_info': 'meminfo_save', 'g_local_classinfo_save': 'classinfo_save',
    'g_class_type': 'cur_classtype', 'p_deque_showlist': 'pdeq_showlist',
    'p_vector_select_record': 'pvec_selectrecord', 'g_play_id3_info': 'playsong_id3info',
    'g_power_chargestate': 'pmucharge_status', 'p_deque_screensaverlist': 'pdeq_screensaverlist',
    'g_lastcover_url': 'savecover_path',
}
# Reviewed private routines; the complete executable hash pins their bytes.
PRIVATE = {'stock_search': 0x535738, 'mcl_open_preload': 0x5d0bd8,
           'mcl_shuffle_pick': 0x5d03b0, 'album_row': 0x4e93c8, 'folder_refresh': 0x5318ac,
           'folder_load_top': 0x4db51c, 'mcl_preload': 0x5d0ea4,
           'btmenu_rows': 0x4a3734, 'np_info': 0x539c40,
           'playlist_rebuild': 0x53e74c, 'saver_cover': 0x53f9b4, 'album_scroll_end':0x524134}
HOOK_ALIASES = {
    'load_localclass_list': 'loadLocalClassList', 'load_album_detaillist': 'loadAlbumdetailList',
    'player_play_pause': 'play_pause_music',
    'saverscreen_page_init': 'screensaver_page_init',
    'player_change_music': 'change_music',
    'on_wm_tsdown_before_fun': 'on_wm_before_tsdown_fun',
}
# M1 input dispatch is attached by its device adapter, not Q2's key callbacks.
EXCLUDE_HOOKS = {'on_wm_keydown_before_fun', 'on_wm_keyup_before_fun',
                 'buzzeer_switch', 'stream_page_init', 'mcl_tidalStartPlayer',
                 'localmusic_page_init', 'load_localartist_list', 'screensaver_rows', 'list_get_img_pic'}
SOURCES = ['navigation.c', 'peq.c', 'peq_ui.c', 'coverflow.c', 'scrobble.c', 'photos.c',
           'books.c', 'visualizer.c', 'playback.c', 'crossfade.c', 'headset.c', 'lockscreen.c',
           'm1plus/offline.c', 'm1plus/resolve.c', 'm1plus/compat.c', 'm1plus/frontend.c',
           'm1plus/input.c', 'm1plus/controls.c', 'm1plus/library.c']

PRIVATE_CONSTANTS = {
    'INITCONFIG_SPEED_RET': 0x4d86c4, 'INITCONFIG_MODE_RET': 0x4d8738,
    'SCAN_DONE': 0xa03a40, 'SCAN_THREAD': 0xa03a44,
    'BOOTVOL_SWITCH': 0x49d328, 'BOOTVOL_DEC': 0x49d39c, 'BOOTVOL_ADD': 0x49d4c8,
    'BOOTVOL_CHANGED': 0x49d418, 'BOOTVOL_CHANGING': 0x49d418,
    'STYLE_COLOR_GRADIENT_RET': 0x65a050,
    'FAV_CLICK_ADDR': 0x53b480, 'PLAYLIST_PICK_ADDR': 0x53d300,
    'SORTSELECT_KEYUP': 0, # native M1 dialog has no key-up handler
    'SORTSELECT_CLOSE': 0x47d0f0, # foreach binder 47d300
    'LIST_VIEW_LAYOUT': 0x60abb0, 'LIST_VIEW_LAYOUT_SLOT': 0x9047a8,
}

def private_header(out):
    """Never inherit an unreviewed Q2 absolute address into an M1 executable."""
    original = (ROOT/'patch/offsets.inc').read_text()
    reviewed = (ROOT/'patch/m1plus/abi.inc').read_text()
    lines = []
    # Only the ABI portion contains these address names; RGB values are excluded.
    address_names = ['DEFAULT_LAYOUT_VTABLE', 'STYLE_COLOR_GRADIENT_RET', 'LIST_VIEW_LAYOUT',
                     'LIST_VIEW_LAYOUT_SLOT', 'KEY_LOCKOUT', 'WHEEL_POST', 'BOOT_KEY_GUARD',
                     'RETURN_RELEASE_LATCH', 'ALBUMINFO_ROW', 'USB_MIXER', 'FAV_CLICK_ADDR',
                     'PLAYLIST_PICK_ADDR', 'SORTSELECT_KEYUP', 'SORTSELECT_CLOSE']
    address_names += re.findall(r'^#define ((?:MCL_|INITCONFIG_|BOOTVOL_|SCAN_)[A-Z_]+) 0x', original, re.M)
    for name in dict.fromkeys(address_names):
        if re.search(r'^#define '+name+r' ', reviewed, re.M): continue
        lines.append('#undef '+name)
        if name in PRIVATE_CONSTANTS:
            lines.append(f'#define {name} 0x{PRIVATE_CONSTANTS[name]:x}u')
        else:
            lines += ['extern unsigned char m1_unmapped_'+name+'[];',
                      f'#define {name} ((unsigned)m1_unmapped_{name})']
    (out/'m1_private.inc').write_text('\n'.join(lines)+'\n')


def extra_import(asm, name):
    """Preserve the complete o32 argument window, including hard-float arguments."""
    stub = 'm1_extra_'+name
    asm += [f'.section .data.{stub},"aw",@progbits', '.balign 4', stub+'_cache: .word 0',
            f'.section .rodata.{stub},"a",@progbits', stub+'_name: .asciz "'+name+'"',
            f'.section .text.{stub},"ax",@progbits', f'.globl {stub}', stub+':',
            f'lui $t8, %hi({stub}_cache)', f'lw $t9, %lo({stub}_cache)($t8)',
            'bnez $t9, 1f', 'nop',
            'addiu $sp, $sp, -64', 'sw $ra, 60($sp)',
            'sw $a0, 16($sp)', 'sw $a1, 20($sp)', 'sw $a2, 24($sp)', 'sw $a3, 28($sp)',
            'sdc1 $f12, 32($sp)', 'sdc1 $f14, 40($sp)',
            f'lui $a0, %hi({stub}_name)', 'jal m1_resolve', f'addiu $a0, $a0, %lo({stub}_name)',
            'beqz $v0, 2f', 'move $t9, $v0',
            f'lui $t8, %hi({stub}_cache)', f'sw $t9, %lo({stub}_cache)($t8)',
            'lw $a0, 16($sp)', 'lw $a1, 20($sp)', 'lw $a2, 24($sp)', 'lw $a3, 28($sp)',
            'ldc1 $f12, 32($sp)', 'ldc1 $f14, 40($sp)', 'lw $ra, 60($sp)', 'addiu $sp, $sp, 64',
            '1: jr $t9', 'nop', '2: li $v0, 4001', 'li $a0, 127', 'syscall', 'break']
    return stub


def generate(raw, out):
    checked(sha(raw) == STOCK_SHA, 'Not the pinned M1 Plus V2.1 executable')
    elf = ELFFile(io.BytesIO(raw))
    symbols = list(elf.get_section_by_name('.dynsym').iter_symbols())
    named = {s.name: s for s in symbols}
    defined = {s.name: s for s in symbols if s['st_shndx'] != 'SHN_UNDEF'}
    tags = {t.entry.d_tag: t.entry.d_val for t in elf.get_section_by_name('.dynamic').iter_tags()}
    dynamic = elf.get_section_by_name('.dynamic')
    debug = [t.entry.d_val for t in dynamic.iter_tags() if t.entry.d_tag == 'DT_MIPS_RLD_MAP']
    relative = [dynamic['sh_addr']+i*8+t.entry.d_val for i,t in enumerate(dynamic.iter_tags())
                if t.entry.d_tag=='DT_MIPS_RLD_MAP_REL']
    checked(len(debug) == 1 and relative==debug, 'MIPS loader debug entries disagree')
    (out/'m1_loader.h').write_text(f'#define M1_RLD_MAP 0x{debug[0]:x}u\n')
    got = elf.get_section_by_name('.got')
    imports = {s.name: got['sh_addr']+4*(tags['DT_MIPS_LOCAL_GOTNO']+i-tags['DT_MIPS_GOTSYM'])
               for i, s in enumerate(symbols) if i >= tags['DT_MIPS_GOTSYM']}
    header = ['#ifndef M1_UI_PLATFORM_H', '#define M1_UI_PLATFORM_H',
              'struct dirent { unsigned ino, off; unsigned short reclen; unsigned char d_type; char d_name[256]; };']
    asm = ['.module fp=64', '.module oddspreg', '.set noreorder']
    notify = defined['notifyPlayMode']['st_value']
    header.append(f'#define m1_notify_playmode ((int (*)(int))0x{notify:x}u)')
    pair=defined['pdeq_btpairlist'];checked(pair['st_size']==4,'Unexpected Bluetooth pair container')
    header.append(f'#define m1_bt_pairs (*(void *volatile *)0x{pair["st_value"]:x}u)')
    for name in ('keylock_flag', 'boot_guidestep', 'rotate_mode'):
        symbol = defined[name]
        checked(symbol['st_size'] in (1, 4), 'Bad M1 input state size')
        ctype = 'unsigned char' if symbol['st_size'] == 1 else 'int'
        header.append(f'#define m1_{name} (*(volatile {ctype} *)0x{symbol["st_value"]:x}u)')
    report = dict(functions={}, data={}, hooks={}, unresolved_functions=[], unresolved_data=[], unresolved_hooks=[])
    functions = LIBC | q2.FUNCTIONS | {'view_create': ('void *', 'void *, int, int, int, int'),
         'toolsGetSysMemFree':('int','void'), 'batchadd_albumcover_task':('int','int, int'),
         'widget_set_self_layout':('int','void *, const char *')}
    for name, (ret, args) in functions.items():
        alias = ALIASES.get(name, name)
        symbol = defined.get(alias)
        address = PRIVATE.get(name) or (symbol['st_value'] if symbol else None)
        if address:
            header.append(f'#define {name} (({ret} (*)({args}))0x{address:x}u)')
            report['functions'][name] = dict(address=address, symbol=alias, size=symbol['st_size'] if symbol else None)
        elif alias in imports:
            slot = imports[alias]
            stub = 'm1_import_'+name
            header += [f'extern {ret} {stub}({args});', f'#define {name} {stub}']
            asm += [f'.section .text.{stub},"ax",@progbits', f'.globl {stub}', stub+':',
                    f'lui $gp, {GP>>16}', f'ori $gp, $gp, {GP&65535}',
                    f'lui $t8, {slot>>16}', f'ori $t8, $t8, {slot&65535}', 'lw $t9, 0($t8)', 'jr $t9', 'nop']
            if name in ('memcpy', 'memset'):
                asm += [f'.globl {name}', f'.set {name}, {stub}']
            report['functions'][name] = dict(got=slot, symbol=alias)
        elif name in ('lseek64', 'mmap64', 'getsockopt', 'deque_init_copy', 'deque_pop_back'):
            stub = extra_import(asm, name)
            header += [f'extern {ret} {stub}({args});', f'#define {name} {stub}']
            report['functions'][name] = dict(loader_symbol=name)
        else:
            header += [f'extern {ret} {name}({args});']
            report['unresolved_functions'].append(name)
    stock = ['#ifndef M1_STOCK_H', '#define M1_STOCK_H', '#define RING_STEP 48',
             '#define STOCK_VERSION "V2.1"', '#define Q2POD_VERSION "M1 Pod test"',
             '#define ROCKBOX_FLAG "/tmp/unsupported-rockbox"',
             '#define SETTINGS_ICON_NAMES "' + ''.join(n.removesuffix('.png')+'\\0' for n in SETTINGS_ICONS) + '"']
    for name in q2.GLOBALS + list(q2.CONTEXT_DATA):
        if name in ('g_testmode_flag', 'g_ingore_bootkey_flag'):
            # Q2-only states. M1 wake/boot filtering belongs to its input adapter.
            header.append(f'#define {name} 0')
            report['data'][name] = dict(absent_on_m1=True)
            continue
        if name == 'g_power_longkey':
            header.append('#define g_power_longkey (*(volatile unsigned char *)0xa041b8u)')
            report['data'][name] = dict(address=0xa041b8, size=1, witness='on_wm_keylong_fun')
            continue
        alias = DATA_ALIASES.get(name, name if name in defined else name.removeprefix('g_'))
        symbol = defined.get(alias)
        if symbol and symbol['st_info']['type'] == 'STT_OBJECT':
            size, address = symbol['st_size'], symbol['st_value']
            if name in q2.GLOBALS:
                checked(size in (1, 4), 'Unsupported setting width: '+name)
                header.append(f'#define {name} (*(volatile {"unsigned char" if size == 1 else "int"} *)0x{address:x}u)')
            else:
                checked(size == q2.CONTEXT_DATA[name], 'Context size mismatch: '+name)
                stock.append(f'#define {name} ((const unsigned char *)0x{address:x}u)')
            report['data'][name] = dict(symbol=alias, address=address, size=size)
        else:
            report['unresolved_data'].append(name)
            if name in q2.GLOBALS: header.append('extern volatile unsigned char '+name+';')
            else: stock.append(f'extern unsigned char {name}[{q2.CONTEXT_DATA[name]}];')
    hooks = q2.HOOKS | q2.IPOD_HOOKS | {
        'application_init': (0, 'm1_ui_application', 'application'),
        'np_info': (0, 'ringnav_np_info', 'npinfo'),
        'album_scroll_end':(0,'m1_album_scroll',None),
        'album_page_init':(0,'m1_album_page','albumpage'),
        'widget_on_keyup': (0, 'm1_ui_keyup', 'widget_keyup'),
        'window_manager_dispatch_input_event': (0, 'm1_ui_dispatch', 'input'),
        'on_wm_keylong_fun': (0, 'm1_ui_long', 'keylong'),
        'systemset_screensaver_page_init': (0, 'm1_lockscreen_settings', 'saver_settings')}
    for name, (_, replacement, resume) in hooks.items():
        if name in EXCLUDE_HOOKS: continue
        alias = HOOK_ALIASES.get(name, ALIASES.get(name, name))
        symbol = defined.get(alias)
        address = PRIVATE.get(name) or (symbol['st_value'] if symbol else None)
        if not address:
            report['unresolved_hooks'].append(name)
            continue
        report['hooks'][name] = dict(address=address, replacement=replacement, resume=resume)
        if resume:
            stub = 'stock_'+resume+'_trampoline'
            asm += [f'.section .text.{stub},"ax",@progbits', f'.globl {stub}', stub+':',
                    f'lui $gp, {GP>>16}', f'ori $gp, $gp, {GP&65535}', f'j 0x{address+12:x}', 'nop']
    for name, replacement in {'navigator_to': 'm1_navigate', 'navigator_to_with_context': 'm1_navigate_context',
                              'widget_lookup': 'm1_lookup'}.items():
        line = next(x for x in header if x.startswith('#define '+name+' '))
        header.remove(line)
        ret, args = (LIBC | q2.FUNCTIONS)[name]
        header += [line.replace('#define '+name+' ', '#define m1_native_'+name+' '),
                   f'extern {ret} {replacement}({args});', f'#define {name} {replacement}']
    header.append('#endif'); stock.append('#endif')
    (out/'peq_platform.h').write_text('\n'.join(header)+'\n')
    (out/'stock.h').write_text('\n'.join(stock)+'\n')
    (out/'imports.S').write_text('\n'.join(asm)+'\n')
    (out/'abi-report.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def build(stock, out, zig):
    raw = stock.read_bytes()
    checked(sha(raw) == STOCK_SHA, 'Not the pinned M1 Plus V2.1 executable')
    out = out.resolve()
    checked(out.is_relative_to(ROOT/'work') and out != ROOT/'work' and not out.exists(), 'Use a new work/ subdirectory')
    out.mkdir(parents=True)
    report = generate(raw, out)
    private_header(out)
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'), ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    objects = []
    flags = [*FLAGS, '-fno-math-errno', '-DM1PLUS=1', '-DM1_NATIVE_ABI=1', '-DIPOD=1', '-I', str(out)]
    for src in [*(ROOT/'patch'/name for name in SOURCES), out/'imports.S']:
        obj = out/(src.stem+'.o'); objects.append(str(obj))
        subprocess.run([str(zig), 'cc', *flags, '-c', str(src), '-o', str(obj)], env=env, check=True)
    roots = [x['replacement'] for x in report['hooks'].values()] + ['ringnav', 'ringnav_keylong', 'ringnav_touch',
             'ipod_list_layout', 'ringnav_style_gradient', 'ringnav_wm_paint', 'ringnav_localmusic',
             'ringnav_np_info', 'ringnav_sort_key', 'ringnav_audio_extension', 'ringnav_scan_room',
             'ringnav_shuffle', 'ringnav_bt_connect_start', 'm1_album_covers', 'm1_album_art_name',
             'ringnav_art_header', 'ringnav_boot', 'compact_set_row_layout']
    link = out/'link.ld'
    link.write_text('EXTERN('+' '.join(roots)+')\nSECTIONS { . = 0xb00000; '
                    '.text : { *(.text*) } .rodata : { *(.rodata*) } '
                    '.data : { *(.data*) *(.sdata*) *(.got*) } '
                    '.bss : { *(.bss*) *(.sbss*) } '
                    '.scratch 0xb80000 (NOLOAD) : { __scratch_start = .; *(.scratch) __scratch_end = .; } '
                    '/DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) } }')
    subprocess.run([str(zig), 'cc', *flags, '-g', '-nostdlib', '-static', '-Wl,--build-id=none',
                    '-Wl,--gc-sections', '-Wl,-T,'+str(link), '-Wl,-e,coverflow_home',
                    *objects, '-o', str(out/'payload.elf')], env=env, check=True)
    patched, manifest = patch(raw, out/'payload.elf', report)
    (out/'demo.m1pod').write_bytes(patched)
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'demo':str(out/'demo.m1pod'), 'sha256':sha(patched), 'patches':len(manifest['changes'])}))


def patch(raw, payload_path, report):
    checked(sha(raw) == STOCK_SHA, 'Unpinned stock executable')
    checked(not report['unresolved_hooks'], 'Unresolved feature hooks: '+str(report['unresolved_hooks']))
    elf = ELFFile(io.BytesIO(raw))
    payload = ELFFile(io.BytesIO(payload_path.read_bytes()))
    symbols = list(payload.get_section_by_name('.symtab').iter_symbols())
    checked(not [s.name for s in symbols if s.name and s['st_shndx']=='SHN_UNDEF'], 'Unresolved payload symbols')
    syms = {s.name:s['st_value'] for s in symbols}
    checked(not any(n.startswith('m1_unmapped_') for n in syms), 'Unaudited private ABI')
    checked(payload['e_flags']==0x70001401, 'Unexpected payload ABI')
    sections = [s for s in payload.iter_sections() if s['sh_flags']&2 and s['sh_size']]
    base = 0xb00000
    file_end = max(s['sh_addr']+s['sh_size'] for s in sections if s['sh_type']!='SHT_NOBITS')
    mem_end = max(s['sh_addr']+s['sh_size'] for s in sections)
    checked(min(s['sh_addr'] for s in sections)==base and file_end<=0xb80000 and mem_end<=0xd00000,
            'Payload mapping exceeds reserved space')
    blob = bytearray(file_end-base)
    for s in sections:
        if s['sh_type']!='SHT_NOBITS':blob[s['sh_addr']-base:s['sh_addr']-base+s['sh_size']]=s.data()
    data, changes = bytearray(raw), []
    def replace(name, address, expected, new):
        off=offset(elf,address,len(expected))
        checked(raw[off:off+len(expected)]==expected, 'Patch bytes changed: '+name)
        checked(data[off:off+len(expected)]==expected, 'Overlapping patch: '+name)
        checked(len(new)==len(expected), 'Patch length differs')
        data[off:off+len(new)]=new
        changes.append(dict(name=name,address=address,offset=off,before=expected.hex(),after=new.hex()))
    def jump(name, link=False):
        dest=syms[name]
        checked(base<=dest<file_end and not dest%4, 'Invalid code destination: '+name)
        return (0x0c000000 if link else 0x08000000)|(dest>>2)
    for name,h in report['hooks'].items():
        a=h['address']; old=raw[offset(elf,a,12):offset(elf,a,12)+12]
        x,y,z=struct.unpack('<3I',old)
        checked(x>>16==0x3c1c and y>>16==0x279c and z==0x0399e021, 'Unsupported PIC entry: '+name)
        signed=(y&65535)-((y&0x8000)<<1)
        checked(((x&65535)*65536+signed+a)&0xffffffff==GP,'Unexpected PIC GP: '+name)
        replace(name,a,old,struct.pack('<3I',jump(h['replacement']),0,0))
    dyn={s.name:s['st_value'] for s in elf.get_section_by_name('.dynsym').iter_symbols()}
    for name,replacement,third in [('style_get_gradient','ringnav_style_gradient',0x8c820000),
                                    ('window_manager_paint','ringnav_wm_paint',0x8c820088)]:
        a=dyn[name]; old=raw[offset(elf,a,12):offset(elf,a,12)+12]
        checked(struct.unpack('<3I',old)==(0x10800009,0,third),'Unexpected leaf: '+name)
        replace(name,a,old[:8],struct.pack('<2I',jump(replacement),0))
    calls=[*(('sort',a,'ringnav_sort_key',None,0x5e0cc0) for a in [0x5e0ea4,0x5e0f10,0x5e17bc,0x5e1828]),
           ('extension',0x5e8af0,'ringnav_audio_extension',0x0320f809,None),
           ('extension',0x5ea840,'ringnav_audio_extension',0x0320f809,None),
           ('shuffle',0x5d5a28,'ringnav_shuffle',None,0x5d03b0),
           ('bt-connect',0x4d6320,'ringnav_bt_connect_start',None,0x4e23e8),
           ('boot-resume',0x534f04,'ringnav_boot',0x0320f809,None)]
    calls += [('album-covers',a,'m1_album_covers',0x0320f809,None) for a in [0x524720,0x524760,0x5248d0]]
    # Native constructors' widget_set_children_layout calls. Preserve their row
    # geometry and callbacks while installing the Pod title/chevron layouter.
    calls += [('row-layout',a,'compact_set_row_layout',0x0320f809,None)
              for a in [0x5332bc,0x53e6ec,0x528624,0x5287e4,0x53696c,0x52651c]]
    calls += [('album-art-name',0x523a34,'m1_album_art_name',0x0320f809,None),
              ('album-art-header',0x525b84,'ringnav_art_header',0x0320f809,None)]
    for name,a,replacement,expected,target in calls:
        old=struct.unpack_from('<I',raw,offset(elf,a,4))[0]
        if target:
            expected=0x04110000|(((target-a-4)//4)&65535)
        replace(name,a,struct.pack('<I',expected),struct.pack('<I',jump(replacement,True)))
    replace('scan-limit',0x5efeb4,struct.pack('<2I',0x8fc2b084,0x28424e20),
            struct.pack('<2I',jump('ringnav_scan_room',True),0x8fc4b084))
    replace('settings-layout',0x9047a8,struct.pack('<I',0x60abb0),struct.pack('<I',syms['ipod_list_layout']))
    for name,a,old,new in [('album-art-row',0x523a38,0x24c61158,0x02403025),
                         ('album-grid-visible',0x5239d8,0x24840007,0x2484000c),
                         ('album-grid-prefetch-init',0x524970,0x24050007,0x2405000c),
                         ('album-grid-prefetch-return',0x524798,0x24050007,0x2405000c),
                         ('album-worker-scroll',0x522890,0xac430000,0),
                         ('ldac-quality-index',0x4d304c,0x00042080,0x00041880),
                         ('ldac-quality-table',0x4d3050,0x2442a4b0,0x00431021),
                         ('ldac-quality-load',0x4d3054,0x00442021,0x8c42a4b0),
                         ('ldac-quality-value',0x4d3058,0x8c820000,0x24840015),
                         ('ldac-quality-save',0x4d3064,0,0xafa40014),
                         ('ldac-quality-hq',0x4d3070,0x24040016,0x8fa40014)]:
        replace(name,a,struct.pack('<I',old),struct.pack('<I',new))
    segments=list(elf.iter_segments());nulls=[i for i,s in enumerate(segments) if s['p_type']=='PT_NULL']
    checked(nulls==[len(segments)-1], 'Missing final payload segment slot')
    checked(all(s['p_vaddr']+s['p_memsz']<base for s in segments if s['p_type']=='PT_LOAD'), 'Overlapping load segment')
    at=(len(data)+65535)&~65535
    data.extend(bytes(at-len(data)));data.extend(blob)
    ph=elf['e_phoff']+nulls[0]*elf['e_phentsize']
    struct.pack_into('<8I',data,ph,1,at,base,base,len(blob),mem_end-base,7,65536)
    allowed={i for c in changes for i in range(c['offset'],c['offset']+len(bytes.fromhex(c['before'])))}
    allowed.update(range(ph,ph+32))
    checked(all(a==b or i in allowed for i,(a,b) in enumerate(zip(raw,data))), 'Change outside patch allowlist')
    return bytes(data),dict(stock_sha256=sha(raw),sha256=sha(data),payload_sha256=sha(blob),
                           payload_bytes=len(blob),payload_memory=mem_end-base,changes=changes)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock-demo', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--zig', type=Path, required=True)
    a = p.parse_args(); build(a.stock_demo, a.out, a.zig.resolve())
