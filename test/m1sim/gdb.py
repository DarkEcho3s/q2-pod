"""A minimal GDB remote-protocol client for qemu-mipsel's stub (Sim.start(gdb=port)): threads,
registers, memory, breakpoints. Enough to see where demo's threads are and why."""
import socket, struct

REGS = 'zero at v0 v1 a0 a1 a2 a3 t0 t1 t2 t3 t4 t5 t6 t7 s0 s1 s2 s3 s4 s5 s6 s7 t8 t9 k0 k1 gp sp fp ra'.split()


class Gdb:
    def __init__(self, port, host='127.0.0.1'):
        self.s = socket.create_connection((host, port), timeout=30)
        self.buf = b''
        self.ack = True

    def _read(self):
        while True:
            if b'#' in self.buf:
                start = self.buf.find(b'$')
                end = self.buf.find(b'#', start)
                if start >= 0 and end >= 0 and len(self.buf) >= end + 3:
                    pkt = self.buf[start + 1:end]
                    self.buf = self.buf[end + 3:]
                    if self.ack: self.s.sendall(b'+')
                    return pkt
            data = self.s.recv(65536)
            if not data: raise EOFError
            self.buf += data

    def cmd(self, c):
        if isinstance(c, str): c = c.encode()
        self.s.sendall(b'$' + c + b'#%02x' % (sum(c) & 255))
        return self._read()

    def stop(self):
        self.s.sendall(b'\x03')
        return self._read()

    def threads(self):
        out, r = [], self.cmd('qfThreadInfo')
        while r.startswith(b'm'):
            out += [int(t.split(b'.')[-1], 16) for t in r[1:].split(b',')]
            r = self.cmd('qsThreadInfo')
        return out

    def regs(self, tid=None):
        if tid is not None: self.cmd(f'Hg{tid:x}')
        raw = bytes.fromhex(self.cmd('g').decode())
        w = struct.unpack(f'<{len(raw) // 4}I', raw[:len(raw) // 4 * 4])
        r = dict(zip(REGS, w[:32]))
        r['pc'] = w[37]  # sr, lo, hi, bad, cause, pc
        return r

    def mem(self, addr, n):
        r = self.cmd(f'm{addr:x},{n:x}')
        return bytes.fromhex(r.decode()) if not r.startswith(b'E') else None

    def word(self, addr):
        b = self.mem(addr, 4)
        return struct.unpack('<I', b)[0] if b else None

    def cont(self):
        self.s.sendall(b'$c#63')

    def brk(self, addr, on=True):
        return self.cmd(f'{"Z" if on else "z"}0,{addr:x},4')

    def wait(self): return self._read()


# The M1 V2.1 demo's AWTK: widget_t name @0x10, flags @0x24 (visible bit 2), parent @0x44, children
# darray @0x58 (size @0, elements @8), vt @0x70 (type string @4); the window manager at 0xa0bf10.
M1_AWTK = dict(name=0x10, flags=0x24, children=0x58, vt=0x70, wm=0xa0bf10)


def cstr(g, a, n=64):
    if not a: return ''
    b = g.mem(a, n) or b''
    return b.split(b'\0')[0].decode('utf-8', 'replace')


def widget(g, w, o=M1_AWTK):
    raw = g.mem(w, 0x74)
    if not raw: return None
    x, y, ww, hh = struct.unpack_from('<4i', raw, 0)
    name = cstr(g, struct.unpack_from('<I', raw, o['name'])[0])
    vt = struct.unpack_from('<I', raw, o['vt'])[0]
    kind = cstr(g, g.word(vt + 4)) if vt else '?'
    visible = bool(struct.unpack_from('<I', raw, o['flags'])[0] & 4)
    kids = []
    arr = struct.unpack_from('<I', raw, o['children'])[0]
    if arr:
        n, elms = g.word(arr), g.word(arr + 8)
        if n and n < 512 and elms:
            kids = list(struct.unpack(f'<{n}I', g.mem(elms, 4 * n) or b''))
    return dict(addr=w, kind=kind, name=name, x=x, y=y, w=ww, h=hh, visible=visible, children=kids)


def tree(g, w=None, depth=0, maxdepth=12, o=M1_AWTK, out=None):
    """Lines describing w's subtree (the window manager's by default)."""
    out = [] if out is None else out
    if w is None: w = g.word(o['wm'])
    d = widget(g, w, o)
    if not d: return out
    out.append('  ' * depth + f"{d['kind']} {d['name']} [{d['x']},{d['y']},{d['w']},{d['h']}]" +
               ('' if d['visible'] else ' (hidden)') + f" @{w:#x}")
    if depth < maxdepth:
        for c in d['children']: tree(g, c, depth + 1, maxdepth, o, out)
    return out
