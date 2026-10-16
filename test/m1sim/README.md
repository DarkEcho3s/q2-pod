# m1sim

The Shanling M1 Plus's own `demo` (stock or patched), run under `qemu-mipsel` (user mode) with its
real UI, assets, database and payload. It is how the M1 port is checked without the device: boot,
turn the wheel, press the buttons, tap the screen, and read the framebuffer back as PNGs.

It is not a device emulator. There is no audio, DAC, hciplayer, Bluetooth, Wi-Fi or USB; their
calls fail as on a device without them. Timing is slower than the device's.

## Pieces

- `shim.c`, LD_PRELOADed into demo (`m1sim.so`): `/dev/fb0` becomes a file, `/tmp/m1sim/fb`, with
  the page AWTK pans to in `/tmp/m1sim/pan`; the input devices are FIFOs; tslib is replaced by a
  FIFO of (x, y, pressure) samples; `system()` and `popen()` are logged to `/tmp/m1sim/system.log`
  and not run (they would run on the host); the factory serial record is supplied; libbtctl's
  server, which waits for bluetoothd, is skipped.
- `sim.py`: prepares a rootfs (FIFOs, the shim, battery sysfs files), links `/mnt/data` and
  `/mnt/mmc` on the host to directories under `/tmp/m1sim`, starts demo, and drives it:
  `wheel(n)`, `click()`, `press('play'|'prev'|'next'|'center')`, `tap(x, y)`, `swipe(...)`,
  `shot(path)`, `wait_idle()`. `trace()` runs demo under qemu's GDB stub with one-shot breakpoints.
- `gdb.py`: a minimal GDB remote-protocol client (threads, registers, memory, breakpoints).

## Use

Needs `qemu-mipsel` (8.2, linux-user, built with `--target-list=mipsel-linux-user`), clang/lld
and Pillow. Unpack a build's rootfs (`unsquashfs -d ROOT rootfs.squashfs`), then:

```python
import sim
s = sim.Sim(ROOT).start()
s.wait_idle(timeout=180)
s.tap(160, 157)   # first boot: English
s.wheel(2); s.click(); s.shot('page.png')
s.stop()
```

The first boot asks for the language and shows a guide; keep `/tmp/m1sim/data` afterwards (copy it)
and pass it as `data=` to start at Home.
