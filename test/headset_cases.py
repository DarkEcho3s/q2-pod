# Executed by patch.py after its shared emulator fixtures.
# Audio recognition executes each actual patched stock call site, including its delay slot.
from build import AUDIO_EXTENSION_CALLS
for site in AUDIO_EXTENSION_CALLS:
    for ext, accepted in (('.m4b',1),('.M4B',1),('.m4B',1),('.M4b',1),('.m4a',1),('.M4A',1),('.flac',1),('.mp3',1),('.m4b.tmp',0),('.pdf',0)):
        m=Machine(); m.mock('strstr@GLIBC_2.0')
        formats=m.string('.mp3 .flac .m4a .M4A'); suffix=m.string(ext)
        m.word(0x7000f000+(0xdd4 if site==0x5c2054 else 0xd64),formats)
        def extension_return(u,address,size,unused):
            u.reg_write(UC_MIPS_REG_PC,0x1000000)
        m.u.hook_add(UC_HOOK_CODE,extension_return,begin=site+8,end=site+8)
        assert bool(m.call(address=site,args=(formats,suffix,0,0),gap=0))==bool(accepted)
        passed()

# M4B is spoken audio anywhere, at short duration; persistence and CUE rules stay shared.
for path in ('/mnt/mmc/Novel.m4b','/mnt/mmc/Music/Novel.M4B','/mnt/mmc/Novel.m4B'):
    m=ResumeMachine(); r=m.items(m.get(syms['mcl_pdeqplaylist']))[0]
    m.word(r+O['REC_PATH'],m.string(path)); playing(m,0,200,pos=0,n=110)
    assert m.places()==[(fnv(path),61)] and '/mnt/data/ringnav-plays' not in m.files and '/mnt/mmc/.scrobbler.log' not in m.files
    m.poll(110,200,n=3)
    files=m.files
    m=ResumeMachine(files); r=m.items(m.get(syms['mcl_pdeqplaylist']))[0]; m.word(r+O['REC_PATH'],m.string(path))
    m.poll(0,200,pos=0,n=2); playing(m,1,200,n=2); assert m.seeks==[110]
    m.poll(195,200,n=3); assert not m.places()
    passed()
m=ResumeMachine(); r=m.items(m.get(syms['mcl_pdeqplaylist']))[0]
m.word(r+O['REC_PATH'],m.string('/mnt/mmc/cue.m4b')); m.word(r+O['REC_CUE_START'],200)
playing(m,0,200,pos=0,n=110); assert not m.places(); passed()

# Mock only player endpoints, exercising the actual routing and ear/AVRCP state machine.
class HeadsetMachine(Machine):
    def __init__(self,owner=1):
        super().__init__(); self.owner=owner; self.playing=True; self.session=42; self.actions=[]
        for name in ('spot_status','radio_status','video_status','spot_session','radio_session','video_session',
                     'spot_set_playing','radio_set_playing','video_set_playing','spot_media','radio_media','video_key'):
            self.handlers[payload_syms[name]]='hs:'+name
        self.handlers[syms['mclGetPlayStatus']]='hs:local_status'
        self.handlers[syms['player_play_pause']]='hs:local_toggle'
        self.handlers[syms['player_next_music']]='hs:local_next'
        self.handlers[syms['player_prev_music']]='hs:local_prev'
    def hook(self,u,address,size,unused):
        name=self.handlers.get(address,'')
        if not name.startswith('hs:'): return super().hook(u,address,size,unused)
        name=name[3:]; a=u.reg_read(REGS[0]); ret=0
        owner=4 if name.startswith('video') else 3 if name.startswith('radio') else 2 if name.startswith('spot') else 1
        if name.endswith('_status'): ret=(2 if self.playing else 3) if self.owner==owner else 0
        elif name.endswith('_session'): ret=self.session
        elif name.endswith('_set_playing'): self.playing=bool(a); self.actions.append((owner,'play' if a else 'pause'))
        elif name=='local_toggle': self.playing=not self.playing; self.actions.append((1,'play' if self.playing else 'pause'))
        else: self.actions.append((owner,a if owner!=1 else name))
        u.reg_write(UC_MIPS_REG_V0,ret); u.reg_write(UC_MIPS_REG_PC,u.reg_read(UC_MIPS_REG_RA))
    def fn(self,name,value=0,gap=0): return self.call(address=payload_syms[name],args=(value,0,0,0),gap=gap)
    def ears(self,mask,gap=100): return self.fn('headset_ears',4|mask,gap)
    def command(self,code,gap=200): return self.fn('headset_command',code,gap)
for owner in (1,2,3,4):
    m=HeadsetMachine(owner); m.byte(syms['g_backlight_status'],0)
    m.ears(3); assert m.playing and not m.actions
    m.ears(2); assert not m.playing and m.actions==[(owner,'pause')]
    m.command(201); m.command(164); assert not m.playing and len(m.actions)==1
    m.ears(0); m.ears(1); assert not m.playing  # other bud alone does not resume
    m.ears(3); assert m.playing and m.actions[-1]==(owner,'play')
    m.ears(2); m.fn('headset_manual'); m.ears(3); assert not m.playing
    m=HeadsetMachine(owner); m.ears(3); m.command(201); m.ears(2); m.ears(3); assert m.playing
    m=HeadsetMachine(owner); m.ears(0); m.ears(3); assert not m.playing  # initial report establishes state
    m=HeadsetMachine(owner); m.ears(3); m.ears(2); m.owner=1 if owner!=1 else 2; m.ears(3); assert not m.playing
    m=HeadsetMachine(owner); m.ears(3); m.ears(2)
    if owner!=1: m.session+=1
    else: m.word(O['MCL_POS'],1)
    m.ears(3); assert not m.playing
    m=HeadsetMachine(owner); m.command(163); m.command(163,gap=1); assert len(m.actions)==1
    m.command(165); assert len(m.actions)==2 and all(a[0]==owner for a in m.actions)
    passed()
m=HeadsetMachine(); good=bytes([4,0,4,0,6,0,0,2])
for packet in (b'',good[:7],good+b'\0',bytes([4,0,4,0,6,0,3,0]),bytes([4,1,4,0,6,0,0,0])):
    p=m.alloc(max(1,len(packet))); m.u.mem_write(p,packet)
    assert m.call(address=payload_syms['ringnav_aap_parse'],args=(p,len(packet),0,0),gap=0)==0
p=m.alloc(8); m.u.mem_write(p,good); assert m.call(address=payload_syms['ringnav_aap_parse'],args=(p,8,0,0),gap=0)==2; passed()

for absolute,limit,want in ((127,40,40),(0,100,0),(64,100,50),(1,100,1),(126,100,99)):
    b=BtVolumeMachine(); b.poll(); b.byte(syms['g_maxvolume'],limit)
    b.absolute=absolute; b.poll()
    assert b.u.mem_read(syms['g_volume'],1)[0]==want
    assert b.absolute==(want*127+50)//100
    b.poll(); assert not b.writes()
    passed()
print('M4B recognition/resume and headset routing, ear masks, manual cancellation, malformed packets and volume limits passed.')

# Real helper APIs: explicit pause/resume is observable and repeatable, with shared gain changes.
def endpoint(m,name,value=0):
    return m.call(address=payload_syms[name],args=(value,0,0,0),gap=0,clear=False)
def ready_gain(m,ready,volume):
    m.way=1
    for name in ('g_bluetoothflag','bt_linkstatus'): m.byte(syms[name],1)
    m.word(syms['bt_showcoding'],1); m.byte(syms['g_volume'],volume)
    m.word(payload_syms['btvol']+4 if 'btvol' in payload_syms else payload_syms['btvol.1'],ready)  # clang may split scalar fields
m=SpotMachine({BIN:bytearray()}); spot_open(m,stream_page(m)); m.state('playing'); m.poll()
for playing,command in ((0,'s'),(1,'p')):
    m.sent=[]; endpoint(m,'spot_set_playing',playing); endpoint(m,'spot_set_playing',playing)
    assert [x[1] for x in m.sent]==[command] and endpoint(m,'spot_status')==(2 if playing else 3)
ready_gain(m,1,32); m.now+=500; m.sent=[]; endpoint(m,'spot_poll'); assert m.sent[-1][1]=='v'+chr(100)
ready_gain(m,1,0); m.now+=500; endpoint(m,'spot_poll'); assert m.sent[-1][1]=='v\0'
ready_gain(m,0,32); m.now+=500; endpoint(m,'spot_poll'); assert m.sent[-1][1]=='v'+chr(32)
passed()
m=RadioMachine(); radio_open(m); m.row(1); m.row(0)
assert endpoint(m,'radio_status')==2
m.waited=m.forked
endpoint(m,'media_set_playing',0); endpoint(m,'media_set_playing',0); assert endpoint(m,'radio_status')==3
m.waited=0
endpoint(m,'media_set_playing',1); assert endpoint(m,'radio_status')==2
ready_gain(m,1,32); m.sent=[]; m.now+=500; endpoint(m,'radio_poll'); assert m.sent[-1][1]=='v'+chr(100)
ready_gain(m,0,32); m.sent=[]; m.now+=500; endpoint(m,'radio_poll'); assert m.sent[-1][1]=='v'+chr(32)
passed()
m=BooksMachine({},{}); vid=payload_syms['vid']; m.word(vid+12,4242); m.word(vid+16,7)
for playing,command in ((0,'a'),(1,'r')):
    m.sent=[]; endpoint(m,'video_set_playing',playing); endpoint(m,'video_set_playing',playing)
    assert [x[1] for x in m.sent]==[command,command] and endpoint(m,'video_status')==(2 if playing else 3)
ready_gain(m,1,32); m.now+=1500; m.sent=[]; endpoint(m,'video_poll')
assert [x[1] for x in m.sent]==['v'+chr(32),'g'+chr(100)]
ready_gain(m,0,32); m.now+=500; m.sent=[]; endpoint(m,'video_poll'); assert m.sent[-1][1]=='g'+chr(32)
m.files['/tmp/q2video.state']=bytearray(struct.pack('<i',1)); m.now+=500; endpoint(m,'video_poll'); assert endpoint(m,'video_status')==3
passed()
# Manual video pause must take effect before the helper's next state report.
m=BooksMachine({},{}); m.word(payload_syms['vid']+12,4242); m.word(payload_syms['vid']+16,7)
endpoint(m,'headset_ears',7); endpoint(m,'video_key',O['KEY_PLAY'])
assert endpoint(m,'video_status')==3
endpoint(m,'headset_ears',6); endpoint(m,'headset_ears',7)
assert endpoint(m,'video_status')==3
m.files['/tmp/q2video.state']=bytearray(struct.pack('<i',0)); m.now+=400; endpoint(m,'video_poll')
assert endpoint(m,'video_status')==3  # stale helper state cannot undo the manual pause
endpoint(m,'video_key',O['KEY_PLAY']); assert endpoint(m,'video_status')==2
passed()
# Stock Tidal shares the native queue controls and session cancellation.
m=HeadsetMachine(); m.word(O['MCL_TYPE'],2); m.ears(3); m.ears(1); assert not m.playing
m.ears(3); assert m.playing; m.command(163); assert m.actions[-1]==(1,'local_next'); passed()
print('Real Spotify/radio/video play-state APIs, helper gain updates and stock Tidal routing passed.')
