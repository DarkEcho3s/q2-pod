# M1 Pod for Shanling M1 Plus V2.1

The integrated non-streaming port is built as **V2.1-M1P-full1**, an experimental
flashable feature test. Hardware verification is pending. The application boots
directly from the firmware, with the original M1 kernel, drivers and startup
service. No alternate launcher or stock fallback is installed.

Source branch: [DarkEcho3s/q2-pod:m1plus-port](https://github.com/DarkEcho3s/q2-pod/tree/m1plus-port).
Installation, controls and the device test checklist are in
[m1plus-full-test.md](m1plus-full-test.md). Earlier prototype/bootstrap tools and
[m1plus-testing.md](m1plus-testing.md) are historical; use the full builder below.

## Included in this build

- Portrait Home with split/full layout, Library, Now Playing, Coverflow, four
  visualizers, Minimal/Classic themes, accent and battery-display settings.
- Native M1 library database and scanners, album grids, artist/album-artist
  browsing, genres, favourites, playlists, queue actions, ratings, Loved,
  Top Rated, Most Played and Long Songs. Artist/composer album pages gain a
  Songs button; Back returns to the album grid.
- Persistent wheel navigation toggle, click to confirm, native volume on Now
  Playing, plus Previous/Next holds for Back/Now Playing on M1's button layout.
- Simple three-band EQ, up to 30 PEQ bands, preset import, preamp, balance,
  crossfade, shuffle/repeat grouping, queue persistence and paused boot resume.
- Podcasts, audiobooks, M4B cover extraction, resume and per-folder speed;
  photo, text-book and video viewers using the M1 portrait framebuffer.
- Wallpapers, large lock-screen clock, custom boot logo, charge limit, low
  power, double-press wake, headset/AirPods controls, ear detection, absolute
  volume and resume on connect. Scrobbling remains available over Wi-Fi.
- Streaming menus and Rockbox integration are excluded. Native networking is
  retained for scrobbling and normal M1 settings.

The touchscreen and M1 navigation headers remain available. The 320x480 layout
adapts the Q2 theme to this portrait display; it does not use Q2's landscape
coordinates. Headphone, Bluetooth, USB, standby and media behavior must now be
checked on the physical player. The compilation and emulator checks do not
establish that every feature works on hardware.

## Implementation and evidence

`build_m1plus_ui.py` compiles the shared feature code and M1 adapters into a
SHA-pinned V2.1 executable. Its 86 patches check PIC prologues, GOT state, native
call sites and leaf functions. The builder rejects unresolved adapters and
changes outside its byte allowlist. Recovered ABI fields include widget
parents, canvas, layouts, event emitters, input state and native library IDs.
The loader uses MIPS DT_MIPS_RLD_MAP/DT_MIPS_RLD_MAP_REL for lazy libc/container
imports, with complete o32 integer, float and stack-argument preservation.

The payload retains native M1 SQL queries and queue containers. Artist groups,
album cover keys, unknown tags and local media queries are adapted separately
from Q2 addresses. The M1 audio payload is built with
`targets/m1plus/player-v2.1.json`; the shipped TagLib C library has its own pinned
M4B patch. BlueALSA is byte-identical between the two stock firmwares and takes
the audited AAC/drop fix. LDAC HQ's native application call is patched separately.

Offline validation for this feature build:

- 27 integrated MIPS UI/input/ABI tests, including wheel ownership, native
  emitter fields, album-grid bounds/prefetch, LDAC quality, double-press wake,
  navigation-hold release suppression, lazy imports and patch tamper rejection.
- 11 audio tests executing MIPS DSP: PCM rates, PEQ/preamp/balance,
  DSD/DoP passthrough, invalid-channel handling and MP3/ReplayGain paths.
- 5 media/asset tests, including relocated M4B dispatch, native dynamic imports,
  retained widget names, portrait assets and the scrobbling certificate bundle.
- All 11 shared UI modules compile for Q2 and M1. The actual EQ paint functions
  produce 301 checked rectangles at each size.
- Repacked filesystem inventories check regular-file bytes, ownership, modes,
  times, links, devices and hardlink groups. The package verifies payload MD5s,
  kernel CRCs, M1 identity, unchanged kernel and original-input SHA-256.

Two independent package runs produced SHA-256
`2b3bc40ab8f14e23a3a89148d627bbb3dab2c1ca316910d3908fb8cf45cdf60f`.
The update is 60,805,120 bytes; its rootfs is 55,386,112 bytes, compared with
55,738,368 in stock. All 4,016 filesystem paths and 208 hardlink groups passed
validation. `graphify update .` was attempted; the command is unavailable on
this host and no graphify graph is present.

The LZO rootfs is constrained to the original compressed image size. To fit,
the builder removes five dormant GLib 2.54.3 library copies after checking every
file and symlink for references. All active GLib 2.74.4 files and loader symlinks
remain. No other original path is removed. Detailed changes and validation are
included with the local build.

## Rebuild

Install `requirements-m1plus.txt` and squashfs-tools 4.7.x (`sqfstar`). All output
directories must be fresh children of ignored `work/`. Inputs are the owner's
unmodified M1 Plus V2.1 and Q2 Pod 1.1.9 packages. `port_inspect.py` extracts the
M1 demo and player for the component builders without reconstructing a rootfs.

```text
python tools/port_inspect.py --m1 <M1-update.bin> --q2 <Q2-stock-update.tar> --q2-pod <Q2Pod-update.tar> --out work/analysis
python tools/build_m1plus_ui.py --stock-demo work/analysis/m1/analysis-files/release/bin/demo --out work/ui --zig <zig>
python tools/build_m1plus_player.py --stock-player work/analysis/m1/analysis-files/usr/bin/hciplayer --out work/player --zig <zig>
python tools/build_m1plus_helper.py --original <M1-update.bin> --out work/video --zig <zig>
python tools/build_m1plus_assets.py --original <M1-update.bin> --pod-update <Q2Pod-update.tar> --out work/assets
python test/m1plus_ui.py --build work/ui --stock work/analysis/m1/analysis-files/release/bin/demo --libs work/video
python test/m1plus_player.py --build work/player --stock-player work/analysis/m1/analysis-files/usr/bin/hciplayer
python test/m1plus_media.py --original <M1-update.bin> --helper work/video --assets work/assets
python test/m1plus_layout.py --out work/layout --zig <zig>
python tools/build_m1plus_full.py --original <M1-update.bin> --out work/full --ui work/ui --player work/player --helper work/video --assets work/assets --sqfstar <sqfstar>
```

The Python runtime, compiler, dependency cache and MSYS squashfs-tools used on
this Windows host reside under `F:/DAP` (Python itself is the Codex bundled
runtime). Executing the compiler and MSYS packer required sandbox escalation;
all derived firmware and build outputs remain local and ignored by Git.

## Pinned sources and attribution

| Input | SHA-256 |
| --- | --- |
| M1 Plus V2.1 update | `1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925` |
| M1 Plus demo | `29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1` |
| Q2 Pod 1.1.9 update | `330f09c51b6d6cbe5ca6911de7ad68a81e795db468b573718b994a0de9854bd9` |

The upstream source baseline is `bb724dd80bc2d675e8d582e08c160ed2096ec131`.
The native M1 reference project informed the initial ABI research; its MIT
notice is in [targets/m1plus/NOTICE](../targets/m1plus/NOTICE). Vendor firmware
is not committed to the fork. `port_disasm.py`, `port_refs.py` and
`port_correspond.py` support review; address similarity alone is never used as
permission to patch a site.
