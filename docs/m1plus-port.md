# Shanling M1 Plus port assessment

Status: feasibility investigation completed on 2026-10-15. A port is technically
plausible, including context-sensitive volume-wheel navigation. There is no
working M1 Plus Q2-pod build yet. Nothing here should be flashed to a player.

The user has an M1 Plus available for staged hardware testing. The desired scope
is Q2-pod's interface, theme and non-streaming features, without Rockbox or
network streaming sources. Host inspection cannot establish bootability or full
feature parity.

## Local source and inputs

Source: [DiamondBond/q2-pod](https://github.com/DiamondBond/q2-pod), revision
`bb724dd80bc2d675e8d582e08c160ed2096ec131`, on local branch `m1plus-port`.
The supplied Q2-pod release is 1.1.9, firmware tag `V119I`. Its update and demo
hashes match its accompanying manifest. The checkout may include changes after
that release; the release label alone must not be used to assert source identity.

| Input | SHA-256 |
| --- | --- |
| M1 Plus V2.1 update.bin | `1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925` |
| Q2 V1.32 update.tar | `0a910790ef7902b0fe7de7d0f9f26cdac3f2c0909368c6c90778a67ee3b5dab1` |
| Q2-pod 1.1.9 update.tar | `330f09c51b6d6cbe5ca6911de7ad68a81e795db468b573718b994a0de9854bd9` |
| M1 Plus stock release/bin/demo | `29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1` |
| Q2 stock release/bin/demo | `2c5f06142850b4fc168f82b44a81550cce0a5b4b9fe1c179dced4a08a3049138` |

The ONIX XM2 files were not needed for this comparison and were left alone.
Original firmware files were read only. Extracted analysis copies and generated
inventories are under ignored `work/m1plus-analysis/`; they are not rebuildable
root filesystem trees.

## Verified similarities and differences

| Item | Evidence | Consequence |
| --- | --- | --- |
| Update container | All three files are tar archives containing firmware_v20.info, xImage and rootfs.squashfs. Payload MD5 entries and kernel header/data CRCs pass. | Existing packaging research is relevant; changing the filename is not a port. These checks establish consistency, not updater acceptance. |
| Operating system | Both stock uImage headers identify Linux-5.10.21+. Kernels have different hashes. | Retain the M1 Plus kernel and hardware support. |
| Main executable | Both are ELF32 little-endian MIPS, O32 flags 0x70001405, MIPS32r2, FP ABI 6. | The payload toolchain approach is compatible in principle. Addresses and data layouts still need an M1 audit. |
| Interface toolkit | Both contain AWTK UI binaries and exported AWTK functions. | Reuse rendering/navigation concepts and C logic after ABI adaptation. |
| Display | Q2-pod's layout is 375×320. M1 main() initializes 320×480; Shanling documents the same resolution. | Reflow layouts, Coverflow, visualizers, touch targets and artwork; do not stretch the Q2 screen. |
| Shared libraries | 111 of 116 common regular-file paths under lib/ and usr/lib/ are byte-identical. | Much of the runtime can remain stock. This count is per path, not unique library or feature. |
| Different common libraries | libSL.so, libWL.so, libsacd.so, libtag.so.2.0.1, libtag_c.so.2.0.1. | Validate SyncLink, decoding and metadata behavior separately. |
| Bluetooth audio | Stock usr/bin/bluealsa is byte-identical on both devices. | Q2-pod's changes have a strong reuse candidate, subject to dependencies and hardware tests. |
| Audio player | hciplayer differs in executable code/data, despite nearly equal total sizes and matching ABI flags. | Retarget the PEQ, visualizer tap, seeking and ReplayGain patches; don't transplant Q2 instruction addresses. |
| Main UI hooks | 33 of 54 named entries in HOOKS/IPOD_HOOKS have defined names in the M1 executable. | Useful starting map, not 61% port completion. Missing names can be private/renamed functions. All matched functions need semantic checks too. |
| UI assets | 47 shared UI paths, versus 135 M1 pages and 120 Q2 stock pages. | Page naming, widget trees and native page builders need mapping beyond screen dimensions. |

M1 stock rootfs: 55,738,368 bytes, with SquashFS bytes_used 55,735,728.
The 2,640-byte difference is filesystem image padding, **not measured free flash
space**. Preserve filesystem metadata and hardlinks during repacking and keep a
conservative size limit until the actual MTD layout is verified.

## Requested wheel behavior

Proposed persisted setting: **Settings → Controls → Wheel navigation**, off by
default for initial testing. Touch continues to work in both modes.

| Foreground context with the setting on | Rotate wheel | Short wheel click |
| --- | --- | --- |
| Home, library, settings lists, playlists | Move selection and scroll into view | Open/confirm selected item |
| Coverflow | Browse albums | Open selected album |
| Focused EQ or settings editor | Adjust selected value within its limits | Confirm/advance editor |
| Now Playing, with no dialog/editor over it | Stock volume adjustment | Preserve stock screen/wake behavior |
| Display off, lock screen, USB mode or unsupported page | Preserve stock behavior | Preserve stock behavior |
| Setting off | Stock volume behavior everywhere | Stock behavior |

Keep long-click power handling separate from short-click confirmation. The
release following a long hold must not activate a menu item. A click used to wake
the screen must not also select something. A menu-owned wheel gesture must never
also change the volume. Use the foreground dialog's context, rather than the
Now Playing page underneath it. Preserve the hardware playback buttons; use
touch Back initially because the M1 Plus has no dedicated Q2 Return button.

Static M1 input evidence, tied to the exact demo hash above:

- `on_wm_keyup_fun`, `0x4cd9ac`, reads the AWTK event key at offset `0x18`.
- Its `0xdc`/`0xdd` (220/221) path opens the volume UI; these are candidates for
  the wheel directions. Physical direction and actual press/release sequencing
  still need an input trace.
- Its `0xd2` (210) path changes the screen state. `on_wm_keylong_fun`,
  `0x4cdd9c`, uses the same key for power handling. This is the wheel-click
  candidate, not a claim that Linux evdev uses code 210.
- `window_manager_dispatch_input_event`, `0x677b74`, is a possible integration
  boundary. Audit the earlier input path before choosing the interception point:
  suppressing a late event is insufficient if volume has already changed.
- M1's stock GP is `0xa03ed0`; Q2's is `0xa26cc0`. Q2's key constants, global
  addresses, trampolines and lockout bytes must not be reused unchanged.
- Q2's named keydown-before/keyup-before callbacks are absent from M1's defined
  symbol list. Hook registration and event order need recovery on M1.

The UI design and routing rules are specified here. They are not implemented in
the firmware by the inspection scripts.

## Feature scope and work required

| Feature group | Intended result | Remaining work |
| --- | --- | --- |
| iPod appearance | Retain themes/accents, selection, transitions, home layouts, status bar and Now Playing style | Parameterize dimensions, reflow for portrait, audit native drawing hooks and touch navigation |
| Coverflow and four visualizers | Keep | Adapt framebuffer geometry, album cache integration and PCM tap |
| Library enhancements | Favourites, playlists, queue actions, ratings, Loved/Top Rated, Most Played, Long Songs, album-artist browsing | Recover M1 library/queue structures and callbacks; verify persistence and card swaps |
| Playback | Shuffle by song/album/folder, repeat, crossfade, resume and related fixes | Retarget player hooks and validate local, Bluetooth and USB outputs |
| EQ | Simple three-band controls and up to 30-band PEQ, presets and imports | Retarget hciplayer DSP hooks and EQ UI; test sample rates, bypass, clipping and DSD paths |
| Podcasts/audiobooks | Resume positions, per-folder speed, M4B support | M1 metadata-library differences and playback queue ABI need validation |
| Photos/books/videos | Keep local viewers and supported playback | Portrait geometry, framebuffer/audio helper compatibility and media controls |
| Lock screen and display | Wallpapers, clock, boot art, theme options | Map M1 lock/wake flow and portrait asset sizes |
| Bluetooth/AirPods | Controls, ear detection, volume sync, resume on connect | Same bluealsa is promising; update main-app globals and verify headset events on hardware |
| Battery and power | Aim to retain charge limit and Low Power mode | Audit M1 charging/CPU interfaces before enabling; match physical charge behavior |
| Scrobbling | Keep optional Last.fm/ListenBrainz as a separate feature | It is not an audio streaming source. No accounts need configuring during bring-up. |
| M1 stock functions | Retain touchscreen, local codec support, output/gain controls, USB DAC/output and Bluetooth | Build on M1 stock hardware support and test regressions |
| Rockbox | Excluded | Omit launcher, boot choice, home entry and related dependencies |
| Streaming sources | Excluded: Spotify Connect, Internet Radio, Tidal, AirPlay/DLNA playback | Remove custom UI, modules, hooks and references consistently; retain Wi-Fi when needed for diagnostics, OTA or optional scrobbling |

Feature exclusions reduce scope, but upstream source references are interwoven:
`tools/peq.py` unconditionally compiles Spotify, radio and Tidal modules alongside
the UI. Removing menu entries alone does not produce a streaming-free build.

## Bring-up sequence

1. Establish the exact M1 recovery procedure and obtain a bounded input trace.
   Confirm wheel codes, direction, repeats, short/long clicks, wake, locking and
   screen rotation. A normal stock update is not proof of recovery after a boot
   failure. Do not assume Q2 recovery button combinations apply.
2. Introduce an M1 target with pinned hashes and no fallthrough to Q2 addresses.
   Keep M1 kernel, drivers, audio calibration, boot configuration and metadata.
   Recover required application globals, structures and hook prologues. The
   existing Q2 builder must keep rejecting incompatible firmware.
3. Bring up a small UI/input extension with stock fallback, then the portrait
   theme and local library navigation. Test the toggle and power handling before
   adding audio patches.
4. Port local playback features, EQ/visualizers, media viewers and Bluetooth
   enhancements in independently testable increments. Enable battery changes
   only after their hardware behavior is verified.
5. Validate reproducible packaging, unchanged kernel, filesystem metadata,
   hardlinks, checksums and capacity. Perform device tests for boot, updates,
   local/BT/USB audio, sleep/wake, battery, card swaps and settings persistence.

This Windows host currently has no WSL, Docker or LLVM toolchain available on
PATH. Static Python analysis works. A Linux build environment or a validated
Windows equivalent is still needed for the upstream LLVM/squashfs build and its
host/emulator tests. No unverified update image was generated.

## Reproducing the inspection

Install `requirements-port.txt` in an analysis Python environment, then run:

```powershell
python tools/port_inspect.py --m1 '..\M1 Plus Firmware V2.1\M1 Plus Firmware V2.1\update.bin' --q2 '..\Q2 Firmware V1.32\Q2 Firmware V1.32\update.tar' --q2-pod '..\Q2-Pod\Q2.Firmware.1.1.9\update.tar' --out work/m1plus-analysis-new
python tools/port_disasm.py work/m1plus-analysis/m1/analysis-files/release/bin/demo '^on_wm_key|^main$'
python test/port_inspect.py
```

The current host ran the tools using the bundled Python 3.12 interpreter and
dependencies installed locally in `F:\DAP\.analysis-deps`. Inspection validated
all three real containers. Seven synthetic tests passed, covering valid inputs,
bad payload hashes, kernel CRC failure, SquashFS bounds, repeated digests,
unexpected/duplicate paths and symlinks. `git diff --check` passed. No device
tests, firmware build or emulator runtime tests have been performed. The
repository asks for `graphify update .`; it was attempted but graphify is not
installed and no graphify graph was present.

## Supporting projects

- [Shanling's M1 Plus specification](https://en.shanling.com/article/101246)
  confirms the Ingenic X2000 platform and 320×480 touchscreen.
- [shanling-m1plus-navidrome](https://github.com/shivaluma/shanling-m1plus-navidrome)
  targets the exact same M1 V2.1 firmware hash. It documents an AWTK extension,
  metadata-preserving packaging and owner-reported browsing/audio playback on
  one player. This is useful evidence that M1 extensions are possible, not proof
  that a Q2-pod port works. Its streaming feature is outside this port's scope.
  A read-only reference checkout is available locally in `F:\DAP\m1plus-reference`.
- [Upstream Q2-pod build documentation](building.md) and
  [internals](internals.md) describe the existing binary-patch architecture.
