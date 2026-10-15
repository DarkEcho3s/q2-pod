#!/usr/bin/env python3
"""MIPS execution checks for the integrated M1 image, native ABI and loader.

Toolkit boundary mocks do not simulate Linux, the panel, DAC or physical keys.
"""
import argparse,io,json,re,struct,sys,unittest
from pathlib import Path
from elftools.elf.elffile import ELFFile
from unicorn import Uc,UC_ARCH_MIPS,UC_MODE_MIPS32,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
import unicorn.mips_const as r
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_m1plus_ui as builder
import m1plus as policy
BUILD=STOCK=LIBS=None
DATA,STOP,STACK=0x1000000,0x11e0000,0x11f0000

class Machine:
    def __init__(self):
        self.u=Uc(UC_ARCH_MIPS,UC_MODE_MIPS32|UC_MODE_LITTLE_ENDIAN)
        self.u.ctl_set_cpu_model(r.UC_CPU_MIPS32_P5600)
        self.u.reg_write(r.UC_MIPS_REG_CP0_STATUS,self.u.reg_read(r.UC_MIPS_REG_CP0_STATUS)|0x24000000)
        self.u.mem_map(0x400000,0x900000);self.u.mem_map(DATA,0x200000)
        self.vendor=ELFFile(io.BytesIO((BUILD/'demo.m1pod').read_bytes()))
        for s in self.vendor.iter_segments():
            if s['p_type']=='PT_LOAD':self.u.mem_write(s['p_vaddr'],s.data())
        e=ELFFile(io.BytesIO((BUILD/'payload.elf').read_bytes()))
        self.syms={s.name:s['st_value'] for s in e.get_section_by_name('.symtab').iter_symbols()}
        self.native={s.name:s['st_value'] for s in self.vendor.get_section_by_name('.dynsym').iter_symbols()}
        self.callbacks={};self.u.hook_add(UC_HOOK_CODE,self.intercept)
    def word(self,a,v=None):
        if v is None:return struct.unpack('<I',self.u.mem_read(a,4))[0]
        self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def string(self,a):
        b=bytearray()
        while (x:=self.u.mem_read(a,1)[0]):
            b.append(x);a+=1
            if len(b)>4096:raise AssertionError('Unbounded string')
        return bytes(b)
    def intercept(self,u,a,size,_):
        fn=self.callbacks.get(a)
        if fn is None:return
        v=fn(*[u.reg_read(x) for x in [r.UC_MIPS_REG_A0,r.UC_MIPS_REG_A1,r.UC_MIPS_REG_A2,r.UC_MIPS_REG_A3]])
        u.reg_write(r.UC_MIPS_REG_V0,v&0xffffffff);u.reg_write(r.UC_MIPS_REG_PC,u.reg_read(r.UC_MIPS_REG_RA))
    def call(self,name,*args):
        a=self.syms[name] if isinstance(name,str) else name
        for reg,val in [(r.UC_MIPS_REG_SP,STACK),(r.UC_MIPS_REG_RA,STOP),(r.UC_MIPS_REG_T9,a),
                        *zip([r.UC_MIPS_REG_A0,r.UC_MIPS_REG_A1,r.UC_MIPS_REG_A2,r.UC_MIPS_REG_A3],args)]:self.u.reg_write(reg,val)
        try:self.u.emu_start(a,STOP,count=500000)
        except Exception as ex:
            raise RuntimeError(f'{name}: pc={self.u.reg_read(r.UC_MIPS_REG_PC):x} ra={self.u.reg_read(r.UC_MIPS_REG_RA):x} t9={self.u.reg_read(r.UC_MIPS_REG_T9):x}') from ex
        assert self.u.reg_read(r.UC_MIPS_REG_PC)==STOP,'Instruction budget exceeded'
        assert self.u.reg_read(r.UC_MIPS_REG_SP)==STACK,'Stack not restored'
        return self.u.reg_read(r.UC_MIPS_REG_V0)
    route=policy.Machine.route

class PolicyTests(policy.PolicyTests):
    def setUp(self):self.m=Machine()

class NativeAbiTests(unittest.TestCase):
    def setUp(self):self.m=Machine()
    def test_canvas_offsets_match_native_accessors(self):
        m=self.m;seen=[];m.word(DATA+0x30,DATA+0x1000)
        m.callbacks[m.native['lcd_set_fill_color']]=lambda a,b,c,d:seen.append((a,b)) or 0
        self.assertEqual(m.call(m.native['canvas_set_fill_color'],DATA,0xff123456),0)
        self.assertEqual(seen,[(DATA+0x1000,0xff123456)])
        self.assertEqual(m.call(m.native['canvas_set_text_align'],DATA,1,2),0)
        self.assertEqual((m.word(DATA+0x2c),m.word(DATA+0x28)),(1,2))
    def test_native_parent_chain(self):
        m=self.m;m.word(DATA+0x44,DATA+0x1000)
        m.callbacks[m.native['widget_is_window']]=lambda a,b,c,d:int(a==DATA+0x1000)
        self.assertEqual(m.call(m.native['widget_get_window'],DATA),DATA+0x1000)
    def test_native_pressed_keys_layout(self):
        m=self.m
        for i in range(16):m.word(DATA+0x18+i*0x18,213 if i%2 else 0)
        m.call(m.native['input_device_status_abort_all_pressed_keys'],DATA)
        self.assertEqual([m.u.mem_read(DATA+0x18+i*0x18+0x10,1)[0] for i in range(16)],[i%2 for i in range(16)])
    def test_native_default_layout_fields(self):
        m=self.m;m.callbacks[m.native['value_int']]=lambda a,b,c,d:13
        for name,offset in [(b'x',0x14),(b's',0x16)]:
            m.u.mem_write(DATA+0x100,name+b'\0');m.call(0x63a0e4,DATA,DATA+0x100,DATA+0x200)
            self.assertEqual(m.u.mem_read(DATA+offset,1)[0],13)
        self.assertEqual(m.word(0x9047a8),m.syms['ipod_list_layout'])
    def test_slider_and_now_playing_context(self):
        m=self.m;names={DATA:b'bootvol_page',DATA+0x100:b'playing_page'}
        report=json.loads((BUILD/'abi-report.json').read_text())
        for n,v in [('g_backlight_status',1),('g_usblink_status',0),('g_lockscreen_pageflag',0),('g_poweroff_state',0),('g_guideflag',0),('bt__recv_pageflag',0)]:
            s=report['data'][n];m.u.mem_write(s['address'],v.to_bytes(s['size'],'little'))
        m.callbacks[m.native['window_manager']]=lambda *a:DATA+0x1000
        m.callbacks[m.native['window_manager_get_top_window']]=lambda *a:DATA
        def name(a,b,c,d):m.u.mem_write(DATA+0x2000,names[a]+b'\0');return DATA+0x2000
        m.callbacks[m.native['widget_get_prop_str']]=name
        m.callbacks[m.syms['m1_import_strcmp']]=lambda a,b,c,d:(m.string(a)>m.string(b))-(m.string(a)<m.string(b))
        self.assertEqual(m.call('ringnav_m1_supported',DATA),1)
        self.assertEqual(m.call('ringnav_m1_supported',DATA+0x100),0)
    def test_native_emitter_pending_removal_byte(self):
        m=self.m;item=DATA+0x100
        m.word(DATA,item);m.word(DATA+12,item)
        for off,v in [(0,0x1234),(8,0x10c),(12,0x5555)]:m.word(item+off,v)
        def clear(a,b,c,d):m.u.mem_write(a,bytes([b&255])*c);return a
        m.callbacks[m.word(0xa03ed0-0xadc)]=clear
        self.assertEqual(m.call(m.native['emitter_off_by_func'],DATA,0x10c,0x5555,0x1234),0)
        self.assertEqual(m.u.mem_read(item+0x14,2),b'\1\0')
        self.assertEqual(m.word(DATA),item)
    def test_ldac_hq_and_standard_are_distinct(self):
        m=self.m;seen=[]
        for slot,name in [(0xa03084,'codec'),(0xa037fc,'ldac'),(0xa03148,'sbc')]:
            m.callbacks[m.word(slot)]=lambda a,b,c,d,name=name:seen.append((name,a)) or 0
        for row,quality in [(0,0x15),(1,0x16),(2,0x18)]:
            seen.clear();self.assertEqual(m.call(m.native['switchBtPriority'],row),1)
            self.assertIn(('ldac',quality),seen)
    def test_double_press_wake_and_dark_volume_keys(self):
        m=self.m;now=[10000]
        def config(a,b,c,d):
            default=m.word(m.u.reg_read(r.UC_MIPS_REG_SP)+16)
            value=b'1' if m.string(c)==b'WAKEDOUBLE' else m.string(default)
            m.u.mem_write(d,value+b'\0');return 0
        m.callbacks[m.native['toolsReadConfig']]=config
        def clear(a,b,c,d):m.u.mem_write(a,bytes([b&255])*c);return a
        m.callbacks[m.syms['m1_import_memset']]=clear
        m.callbacks[m.native['time_now_ms']]=lambda *_:now[0]
        report=json.loads((BUILD/'abi-report.json').read_text());backlight=report['data']['g_backlight_status']['address']
        m.u.mem_write(backlight,b'\0')
        def key(typ,k):m.word(DATA,typ);m.word(DATA+24,k);return m.call('ringnav_m1_wake',DATA)
        self.assertEqual(key(0x10f,210),1);self.assertEqual(key(0x113,210),1)
        now[0]+=100
        self.assertEqual(key(0x10f,210),0);self.assertEqual(key(0x113,210),0)
        self.assertEqual(key(0x10f,220),0);self.assertEqual(key(0x113,221),0)
        now[0]+=2000;self.assertEqual(key(0x10f,210),1)
        m.u.mem_write(backlight,b'\1');self.assertEqual(key(0x10f,210),0)
    def test_m1_navigation_holds_consume_only_their_own_release(self):
        m=self.m;seen=[];native_up=[]
        report=json.loads((BUILD/'abi-report.json').read_text())
        for name,value in [('g_backlight_status',1),('g_lockscreen_pageflag',0),('g_poweroff_state',0)]:
            s=report['data'][name];m.u.mem_write(s['address'],value.to_bytes(s['size'],'little'))
        for name in ('keylock_flag','boot_guidestep','rotate_mode'):m.word(m.native[name],0)
        callbacks={'window_manager':lambda *_:DATA+0x1000,'window_manager_get_top_window':lambda *_:DATA+0x2000,
                   'window_manager_is_animating':lambda *_:0,'navigator_back':lambda *_:seen.append('back') or 0,
                   'reset_poweroptions_timer':lambda *_:0}
        for name,fn in callbacks.items():m.callbacks[m.native[name]]=fn
        m.callbacks[m.native['time_now_ms']]=lambda *_:10000
        m.callbacks[m.syms['m1_import_fopen']]=lambda *_:0
        for name in ('ringnav_m1_wake','ringnav_m1_activity','video_on'):m.callbacks[m.syms[name]]=lambda *_:0
        m.callbacks[m.syms['ringnav_m1_supported']]=lambda *_:1
        m.callbacks[m.syms['compact_now_playing']]=lambda *_:seen.append('playing') or 0
        m.callbacks[m.syms['stock_widget_keyup_trampoline']]=lambda a,b,*_:native_up.append(m.word(b+24)) or 0
        def dispatch(a,b,c,d):
            context=m.u.context_save()
            m.call('m1_ui_keyup',DATA+0x2000,b)
            m.u.context_restore(context)
            return 77
        m.callbacks[m.syms['stock_input_trampoline']]=dispatch
        for key,name in [(214,'back'),(215,'playing')]:
            m.word(DATA,0x110);m.word(DATA+24,key)
            self.assertEqual(m.call('m1_ui_long',0,DATA),11)
            self.assertEqual(seen[-1],name)
            m.word(DATA,0x113)
            self.assertEqual(m.call('m1_ui_dispatch',DATA+0x1000,DATA),77)
            self.assertNotIn(key,native_up)
            self.assertEqual(m.call('m1_ui_dispatch',DATA+0x1000,DATA),77)
            self.assertIn(key,native_up)
    def test_awake_menu_wheel_ignores_screen_off_button_lock_preference(self):
        """Run the native dispatcher and pressed-key bookkeeping, not a fake release."""
        m=self.m;wm=DATA+0x1000;top=DATA+0x2000;vt=DATA+0x3000
        seen=[];native_up=[]
        report=json.loads((BUILD/'abi-report.json').read_text())
        for name,value in [('g_backlight_status',1),('g_lockscreen_pageflag',0),
                           ('g_poweroff_state',0),('g_guideflag',0),('bt__recv_pageflag',0),
                           ('g_usblink_status',0),('g_volume',35)]:
            s=report['data'][name];m.u.mem_write(s['address'],value.to_bytes(s['size'],'little'))
        # keylock_flag is the saved screen-OFF lock preference, not a live UI lock.
        m.u.mem_write(m.native['keylock_flag'],b'\1')
        m.word(m.native['boot_guidestep'],0);m.word(m.native['rotate_mode'],0)
        m.word(wm+0x88,vt);m.word(vt+0x38,0x68fef4)
        m.u.mem_write(DATA+0x4000,b'home_page\0')
        fns={'window_manager':lambda *_:wm,'window_manager_get_top_window':lambda *_:top,
             'window_manager_is_animating':lambda *_:0,'widget_get_window_manager':lambda *_:wm,
             'widget_get_prop_str':lambda *_:DATA+0x4000,'native_window_preprocess_event':lambda *_:0,
             'widget_on_keydown':lambda *_:0,'reset_poweroptions_timer':lambda *_:0,
             'time_now_ms':lambda *_:10000,'timer_add':lambda *_:1}
        for name,fn in fns.items():m.callbacks[m.native[name]]=fn
        m.callbacks[0x68fe1c]=lambda *_:0 # native cursor update (no framebuffer here)
        m.callbacks[m.syms['m1_import_fopen']]=lambda *_:0
        m.callbacks[m.syms['m1_import_strcmp']]=lambda a,b,*_:(m.string(a)>m.string(b))-(m.string(a)<m.string(b))
        def clear(a,b,c,d):m.u.mem_write(a,bytes([b&255])*c);return a
        m.callbacks[m.word(0xa03ed0-0xadc)]=clear
        for name in ('ringnav_m1_wake','ringnav_m1_activity','video_on'):m.callbacks[m.syms[name]]=lambda *_:0
        m.callbacks[m.syms['ringnav']]=lambda a,b,*_:seen.append(m.word(b+24)) or 11
        m.callbacks[m.syms['stock_widget_keyup_trampoline']]=lambda a,b,*_:native_up.append(m.word(b+24)) or 0
        for key,logical in [(220,172),(221,173),(210,210)]:
            m.word(DATA,0x10f);m.word(DATA+24,key)
            m.call(m.native['window_manager_dispatch_input_event'],wm,DATA)
            self.assertIn(key,[m.word(wm+0xf8+0x18+i*0x18) for i in range(16)])
            m.word(DATA,0x113);m.call(m.native['window_manager_dispatch_input_event'],wm,DATA)
            self.assertEqual(seen[-1:] ,[logical])
            self.assertNotIn(key,native_up)
            self.assertNotIn(key,[m.word(wm+0xf8+0x18+i*0x18) for i in range(16)])
        self.assertEqual(m.word(m.native['volume']),35)
        # The same physical wheel still reaches stock on Now Playing, dark,
        # on the actual lock screen, and with the menu-wheel toggle disabled.
        for name,dark,locked,enabled in [(b'playing_page',0,0,1),(b'home_page',1,0,1),
                                         (b'home_page',0,1,1),(b'home_page',0,0,0)]:
            seen.clear();native_up.clear();m.u.mem_write(DATA+0x4000,name+b'\0')
            m.u.mem_write(m.native['backlight_status'],bytes([1-dark]))
            m.word(m.native['lockscreen_pageflag'],locked);m.word(m.syms['enabled'],enabled)
            for typ in (0x10f,0x113):
                m.word(DATA,typ);m.word(DATA+24,221)
                m.call(m.native['window_manager_dispatch_input_event'],wm,DATA)
            self.assertEqual(seen,[]);self.assertEqual(native_up,[221])
    def test_home_settings_has_working_touch_back_and_button_hold(self):
        m=self.m;win=DATA;wm=DATA+0x1000;nodes={win:{'children':[], 'visible':1}};bindings={};next_node=DATA+0x2000
        def create(parent,x,y,w):
            nonlocal next_node
            a=next_node;next_node+=0x100;h=m.word(m.u.reg_read(r.UC_MIPS_REG_SP)+16)
            nodes[a]={'children':[],'visible':1,'name':b'', 'text':b''}
            nodes[parent]['children'].append(a)
            for off,v in [(0,x),(4,y),(8,w),(12,h),(0x44,parent)]:m.word(a+off,v)
            return a
        def lookup(parent,name,recursive,_):
            name=m.string(name)
            return next((a for a,n in nodes.items() if n.get('name')==name),0)
        def named(a,b,*_):nodes[a]['name']=m.string(b);return 0
        def text(a,b,*_):nodes[a]['text']=m.string(b);return 0
        def visible(a,b,*_):nodes[a]['visible']=b;return 0
        def bind(a,b,c,d):bindings[a,b]=(c,d);return 1
        def fmt(a,n,f,value):
            result=m.string(f).replace(b'%s',m.string(value));m.u.mem_write(a,result[:n-1]+b'\0');return len(result)
        for name in ('image_create','view_create','list_view_create','scroll_view_create','hscroll_label_create'):
            m.callbacks[m.native[name]]=create
        fns={'widget_lookup':lookup,'widget_count_children':lambda a,*_:len(nodes[a]['children']),
             'widget_get_child':lambda a,b,*_:nodes[a]['children'][b], 'widget_set_name':named,
             'widget_set_text_utf8':text,'widget_set_visible':visible,'widget_get_visible':lambda a,*_:nodes[a]['visible'],
             'widget_on':bind,'tk_snprintf':fmt,'window_manager':lambda *_:wm,
             'window_manager_get_top_window':lambda *_:win,'window_manager_is_animating':lambda *_:0}
        for name in ('widget_set_sensitive','widget_set_prop_int','widget_set_prop_str','widget_use_style',
                     'hscroll_label_set_ellipses','widget_move_resize','widget_animator_prop_create'):
            fns[name]=lambda *_:0
        for name,fn in fns.items():m.callbacks[m.native[name]]=fn
        m.callbacks[m.syms['stock_home_trampoline']]=lambda *_:0
        m.callbacks[m.syms['coverflow_home_layout']]=lambda *_:0
        m.callbacks[m.syms['m1_import_strcmp']]=lambda a,b,*_:(m.string(a)>m.string(b))-(m.string(a)<m.string(b))
        m.call('coverflow_home',win,0)
        def node(name):return next(a for a,n in nodes.items() if n.get('name')==name.encode())
        def click(name):
            callback,ctx=bindings[node(name),0x10c];m.call(callback,ctx,DATA+0x18000)
        home,settings=node('list_view_home'),node('list_view_homeset')
        self.assertEqual(nodes[node('label_homeback')]['text'],b'Back to Home')
        click('img_settings');self.assertEqual((nodes[home]['visible'],nodes[settings]['visible']),(0,1))
        click('img_homeback');self.assertEqual((nodes[home]['visible'],nodes[settings]['visible']),(1,0))
        # Hold Previous also exits this internal pane with wheel navigation OFF.
        click('img_settings');m.word(m.syms['enabled'],0)
        m.u.mem_write(m.native['backlight_status'],b'\1');m.u.mem_write(m.native['keylock_flag'],b'\1')
        m.callbacks[m.syms['ringnav_m1_supported']]=lambda *_:1
        m.word(DATA+0x18000,0x110);m.word(DATA+0x18018,214)
        self.assertEqual(m.call('m1_ui_long',0,DATA+0x18000),11)
        self.assertEqual((nodes[home]['visible'],nodes[settings]['visible']),(1,0))
    def test_album_grid_geometry_and_scroll_prefetch(self):
        m=self.m;view=DATA;rows=[DATA+0x1000+i*0x100 for i in range(10)]
        children={view:rows};names={};types={};rects={};props=[];calls=[]
        for i,row in enumerate(rows):
            children[row]=[DATA+0x4000+i*0x400+j*0x80 for j in range(4)]
            for c,name,kind in zip(children[row],['imgleftcover','listsscrlabel','listsscrartist','button'],['image','hscroll_label','hscroll_label','button']):
                names[c]=name;types[c]=kind;children[c]=[]
        cursor=DATA+0x10000
        def cstr(s):
            nonlocal cursor
            at=cursor;cursor+=len(s)+1;m.u.mem_write(at,s.encode()+b'\0');return at
        def move(a,b,c,d):
            rects[a]=(b,c,d,m.word(m.u.reg_read(r.UC_MIPS_REG_SP)+16));return 0
        def prop(a,b,c,d):props.append((a,m.string(b),c));return 0
        fns={'widget_count_children':lambda a,*_:len(children[a]),'widget_get_child':lambda a,b,*_:children[a][b],
             'widget_set_children_layout':lambda *_:0,'widget_set_self_layout':lambda *_:0,
             'widget_move_resize':move,'widget_get_prop_str':lambda a,*_:cstr(names.get(a,'')),
             'widget_get_type':lambda a,*_:cstr(types.get(a,'')),'widget_set_prop_int':prop,
             'widget_lookup':lambda *_:0}
        for name,fn in fns.items():m.callbacks[m.native[name]]=fn
        m.callbacks[m.syms['m1_import_strcmp']]=lambda a,b,*_:(m.string(a)>m.string(b))-(m.string(a)<m.string(b))
        m.callbacks[m.native['tk_str_start_with']]=lambda a,b,*_:int(m.string(a).startswith(m.string(b)))
        m.word(view+12,400) # widget height
        self.assertEqual(m.call('m1_album_grid',view),0)
        self.assertEqual(rects[rows[-1]],(2,444,102,148))
        for row in rows:
            for c in children[row]:
                x,y,w,h=rects[c];self.assertLessEqual(x+w,102);self.assertLessEqual(y+h,148)
        self.assertIn((view,b'virtual_h',592),props)
        m.callbacks[m.native['widget_lookup']]=lambda *_:view
        m.callbacks[m.native['widget_get_prop_int']]=lambda *_:296
        m.callbacks[m.native['toolsGetSysMemFree']]=lambda *_:30000
        m.callbacks[m.native['batchadd_albumcover_task']]=lambda a,b,*_:calls.append((a,b)) or 0
        m.word(0xa045d8,DATA+0x18000)
        m.call('m1_album_scroll',DATA+0x19000,0);self.assertEqual(calls,[(6,12)])

class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.m=Machine();m=self.m
        self.library=ELFFile(io.BytesIO((LIBS/'libc-2.28.so').read_bytes()))
        self.base=0x2000000;m.u.mem_map(self.base,0x400000)
        for s in self.library.iter_segments():
            if s['p_type']=='PT_LOAD':m.u.mem_write(self.base+s['p_vaddr'],s.data())
        self.exports={s.name:s['st_value'] for s in self.library.get_section_by_name('.dynsym').iter_symbols()}
        self.debug=int(re.search(r'0x([0-9a-f]+)',(BUILD/'m1_loader.h').read_text())[1],16)
        m.word(self.debug,DATA);m.word(DATA+4,DATA+0x100)
        m.word(DATA+0x100,self.base);m.word(DATA+0x108,self.base+self.library.get_section_by_name('.dynamic')['sh_addr'])
    def test_actual_glibc_hash_and_relative_dynamic_pointers(self):
        for name in ['lseek64','mmap64','getsockopt']:
            self.m.u.mem_write(DATA+0x200,name.encode()+b'\0')
            self.assertEqual(self.m.call('m1_resolve',DATA+0x200),self.base+self.exports[name])
    def test_missing_import_and_missing_loader_return_zero(self):
        m=self.m;m.u.mem_write(DATA+0x200,b'no_such_export\0')
        self.assertEqual(m.call('m1_resolve',DATA+0x200),0)
        m.word(self.debug,0);self.assertEqual(m.call('m1_resolve',DATA+0x200),0)
    def test_lazy_thunk_preserves_integer_float_stack_and_cache(self):
        m=self.m;seen=[]
        def callee(a,b,c,d):
            seen.append((a,b,c,d,m.u.reg_read(r.UC_MIPS_REG_F12),m.u.reg_read(r.UC_MIPS_REG_F14),m.word(STACK+16)))
            return 42
        m.callbacks[self.base+self.exports['getsockopt']]=callee
        m.u.reg_write(r.UC_MIPS_REG_F12,0x400921fb54442d18);m.u.reg_write(r.UC_MIPS_REG_F14,0x3ff0000000000000)
        m.word(STACK+16,0x12345678)
        for _ in range(2):
            self.assertEqual(m.call('m1_extra_getsockopt',3,4,5,6),42);m.word(self.debug,0)
        self.assertEqual(seen,[(3,4,5,6,0x400921fb54442d18,0x3ff0000000000000,0x12345678)]*2)

class PatchTests(unittest.TestCase):
    def test_rebuild_matches_and_tampering_rejected(self):
        raw=STOCK.read_bytes();report=json.loads((BUILD/'abi-report.json').read_text())
        b,m=builder.patch(raw,BUILD/'payload.elf',report)
        self.assertEqual(b,(BUILD/'demo.m1pod').read_bytes());self.assertGreaterEqual(len(m['changes']),72)
        damaged=bytearray(raw);damaged[100]^=1
        with self.assertRaisesRegex(ValueError,'Unpinned'):builder.patch(damaged,BUILD/'payload.elf',report)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','stock','libs'):p.add_argument('--'+n,type=Path,required=True)
    a,extra=p.parse_known_args();BUILD,STOCK,LIBS=a.build,a.stock,a.libs
    unittest.main(argv=[sys.argv[0],*extra])
