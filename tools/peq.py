"""Checked Q2 V1.32 PEQ hooks and target ABI imports; no vendor code is distributed."""
import re
import struct
from build import ROOT, FLAGS, GP, FUNCTIONS, GLOBALS, PRIVATE_FUNCTIONS, append_payload, check, fileoff, run, sha, symbols
from ipod import jal, patch_word

# The Q2 V1.32 hciplayer's checked sites (patch_player's target; tools/m1plus.py has the M1 Plus's).
Q2_PLAYER = dict(
    sha='9c3f8c6d01f1ba62392622f6098b06a36b3e4f022a5468eaca6a5803e74f8e11',
    base=0xe10000,  # stock final LOAD ends at 0xe03b58
    # demux_audio_open's branch to the whole-file frame walk for Xing/VBRI MP3s; see docs/internals.md.
    vbr_scan=0x48fb3c,
    # The audio demuxer's seek slot (demuxer_desc_audio at 0x89fd90) holds demux_audio_seek; see docs/internals.md.
    seek_slot=0x89fdbc, stock_seek=0x48d1ac,
    # demux_audio_open's calls to the ID3v2 frame walker (0x48e6b0) that feeds ReplayGain; see docs/internals.md.
    id3_calls=(0x48f704, 0x4923d8), stock_id3=0x48e6b0,
    # The equalizer filter's descriptor (pinned) and its open slot, which becomes peq_open.
    eq_desc=0x893df8, eq_open_slot=0x893e0c, eq_desc_bytes='ac3d8900cc6388003c3b890098c988000100000024014500',
    # Stock skips the equalizer above 48 kHz (address, stock word, patched word); see docs/internals.md.
    rate_gates=((0x42ced0, 0x10400098, 0),            # beqz $v0 to "setequalizer off" -> nop
                (0x42fd84, 0x1440003b, 0x1000003b)),  # bnez $v0 to the insert -> b
    # The addresses peq_player.c calls and reads (its PLAYER_* macros; these are its defaults).
    defines={})
PLAYER_SHA, PLAYER_BASE = Q2_PLAYER['sha'], Q2_PLAYER['base']
# The Q2's sites by their old names, as the tests read them.
VBR_SCAN, SEEK_SLOT, STOCK_SEEK = Q2_PLAYER['vbr_scan'], Q2_PLAYER['seek_slot'], Q2_PLAYER['stock_seek']
ID3_CALLS, STOCK_ID3, EQ_RATE_GATES = Q2_PLAYER['id3_calls'], Q2_PLAYER['stock_id3'], Q2_PLAYER['rate_gates']
EQ_DESC, EQ_OPEN_SLOT = Q2_PLAYER['eq_desc'], Q2_PLAYER['eq_open_slot']
LIBC = {
    'memset': ('void *', 'void *, int, unsigned'),
    'memcpy': ('void *', 'void *, const void *, unsigned'),
    'memcmp': ('int', 'const void *, const void *, unsigned'),
    'strcmp': ('int', 'const char *, const char *'),
    'strlen': ('unsigned', 'const char *'),
    'calloc': ('void *', 'unsigned, unsigned'),
    'free': ('void', 'void *'),
    'pow': ('double', 'double, double'), 'cos': ('double', 'double'),
    'sin': ('double', 'double'), 'log': ('double', 'double'),
    'fopen': ('void *', 'const char *, const char *'),
    'fread': ('unsigned', 'void *, unsigned, unsigned, void *'),
    'fwrite': ('unsigned', 'const void *, unsigned, unsigned, void *'),
    'fclose': ('int', 'void *'), 'ferror': ('int', 'void *'),
    'fflush': ('int', 'void *'), 'fileno': ('int', 'void *'), 'fsync': ('int', 'int'),
    'rename': ('int', 'const char *, const char *'), 'unlink': ('int', 'const char *'),
    '__xstat': ('int', 'int, const char *, void *'),
    'access': ('int', 'const char *, int'), 'mkdir': ('int', 'const char *, unsigned'),
    'lseek64': ('long long', 'int, long long, int'), 'read': ('int', 'int, void *, unsigned'),
    'snprintf': ('int', 'char *, unsigned, const char *, ...'),
    '__isoc99_sscanf': ('int', 'const char *, const char *, ...'),  # peq.c peq_number: no strtod in demo's GOT
    'opendir': ('void *', 'const char *'), 'closedir': ('int', 'void *'),
    'readdir': ('struct dirent *', 'void *'),
    'qsort': ('void', 'void *, unsigned, unsigned, int (*)(const void *, const void *)'),
    # libcstl and socket imports for the Play/Pause queue menu in navigation.c
    '_create_deque': ('void *', 'const char *'), 'deque_init': ('void', 'void *'),
    'deque_init_copy': ('void', 'void *, const void *'), 'deque_size': ('unsigned', 'const void *'),
    'deque_at': ('void *', 'const void *, unsigned'), '_deque_push_back': ('void', 'void *, ...'),
    'deque_assign': ('void', 'void *, const void *'), 'deque_clear': ('void', 'void *'),
    'deque_pop_back': ('void', 'void *'),
    'deque_destroy': ('void', 'void *'), 'send': ('int', 'int, const void *, unsigned, int'),
    # Coverflow's art thread (coverflow.c)
    'pthread_create': ('int', 'unsigned long *, const void *, void *(*)(void *), void *'),
    'pthread_join': ('int', 'unsigned long, void **'), 'pthread_detach': ('int', 'unsigned long'), 'pthread_mutex_lock': ('int', 'void *'),
    'pthread_mutex_unlock': ('int', 'void *'), 'statfs': ('int', 'const char *, void *'),
    'strdup': ('char *', 'const char *'),
    'strrchr': ('char *', 'const char *, int'), 'strcasecmp': ('int', 'const char *, const char *'),
    'strncasecmp': ('int', 'const char *, const char *, unsigned'),
    # iPod status bar clock (navigation.c)
    'time': ('long', 'long *'), 'localtime': ('const int *', 'const long *'),
    # Scrobble upload (scrobble.c): demo's libcurl and libcrypto
    'fseek': ('int', 'void *, long, int'), 'ftell': ('long', 'void *'), 'atoi': ('int', 'const char *'),
    'strstr': ('char *', 'const char *, const char *'),
    'curl_easy_init': ('void *', 'void'), 'curl_easy_setopt': ('int', 'void *, int, ...'),
    'curl_easy_perform': ('int', 'void *'), 'curl_easy_getinfo': ('int', 'void *, int, ...'),
    'curl_easy_cleanup': ('void', 'void *'), 'curl_slist_append': ('void *', 'void *, const char *'),
    'curl_slist_free_all': ('void', 'void *'), 'MD5_Init': ('int', 'void *'),
    'MD5_Update': ('int', 'void *, const void *, unsigned'), 'MD5_Final': ('int', 'unsigned char *, void *'),
    # Videos (books.c): q2video started and waited for, and its key socket
    'fork': ('int', 'void'), 'execl': ('int', 'const char *, const char *, ...'), 'exit': ('void', 'int'),
    # Home's Rockbox row (navigation.c rockbox_open)
    'system': ('int', 'const char *'),
    'waitpid': ('int', 'int, int *, int'), 'socket': ('int', 'int, int, int'), 'close': ('int', 'int'),
    'connect': ('int', 'int, const void *, unsigned'),
    'recv': ('int', 'int, void *, unsigned, int'),
    'select': ('int', 'int, void *, void *, void *, void *'),
    'getsockopt': ('int', 'int, int, int, void *, unsigned *'),
    'fcntl': ('int', 'int, int, ...'), 'ioctl': ('int', 'int, unsigned, ...'),
    'usleep': ('int', 'unsigned'),
    'sendto': ('int', 'int, const void *, unsigned, int, const void *, unsigned'),
    # The visualizer's PCM tap (peq_player.c writes, visualizer.c reads) and its analysis
    'open': ('int', 'const char *, int, ...'), 'ftruncate': ('int', 'int, long'),
    'mmap': ('void *', 'void *, unsigned, int, int, int, long'),
    'mmap64': ('void *', 'void *, unsigned, int, int, int, long long'),
    'clock_gettime': ('int', 'int, void *'),
    'sinf': ('float', 'float'), 'cosf': ('float', 'float'),
}

def compile_common(out, binary, player=False, ipod=False, defines=None):
    got = {}
    for line in run('readelf', '-AW', binary).splitlines():
        words = line.split()
        if len(words) >= 6 and 'UND' in words and re.fullmatch('[0-9a-f]{8}', words[0]):
            got[words[-1].split('@')[0]] = int(words[0], 16)
    gp = 0xb16750 if player else GP
    header = ['struct dirent { unsigned ino, off; unsigned short reclen; unsigned char d_type; char d_name[256]; };']
    asm = ['.set noreorder', '.text']
    for name, (ret, args) in LIBC.items():
        # Unused I/O is removed by --gc-sections in the player payload.
        alias = {'fopen': 'fopen64', 'readdir': 'readdir64', 'pow': '__pow_finite'}.get(name, name) if player else name
        if alias not in got:
            header.append(f'extern {ret} {name}({args});')
            continue
        address = got[alias]
        header += [f'extern {ret} peq_lib_{name}({args});', f'#define {name} peq_lib_{name}']
        asm += [f'.section .text.peq_lib_{name},"ax",@progbits', f'.globl peq_lib_{name}',
                f'peq_lib_{name}:', f'lui $gp, {gp >> 16}', f'ori $gp, $gp, {gp & 65535}',
                f'lui $t8, {address >> 16}', f'ori $t8, $t8, {address & 65535}',
                'lw $t9, 0($t8)', 'jr $t9', 'nop']
        if name in ('memcpy', 'memset'):
            asm += [f'.globl {name}', f'.set {name}, peq_lib_{name}']
    if not player:
        syms = symbols(binary) | PRIVATE_FUNCTIONS
        for name, (ret, args) in FUNCTIONS.items():
            if name in syms and syms[name]:
                header.append(f'#define {name} (({ret} (*)({args}))0x{syms[name]:x}u)')
        # build.py has already checked each is a one-byte global.
        header += [f'#define {name} (*(volatile unsigned char *)0x{syms[name]:x}u)' for name in GLOBALS]
    (out/'peq_platform.h').write_text('\n'.join(header)+'\n')
    (out/'peq_imports.S').write_text('\n'.join(asm)+'\n')
    flags = [*FLAGS, '-fno-math-errno', '-ffunction-sections', '-fdata-sections', f'-DIPOD={int(ipod)}',
             *(f'-D{k}={v:#x}u' for k, v in (defines or {}).items())]
    if player: flags += ['-mnan=2008']
    objects = []
    for name in ['peq.c', 'peq_player.c'] if player else ['peq.c', 'shared.c', 'peq_ui.c', 'coverflow.c', 'scrobble.c', 'photos.c', 'books.c', 'visualizer.c', 'playback.c', 'spotify.c', 'radio.c', 'tidal.c', 'crossfade.c', 'headset.c', 'lockscreen.c']:
        obj = out/(name+'.o')
        run('clang', *flags, '-I', out, '-c', ROOT/'patch'/name, '-o', obj)
        objects.append(obj)
    obj = out/'peq_imports.o'
    run('clang', *flags, '-c', out/'peq_imports.S', '-o', obj)
    return [*objects, obj]

def patch_player(raw, out, t=Q2_PLAYER):
    out.mkdir(exist_ok=True)
    check(sha(raw) == t['sha'], 'Unexpected stock hciplayer')
    binary = out/'stock-hciplayer'
    binary.write_bytes(raw)
    check(raw[fileoff(raw, t['eq_desc']):fileoff(raw, t['eq_desc'])+24].hex() == t['eq_desc_bytes'], 'EQ descriptor mismatch')
    objects = compile_common(out, binary, True, defines=t['defines'])
    base = t['base']
    script = out/'link.ld'
    script.write_text(f'SECTIONS {{ . = {base:#x}; .text : {{ *(.text*) }} .rodata : {{ *(.rodata*) }} '
                      '.data : { *(.data*) *(.sdata*) } .bss : { *(.bss*) *(.sbss*) } '
                      '__end = .; /DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) '
                      '*(.MIPS.abiflags) *(.reginfo) } }')
    run('ld.lld', '-m', 'elf32ltsmip', '--gc-sections', '-T', script, '-e', 'peq_open', '--undefined=mp3_seek', '--undefined=id3_gain',
        *objects, '-o', out/'peq.elf')
    run('llvm-objcopy', '-O', 'binary', out/'peq.elf', out/'peq.bin')
    ps = symbols(out/'peq.elf')
    payload = (out/'peq.bin').read_bytes()
    data = bytearray(raw)
    off = fileoff(raw, t['eq_open_slot'])
    data[off:off+4] = struct.pack('<I', ps['peq_open'])
    patch_word(data, t['vbr_scan'], 0x144008a8, 0, 'VBR scan')  # bnez $v0, the frame walk -> nop
    for address, stock, patched in t['rate_gates']:
        patch_word(data, address, stock, patched, 'Equalizer rate gate')
    patch_word(data, t['seek_slot'], t['stock_seek'], ps['mp3_seek'], 'Audio demuxer seek slot')
    for address in t['id3_calls']:
        patch_word(data, address, jal(t['stock_id3']), jal(ps['id3_gain']), 'MP3 ReplayGain')
    append_payload(data, payload, base, max(len(payload), ps['__end']-base), 'player')
    (out/'hciplayer').write_bytes(data)
    return dict(stock_sha256=t['sha'], sha256=sha(data), payload_sha256=sha(payload))
