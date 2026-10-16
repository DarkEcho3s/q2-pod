#!/usr/bin/env python3
"""m1sim: the M1 Plus's demo under qemu-mipsel, with a file framebuffer and FIFO input
(test/m1sim/README.md). Not a device emulator: no audio, DAC, Bluetooth or hciplayer; the UI, its
pages and the payload's input and paint paths run as the device runs them.

    sim = Sim(rootfs_dir)          # an unpacked M1 rootfs (unsquashfs -d), patched or stock
    sim.start(); sim.wait_idle()
    sim.wheel(+1); sim.click(); sim.press('prev'); sim.shot('home.png')
"""
import os, pathlib, shutil, signal, struct, subprocess, time

HERE = pathlib.Path(__file__).resolve().parent
W, H = 320, 480
RUN = pathlib.Path('/tmp/m1sim')
# The M1's input devices as demo's main_loop_init reads them: the buttons (md-gpio-keys) on event1,
# whose keymap makes KEY_POWER the wheel's press (210); the encoder (md-rotary-knob) on event2, whose
# keymap turns KEY_VOLUMEUP/DOWN into the wheel's 220/221; the touch panel through tslib on event3.
KEYS_DEV, WHEEL_DEV, TOUCH_DEV = 'event1', 'event2', 'event3'
KEYS = {'center': 116, 'play': 164, 'next': 163, 'prev': 165}
WHEEL = {+1: 114, -1: 115}  # KEY_VOLUMEDOWN rolls the selection down, KEY_VOLUMEUP up


def build_shim(root, out):
    flags = ['--target=mipsel-linux-gnu', '-march=mips32r2', '-mabi=32', '-mfp64', '-mnan=2008', '-mabs=2008',
             '-fPIC', '-O2', '-ffreestanding', '-fno-builtin', '-fno-stack-protector']
    subprocess.run(['clang', *flags, '-c', HERE/'shim.c', '-o', out.with_suffix('.o')], check=True)
    subprocess.run(['ld.lld', '-m', 'elf32ltsmip', '-shared', '--hash-style=sysv', '-soname', 'm1sim.so',
                    out.with_suffix('.o'), root/'lib/libc.so.6', root/'lib/libdl.so.2', '-o', out], check=True)


class Sim:
    def __init__(self, root, data=None, card=None, qemu='qemu-mipsel'):
        """root: the rootfs the demo runs from (it is changed: FIFOs, the shim, sysfs files). data and
        card: directories for /mnt/data and /mnt/mmc, fresh ones under RUN by default."""
        self.root = pathlib.Path(root)
        self.data = pathlib.Path(data or RUN/'data')
        self.card = pathlib.Path(card or RUN/'mmc')
        self.qemu, self.proc, self.log = qemu, None, None

    def prepare(self):
        RUN.mkdir(exist_ok=True)
        for d in (self.data, self.card): d.mkdir(parents=True, exist_ok=True)
        # What demo's first boot copies there with cp (system(), which the shim only logs).
        for name in ('config.ini', 'wpa_supplicant.conf', 'userequalizer'):
            if not (self.data/name).exists():
                shutil.copy(self.root/'release/assets/default/raw'/name, self.data/name)
        build_shim(self.root, self.root/'m1sim.so')
        inputs = self.root/'dev/input'
        inputs.mkdir(parents=True, exist_ok=True)
        for n in range(5):
            p = inputs/f'event{n}'
            if p.exists() or p.is_symlink(): p.unlink()
            os.mkfifo(p)
        (self.root/'dev/fb0').touch()
        # The battery: full and not charging, as the cw2015 fuel gauge and the charger report it.
        for path, value in (('sys/class/power_supply/battery/status', 'Discharging'),
                            ('sys/class/power_supply/battery/voltage_now', '4100000'),
                            ('sys/bus/i2c/drivers/cw2015/3-0062/cw2015_battery', '88')):
            f = self.root/path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(value + '\n')
        # qemu maps a guest path into root only when the file already exists there; /mnt/data and
        # /mnt/mmc gain files at run time, so the host's own /mnt/data and /mnt/mmc point there.
        for name, target in (('data', self.data), ('mmc', self.card)):
            link = pathlib.Path('/mnt')/name
            if link.is_symlink() or link.exists():
                if not link.is_symlink(): raise SystemExit(f'{link} exists and is not m1sim\'s link')
                link.unlink()
            link.symlink_to(target)
            inner = self.root/'mnt'/name
            if inner.exists() and not any(inner.iterdir()): inner.rmdir()

    def start(self, args=(), gdb=None):
        self.prepare()
        (RUN/'fb').unlink(missing_ok=True)
        self.log = open(RUN/'demo.log', 'wb')
        # No system bus: the Bluetooth server's D-Bus calls fail instead of aborting demo.
        env = ['-E', 'LD_PRELOAD=/m1sim.so', '-E', 'DBUS_FATAL_WARNINGS=0', '-E', 'TSLIB_TSDEVICE=/dev/input/event2',
               '-E', 'TSLIB_CONFFILE=/etc/ts.conf', '-E', 'TSLIB_PLUGINDIR=/usr/lib/ts']
        dbg = ['-g', str(gdb)] if gdb else []
        self.proc = subprocess.Popen([self.qemu, '-cpu', 'P5600', *dbg, '-L', str(self.root), *env,
                                      str(self.root/'release/bin/demo'), *args],
                                     stdout=self.log, stderr=subprocess.STDOUT, cwd=self.root/'release/bin',
                                     start_new_session=True)
        if gdb:  # qemu waits for the debugger before the first instruction
            import gdb as gdbmod
            for _ in range(50):
                try: self.gdb = gdbmod.Gdb(gdb); break
                except OSError: time.sleep(0.1)
            self.gdb.cont()
        # Keep each FIFO open from this side too, so a write never blocks and demo never sees EOF.
        self.fifos = {}
        for n in range(1, 5):
            self.fifos[f'event{n}'] = os.open(self.root/f'dev/input/event{n}', os.O_RDWR | os.O_NONBLOCK)
        return self

    def alive(self): return self.proc and self.proc.poll() is None

    def stop(self):
        if self.alive():
            os.killpg(self.proc.pid, signal.SIGKILL)
            self.proc.wait()
        for fd in getattr(self, 'fifos', {}).values(): os.close(fd)
        self.fifos = {}

    def event(self, dev, type_, code, value):
        t = time.time()
        os.write(self.fifos[dev], struct.pack('<iiHHi', int(t), int(t % 1 * 1e6), type_, code, value))

    def key(self, dev, code, hold=0.06):
        self.event(dev, 1, code, 1); self.event(dev, 0, 0, 0)
        time.sleep(hold)
        self.event(dev, 1, code, 0); self.event(dev, 0, 0, 0)

    def press(self, name, hold=0.06, after=0.25):
        self.key(KEYS_DEV, KEYS[name], hold)
        time.sleep(after)

    def click(self, after=0.6): self.press('center', after=after)

    def wheel(self, steps, gap=0.08, after=0.25):
        for _ in range(abs(steps)):
            self.key(WHEEL_DEV, WHEEL[1 if steps > 0 else -1], 0.01)
            time.sleep(gap)
        time.sleep(after)

    def touch(self, x, y, pressure=1):
        os.write(self.fifos[TOUCH_DEV], struct.pack('<iii', x, y, pressure))

    def tap(self, x, y, after=0.6):
        self.touch(x, y, 1); time.sleep(0.08); self.touch(x, y, 0)
        time.sleep(after)

    def swipe(self, x0, y0, x1, y1, steps=8, after=0.6):
        for i in range(steps + 1):
            self.touch(x0 + (x1 - x0) * i // steps, y0 + (y1 - y0) * i // steps, 1)
            time.sleep(0.02)
        self.touch(x1, y1, 0)
        time.sleep(after)

    def frame(self):
        """The page on screen, as (W*H*4) BGRA bytes."""
        raw = (RUN/'fb').read_bytes()
        try: y = int((RUN/'pan').read_text().split()[0])
        except (OSError, ValueError, IndexError): y = 0
        y = 0 if y not in (0, H) else y
        return raw[y*W*4:(y+H)*W*4]

    def shot(self, path):
        from PIL import Image
        img = Image.frombuffer('RGBA', (W, H), self.frame(), 'raw', 'BGRA', 0, 1).convert('RGB')
        img.save(path)
        return img

    def wait_idle(self, timeout=60, still=1.5):
        """Until the screen has stopped changing for still seconds (or timeout)."""
        end, last, since = time.time() + timeout, None, time.time()
        while time.time() < end:
            if not self.alive(): raise RuntimeError('demo exited:\n' + (RUN/'demo.log').read_text(errors='replace')[-3000:])
            try: f = self.frame()
            except OSError: f = None
            if f != last: last, since = f, time.time()
            elif f and time.time() - since >= still: return True
            time.sleep(0.2)
        return False


def trace(root, names, seconds=90, port=1240, syms=None):
    """Run demo under the debugger with a one-shot breakpoint on each address in names ({name:
    address}); returns the names hit, in order, and the debugger stopped at the last (or None)."""
    import gdb as gdbmod
    s = Sim(root)
    s.prepare()
    env = ['-E', 'LD_PRELOAD=/m1sim.so', '-E', 'DBUS_FATAL_WARNINGS=0']
    s.log = open(RUN/'demo.log', 'wb')
    s.proc = subprocess.Popen(['qemu-mipsel', '-cpu', 'P5600', '-g', str(port), '-L', str(s.root), *env,
                               str(s.root/'release/bin/demo')], stdout=s.log, stderr=subprocess.STDOUT,
                              cwd=s.root/'release/bin', start_new_session=True)
    for _ in range(50):
        try: g = gdbmod.Gdb(port); break
        except OSError: time.sleep(0.1)
    g.cmd('?')
    s.fifos = {f'event{n}': os.open(s.root/f'dev/input/event{n}', os.O_RDWR | os.O_NONBLOCK) for n in range(1, 5)}
    left = {a: n for n, a in names.items()}
    for a in left: g.brk(a)
    hit, end = [], time.time() + seconds
    while left and time.time() < end:
        g.cont()
        g.s.settimeout(max(1, end - time.time()))
        try: r = g.wait()
        except OSError: break
        pc = g.regs()['pc']
        if pc in left:
            hit.append(left.pop(pc))
            g.brk(pc, False)
    return hit, s, g
