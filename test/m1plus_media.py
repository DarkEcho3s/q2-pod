#!/usr/bin/env python3
"""Execute the M1 M4B dispatch and check the shipped media/asset dependencies."""
import argparse,io,json,posixpath,struct,sys,unittest
from pathlib import Path
from dissect.squashfs import SquashFS
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
import unicorn.mips_const as r
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from port_inspect import read_container
from m1plus_media import tag_cover,bluealsa
from ipod import decode,walk
ORIGINAL=HELPER=ASSETS=None

class MediaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data,_=read_container(ORIGINAL)
        cls.fs=SquashFS(io.BytesIO(data['recovery-update/rootfs.squashfs']))
    def read(self,path):
        for _ in range(20):
            n=self.fs.get(path)
            if not n.is_symlink():return n.open().read()
            path=posixpath.normpath(posixpath.join(posixpath.dirname(path),n.link)) if not n.link.startswith('/') else n.link[1:]
        self.fail('Symlink loop: '+path)
    def test_m4b_dispatch_is_case_insensitive_and_relocatable(self):
        original=self.fs.get('usr/lib/libtag_c.so.2.0.1').open().read()
        raw=tag_cover(original)
        for base in (0x2000000,0x3400000):
            for ext,first,expected in [('m4a',0,0x12688),('M4B',1,0x12688),('m4b',1,0x12688),
                                       ('flac',1,0x12564),('mp3',1,0x12564),('m4bad',1,0x12564)]:
                with self.subTest(base=base,ext=ext):
                    u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
                    u.ctl_set_cpu_model(r.UC_CPU_MIPS32_P5600)
                    u.mem_map(base,0x50000);u.mem_map(0x1000000,0x20000)
                    for s in ELFFile(io.BytesIO(raw)).iter_segments():
                        if s['p_type']=='PT_LOAD':u.mem_write(base+s['p_vaddr'],s.data())
                    gp=base+0x32770;sp=0x1010000;compare=0x1004000
                    u.mem_write(gp-0x7e90,struct.pack('<I',compare));u.mem_write(sp+16,struct.pack('<I',gp))
                    u.mem_write(0x1000000,ext.encode()+b'\0')
                    def string(a):
                        return bytes(u.mem_read(a,16)).split(b'\0')[0].lower()
                    hit=[]
                    def hook(u,a,size,_):
                        if a==compare:
                            self.assertEqual(string(u.reg_read(r.UC_MIPS_REG_A1)),b'm4b')
                            u.reg_write(r.UC_MIPS_REG_V0,int(string(u.reg_read(r.UC_MIPS_REG_A0))!=b'm4b'))
                            u.reg_write(r.UC_MIPS_REG_PC,u.reg_read(r.UC_MIPS_REG_RA))
                        elif a in (base+0x12688,base+0x12564):hit.append(a-base);u.emu_stop()
                    u.hook_add(UC_HOOK_CODE,hook)
                    for reg,val in [(r.UC_MIPS_REG_GP,gp),(r.UC_MIPS_REG_SP,sp),(r.UC_MIPS_REG_S0,0x1000000),(r.UC_MIPS_REG_V0,first)]:u.reg_write(reg,val)
                    u.emu_start(base+0x1255c,0,count=100)
                    self.assertEqual(hit,[expected]);self.assertEqual(u.reg_read(r.UC_MIPS_REG_GP),gp)
    def test_unpinned_media_libraries_are_rejected(self):
        for path,fn in [('usr/lib/libtag_c.so.2.0.1',tag_cover),('usr/bin/bluealsa',bluealsa)]:
            raw=bytearray(self.fs.get(path).open().read());raw[-1]^=1
            with self.assertRaises(ValueError):fn(raw)
    def test_video_dynamic_imports_resolve_in_native_libraries(self):
        helper=ELFFile(io.BytesIO((HELPER/'q2video').read_bytes()))
        libs=[];pending=[t.needed for t in helper.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED'];seen=set()
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name);raw=None
            for directory in ('lib','usr/lib'):
                try:raw=self.read(directory+'/'+name);break
                except FileNotFoundError:pass
            self.assertIsNotNone(raw,name)
            e=ELFFile(io.BytesIO(raw));libs.append(e)
            pending.extend(t.needed for t in e.get_section_by_name('.dynamic').iter_tags() if t.entry.d_tag=='DT_NEEDED')
        exports={s.name for e in libs for s in e.get_section_by_name('.dynsym').iter_symbols() if s['st_shndx']!='SHN_UNDEF'}
        required={s.name for s in helper.get_section_by_name('.dynsym').iter_symbols() if s.name and s['st_shndx']=='SHN_UNDEF' and s['st_info']['bind']!='STB_WEAK'}
        self.assertFalse(required-exports,required-exports)
        self.assertIn('libasound.so.2',seen)
        self.assertIn(b'scale=320:480:',(HELPER/'q2video').read_bytes())
        self.assertNotIn(b'transpose=clock',(HELPER/'q2video').read_bytes())
    def test_portrait_assets_keep_all_native_callback_names(self):
        manifest=json.loads((ASSETS/'manifest.json').read_text())
        for path in manifest['files']:
            if '/ui/' not in path:continue
            native=decode(self.fs.get(path).open().read())
            ported=decode((ASSETS/'overlay'/path).read_bytes())
            old={n[2]['name'] for n in walk(native) if n[2].get('name')}
            new={n[2]['name'] for n in walk(ported) if n[2].get('name')}
            self.assertFalse(old-new,(path,old-new))
        path='release/assets/default/raw/ui/playing_page.bin'
        names={n[2].get('name'):n for n in walk(decode((ASSETS/'overlay'/path).read_bytes()))}
        for name in ('img_playcover','scrlabel_title','scrlabel_artist','label_ipod_album','slider_play','label_ipod_remain','view_buttons'):
            self.assertIn(name,names)
        self.assertEqual(names['img_playcover'][1],[56,0,208,208])
        cert=(ASSETS/'overlay/etc/scrobble-ca.pem').read_text()
        self.assertIn('-----BEGIN CERTIFICATE-----',cert)
    def test_local_video_decoder_and_toolkit_dependencies_exist(self):
        for p in ('usr/bin/ffmpeg','lib/ld-linux-mipsn8.so.1','usr/lib/libtag_c.so.2.0.1'):
            self.assertTrue(self.read(p)[:4]==b'\x7fELF',p)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('original','helper','assets'):p.add_argument('--'+n,type=Path,required=True)
    a,rest=p.parse_known_args();ORIGINAL,HELPER,ASSETS=a.original,a.helper,a.assets
    unittest.main(argv=[sys.argv[0],*rest])
