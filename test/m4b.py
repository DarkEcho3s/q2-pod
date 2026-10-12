#!/usr/bin/env python3
"""Exercise the installed TagLib's native MP4 dispatch, without decoding audio or flashing."""
import pathlib, struct, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from build import segments, symbols, fileoff
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import *
raw = subprocess.check_output(['unsquashfs','-cat',str(pathlib.Path(sys.argv[1])/'stock.squashfs'),'usr/lib/libtag.so.2.0.1'])
# Pin the native resolver: M4A and M4B compare in the same chain and branch to MP4's constructor.
assert raw[fileoff(raw,0x115130):fileoff(raw,0x115130)+4] == b'M4B\0'
for ext in ('M4A','M4B','m4b','M4b','m4B','MP4'):
    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
    for _,(kind,off,addr,_,size,mem,_,_) in segments(raw):
        if kind==1:
            start=addr&~4095; u.mem_map(start,((addr+mem+4095)&~4095)-start); u.mem_write(addr,raw[off:off+size])
    u.mem_map(0x2000000,0x10000)
    def word(addr): return struct.unpack('<I',u.mem_read(addr,4))[0]
    gp=0x158590
    eq,alloc,mp4=[word(gp+n) for n in (-0x7c10,-0x69ac,-0x6e90)]
    assert eq==0xa44e8 and mp4==0xdcc9c
    seen=[]
    def hook(u,addr,size,_):
        if addr==eq:
            p=u.reg_read(UC_MIPS_REG_A1); b=bytes(u.mem_read(p,4)).split(b'\0')[0].decode()
            # FileRef normalizes the extension to uppercase before this dispatch chain.
            u.reg_write(UC_MIPS_REG_V0,int(ext.upper()==b))
        elif addr==alloc: u.reg_write(UC_MIPS_REG_V0,0x2000200)
        elif addr==mp4: seen.append(addr); u.emu_stop(); return
        else: return
        u.reg_write(UC_MIPS_REG_PC,u.reg_read(UC_MIPS_REG_RA))
    u.hook_add(UC_HOOK_CODE,hook)
    u.reg_write(UC_MIPS_REG_GP,gp); u.reg_write(UC_MIPS_REG_SP,0x200f000)
    u.reg_write(UC_MIPS_REG_S1,0x2000100); u.reg_write(UC_MIPS_REG_S2,0x2000300)
    u.mem_write(0x200f018,struct.pack('<I',gp))
    u.emu_start(0x10a7ac,0x10a3f4,count=200)
    assert seen==[mp4],ext
print('Installed TagLib: M4B and M4A reach the same MP4 metadata constructor (audio decoding untested).')
