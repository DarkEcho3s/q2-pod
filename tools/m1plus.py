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
    'home_card_click': 0x533b80,
    'load_localclass_list': 'loadLocalClassList', 'load_album_detaillist': 'loadAlbumdetailList',         # Home's card click: the HOMEMENU id's page (sub_533d8c binds it)
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
    'slide_view_set_active_ex': ('int', 'void *, unsigned, int'),  # Home's card pages (navigation.c slide_follow)
}
# libcstl iterators the M1's demo imports, which compat.c's deque shims walk.
M1_LIBC = {'deque_begin': ('m1_iterator', 'void *'), 'iterator_next': ('m1_iterator', 'm1_iterator'),
           'deque_erase': ('m1_iterator', 'void *, m1_iterator')}
M1_SHIMS = {'deque_init_copy', 'deque_pop_back', 'widget_use_style', 'image_base_set_image', 'tk_strcmp', 'tk_str_end_with', 'window_manager_get_input_device_status',
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
    # The equalizer (peq_ui.c peq_stock_eq): set_equalizer_value is the Q2's, instruction for
    # instruction; the PEQ filter replaces stock's in hciplayer (M1_PLAYER).
    'set_equalizer_value': (0x4d851c, 'peq_stock_eq', 'eq'),
    # The DAC and software volume (m1plus/volume.c): the software half goes through ringnav_btvol.
    'mclSetVol': (0x5d4cb0, 'm1_setvol', None),
    # The queue (playback.c): the same mcl routines as the Q2's, prologue, arguments and state
    # (abi.inc MCL_*), each paired instruction for instruction (docs/m1plus.md#mapping).
    'mclLoadPlayList': (0x5d1f28, 'ringnav_load', 'load'),
    'mclNextSong': (0x5d5800, 'ringnav_next', 'next'),
    'mclPrevSong': (0x5d56dc, 'ringnav_prev', 'prev'),
    'mclSetPlayMode': (0x5d278c, 'ringnav_mode', 'mode'),
    'mclSetPlaySpeed': (0x5d281c, 'ringnav_speed', 'speed'),
    'mcl_open_preload': (0x5d0bd8, 'ringnav_open_preload', 'open_preload'),
    'mcl_preload': (0x5d0ea4, 'ringnav_preload', 'preload'),
    'mclStartPlayer': (0x5d5300, 'ringnav_start_player', 'start_player'),
    'player_change_music': (0x4e3cec, 'ringnav_change', 'change'),
    'player_play_pause': (0x4e43b4, 'ringnav_play_pause', 'pause'),
    'memeory_startplayer': (0x4e34dc, 'ringnav_memory', 'memory'),
    'save_memoryplay_info': (0x4e3340, 'ringnav_savequeue', 'savequeue'),
    # The library's writers (coverflow.c library_gen).
    'scanAllMusicFile': (0x4e9df4, 'coverflow_scan_all', 'scan_all'),
    'scanSpecFolder': (0x4e9e90, 'coverflow_scan_folder', 'scan_folder'),
    'deleteMusicFromMusicDb': (0x4ede44, 'coverflow_delete_song', 'delete_song'),
    # Settings pages: stock builds its rows, the payload's follow (navigation.c pod_rows, abi.inc
    # SV_*); the EQ row opens the PEQ editor instead of stock's page (peq_ui.c).
    'playset_equalizer_page_init': (0x49e358, 'peq_page_init', None),
    'playset_playset_page_init': (0x4a0c88, 'ringnav_audioset', 'audioset'),
    'systemset_display_page_init': (0x4a5eb8, 'ringnav_display', 'display'),
    'systemset_powermanager_page_init': (0x4a9d18, 'ringnav_powermanager', 'power'),
    # More's Podcasts and Audiobooks open folder_page at their card folder (navigation.c media_click);
    # Back at that root leaves the page.
    'folder_page_init': (0x53349c, 'ringnav_folder', 'folder'),
    'folder_back': (0x4dbecc, 'ringnav_folder_back', 'folder_back'),
    # Now Playing: the heart's hold rates the song (navigation.c rate_bind; abi.inc FAV_*).
    'playing_page_init': (0x53d1e4, 'ringnav_playing', 'playing'),
    # The library's lists: Albums splits albums sharing a name (coverflow_split), an album's page
    # lists that album alone, an empty category says so (navigation.c ringnav_localclass).
    'load_localclass_list': (0x4ee504, 'ringnav_localclass', 'localclass'),
    'load_album_detaillist': (0x4eea98, 'ringnav_album_detail', 'detail'),
    # About: Q2 Pod's version row.
    'systemset_about_page_init': (0x4a170c, 'ringnav_about', 'about'),
    # Home's card click (atoi of the card image's name, the HOMEMENU id): the two streaming cards
    # are Coverflow and More (m1plus/home.c).
    'home_card_click': (0x533b80, 'm1_card_click', 'card'),
}
M1_IPOD_HOOKS = {
    'widget_on_paint_background': (0x66b778, 'ringnav_paint_bg', 'paint_bg'),
}
WM_PAINT_LEAF = ('window_manager_paint', 0x677b44, 'ringnav_wm_paint', (0x10800009, 0, 0x8c820088))

# Home's streaming cards become Coverflow and More (patch/m1plus/home.c): the HOMEMENU names table
# (get_homemenu_showinfo, 0x97c940) points ids 0 and 1 at the payload's names, which Home's theme
# (styles/home_page.bin) knows as its two renamed card styles, each with its renamed images, the
# same size, and the cards' new icons join the images (assets/icons/m1, tools/m1icons.py).
HOMEMENU = 0x97c940
HOME_CARDS = ((0, 0x74a500, 'hifimusic', 'm1_card_coverflow', 'Coverflow'),
              (1, 0x74944c, 'tidal', 'm1_card_more', 'More'))
HOME_STYLES = 'release/assets/default/raw/styles/home_page.bin'
HOME_STYLES_SHA = '116fa726be7b71381691a00d36570650b8588e9cccc8f9e2981e1374c1630862'
IMAGES = 'release/assets/default/raw/images/xx/'
# Windows the payload creates on the M1 alone (check_contexts).
M1_PAYLOAD_WINDOWS = {'more_page'}

# Payload sources: the Q2's demo payload (tools/peq.py compile_common) without its streaming
# pages (spotify.c, radio.c, tidal.c), and the M1's own input layer and shims.
SOURCES = ['m1plus/compat.c', 'm1plus/input.c', 'm1plus/home.c', 'm1plus/volume.c', 'm1plus/nostream.c', 'navigation.c', 'peq.c', 'shared.c', 'peq_ui.c', 'coverflow.c',
           'scrobble.c', 'photos.c', 'books.c', 'visualizer.c', 'playback.c', 'crossfade.c',
           'headset.c', 'lockscreen.c']

# Stock files nothing on the M1 opens: AWTK's shared libraries (demo links AWTK statically; only
# libtable_view.so, itself unused, names libawtk.so) and the glib/dbus versions every soname link
# skips. Removing them makes room for the payload's files in the rootfs, which must not outgrow stock.
UNUSED = ['release/bin/libawtk.so', 'release/bin/libtkc.so', 'release/bin/libtable_view.so',
          'usr/lib/libdbus-1.so.3.19.8',
          *(f'usr/lib/lib{n}-2.0.so.0.5400.3' for n in ('gio', 'glib', 'gmodule', 'gobject', 'gthread'))]

M1FLAGS = [*FLAGS, '-DM1PLUS=1']

# The M1 Plus V2.1 hciplayer: the Q2's build of the same player, 0x540 lower in most of its code and
# its bss 0x1c to 0x20 lower; each site was found by aligning the two (unique 8-instruction anchors)
# and checked word for word, and the descriptors by their strings (docs/m1plus.md#player).
M1_PLAYER = dict(
    sha='a64503746862af3e69b57f2e06167351b30cda28479348a845be5172e083a8c6',
    base=0xe10000,  # stock final LOAD ends at 0xe03b38
    vbr_scan=0x48f5fc,
    seek_slot=0x89f76c, stock_seek=0x48cc6c,  # demuxer_desc_audio @0x89f740
    id3_calls=(0x48f1c4, 0x491e98), stock_id3=0x48e170,
    eq_desc=0x893808, eq_open_slot=0x89381c, eq_desc_bytes='bc3789002c5e88004c358900b8c388000100000014fd4400',
    rate_gates=((0x42ce34, 0x10400098, 0),             # beqz $v0 to "setequalizer off" -> nop
                (0x42fa78, 0x14400052, 0x10000052)),   # bnez $v0 to the insert -> b
    defines=dict(PLAYER_MPCTX=0xaf9e30, PLAYER_DECODED=0x44600c, PLAYER_LENGTH=0xb10e68,
                 PLAYER_STOCK_ID3=0x48e170, PLAYER_AV_DICT_SET=0x6ea1a4, PLAYER_AV_DICT_FREE=0x6ea65c,
                 PLAYER_RG_EXPORT=0x5381c4, PLAYER_STOCK_SEEK=0x48cc6c, PLAYER_HR_MP3_SEEK=0xb15298))


def home_styles(data):
    """Home's theme with the two streaming cards' styles renamed for their new names: each style's
    32-byte name and its images' names, every value the same size (a shorter name is NUL-padded)."""
    from ipod import style_props
    check(sha(data) == HOME_STYLES_SHA, 'Unaudited Home theme')
    out = bytearray(data)
    magic, _, count = struct.unpack_from('<3I', data)
    for _, _, old, _, new in HOME_CARDS:
        renamed = 0
        for i in range(count):
            at = 12 + 100*i + 4 + 32  # the entry's style name, after its offset and state
            if out[at:at+32].split(b'\0')[0] == f'home_{old}_style'.encode():
                out[at:at+32] = f'home_{new}_style'.encode().ljust(32, b'\0')
                renamed += 1
        check(renamed == 5, f'home_{old}_style: expected its 5 states')
        images = 0
        for _, style, _, prop, at, value in style_props(data):
            if style == f'home_{old}_style' and prop == 'bg_image':
                stem = value.split(b'\0')[0].decode()
                check(stem in (old, old + '_down'), f'home_{old}_style: unexpected image {stem}')
                image = (new + stem[len(old):]).encode()
                check(len(image) < len(value), f'{image}: longer than {stem}')
                out[at:at+len(value)] = image.ljust(len(value), b'\0')
                images += 1
        check(images == 5, f'home_{old}_style: expected 5 images')
    return bytes(out)


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
    header = ['struct dirent { unsigned ino, off; unsigned short reclen; unsigned char d_type; char d_name[256]; };',
              'typedef struct { unsigned word[7]; } m1_iterator;']
    asm = ['.set noreorder', '.text']
    for name, (ret, args) in (LIBC | M1_LIBC).items():
        if name in M1_SHIMS:
            header.append(f'{ret} {name}({args});')
            continue
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
            if syms.get(name):  # the shim's way to stock's own
                header.append(f'#define stock_{name} (({ret} (*)({args}))0x{syms[name]:x}u)')
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
        *[f'--undefined={card[3]}' for card in HOME_CARDS],
        *objects, out/'peq_imports.o', out/'trampoline.o', '-o', out/'patch.elf')
    run('llvm-objcopy', '-O', 'binary', out/'patch.elf', out/'patch.bin')
    return symbols(out/'patch.elf'), hooks


def check_contexts(cat, sq):
    """Every name in patch/m1plus/contexts.inc is a window of the stock UI assets or one the payload
    creates, as tools/build.py checks the Q2's."""
    from build import PAYLOAD_WINDOWS
    names = re.findall(r'"([^"]+)"', (ROOT/'patch/m1plus/contexts.inc').read_text())
    check(names, 'No M1 navigation contexts')
    windows = set()
    for line in run('unsquashfs', '-l', sq).splitlines():
        found = re.search(r'/raw/ui/(.+)\.bin$', line)
        if not found: continue
        data = cat('release/assets/default/raw/ui/' + found.group(1) + '.bin')
        i = data.find(b'name\x00')
        windows.add(data[i+5:data.find(b'\x00', i+5)].decode('utf-8', 'replace') if i >= 0 else '')
    for name in names:
        check(name in windows | PAYLOAD_WINDOWS | M1_PAYLOAD_WINDOWS, f'Context {name} is not an M1 window name')


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
    for index, stock, _, symbol, name in HOME_CARDS:
        off = fileoff(patched, HOMEMENU + 4*index)
        check(struct.unpack_from('<I', patched, off)[0] == stock, f'HOMEMENU {index}: unexpected name')
        struct.pack_into('<I', patched, off, ps[symbol])
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
    check_contexts(cat, sq)
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
    # The player's PEQ filter and MP3 fixes, and the Q2's bluealsa and watchdog changes: both files
    # are byte for byte the Q2's (patch_bluealsa pins its sites; the watchdog its one line).
    from peq import patch_player
    from build import patch_bluealsa, BLUEALSA, WATCHDOG, WATCHDOG_SLEEP
    audio = patch_player(cat('usr/bin/hciplayer'), out/'peq', M1_PLAYER)
    (out/'bluealsa').write_bytes(patch_bluealsa(cat(BLUEALSA)))
    watchdog = cat(WATCHDOG)
    check(watchdog.count(WATCHDOG_SLEEP[0]) == 1, 'Unexpected watchdog')
    (out/'watchdog').write_bytes(watchdog.replace(*WATCHDOG_SLEEP))
    for path, src in ((b'usr/bin/hciplayer', out/'peq/hciplayer'), (BLUEALSA.encode(), out/'bluealsa'),
                      (WATCHDOG.encode(), out/'watchdog')):
        p = swap_inode(p, path, src)
    # Home's Coverflow and More cards: their theme, and their icons as new inodes with the metadata
    # of the stock card images they stand in for.
    styles = out/'home_page.bin'
    styles.write_bytes(home_styles(cat(HOME_STYLES)))
    p = swap_inode(p, HOME_STYLES.encode(), styles)
    added = []
    for _, _, old, _, new in HOME_CARDS:
        for suffix in ('', '_down'):
            like = inode(p, f'{IMAGES}{old}{suffix}.png'.encode())
            check(like is not None, f'Missing stock image {old}{suffix}.png')
            src = ROOT/'assets/icons/m1'/f'{new}{suffix}.png'
            path = f'{IMAGES}{new}{suffix}.png'.encode()
            at = p.index(b'# START OF DATA')
            p = p[:at]+path+b' F '+b' '.join(like.groups())+b' cat '+shlex.quote(str(src)).encode()+b'\n'+p[at:]
            added.append([path, b'R', *like.groups()])
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
    check(inodes(newsq) == sorted([i for i in inodes(sq) if i not in removed] + added), 'Repacked rootfs metadata differs from stock')
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
                    version=version, ipod=ipod, dev=dev, removed=UNUSED, peq=audio,
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
