#!/usr/bin/env python3
"""Build the portrait M1 UI overlay using the supplied, pinned firmware assets.

No vendor binary assets are committed to Git. Native widget names remain intact
so M1 callbacks keep finding the controls they own.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

from dissect.squashfs import SquashFS
from port_inspect import read_container
from ipod import decode, encode, walk, png_header
from build_m1plus import ROOT, checked, sha

ASSETS = 'release/assets/default/raw/'

def styles(data):
    magic, version, count = struct.unpack_from('<3I', data)
    checked(magic == 0xfafbfcfd and 12+count*100 <= len(data), 'Invalid style table')
    result = []
    for i in range(count):
        at, state, style, widget = struct.unpack_from('<I32s32s32s', data, 12+i*100)
        start = at
        props, = struct.unpack_from('<I', data, at); at += 4
        for _ in range(props):
            _, keylen, size = struct.unpack_from('<BBH', data, at)
            at += 4+keylen+size
        checked(at <= len(data), 'Style properties exceed file')
        key = (state, style, widget)
        result.append((key, data[start:at]))
    return version, result

def merge_styles(native, pod):
    version, entries = styles(native)
    other_version, extra = styles(pod)
    checked(version == other_version, 'Theme format changed')
    native_keys = {key for key, _ in entries}
    entries += [(key, block) for key, block in extra if key not in native_keys]
    header = bytearray(struct.pack('<3I', 0xfafbfcfd, version, len(entries)))
    blocks, offset = bytearray(), 12+100*len(entries)
    for (state, style, widget), block in entries:
        header += struct.pack('<I32s32s32s', offset, state, style, widget)
        blocks += block; offset += len(block)
    result = bytes(header+blocks)
    checked(styles(result) == (version, entries), 'Theme round trip failed')
    return result

def node(kind, name, rect, **props):
    return [kind, list(rect), {'name': name, **props}, []]

def named(root): return {n[2].get('name'): n for n in walk(root) if n[2].get('name')}

def position(n, rect):
    n[1] = list(rect)
    n[2].pop('self_layout', None)

def relocate(root, child, parent, rect):
    for n in list(walk(root)):
        if any(x is child for x in n[3]): n[3] = [x for x in n[3] if x is not child]
    parent[3].append(child); position(child, rect)

def now_playing(root):
    w = named(root)
    checked(all(n in w for n in ['view_local','slide_view_view','slide_view','img_playcover','btn_fav',
                                'btn_more','view_buttons','scrlabel_title','scrlabel_artist']), 'M1 player layout changed')
    local, outer, slide = w['view_local'], w['slide_view_view'], w['slide_view']
    position(w['app_gesture'], (0,0,320,450)); position(local, (0,0,320,450))
    position(outer,(0,38,320,302)); position(slide,(0,0,320,302))
    first = slide[3][0]; position(first,(0,0,320,302))
    position(w['img_playcover'],(56,0,208,208))
    relocate(root,w['scrlabel_title'],first,(20,216,280,28))
    relocate(root,w['scrlabel_artist'],first,(20,246,280,24))
    w['scrlabel_title'][2].update({'style:normal:font_size':'22','only_focus':'true'})
    w['scrlabel_artist'][2].update({'style:normal:font_size':'18','only_focus':'true'})
    first[3].append(node('hscroll_label','label_ipod_album',(20,274,280,22),
                         **{'style':'s_scrlabel_white20l','style:normal:font_size':'15','only_focus':'true'}))
    for page in slide[3][1:]: position(page,(0,0,320,302))
    relocate(root,w['btn_return'],local,(0,0,48,36))
    relocate(root,w['btn_more'],local,(278,0,42,36))
    relocate(root,w['btn_fav'],local,(236,0,42,36))
    local[3].append(node('label','label_ipod_pos',(48,0,180,36),
                         **{'style:normal:font_size':'15','style:normal:text_color':'#AAAAAA'}))
    w['slide_indicator'][2]['visible']='false'
    w['label_index'][2]['visible']='false'
    w['img_hr'][2]['visible']='false'
    relocate(root,w['slider_play'],local,(16,350,288,22))
    w['slider_play'][2].update({'style':'s_ipod_progress','bar_size':'4',
        'style:normal:bg_color':'#1C1C1C','style:normal:fg_color':'#6E6E6E',
        'style:normal:bg_image':'','style:normal:fg_image':'','style:normal:icon':''})
    relocate(root,w['label_playtime'],local,(20,373,90,18))
    w['label_playtime'][2]['style:normal:font_size']='14'
    w['label_playlen'][2]['visible']='false'
    local[3].append(node('label','label_ipod_remain',(210,373,90,18),
        **{'style:normal:font_size':'14','style:normal:text_align_h':'right','style:normal:text_color':'#AAAAAA'}))
    position(w['view_buttons'],(0,396,320,54))
    for c in w['view_buttons'][3]:
        if c[0]=='button': position(c,(c[1][0],0,c[1][2],54))
    # Native repeat markers still update, but must not sit over the new text.
    for n in ('img_repeata','img_repeatb'): w[n][2]['visible']='false'

def status_bar(root):
    w = named(root)
    left,right=w['view_bar_left'],w['view_bar_right']
    position(left,(0,0,72,30)); left[2]['children_layout']='default(r=1,c=0,x=8,s=4)'
    position(right,(207,0,105,30));right[2]['children_layout']='default(r=1,c=0,a=right,s=4)'
    for name in ('img_volume','label_volume','img_digital','bar_dclock','pgbar_battery','img_synclink'):
        w[name][2]['visible']='false'
    position(w['img_wifi'],(0,0,14,30))
    relocate(root,w['img_battery'],right,(0,0,16,30))
    root[2]['style:normal:bg_color']='#000000'
    root[3] += [node('hscroll_label','label_clock',(72,0,135,30),style='s_scrlabel_white20c',
                      **{'style:normal:font_size':'16','only_focus':'true'}),
                node('label','label_idle',(8,0,44,30),text='M1',visible='false',
                      **{'style:normal:font_size':'14','style:normal:text_color':'#AAAAAA'})]
    left[3].append(node('label','label_eq',(0,0,22,30),text='EQ',visible='false',
                       **{'style:normal:font_size':'12','style:normal:text_color':'#FFFFFF'}))
    right[3] += [node('label','label_battery',(0,0,42,30),text='0%',visible='false'),
                 node('view','view_battery',(0,0,64,30),visible='false')]

def lock_settings(root):
    w=named(root); covers=w['view_covers']
    covers[0]='scroll_view'; covers[2]['yslidable']='true'
    covers[2]['virtual_h']='750'

def sort_dialog(root):
    w=named(root)
    position(root,(0,0,320,430));root[2]['self_layout']='default(x=c,y=m,w=320,h=430)'
    position(w['hscroll_label'],(20,12,280,36))
    position(w['list_view'],(0,52,320,318))
    position(w['scrollview_sortselect'],(0,0,320,318))
    position(w['button_return'],(0,370,320,60))

def build(original, pod_update, out):
    out=out.resolve()
    checked(out.is_relative_to(ROOT/'work') and not out.exists(), 'Use a fresh work/ directory')
    mdata, msummary=read_container(original); qdata,qsummary=read_container(pod_update)
    checked(msummary['sha256']=='1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925', 'Unpinned M1 firmware')
    checked(qsummary['sha256']=='330f09c51b6d6cbe5ca6911de7ad68a81e795db468b573718b994a0de9854bd9','Unpinned Pod theme firmware')
    m=SquashFS(io.BytesIO(mdata['recovery-update/rootfs.squashfs']))
    q=SquashFS(io.BytesIO(qdata['recovery-update/rootfs.squashfs']))
    def read(fs,path): return fs.get(path).open().read()
    checked(decode(read(q,ASSETS+'ui/home_page.bin'))[3][0][2].get('name')=='img_homeart', 'Source is not the Pod theme')
    out.mkdir(parents=True)
    changes={}
    def put(path,data):
        dest=out/'overlay'/path;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
        changes[path]={'sha256':sha(data),'bytes':len(data)}
    put(ASSETS+'styles/default.bin',merge_styles(read(m,ASSETS+'styles/default.bin'),read(q,ASSETS+'styles/default.bin')))
    for name,fn in {'playing_page.bin':now_playing,'system_bar.bin':status_bar,
                    'systemset/screensaver_page.bin':lock_settings,'dialog/sortselect_dialog.bin':sort_dialog}.items():
        path=ASSETS+'ui/'+name;root=decode(read(m,path));fn(root)
        data=encode(root);checked(decode(data)==root,'UI round trip failed: '+name);put(path,data)
    # Keep native images when their dimensions differ; new Pod art is imported.
    def files(fs,node,path):
        for child in node.iterdir():
            p=path+'/'+child.name
            if child.is_dir():yield from files(fs,child,p)
            elif child.is_file():yield p
    image_root=ASSETS+'images'
    skip=('tidal','stream_','spotify','radio_')
    for path in files(q,q.get(image_root),image_root):
        if Path(path).name.lower().startswith(skip):continue
        try: native=read(m,path)
        except FileNotFoundError:native=None
        content=read(q,path)
        if native is None:put(path,content)
        elif path.endswith('.png') and png_header(native)[:2]==png_header(content)[:2] and native!=content:
            put(path,content)
    for path in files(q,q.get(ASSETS+'fonts'),ASSETS+'fonts'):put(path,read(q,path))
    put('etc/scrobble-ca.pem',read(q,'etc/scrobble-ca.pem'))
    result={'status':'portrait-assets-not-device-tested','m1_source':msummary['sha256'],
            'pod_source':qsummary['sha256'],'files':changes}
    (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'overlay':str(out/'overlay'),'files':len(changes),'bytes':sum(x['bytes'] for x in changes.values())}))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--original',type=Path,required=True);p.add_argument('--pod-update',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build(a.original,a.pod_update,a.out)
