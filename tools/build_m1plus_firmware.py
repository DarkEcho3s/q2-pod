#!/usr/bin/env python3
"""Build the stock-first M1 Plus bootstrap update, offline; never flash a device.

The experimental application lives on SD. Only S90play and two small launcher
files differ in rootfs. All existing file bytes, Unix metadata and hardlinks
are validated after recompression. Original kernel and demo remain untouched.
"""
import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import tarfile

from dissect.squashfs import SquashFS
from elftools.elf.elffile import ELFFile

from build_m1plus import FLAGS, ROOT, checked, sha, validate_stock
from m1plus_rootfs import inventory, link_groups, validate, write_root_tar, file_digest
from port_inspect import read_container

ORIGINAL = '1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925'
INFO = 'firmware_v20.info'
KERNEL = 'recovery-update/xImage'
ROOTFS = 'recovery-update/rootfs.squashfs'
VERSION = 'V2.1-M1P-dev1'
RESTORE_VERSION = 'V2.1-M1P-restore'


def package(original, destination, data, version):
    checked(version.startswith('V2.1-M1P-') and len(version) < 63 and '\n' not in version,
            'Invalid development package version')
    replacements = {KERNEL: data[KERNEL], ROOTFS: data[ROOTFS]}
    replacements[INFO] = ('Shanling M1 Plus\n'+version+'\n'+''.join(
        hashlib.md5(replacements[n]).hexdigest()+'  '+n+'\n' for n in (KERNEL, ROOTFS))).encode()
    with tarfile.open(original) as src, tarfile.open(destination, 'w', format=tarfile.GNU_FORMAT) as dst:
        for original_member in src:
            member = copy.copy(original_member)
            if member.isfile():
                blob = replacements[member.name]
                member.size = len(blob)
                dst.addfile(member, io.BytesIO(blob))
            else:
                dst.addfile(member)
    return read_container(destination)


def build_exec(out, zig):
    checked(subprocess.check_output([str(zig), 'version'], text=True).strip() == '0.15.2',
            'Use Zig 0.15.2')
    env = os.environ.copy()
    env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'),
               ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    link = out/'exec.ld'
    link.write_text('ENTRY(_start)\nSECTIONS { . = 0x400000; '
                    '.text : { *(.text*) } .rodata : { *(.rodata*) } '
                    '.data : { *(.data*) *(.got*) } '
                    '/DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) } }\n')
    exe = out/'m1pod-exec'
    subprocess.run([str(zig), 'cc', *FLAGS, '-nostdlib', '-Wl,--build-id=none',
                    '-Wl,-T,'+str(link), '-Wl,-e,_start', str(ROOT/'patch/m1plus/exec.S'),
                    '-o', str(exe)], env=env, check=True)
    elf = ELFFile(io.BytesIO(exe.read_bytes()))
    checked(elf.elfclass == 32 and elf.little_endian and elf['e_machine'] == 'EM_MIPS'
            and elf['e_type'] == 'ET_EXEC' and elf['e_flags'] == 0x70001401,
            'Unexpected exec shim architecture/ABI')
    checked(not any(s['p_type'] in ('PT_INTERP', 'PT_DYNAMIC') for s in elf.iter_segments()),
            'Exec shim must not need a dynamic loader or libraries')
    checked(elf.get_section_by_name('.MIPS.abiflags').data().hex() ==
            '000020020102000600000000000000000100000000000000', 'Exec shim FPU ABI mismatch')
    return exe


def make_overlay(originals, nodes, out, shim, epoch):
    init_path = 'etc/init.d/S90play'
    initial = nodes[init_path].open().read()
    needle = b'    /release/bin/demo &\n'
    checked(initial.count(needle) == 1, 'Unrecognized stock app launch command')
    launch = (ROOT/'patch/m1plus/launch.sh').read_bytes().replace(b'\r\n', b'\n')
    checked(launch.startswith(b'#!/bin/sh\n') and b'\r' not in launch, 'Launcher needs LF newlines')
    blobs = {init_path: initial.replace(needle, b'    /usr/bin/m1pod-launch &\n'),
             'usr/bin/m1pod-launch': launch, 'usr/bin/m1pod-exec': shim.read_bytes()}
    expected, sources = copy.deepcopy(originals), {}
    overlay = out/'overlay'
    overlay.mkdir()
    for path, blob in blobs.items():
        if path == init_path:
            checked(originals[path]['type'] == stat.S_IFREG and
                    not any(path in group for group in link_groups(originals)),
                    'Stock startup script must be an independent regular file')
            row = expected[path]
        else:
            checked(path not in originals, 'Launcher path already exists in stock')
            row = dict(type=stat.S_IFREG, mode=0o755, uid=0, gid=0, mtime=epoch,
                       inode='m1pod:' + path)
            expected[path] = row
        row.update(size=len(blob), sha256=sha(blob))
        target = overlay/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)
        sources[path] = target
    return expected, sources


def build(original, out, zig, sqfstar):
    checked(file_digest(original) == ORIGINAL, 'Not the pinned original M1 Plus V2.1 update.bin')
    data, original_summary = read_container(original)
    checked(original_summary['model'] == 'Shanling M1 Plus' and original_summary['version'] == 'V2.1',
            'Incorrect model or version')
    out = out.resolve()
    checked(out.is_relative_to(ROOT/'work') and out != ROOT/'work' and not out.exists(),
            'Output must be a fresh subdirectory of ignored work/')
    fs = SquashFS(io.BytesIO(data[ROOTFS]))
    checked(fs.sb.xattr_id_table_start == -1, 'Cannot preserve unimplemented extended attributes')
    checked(fs.sb.compression == 3 and fs.block_size == 131072, 'Unexpected stock filesystem format')
    target = json.loads((ROOT/'targets/m1plus/v2.1.json').read_text())
    validate_stock(fs.get('release/bin/demo').open().read(), target)
    originals, nodes = inventory(fs)
    out.mkdir(parents=True)
    shim = build_exec(out, zig)
    expected, sources = make_overlay(originals, nodes, out, shim, fs.sb.mkfs_time)
    root_tar = out/'rootfs.tar'
    write_root_tar(root_tar, expected, nodes, sources)
    root = originals['.']
    # Packing large-file tails into fragments interleaved their placement with
    # subsequent data blocks on Windows, even with one compressor. Keeping
    # fragments for small files only was byte-repeatable. Level 9 fits stock size.
    command = [str(sqfstar), '-comp', 'lzo', '-no-tailends', '-Xcompression-level', '9',
               '-b', '131072', '-processors', '1',
               '-mem', '256M', '-no-progress', '-numeric-owner', '-no-xattrs',
               '-mkfs-time', str(fs.sb.mkfs_time), '-root-mode', format(root['mode'], 'o'),
               '-root-uid', str(root['uid']), '-root-gid', str(root['gid']),
               '-root-time', str(root['mtime']), str(out/'rootfs.squashfs')]
    with root_tar.open('rb') as source, (out/'squashfs-build.log').open('w') as log:
        environment = os.environ.copy()
        environment.pop('SOURCE_DATE_EPOCH', None)  # preserve every original inode time
        subprocess.run(command, stdin=source, stdout=log, stderr=subprocess.STDOUT,
                       env=environment, check=True)
    rebuilt = (out/'rootfs.squashfs').read_bytes()
    rebuilt_fs = SquashFS(io.BytesIO(rebuilt))
    actual, _ = inventory(rebuilt_fs)
    result = validate(originals, expected, actual)
    result.update(compression_matches=rebuilt_fs.sb.compression == 3 and rebuilt_fs.block_size == 131072,
                  no_growth=len(rebuilt) <= len(data[ROOTFS]), image_bytes=len(rebuilt),
                  original_bytes=len(data[ROOTFS]))
    result['passed'] &= result['compression_matches'] and result['no_growth']
    for name, value in [('expected-filesystem', expected), ('actual-filesystem', actual),
                        ('filesystem-validation', result)]:
        (out/(name+'.json')).write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    checked(result['passed'], 'Filesystem validation failed; update package NOT created')
    # Preserve original container order, ownership, times, directory entries.
    candidate = out/'update.bin.pending'
    final_data, final_summary = package(original, candidate, {**data, ROOTFS: rebuilt}, VERSION)
    checked(final_data[KERNEL] == data[KERNEL], 'Kernel changed')
    checked(file_digest(original) == ORIGINAL, 'Original firmware changed while building')
    changed = sorted(p for p in originals if originals[p] != expected[p])
    added = sorted(set(expected)-set(originals))
    checked(changed == ['etc/init.d/S90play'] and
            added == ['usr/bin/m1pod-exec', 'usr/bin/m1pod-launch'], 'Unexpected filesystem changes')
    # Stock demo reports V2.1 and rejects an identically labelled update. Restore
    # only retags firmware_v20.info; original kernel and rootfs bytes are exact.
    # See update_firmware at 0x4e1114..0x4e1144 in the pinned executable.
    (out/'stock-restore').mkdir()
    restore_data, restore_summary = package(original, out/'stock-restore/update.bin', data, RESTORE_VERSION)
    checked(all(restore_data[n] == data[n] for n in (KERNEL, ROOTFS)), 'Restore payload changed')
    (out/'original-stock').mkdir()
    (out/'original-stock/update.bin').write_bytes(original.read_bytes())
    checked(file_digest(out/'original-stock/update.bin') == ORIGINAL, 'Original backup copy mismatch')
    validation = dict(status='bootstrap-offline-validated-not-device-tested',
                      original_sha256=ORIGINAL, version=VERSION, package=final_summary,
                      kernel_unchanged=True, stock_demo_unchanged=True, stock_player_unchanged=True,
                      changed_paths=changed, added_paths=added, filesystem=result,
                      restore=dict(package=restore_summary, kernel_and_rootfs_identical=True,
                                   changed_member=INFO, original_backup_sha256=ORIGINAL),
                      tool=dict(sqfstar_sha256=file_digest(sqfstar), command=command),
                      unknowns=['M1 updater acceptance of development version',
                                'boot and SD mount timing on hardware', 'physical recovery procedure',
                                'experimental application UI/input behavior'])
    (out/'validation.json').write_text(json.dumps(validation, indent=2)+'\n')
    candidate.rename(out/'update.bin')
    print(json.dumps(dict(update=str(out/'update.bin'), sha256=final_summary['sha256'],
                         filesystem=result, validation=str(out/'validation.json')), indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--zig', type=Path, required=True)
    p.add_argument('--sqfstar', type=Path, required=True)
    a = p.parse_args()
    build(a.original.resolve(), a.out, a.zig.resolve(), a.sqfstar.resolve())
