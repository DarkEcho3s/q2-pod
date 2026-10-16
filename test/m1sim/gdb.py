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
