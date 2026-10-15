#!/usr/bin/env python3
"""Assemble the full, direct-boot M1 Plus test firmware from validated components.

No launcher, stock fallback, recovery overlay or kernel change is installed.
Vendor bytes and Unix filesystem metadata are preserved outside the manifest.
"""
import argparse
import copy
import io
import json
import os
from pathlib import Path
import stat
import subprocess
from dissect.squashfs import SquashFS
from build_m1plus import ROOT,checked,sha
from build_m1plus_firmware import ORIGINAL,ROOTFS,KERNEL,package
from m1plus_rootfs import inventory,link_groups,write_root_tar,validate,file_digest
from port_inspect import read_container
from m1plus_media import tag_cover,bluealsa

VERSION='V2.1-M1P-full1'
# The stock symlinks and all DT_NEEDED users select 2.74.4. These five dormant
# 2.54.3 copies are unreferenced; retaining both versions wastes flash space.
OBSOLETE=tuple('usr/lib/lib'+name+'-2.0.so.0.5400.3' for name in ('gio','glib','gmodule','gobject','gthread'))

def build(original,out,ui,player,helper,assets,sqfstar):
    checked(file_digest(original)==ORIGINAL,'Unpinned original firmware')
    data,summary=read_container(original)
    out=out.resolve();checked(out.is_relative_to(ROOT/'work') and not out.exists(),'Use a fresh work/ directory')
    out.mkdir(parents=True)
    fs=SquashFS(io.BytesIO(data[ROOTFS])); originals,nodes=inventory(fs)
    checked(fs.sb.compression==3 and fs.block_size==131072 and fs.sb.xattr_id_table_start==-1,'Unexpected rootfs format')
    expected=copy.deepcopy(originals);sources={};changes={}
    old_names=[Path(p).name.encode() for p in OBSOLETE]
    for p,node in nodes.items():
        if node.is_symlink():
            checked(not any(n.decode() in node.link for n in old_names),'Old library still has a symlink: '+p)
        elif node.is_file() and p not in OBSOLETE:
            content=node.open().read()
            checked(not any(n in content for n in old_names),'Old library still has a reference: '+p)
    for p in OBSOLETE:
        checked(p in originals and originals[p]['type']==stat.S_IFREG,'Missing obsolete library '+p)
        current=p.replace('.5400.3','.7400.4')
        checked(current in originals and nodes[p.rsplit('.',2)[0]].link==Path(current).name,
                'Native loader symlink no longer selects current library '+p)
        del expected[p]
    def put(path,content,mode=0o644):
        for parent in reversed(Path(path).parents):
            p=parent.as_posix()
            if p=='.' or p in expected:continue
            expected[p]=dict(mode=0o755,type=stat.S_IFDIR,uid=0,gid=0,mtime=originals['.']['mtime'],inode='m1:'+p)
        row=expected.get(path)
        checked(row is None or row['type']==stat.S_IFREG,'Cannot replace non-regular inode '+path)
        if row is None:row=dict(mode=mode,type=stat.S_IFREG,uid=0,gid=0,mtime=originals['.']['mtime'])
        row.update(inode='m1:'+path,size=len(content),sha256=sha(content));expected[path]=row
        dest=out/'overlay'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(content);sources[path]=dest
        changes[path]=dict(sha256=sha(content),bytes=len(content))
    for directory,filename,path in [(ui,'demo.m1pod','release/bin/demo'),
                                     (player,'hciplayer','usr/bin/hciplayer'),
                                     (helper,'q2video','usr/bin/q2video')]:
        m=json.loads((directory/'manifest.json').read_text());b=(directory/filename).read_bytes()
        checked(sha(b)==m['sha256'],'Component hash mismatch '+filename)
        put(path,b,0o755)
    am=json.loads((assets/'manifest.json').read_text())
    checked(am['m1_source']==ORIGINAL,'Asset base mismatch')
    for path,entry in am['files'].items():
        b=(assets/'overlay'/path).read_bytes();checked(sha(b)==entry['sha256'],'Asset hash mismatch '+path);put(path,b)
    put('usr/lib/libtag_c.so.2.0.1',tag_cover(nodes['usr/lib/libtag_c.so.2.0.1'].open().read()))
    put('usr/bin/bluealsa',bluealsa(nodes['usr/bin/bluealsa'].open().read()))
    logo='etc/init.d/S11logo_display_shell'
    b=nodes[logo].open().read()
    needle=b'\tif [ `grep -c "ROTATEMODE=1" /mnt/data/config.ini`'
    checked(b.count(needle)==1,'Boot logo launch changed')
    b=b.replace(needle,b'\tif [ -s /mnt/data/boot-logo.jpg ]; then\n\t\tdisplay_logo /mnt/data/boot-logo.jpg\n\t\treturn\n\tfi\n'+needle)
    put(logo,b)
    root_tar=out/'rootfs.tar';write_root_tar(root_tar,expected,nodes,sources)
    root=originals['.']
    command=[str(sqfstar),'-comp','lzo','-no-tailends','-Xcompression-level','9','-b','131072','-processors','1',
             '-mem','256M','-no-progress','-numeric-owner','-no-xattrs','-mkfs-time',str(fs.sb.mkfs_time),
             '-root-mode',format(root['mode'],'o'),'-root-uid',str(root['uid']),'-root-gid',str(root['gid']),
             '-root-time',str(root['mtime']),str(out/'rootfs.squashfs')]
    env=os.environ.copy();env.pop('SOURCE_DATE_EPOCH',None)
    with root_tar.open('rb') as inp,(out/'squashfs.log').open('w') as log:
        subprocess.run(command,stdin=inp,stdout=log,stderr=subprocess.STDOUT,env=env,check=True)
    rebuilt=(out/'rootfs.squashfs').read_bytes();actual_fs=SquashFS(io.BytesIO(rebuilt));actual,_=inventory(actual_fs)
    result=validate(originals,expected,actual,allowed_removed=OBSOLETE)
    result.update(no_growth=len(rebuilt)<=len(data[ROOTFS]),image_bytes=len(rebuilt),original_bytes=len(data[ROOTFS]),
                  native_startup_preserved=actual['etc/init.d/S90play']==originals['etc/init.d/S90play'])
    # inventory inode numbers change on recompression; file content and metadata are compared above.
    result['native_startup_preserved']=all(actual['etc/init.d/S90play'][k]==originals['etc/init.d/S90play'][k]
                                          for k in originals['etc/init.d/S90play'] if k!='inode')
    for name,value in [('filesystem-validation',result),('expected-filesystem',expected),('changed-files',changes)]:
        (out/(name+'.json')).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    checked(result['passed'] and result['no_growth'] and result['native_startup_preserved'],
            'Filesystem validation failed; no update emitted: '+json.dumps(result))
    final,pack=package(original,out/'update.bin.pending',{**data,ROOTFS:rebuilt},VERSION)
    checked(final[KERNEL]==data[KERNEL] and file_digest(original)==ORIGINAL,'Original or kernel changed')
    manifest=dict(status='full-non-streaming-test-not-device-verified',version=VERSION,package=pack,
                  kernel_unchanged=True,direct_boot=True,fallback=False,filesystem=result,changed_files=changes,
                  removed_unreferenced_libraries=list(OBSOLETE),
                  components={n:str(p) for n,p in [('ui',ui),('player',player),('video',helper),('assets',assets)]})
    (out/'validation.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out/'update.bin.pending').rename(out/'update.bin')
    print(json.dumps(dict(update=str(out/'update.bin'),sha256=pack['sha256'],rootfs_bytes=len(rebuilt))))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('original','out','ui','player','helper','assets','sqfstar'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();build(a.original,a.out,a.ui,a.player,a.helper,a.assets,a.sqfstar.resolve())
