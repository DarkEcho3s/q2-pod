#!/usr/bin/env python3
"""Compare local Shanling firmware without executing, changing or repacking it.

Requires requirements-port.txt. Extracted files are analysis copies, NOT a rootfs
that can be repacked: symlinks, special files and Unix metadata are not restored.
Symbol matches are porting candidates, not verified ABI-compatible patch sites.
"""
import argparse
import ast
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = ('recovery-update/xImage', 'recovery-update/rootfs.squashfs')
BINARIES = ('release/bin/demo', 'usr/bin/hciplayer', 'usr/bin/bluealsa')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_container(path):
    """Read only explicitly named regular members; never tar.extractall()."""
    expected = {'firmware_v20.info', *PAYLOADS}
    with tarfile.open(path, 'r:*') as archive:
        members = archive.getmembers()
        files = [m for m in members if m.isfile()]
        if len(files) != len(expected) or {m.name for m in files} != expected:
            raise ValueError('Unexpected or duplicate firmware members')
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or '..' in p.parts or '\\' in member.name or ':' in member.name:
                raise ValueError('Unsafe firmware member: ' + member.name)
            if not (member.isfile() or member.isdir()):
                raise ValueError('Non-regular firmware member: ' + member.name)
        data = {m.name: archive.extractfile(m).read() for m in files}
    info = data['firmware_v20.info'].decode('utf-8').splitlines()
    if len(info) != 4:
        raise ValueError('Expected model, version and two payload digests')
    checked = set()
    for line in info[2:]:
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        if name not in PAYLOADS or name in checked:
            raise ValueError('Unexpected or repeated payload digest')
        if hashlib.md5(data[name]).hexdigest() != digest.lower():
            raise ValueError('Payload MD5 mismatch: ' + name)
        checked.add(name)
    image = data[PAYLOADS[0]]
    h = struct.unpack('>7I4B32s', image[:64])
    header = bytearray(image[:64])
    header[4:8] = b'\0' * 4
    if h[0] != 0x27051956 or h[3] != len(image) - 64:
        raise ValueError('Invalid uImage header or length')
    if zlib.crc32(header) != h[1] or zlib.crc32(image[64:]) != h[6]:
        raise ValueError('uImage CRC mismatch')
    fs = data[PAYLOADS[1]]
    sb = struct.unpack('<5I6H8Q', fs[:96])
    if sb[0] != 0x73717368 or sb[9:11] != (4, 0) or not 96 <= sb[12] <= len(fs):
        raise ValueError('Invalid SquashFS header or bounds')
    summary = dict(sha256=sha(path.read_bytes()), size=path.stat().st_size,
                   model=info[0], version=info[1],
                   payloads={n: dict(size=len(data[n]), sha256=sha(data[n])) for n in PAYLOADS},
                   kernel=dict(name=h[11].split(b'\0')[0].decode(), arch_id=h[8],
                               compression_id=h[10], crc_valid=True),
                   squashfs=dict(inodes=sb[1], compression_id=sb[5], block_size=sb[3],
                                 bytes_used=sb[12], image_size=len(fs)))
    return data, summary


def elf_info(data):
    from elftools.elf.elffile import ELFFile
    elf = ELFFile(io.BytesIO(data))
    result = dict(sha256=sha(data), size=len(data), bits=elf.elfclass,
                  little_endian=elf.little_endian, machine=elf.header.e_machine,
                  type=elf.header.e_type, flags=hex(elf.header.e_flags), needed=[])
    dyn = elf.get_section_by_name('.dynamic')
    if dyn:
        result['needed'] = [t.needed for t in dyn.iter_tags() if t.entry.d_tag == 'DT_NEEDED']
    abi = elf.get_section_by_name('.MIPS.abiflags')
    if abi:
        result['abi'] = dict(zip(('version', 'isa_level', 'isa_revision', 'gpr_size',
                                 'cpr1_size', 'cpr2_size', 'fp_abi', 'isa_ext', 'ases',
                                 'flags1', 'flags2'), struct.unpack('<H6B4I', abi.data())))
    symbols = {}
    for section_name in ('.symtab', '.dynsym'):
        section = elf.get_section_by_name(section_name)
        if section:
            for s in section.iter_symbols():
                if s.name and s.entry.st_shndx != 'SHN_UNDEF':
                    symbols[s.name] = dict(address=hex(s.entry.st_value), size=s.entry.st_size,
                                           type=s.entry.st_info.type)
    result['defined_symbols'] = len(symbols)
    return result, symbols


def inspect(path, destination):
    from dissect.squashfs import SquashFS
    data, result = read_container(path)
    fs = SquashFS(io.BytesIO(data[PAYLOADS[1]]))
    destination.mkdir(parents=True, exist_ok=False)
    files, binaries, symbols, ui = {}, {}, {}, {}

    def visit(node, relative):
        parts = PurePosixPath(relative).parts
        if any(p in ('..', '') or '\\' in p or ':' in p for p in parts):
            raise ValueError('Unsafe filesystem path')
        if node.is_dir():
            for child in node.iterdir():
                if child.name not in ('.', '..'):
                    visit(child, relative + '/' + child.name if relative else child.name)
            return
        row = dict(type=node.type, mode=node.mode, uid=node.uid, gid=node.gid,
                   inode=node.inode_number, mtime=node.mtime.isoformat())
        if node.is_symlink():
            row['target'] = node.link
        elif node.is_file():
            content = node.open().read()
            row.update(size=len(content), sha256=sha(content))
            keep = (relative in BINARIES or relative.startswith('etc/init.d/') or
                    relative.startswith('release/assets/default/raw/ui/'))
            if keep:
                output = destination / 'analysis-files' / relative
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(content)
            if relative in BINARIES:
                binaries[relative], symbols[relative] = elf_info(content)
            if relative.startswith('release/assets/default/raw/ui/') and content[:4] == bytes.fromhex('12122211'):
                ui[relative] = dict(root_type=content[4:36].split(b'\0')[0].decode(),
                                    rectangle=list(struct.unpack_from('<4i', content, 36)))
        files[relative] = row

    visit(fs.root, '')
    for name, value in (('filesystem', files), ('symbols', symbols), ('ui', ui)):
        (destination / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    result.update(binaries=binaries, ui_pages=len(ui), filesystem_entries=len(files))
    (destination / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result, files, symbols, ui


def hook_names():
    """Inspect literal metadata without importing or running the Q2 builder."""
    result = {}
    for node in ast.parse((ROOT / 'tools/build.py').read_text(encoding='utf-8')).body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in
                                               ('HOOKS', 'IPOD_HOOKS') for t in node.targets):
            for name, value in ast.literal_eval(node.value).items():
                result[name] = hex(value[0])
    return result


def compare(m1, q2, pod):
    msum, mfiles, msymbols, mui = m1
    qsum, qfiles, qsymbols, qui = q2
    psum, pfiles, _, _ = pod
    demo = 'release/bin/demo'
    hooks = {name: dict(q2_patch_address=addr, q2_symbol=qsymbols[demo].get(name),
                        m1_symbol=msymbols[demo].get(name)) for name, addr in hook_names().items()}
    same = [p for p in mfiles.keys() & qfiles.keys()
            if mfiles[p].get('sha256') and mfiles[p].get('sha256') == qfiles[p].get('sha256')]
    changed = [p for p in pfiles.keys() & qfiles.keys()
               if pfiles[p].get('sha256') and pfiles[p].get('sha256') != qfiles[p].get('sha256')]
    libraries = [p for p in mfiles.keys() & qfiles.keys()
                 if p.startswith(('lib/', 'usr/lib/')) and mfiles[p].get('sha256')
                 and qfiles[p].get('sha256')]
    return dict(status='static-analysis-only; NOT a build target or ABI validation',
                models=[msum['model'], qsum['model'], psum['model']],
                hooks=hooks, named_hooks_found=sum(bool(h['m1_symbol']) for h in hooks.values()),
                hook_count=len(hooks), byte_identical_files=sorted(same),
                shared_regular_library_paths=len(libraries),
                identical_regular_library_paths=sum(p in same for p in libraries),
                different_libraries=sorted(p for p in libraries if p not in same),
                q2_pod_changed_regular_files=sorted(changed),
                q2_pod_added_paths=sorted(pfiles.keys() - qfiles.keys()),
                q2_pod_removed_paths=sorted(qfiles.keys() - pfiles.keys()),
                shared_ui_paths=len(mui.keys() & qui.keys()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('m1', 'q2', 'q2-pod'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True, help='new directory under ignored work/')
    args = parser.parse_args()
    # Keep proprietary analysis copies out of source control by construction.
    work = (ROOT / 'work').resolve()
    destination = args.out.resolve()
    if not destination.is_relative_to(work) or destination == work:
        parser.error('--out must be a new subdirectory of ' + str(work))
    if destination.exists():
        parser.error('--out already exists; choose a new analysis directory')
    packages = [read_container(path)[1] for path in (args.m1, args.q2, args.q2_pod)]
    if packages[0]['model'] != 'Shanling M1 Plus' or any('Q2' not in p['model'] for p in packages[1:]):
        parser.error('Unexpected model order (expected M1 Plus, Q2, Q2-pod)')
    results = [inspect(path, destination / label) for label, path in
               (('m1', args.m1), ('q2', args.q2), ('q2-pod', args.q2_pod))]
    comparison = compare(*results)
    (destination / 'comparison.json').write_text(json.dumps(comparison, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(output=str(destination), named_hooks_found=comparison['named_hooks_found'],
                          hook_count=comparison['hook_count'],
                          summaries=[r[0] for r in results]), indent=2))


if __name__ == '__main__':
    main()
