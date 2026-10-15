#!/usr/bin/env python3
"""Build the portrait video helper against the pinned M1 runtime libraries."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
from dissect.squashfs import SquashFS
from elftools.elf.elffile import ELFFile
from build_m1plus import ROOT, FLAGS, checked, sha
from build_m1plus_firmware import ORIGINAL, ROOTFS
from port_inspect import read_container
from build import HELPER_LIBS


def build(original,out,zig):
    data,summary=read_container(original)
    checked(summary['sha256']==ORIGINAL,'Unpinned firmware')
    out=out.resolve();checked(out.is_relative_to(ROOT/'work') and not out.exists(),'Use a fresh work/ directory')
    out.mkdir(parents=True)
    fs=SquashFS(io.BytesIO(data[ROOTFS]))
    libs=[];manifest={}
    for rel in HELPER_LIBS:
        b=fs.get(rel).open().read();p=out/Path(rel).name;p.write_bytes(b);libs.append(str(p));manifest[rel]=sha(b)
    flags=[f for f in FLAGS if f not in ('-static','-mno-abicalls','-G0','-fno-pic')]
    flags[flags.index('-mcpu=mips32r2+noabicalls+fp64+nan2008')]='-mcpu=mips32r2+fp64+nan2008'
    flags+=['-mabicalls','-fPIC','-DM1PLUS=1']
    env=os.environ.copy();env.update(ZIG_GLOBAL_CACHE_DIR=str(ROOT/'work/zig-cache'),ZIG_LOCAL_CACHE_DIR=str(out/'zig-cache'))
    objects=[]
    for name in ('video','start'):
        obj=out/(name+'.o');objects.append(str(obj))
        source_flags=[*flags, *(['-fno-pic'] if name=='start' else [])]
        subprocess.run([str(zig),'cc',*source_flags,'-c',str(ROOT/'patch'/(name+'.c')),'-o',str(obj)],env=env,check=True)
    dest=out/'q2video'
    subprocess.run([str(zig),'cc',*flags,'-nostdlib','-no-pie','-Wl,-e,__start',
                    '-Wl,--dynamic-linker,/lib/ld-linux-mipsn8.so.1','-Wl,--image-base=0x400000',
                    '-Wl,-z,noexecstack','-Wl,--gc-sections','-Wl,--hash-style=sysv','-Wl,--build-id=none',
                    '-s',*objects,*libs,'-o',str(dest)],env=env,check=True)
    e=ELFFile(io.BytesIO(dest.read_bytes()))
    checked(e['e_type']=='ET_EXEC' and e['e_machine']=='EM_MIPS' and e['e_flags']==0x70001405,'Helper ABI mismatch')
    checked(e.get_section_by_name('.interp').data().rstrip(b'\0')==b'/lib/ld-linux-mipsn8.so.1','Wrong interpreter')
    (out/'manifest.json').write_text(json.dumps(dict(sha256=sha(dest.read_bytes()),libraries=manifest),indent=2)+'\n')
    print(dest)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('original','out','zig'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();build(a.original,a.out,a.zig.resolve())
