#!/usr/bin/env python3
"""Container rejection checks with synthetic inputs; no vendor firmware needed."""
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('port_inspect', ROOT / 'tools/port_inspect.py')
port = importlib.util.module_from_spec(spec)
spec.loader.exec_module(port)


def fixture():
    payload = b'not executable: synthetic kernel payload'
    header = bytearray(struct.pack('>7I4B32s', 0x27051956, 0, 0, len(payload),
                                  0, 0, zlib.crc32(payload), 5, 5, 2, 0, b'test'))
    struct.pack_into('>I', header, 4, zlib.crc32(header))
    squash = struct.pack('<5I6H8Q', 0x73717368, 1, 0, 131072, 0,
                         3, 17, 0, 1, 4, 0, 0, 96, 0, 0, 0, 0, 0, 0)
    return dict(zip(port.PAYLOADS, (bytes(header) + payload, squash)))


def package(path, files, *, extra=None, digest_lines=None):
    digests = digest_lines or [hashlib.md5(files[n]).hexdigest() + '  ' + n for n in port.PAYLOADS]
    entries = [('firmware_v20.info', ('Shanling M1 Plus\nV2.1\n' + '\n'.join(digests) + '\n').encode()),
               *files.items()]
    if extra:
        entries.append(extra)
    with tarfile.open(path, 'w') as archive:
        for name, data in entries:
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


class ContainerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'update.bin'

    def test_valid_container_and_hashes(self):
        data = fixture()
        package(self.path, data)
        extracted, summary = port.read_container(self.path)
        self.assertEqual(extracted[port.PAYLOADS[0]], data[port.PAYLOADS[0]])
        self.assertEqual(summary['model'], 'Shanling M1 Plus')
        self.assertEqual(summary['sha256'], hashlib.sha256(self.path.read_bytes()).hexdigest())
        self.assertTrue(summary['kernel']['crc_valid'])

    def test_rejects_wrong_payload_digest(self):
        data = fixture()
        lines = ['0' * 32 + '  ' + n for n in port.PAYLOADS]
        package(self.path, data, digest_lines=lines)
        with self.assertRaisesRegex(ValueError, 'MD5 mismatch'):
            port.read_container(self.path)

    def test_rejects_kernel_crc_even_with_matching_md5(self):
        data = fixture()
        data[port.PAYLOADS[0]] = data[port.PAYLOADS[0]][:-1] + b'!'
        package(self.path, data)
        with self.assertRaisesRegex(ValueError, 'CRC mismatch'):
            port.read_container(self.path)

    def test_rejects_out_of_bounds_squashfs(self):
        data = fixture()
        squash = bytearray(data[port.PAYLOADS[1]])
        struct.pack_into('<Q', squash, 40, 4096)
        data[port.PAYLOADS[1]] = bytes(squash)
        package(self.path, data)
        with self.assertRaisesRegex(ValueError, 'SquashFS'):
            port.read_container(self.path)

    def test_rejects_repeated_digest(self):
        data = fixture()
        line = hashlib.md5(data[port.PAYLOADS[0]]).hexdigest() + '  ' + port.PAYLOADS[0]
        package(self.path, data, digest_lines=[line, line])
        with self.assertRaisesRegex(ValueError, 'repeated payload digest'):
            port.read_container(self.path)

    def test_rejects_duplicate_and_unexpected_files(self):
        for name in ('firmware_v20.info', '../escape', '/absolute', 'C:\\escape'):
            with self.subTest(name=name):
                package(self.path, fixture(), extra=(name, b'bad'))
                with self.assertRaises(ValueError):
                    port.read_container(self.path)
        self.assertFalse((self.path.parent.parent / 'escape').exists())

    def test_rejects_symlink_member(self):
        package(self.path, fixture())
        with tarfile.open(self.path, 'a') as archive:
            member = tarfile.TarInfo('link')
            member.type, member.linkname = tarfile.SYMTYPE, '../../outside'
            archive.addfile(member)
        with self.assertRaisesRegex(ValueError, 'Non-regular'):
            port.read_container(self.path)


if __name__ == '__main__':
    unittest.main()
