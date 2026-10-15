#!/usr/bin/env python3
"""Install pinned official MSYS2 sqfstar tools locally; no system installation.

Only regular usr/bin files are extracted after SHA-256 verification. Package
contents are build tools, not firmware payloads. Needs zstandard on Windows.
"""
import hashlib
import io
from pathlib import Path, PurePosixPath
import tarfile
import urllib.request

import zstandard

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://mirror.msys2.org/msys/x86_64/'
PACKAGES = {
    'squashfs-tools-4.7.5-1-x86_64.pkg.tar.zst': 'e80c0303eb74d95318e3fdbe084403ead2d7141aee31c744ca24bb24a0f61fc7',
    'msys2-runtime-3.6.11-3-x86_64.pkg.tar.zst': 'b6478bd1b4cb4b2e07c45db725fee93f9424c19fa248240dcb7b7f4187cd92db',
    'gcc-libs-15.3.0-1-x86_64.pkg.tar.zst': '0d99a122c453c05ae21ba3dcea910f2e0d93d38ae067c677a112a315b0f3cec5',
    'liblzo2-2.10-3-x86_64.pkg.tar.zst': '5881251a3b73ebf7a6b2491e092bafbd62a44925d538d69d0776903d26119794',
    'liblz4-1.10.0-1-x86_64.pkg.tar.zst': '1cbbe51ee91bf32691aabb15bdb7c8548e8b5ef8195122ef31f10edcca6e952f',
    'liblzma-5.8.4-1-x86_64.pkg.tar.zst': '4b7d61656e72a5651a797680b66186338dce4f8fbc62a637ab3b59922dd01074',
    'libzstd-1.5.7-1-x86_64.pkg.tar.zst': '5e370b2e725a0a7e5ff58d84653c9a0cd5a10b9cfe930f2d949a28ad2a11c1f2',
    'zlib-1.3.2-1-x86_64.pkg.tar.zst': 'a04aa79996c57f0db936be66cf94326d7e67e9cd8dbffe4cf6e97693d0a1d9ef',
}


def install():
    cache = ROOT/'work/tools/downloads'
    dest = ROOT/'work/tools/msys/usr/bin'
    cache.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    for name, expected in PACKAGES.items():
        file = cache/name
        if not file.exists():
            with urllib.request.urlopen(BASE+name, timeout=60) as r:
                data = r.read(100*1024*1024+1)
            if len(data) > 100*1024*1024:
                raise ValueError('Oversized package')
        else:
            data = file.read_bytes()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Package hash mismatch: '+name)
        if not file.exists():
            file.write_bytes(data)
        with zstandard.ZstdDecompressor().stream_reader(io.BytesIO(data)) as stream:
            with tarfile.open(fileobj=stream, mode='r|') as archive:
                for member in archive:
                    p = PurePosixPath(member.name)
                    if p.is_absolute() or '..' in p.parts or '\\' in member.name or ':' in member.name:
                        raise ValueError('Unsafe package path')
                    if member.isfile() and p.parent == PurePosixPath('usr/bin'):
                        content = archive.extractfile(member).read()
                        out = dest/p.name
                        if out.exists() and out.read_bytes() != content:
                            raise ValueError('Conflicting tool file: '+p.name)
                        out.write_bytes(content)
        print('Verified', name)
    print(dest/'sqfstar.exe')


if __name__ == '__main__':
    install()
