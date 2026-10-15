#!/usr/bin/env python3
"""Build Q2 Pod for the Shanling M1 Plus from the audited stock V2.1 update.bin (docs/m1plus.md).

The M1 Plus runs an older branch of the Q2's firmware: the same X2000, kernel, updater and AWTK UI
toolkit (an older AWTK), with its own app build. This builder reuses the Q2 payload sources compiled
with -DM1PLUS=1 (patch/m1plus/abi.inc holds the M1's ABI and layout), the M1's own symbol table, the
names the M1 still uses for what the Q2 renamed (M1_NAMES), and the M1 hook sites (M1_HOOKS).
Requires LLVM, squashfs-tools and, for the iPod UI, ImageMagick.
"""
import argparse, hashlib, io, json, pathlib, re, shlex, struct, subprocess, sys, tarfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from build import (ROOT, FLAGS, FUNCTIONS, GLOBALS, CONTEXT_DATA, append_payload, check, fileoff, run,
                   segments, sha, source_sha256, symbols, jpeg_size, VERSION, dev_tag)

UPDATE_SHA = '1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925'
DEMO_SHA = '29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1'
MODEL, STOCK_VERSION = 'Shanling M1 Plus', 'V2.1'
GP = 0xa03ed0  # every audited M1 PIC prologue resolves this GOT base
BASE, SCRATCH = 0xb00000, 0xb50000  # past the RW segment's end (0xa10fc8), as on the Q2
RING_STEP = 48

# The M1's names for what the payload calls by the Q2's name (FUNCTIONS, GLOBALS, CONTEXT_DATA):
# its own symbol when the M1 kept another name, or an address for a local routine. Each was matched
# by its callees, strings and data references against the Q2's (docs/m1plus.md#mapping).
M1_NAMES = {
    # the player layer (the Q2 renamed it player_*): same callees, same arguments
    'player_play_pause': 'play_pause_music', 'player_next_music': 'next_music',
    'player_prev_music': 'prev_music', 'player_stop': 'stop_player',
    'player_save_start': 'save_start_player', 'player_seek_time': 'seek_time',
    'player_playtime_and_length': 'get_playtimeandlength', 'player_change_music': 'change_music',
    'device_set_volume': 'set_devicevolume', 'config_outputchannel': 'set_outputchannel',
    'batch_init_selectrecord': 'select_recordinit', 'batch_set_selectitem': 'set_selectindex',
    # globals the M1 names without the g_ prefix (byte or int: M1_GLOBAL_INTS)
    'g_backlight_status': 'backlight_status', 'g_lockscreen_pageflag': 'lockscreen_pageflag',
    'g_bluetoothflag': 'bluetoothflag', 'g_usblink_status': 'usblink_status',
    'g_equalizer_flag': 'equalizer_flag', 'g_playcover_type': 'playcover_type',
    'g_folder_layer': 'folder_layer', 'g_otg_status': 'otg_status', 'g_delete_flag': 'delete_flag',
    'g_volume': 'volume', 'g_maxvolume': 'max_volume', 'g_po_status': 'po_status',
    'g_bal_status': 'bal_status', 'g_usbvol_mode': 'usbvol_mode',
    'g_usbdac_chargeflag': 'usbdac_chargeflag', 'g_memory_play': 'memory_play',
    'g_carmode': 'car_mode', 'g_headset_output': 'headset_output', 'g_usbdet_value': 'usbdet_value',
    'g_playspeed_mode': 'playspeed_mode', 'bt__recv_pageflag': 'btrecv_pageflag',
    'g_navbar_status': 'navigation_status',
    'g_power_longkey': 0xa041b8,       # on_wm_keylong_fun sets it on the power key's hold; on_wm_keyup_fun skips that release
    'g_ingore_bootkey_flag': 0xa041a3, # on_wm_keyup_fun's other power-release guard
    # context data
    'g_folder_path': 'folder_path', 'g_artist_type': 'artist_type', 'g_dacoff_time': 'dacoff_time',
    'g_power_capacity': 'power_capacity', 'g_screensaver_picture': 'screensaver_picture',
    'p_deque_showlist': 'pdeq_showlist', 'p_deque_screensaverlist': 'pdeq_screensaverlist',
    'g_local_classinfo_save': 'classinfo_save', 'g_class_type': 'cur_classtype',
    'g_memory_info': 'meminfo_save', 'g_play_id3_info': 'playsong_id3info',
    'p_vector_select_record': 'pvec_selectrecord',
    'g_poweroff_state': 'standby_mode',  # 1 while Shut Down? asks (on_wm_keylong_fun), 2 the power-off page
    'g_guideflag': 'boot_guidestep',     # the first-boot guide's step; on_wm_keyup_fun drops keys while set
    'g_time24h_flag': 'time24hflag',
    'g_lastcover_url': 'savecover_path',  # parseplaycover_thd: the track whose cover files it last wrote
    # local routines (the Q2's PRIVATE_FUNCTIONS): the same code at the M1's address
    'mcl_shuffle_pick': 0x5d03b0,        # mclNextSong's shuffle pick, instruction for instruction the Q2's 0x5a8120
    'slide_menu_on_scroll_done': 0x6123f4,
    'folder_reload_data': 'folder_reload', 'folder_reinit_navbarname': 'folder_nagvation_title',
    'mcl_open_preload': 0x5d0bd8, 'mcl_preload': 0x5d0ea4,  # the Q2's 0x5a8948 and 0x5a8c1c
    'album_row': 0x4e93c8,               # getAllAlbum's sqlite3_exec callback (the Q2's 0x4fc324)
    'folder_refresh': 0x5318ac,          # folder_page_init's table rebuild from the showlist (the Q2's 0x52176c)
    # what the M1 does not keep: a zero the payload owns (compat.c m1_zeros)
    'g_testmode_flag': None, 'album_modetype': None,
}
# GLOBALS the M1 keeps as 4-byte ints (the Q2 as bytes): read and written whole.
M1_GLOBAL_INTS = {'g_poweroff_state', 'g_guideflag', 'g_lockscreen_pageflag', 'g_usblink_status', 'g_playcover_type', 'g_folder_layer',
                  'g_otg_status', 'g_volume', 'g_maxvolume', 'g_po_status', 'g_bal_status',
                  'g_usbvol_mode', 'g_usbdac_chargeflag', 'g_memory_play', 'g_headset_output',
                  'g_usbdet_value', 'g_playspeed_mode'}
# Q2 functions the M1 lacks, defined by the payload under the Q2 name (patch/m1plus/compat.c).
# Stock routines the payload calls only on the M1, by their M1 names.
M1_FUNCTIONS = {
    'hscroll_label_set_lull': ('int', 'void *, int'),
    'mclSetPlayMode': ('int', 'int'), 'notifyPlayMode': ('int', 'int'),
    'toolsSetChargeSwitch': ('int', 'int'),  # writes /sys/class/power_supply/battery/charger
    'toolsGetChargeStatus': ('int', 'void'),  # 1 or 2 while charging, else 0
    'toolsReplceQuote': ('int', 'char *, int'),
}
M1_SHIMS = {'tk_strcmp', 'tk_str_end_with', 'window_manager_get_input_device_status',
            'set_hscroll_label_attribute', 'canvas_stroke_rounded_rect', 'slide_menu_item_width',
            'slide_menu_scroll_to_next', 'slide_menu_scroll_to_prev', 'stock_search',
            'config_playmode', 'switch_charge_enable', 'getMusicByAlbumArtist'}

# Hooks: stock entry, payload replacement, trampoline name (None: never resumed).
M1_HOOKS = {
    'widget_on_paint_border': (0x668810, 'ringnav_paint', 'paint'),
    'widget_dispatch': (0x66cec8, 'ringnav_dispatch', 'dispatch'),
    'window_manager_dispatch_input_event': (0x677b74, 'ringnav_input', 'input'),
    'main_loop_sleep_default': (0x658f70, 'ringnav_sleep', 'sleep'),
    'on_wm_keylong_fun': (0x4cdd9c, 'm1_keylong', 'keylong'),
    'on_wm_before_tsdown_fun': (0x4cd608, 'ringnav_touch', 'touch'),
    # Home's init registers the window manager's key callbacks; the payload adds its own key-down
    # and key-up before-children callbacks there (m1plus/input.c), where the Q2's stock filters sat.
    'home_page_init': (0x534cd4, 'm1_home', 'home'),
}
M1_IPOD_HOOKS = {
    'widget_on_paint_background': (0x66b778, 'ringnav_paint_bg', 'paint_bg'),
}
WM_PAINT_LEAF = ('window_manager_paint', 0x677b44, 'ringnav_wm_paint', (0x10800009, 0, 0x8c820088))

# Payload sources: the Q2's demo payload (tools/peq.py compile_common) without its streaming
# pages (spotify.c, radio.c, tidal.c), and the M1's own input layer and shims.
SOURCES = ['m1plus/compat.c', 'm1plus/input.c', 'navigation.c', 'peq.c', 'peq_ui.c', 'coverflow.c',
           'scrobble.c', 'photos.c', 'books.c', 'visualizer.c', 'playback.c', 'crossfade.c',
           'headset.c', 'lockscreen.c']

# Stock files nothing on the M1 opens: AWTK's shared libraries (demo links AWTK statically; only
# libtable_view.so, itself unused, names libawtk.so) and the glib/dbus versions every soname link
# skips. Removing them makes room for the payload's files in the rootfs, which must not outgrow stock.
UNUSED = ['release/bin/libawtk.so', 'release/bin/libtkc.so', 'release/bin/libtable_view.so',
          'usr/lib/libdbus-1.so.3.19.8',
          *(f'usr/lib/lib{n}-2.0.so.0.5400.3' for n in ('gio', 'glib', 'gmodule', 'gobject', 'gthread'))]

M1FLAGS = [*FLAGS, '-DM1PLUS=1']


def m1_symbols(demo):
    """The M1's symbol table, with M1_NAMES resolved to the Q2 names the payload uses."""
    syms = symbols(demo)
    for q2, m1 in M1_NAMES.items():
        if m1 is not None: syms[q2] = m1 if isinstance(m1, int) else syms[m1]
    return syms


def zero_backed(name): return name in M1_NAMES and M1_NAMES[name] is None


def got_imports(binary):
    got = {}
    for line in run('readelf', '-AW', binary).splitlines():
        words = line.split()
        if len(words) >= 6 and 'UND' in words and re.fullmatch('[0-9a-f]{8}', words[0]):
            got[words[-1].split('@')[0]] = int(words[0], 16)
    return got


def platform(out, demo, syms):
    """peq_platform.h and peq_imports.S as tools/peq.py writes them for the Q2, from the M1's GOT
    and symbols: libc through demo's own GOT slots, stock routines and globals by address."""
    from peq import LIBC
    got = got_imports(demo)
    header = ['struct dirent { unsigned ino, off; unsigned short reclen; unsigned char d_type; char d_name[256]; };']
    asm = ['.set noreorder', '.text']
    for name, (ret, args) in LIBC.items():
        if name not in got:
            header.append(f'extern {ret} {name}({args});')
            continue
        address = got[name]
        header += [f'extern {ret} peq_lib_{name}({args});', f'#define {name} peq_lib_{name}']
        asm += [f'.section .text.peq_lib_{name},"ax",@progbits', f'.globl peq_lib_{name}',
                f'peq_lib_{name}:', f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 65535}',
                f'lui $t8, {address >> 16}', f'ori $t8, $t8, {address & 65535}',
                'lw $t9, 0($t8)', 'jr $t9', 'nop']
        if name in ('memcpy', 'memset'):
            asm += [f'.globl {name}', f'.set {name}, peq_lib_{name}']
    for name, (ret, args) in (FUNCTIONS | M1_FUNCTIONS).items():
        if name in M1_SHIMS:
            header.append(f'{ret} {name}({args});')
        elif name in syms and syms[name]:
            header.append(f'#define {name} (({ret} (*)({args}))0x{syms[name]:x}u)')
    header.append('extern unsigned char m1_zeros[];')
    for name in GLOBALS:
        ctype = 'int' if name in M1_GLOBAL_INTS else 'unsigned char'
        if zero_backed(name):
            header.append(f'#define {name} (*(volatile {ctype} *)m1_zeros)')
        elif name in syms:
            header.append(f'#define {name} (*(volatile {ctype} *)0x{syms[name]:x}u)')
    (out/'peq_platform.h').write_text('\n'.join(header)+'\n')
    (out/'peq_imports.S').write_text('\n'.join(asm)+'\n')


def stock_header(out, syms, dev):
    header = [f'#define RING_STEP {RING_STEP}']
    for name in CONTEXT_DATA:
        if zero_backed(name):
            header.append(f'#define {name} ((const unsigned char *)m1_zeros)')
        elif name in syms:
            header.append(f'#define {name} ((const unsigned char *)0x{syms[name]:x}u)')
    header += [f'#define STOCK_VERSION "{STOCK_VERSION}"',
               f'#define Q2POD_VERSION "{VERSION} Pod{f" dev {dev}" if dev else ""}"',
               '#define SETTINGS_ICON_NAMES ""', '#define ROCKBOX_FLAG "/tmp/m1pod-rockbox"']
    (out/'stock.h').write_text('\n'.join(header)+'\n')


def compile_payload(out, demo, syms, ipod):
    hooks = M1_HOOKS | (M1_IPOD_HOOKS if ipod else {})
    flags = [*M1FLAGS, '-fno-math-errno', '-ffunction-sections', '-fdata-sections', f'-DIPOD={int(ipod)}',
             '-I', out, '-I', ROOT/'patch']
    objects = []
    for src in SOURCES:
        obj = out/(src.replace('/', '_') + '.o')
        run('clang', *flags, '-c', ROOT/'patch'/src, '-o', obj)
        objects.append(obj)
    run('clang', *flags, '-c', out/'peq_imports.S', '-o', out/'peq_imports.o')
    asm = ['.set noreorder', '.text']
    for address, _, x in hooks.values():
        if x:
            asm += [f'.globl stock_{x}_trampoline', f'stock_{x}_trampoline:', f'lui $gp, {GP >> 16}',
                    f'ori $gp, $gp, {GP & 65535}', f'j 0x{address + 12:x}', 'nop']
    (out/'trampoline.S').write_text('\n'.join(asm)+'\n')
    run('clang', *M1FLAGS, '-c', out/'trampoline.S', '-o', out/'trampoline.o')
    run('ld.lld', '-m', 'elf32ltsmip', '--gc-sections', '-T', ROOT/'patch/link.ld', '-e', 'm1_home',
        *[f'--undefined={name}' for _, name, _ in hooks.values()], f'--undefined={WM_PAINT_LEAF[2]}',
        *objects, out/'peq_imports.o', out/'trampoline.o', '-o', out/'patch.elf')
    run('llvm-objcopy', '-O', 'binary', out/'patch.elf', out/'patch.bin')
    return symbols(out/'patch.elf'), hooks


def patch_demo(raw, out, ipod, dev):
    demo = out/'stock-demo'
    demo.write_bytes(raw)
    syms = m1_symbols(demo)
    platform(out, demo, syms)
    stock_header(out, syms, dev)
    ps, hooks = compile_payload(out, demo, syms, ipod)
    payload = (out/'patch.bin').read_bytes()
    check(len(payload) < SCRATCH-BASE, 'Payload overlaps its scratch page')
    check(ps['__scratch_start'] == SCRATCH and ps['__scratch_end'] <= SCRATCH + 0x10000, 'Scratch state moved')
    patched = bytearray(raw)
    def jump(off, name): patched[off:off+8] = struct.pack('<II', 0x08000000 | (ps[name] >> 2), 0)
    for name, (address, replacement, _) in hooks.items():
        check(syms[name] == address, f'{name}: hook address mismatch')
        off = fileoff(patched, address)
        prolog = struct.unpack_from('<III', patched, off)
        check(prolog[0] >> 16 == 0x3c1c and prolog[1] >> 16 == 0x279c and prolog[2] == 0x0399e021,
              f'{name}: unexpected PIC prologue')
        low = prolog[1] & 65535
        gp = ((prolog[0] & 65535) << 16) + (low if low < 32768 else low - 65536) + address
        check(gp == GP, f'{name}: unexpected GOT base')
        jump(off, replacement)
    name, address, replacement, words = WM_PAINT_LEAF
    off = fileoff(patched, address)
    check(syms[name] == address and struct.unpack_from('<III', patched, off) == words, f'{name}: unexpected code')
    jump(off, replacement)
    # The updater refuses a firmware_v20.info version equal to the installed one; About shows it.
    check(patched.count(STOCK_VERSION.encode()+b'\0') == 1, 'Version literal is not unique')
    append_payload(patched, payload, BASE, ps['__scratch_end']-BASE, 'demo')
    return bytes(patched), payload, ps


def m1_tag(dev):
    """The updater refuses only a version literal equal to the installed one, and the M1's is the
    4 characters of V2.1: a release is P and VERSION's three digits (1.1.9: P119), a --dev build D
    and its number's three base-36 digits (D001), so none equals stock's or another build's."""
    return 'D' + dev_tag(dev, 'p')[1:4] if dev else 'P' + VERSION.replace('.', '')


def build(update, out, logo, ipod=True, dev=False):
    out.mkdir(parents=True, exist_ok=True)
    check(not (out/'update.bin').exists(), 'Output already exists; use a fresh --out directory')
    if dev:
        counter = ROOT/'.build-number-m1'
        dev = int(counter.read_text()) + 1 if counter.exists() else 1
        counter.write_text(f'{dev}\n')
    version = m1_tag(dev)
    check(len(version) == len(STOCK_VERSION), 'The version tag must keep V2.1\'s length')
    raw = update.read_bytes()
    check(sha(raw) == UPDATE_SHA, 'Unsupported update.bin: SHA-256 differs from the audited M1 Plus V2.1')
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        meta = t.getmembers()
        check([m.name for m in meta] == ['firmware_v20.info', 'recovery-update', 'recovery-update/xImage',
              'recovery-update/rootfs.squashfs'], 'Unexpected package members')
        blobs = {m.name: t.extractfile(m).read() for m in meta if m.isfile()}
    info = blobs['firmware_v20.info'].decode().splitlines()
    check(info[:2] == [MODEL, STOCK_VERSION], 'Wrong model/version')
    sq = out/'stock.squashfs'
    sq.write_bytes(blobs['recovery-update/rootfs.squashfs'])
    def cat(path): return subprocess.check_output(['unsquashfs', '-cat', str(sq), path])
    raw_demo = cat('release/bin/demo')
    check(sha(raw_demo) == DEMO_SHA, 'Unexpected stock demo')
    patched, payload, ps = patch_demo(raw_demo, out, ipod, dev)
    patched = patched.replace(STOCK_VERSION.encode()+b'\0', version.encode()+b'\0')
    (out/'demo').write_bytes(patched)
    # Pseudo-file round trip, as tools/build.py: every other inode keeps its stock metadata.
    pseudo = out/'root.pseudo'
    run('unsquashfs', '-pf', pseudo, sq)
    p = pseudo.read_bytes()
    root = re.search(rb'^/ D (\d+) (\d+) (\d+) (\d+)$', p, re.M)
    check(root is not None, 'Missing root pseudo inode')
    t_, mode, uid, gid = (x.decode() for x in root.groups())
    rootargs = ['-root-time', t_, '-root-mode', mode, '-root-uid', uid, '-root-gid', gid]
    def inode(p, path): return re.search(rb'^'+re.escape(path)+rb' R (\d+) (\d+) (\d+) (\d+) .+$', p, re.M)
    def swap_inode(p, path, src):
        line = inode(p, path)
        check(line is not None, f'Missing {path.decode()} pseudo inode')
        return p[:line.start()]+path+b' F '+b' '.join(line.groups())+b' cat '+shlex.quote(str(src)).encode()+p[line.end():]
    p = swap_inode(p, b'release/bin/demo', out/'demo')
    removed = []
    for path in UNUSED:
        line = re.search(rb'^'+re.escape(path.encode())+rb' R .+\n', p, re.M)
        check(line is not None, f'Missing stock inode {path}')
        removed.append(line.group().split()[:6])
        p = p[:line.start()]+p[line.end():]
    pseudo.write_bytes(p)
    (out/'empty').mkdir(exist_ok=True)
    newsq = out/'rootfs.squashfs'
    epoch = struct.unpack_from('<I', sq.read_bytes(), 8)[0]
    run('mksquashfs', out/'empty', newsq, '-pf', pseudo, '-noappend', '-comp', 'lzo', '-b', '131072',
        '-Xcompression-level', '9', '-tailends', '-mkfs-time', epoch, *rootargs, '-processors', '1', '-no-progress')
    def inodes(image):
        text = subprocess.check_output(['unsquashfs', '-pf', '-', str(image)]).split(b'\n# START OF DATA')[0]
        return sorted(l.split()[:6] for l in text.splitlines() if l and not l.startswith(b'#'))
    check(inodes(newsq) == sorted(i for i in inodes(sq) if i not in removed), 'Repacked rootfs metadata differs from stock')
    blobs['recovery-update/rootfs.squashfs'] = newsq.read_bytes()
    check(len(blobs['recovery-update/rootfs.squashfs']) <= sq.stat().st_size, 'Repacked rootfs exceeds stock size')
    blobs['firmware_v20.info'] = (f'{MODEL}\n{version}\n' + ''.join(
        hashlib.md5(blobs[n]).hexdigest()+'  '+n+'\n' for n in
        ['recovery-update/xImage', 'recovery-update/rootfs.squashfs'])).encode()
    with tarfile.open(out/'update.bin', 'w', format=tarfile.GNU_FORMAT) as t:
        for m in meta:
            data = blobs.get(m.name)
            if data is not None: m.size = len(data)
            t.addfile(m, io.BytesIO(data) if data is not None else None)
    manifest = dict(target='m1plus', input_sha256=UPDATE_SHA, stock_demo_sha256=DEMO_SHA,
                    source_sha256=source_sha256(), demo_sha256=sha(patched), patch_sha256=sha(payload),
                    update_sha256=sha((out/'update.bin').read_bytes()), rootfs_sha256=sha(newsq.read_bytes()),
                    kernel_sha256=sha(blobs['recovery-update/xImage']), patch_bytes=len(payload),
                    version=version, ipod=ipod, dev=dev, removed=UNUSED,
                    rootfs_bytes=len(blobs['recovery-update/rootfs.squashfs']), rootfs_room=sq.stat().st_size,
                    patch_symbols={n: hex(v) for n, v in ps.items() if n.startswith('stock_')})
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({k: manifest[k] for k in ['update_sha256', 'patch_bytes', 'version', 'rootfs_bytes', 'rootfs_room']}, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('update', type=pathlib.Path, help="the stock M1 Plus V2.1 update.bin")
    ap.add_argument('--out', type=pathlib.Path, default=ROOT/'build-m1')
    ap.add_argument('--logo', type=pathlib.Path, default=None)
    ap.add_argument('--legacy', action='store_true', help='stock look: wheel navigation without the iPod UI')
    ap.add_argument('--dev', action='store_true')
    a = ap.parse_args()
    try:
        build(a.update, a.out.resolve(), a.logo, not a.legacy, a.dev)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        ap.error(str(exc))
