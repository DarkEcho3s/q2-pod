"""Metadata-preserving SquashFS inventory and tar transport.

Adapted from shivaluma/shanling-m1plus-navidrome packaging/rebuild.py (MIT).
Copyright (c) 2026 shivaluma and contributors. See targets/m1plus/NOTICE.
The host filesystem is never used to represent Unix ownership or special files.
"""
import collections
import hashlib
import pathlib
import stat
import tarfile


def digest_stream(stream):
    h = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(chunk)
    return h.hexdigest()


def file_digest(path):
    with path.open('rb') as stream:
        return digest_stream(stream)


def inventory(fs):
    records, nodes = {}, {}
    def visit(node, path):
        if path != '.' and (pathlib.PurePosixPath(path).is_absolute() or '..' in pathlib.PurePosixPath(path).parts):
            raise ValueError('Unsafe original path: ' + path)
        row = dict(mode=stat.S_IMODE(node.mode), uid=node.uid, gid=node.gid,
                   mtime=int(node.mtime.timestamp()), type=node.type, inode=node.inode_number)
        if node.is_file():
            row['size'] = node.size
            with node.open() as stream:
                row['sha256'] = digest_stream(stream)
        elif node.is_symlink():
            row['target'] = node.link
        elif node.is_device():
            row['rdev'] = node.header.rdev
        elif not (node.is_dir() or node.is_fifo()):
            raise ValueError('Unsupported original inode type: ' + path)
        nodes[path], records[path] = node, row
        if node.is_dir():
            for child in sorted(node.iterdir(), key=lambda n: n.name):
                if child.name not in ('.', '..'):
                    visit(child, child.name if path == '.' else path + '/' + child.name)
    visit(fs.root, '.')
    return records, nodes


def link_groups(records):
    groups = collections.defaultdict(list)
    for path, row in records.items():
        if row['type'] != stat.S_IFDIR:
            groups[row['inode']].append(path)
    return sorted(sorted(paths) for paths in groups.values() if len(paths) > 1)


def write_root_tar(destination, expected, nodes, sources):
    links = {}
    with tarfile.open(destination, 'w', format=tarfile.GNU_FORMAT) as archive:
        for path, row in sorted(expected.items()):
            if path == '.':
                continue  # Root attributes are passed explicitly to sqfstar.
            entry = tarfile.TarInfo(path)
            entry.mode, entry.uid, entry.gid, entry.mtime = row['mode'], row['uid'], row['gid'], row['mtime']
            kind = row['type']
            if kind != stat.S_IFDIR and row['inode'] in links:
                entry.type, entry.linkname = tarfile.LNKTYPE, links[row['inode']]
                archive.addfile(entry)
                continue
            if kind != stat.S_IFDIR:
                links[row['inode']] = path
            if kind == stat.S_IFDIR:
                entry.type = tarfile.DIRTYPE
            elif kind == stat.S_IFLNK:
                entry.type, entry.linkname = tarfile.SYMTYPE, row['target']
            elif kind == stat.S_IFREG:
                entry.type, entry.size = tarfile.REGTYPE, row['size']
                stream = sources[path].open('rb') if path in sources else nodes[path].open()
                with stream:
                    archive.addfile(entry, stream)
                continue
            elif kind == stat.S_IFIFO:
                entry.type = tarfile.FIFOTYPE
            elif kind in (stat.S_IFCHR, stat.S_IFBLK):
                entry.type = tarfile.CHRTYPE if kind == stat.S_IFCHR else tarfile.BLKTYPE
                # Linux encoded dev_t, independent of the macOS host encoding.
                dev = row['rdev']
                entry.devmajor = (dev >> 8) & 0xfff
                entry.devminor = (dev & 0xff) | ((dev >> 12) & 0xfff00)
            else:
                raise ValueError('Unsupported tar inode type: ' + path)
            archive.addfile(entry)


def validate(originals, expected, actual):
    missing, extra = sorted(set(expected) - set(actual)), sorted(set(actual) - set(expected))
    mismatches = {}
    for path in sorted(set(expected) & set(actual)):
        before = {k:v for k,v in expected[path].items() if k != 'inode'}
        after = {k:v for k,v in actual[path].items() if k != 'inode'}
        if before != after:
            mismatches[path] = dict(expected=before, actual=after)
    expected_links, actual_links = link_groups(expected), link_groups(actual)
    removed_original = sorted(set(originals) - set(actual))
    result = dict(passed=not (missing or extra or mismatches or removed_original or expected_links != actual_links),
                  expected_paths=len(expected), actual_paths=len(actual), removed_original_paths=removed_original,
                  missing_paths=missing, unexpected_paths=extra, mismatches=mismatches,
                  hardlink_groups=len(actual_links), hardlink_equivalence_preserved=expected_links == actual_links,
                  root_metadata_preserved=all(originals['.'][k] == actual.get('.', {}).get(k) for k in ('mode','uid','gid','mtime','type')),
                  files_hashed=sum(row['type'] == stat.S_IFREG for row in actual.values()),
                  symlinks_checked=sum(row['type'] == stat.S_IFLNK for row in actual.values()))
    return result
