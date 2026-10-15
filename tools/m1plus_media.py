"""Pinned M1 media-library patches, independent of the Q2 addresses."""
import struct
import build as q2
from build_m1plus import checked,sha
from ipod import branch

TAG_SHA='2541a577c124d62221c15d68a92ca72d7395b43ead3ed9968aa78c0f28e21dce'
BLUEALSA_SHA='0a4ffb7cc8207a46a3568440c5f31022b7125befd164e2f1af52537340a9892a'

def tag_cover(raw):
    checked(sha(raw)==TAG_SHA,'Unpinned M1 TagLib C library')
    base,site,mp4,next_format,gp=0x30000,0x1255c,0x12688,0x12564,0x32770
    checked(struct.unpack_from('<I',raw,q2.fileoff(raw,site))[0]==0x1040004a,'M4A branch changed')
    words=[branch(0x10400000,base,mp4),0,
           0x8f998170,0x02002025,0x27850000|((base+44-gp)&65535),0x0320f809,0,
           branch(0x10400000,base+28,mp4),0x8fbc0010,
           branch(0x10000000,base+36,next_format),0]
    payload=struct.pack('<11I',*words)+b'm4b\0'
    image=bytearray(raw);q2.append_payload(image,payload,base,len(payload),'M1 TagLib')
    struct.pack_into('<I',image,q2.segments(image)[-1][0]+24,5)
    struct.pack_into('<I',image,q2.fileoff(raw,site),branch(0x10000000,site,base))
    return bytes(image)

def bluealsa(raw):
    checked(sha(raw)==BLUEALSA_SHA,'M1 and audited Q2 BlueALSA must be byte-identical')
    return q2.patch_bluealsa(raw)
