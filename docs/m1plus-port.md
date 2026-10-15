# Shanling M1 Plus port assessment

Status: an initial M1-specific application prototype builds and passes host/MIPS
emulator checks as of 2026-10-15. It includes a portrait menu and context-sensitive
wheel-navigation code. It has **not run on a player**, is not a complete Q2-pod
port, and is not a flashable firmware update.

Development branch: [DarkEcho3s/q2-pod:m1plus-port](https://github.com/DarkEcho3s/q2-pod/tree/m1plus-port).
The local `origin` points to this fork, `upstream` to DiamondBond/q2-pod, and
`m1plus-port` tracks `origin/m1plus-port`.

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
| Main executable | Both are ELF32 little-endian MIPS, O32 flags 0x70001405, MIPS32r2, FP ABI 6, NAN2008. | The payload toolchain approach is compatible in principle. Addresses and data layouts still need an M1 audit. |
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

Intended final setting: **Settings → Controls → Wheel navigation**, off by
default for initial testing. The prototype exposes the toggle in its own menu
and implements navigation only within that menu. The table below is the final
design, not a claim that native library lists and editors are already adapted.
Touch continues to work in both modes.

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
- `window_manager_dispatch_input_event`, `0x677b74`, records press ownership.
  DOWN events still reach stock input bookkeeping. The prototype suppresses
  owned releases at `widget_on_keyup`, `0x670d10`, allowing the caller to clear
  the toolkit's pressed-key state afterward. Swallowing DOWN or UP at the
  dispatcher itself would break that bookkeeping and/or long-press detection.
- The volume dialog registers its key-up handler at `0x47e330`; it calls the
  native volume adjustment functions. The prototype intercepts before that
  handler. No earlier volume adjustment was found in the generic evdev-to-AWTK
  path, but a hardware trace must establish the physical rotary event source.
  The generic evdev key map does not map Linux volume keys 114/115 to 220/221.
- M1 event types are DOWN `0x10f`, LONG `0x110`, UP `0x113`, CLICK `0x10c`;
  the Q2 event constants must not be reused. A separate long-handler hook keeps
  stock power behavior and prevents the held button's release from confirming.
- M1's stock GP is `0xa03ed0`; Q2's is `0xa26cc0`. Q2's key constants, global
  addresses, trampolines and lockout bytes must not be reused unchanged.
- Q2's named keydown-before/keyup-before callbacks are absent from M1's defined
  symbol list. Hook registration and event order need recovery on M1.

The inspection scripts remain read-only. The prototype builder described below
implements the initial menu and input adapter separately from the Q2 builder.

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

The Windows host now has a local Zig 0.15.2/Clang cross-compiler and Unicorn
2.1.4 MIPS emulator. WSL and Docker are not needed for this application prototype.
The complete firmware packaging and recovery path remains to be established;
no update image was generated.

## Prototype implementation and validation

`targets/m1plus/v2.1.json` pins the stock executable hash, ABI, 35 symbol
addresses/sizes, and four hook prologues. `tools/build_m1plus.py` validates them
before compiling or writing output. It imports no Q2 target definitions.
Compiled C and assembly objects must match the stock MIPS/FPU ABI flags; a final
unused program header maps the payload above the existing segments at `0xb00000`.
Only the four checked hook prologues and that header are altered in stock bytes.
The unchanged Q2 builder continues to accept only its own target.

The prototype adds an **M1-pod preview** page to the stock home carousel. Its
menu uses the M1's 320-pixel portrait width, a light background and blue
selection. It links to native Music, Folders, Now Playing and Audio Settings,
offers a wheel toggle and a Stock home exit. This is a small UI foundation, not
the completed Q2-pod theme, library enhancements, Coverflow or media viewers.
Native navigation links, layout, touch and hardware events are not yet verified
on a player. Native streaming entries still exist in the stock interface during
bring-up; the new payload links no Rockbox or streaming modules.

The wheel setting defaults off and is saved to `/mnt/data/m1pod-wheel-nav` using
a checked write/flush/fsync/rename sequence. Failed saves do not change the active
setting. The prototype menu is the only page registered for wheel selection;
Now Playing, native pages, dialogs, screen-off, lock and transition states use
stock handling. A press that began in the menu cannot confirm a different page
or touched selection on release. Long power holds and playback buttons pass
through. An observed volume change during a supposedly consumed gesture disables
navigation for that session; this guard cannot undo a volume change that already
happened and does not replace hardware verification.

For future developer-supervised input tracing, an existing
`/mnt/mmc/m1pod-trace.enable` marker enables `/mnt/mmc/m1pod-input.log` at process
startup. The log is reset at that startup and capped at 256 key-event records.
It contains event type, toolkit key, menu ownership, suppression and volume
before/after, with no song metadata. No marker means no log. This is diagnostic
code, not an installation instruction; do not replace the running stock demo.

Install `requirements-m1plus.txt`, locate the installed `ziglang/zig.exe` (or
`ziglang/zig` on Linux), and use a new ignored output directory:

```powershell
python tools/build_m1plus.py --stock-demo work/m1plus-analysis/m1/analysis-files/release/bin/demo --out work/m1plus-prototype-v0 --zig /path/to/zig.exe
python test/m1plus.py --build work/m1plus-prototype-v0 --stock-demo work/m1plus-analysis/m1/analysis-files/release/bin/demo -v
```

On this host, Python dependencies are in `F:\DAP\.analysis-deps` and
`F:\DAP\.build-deps`; the compiler is
`F:\DAP\.build-deps\ziglang\zig.exe`. Compiler subprocesses needed execution
outside the Windows sandbox; all outputs/caches stayed under `F:\DAP`.

Two clean builds produced the same 6,556-byte payload and patched application:

| Output | SHA-256 |
| --- | --- |
| Payload bytes | `e971cc8b01eafaea71b78807044839feb72779c57a05b6f9c5d8a588acd4f75b` |
| demo.m1pod | `032dfaf83b0c354351a885ba3cd81ecc024ffd1f51d235d219bcb5ab964222ab` |

27 tests passed: compiled MIPS policy and adapter execution, stock passthrough,
ownership changes, touch cancellation, short/long clicks, wake, toggle persistence
failure, exact patch reconstruction, wrong-firmware rejection, segment/jump
bounds and real hook/trampoline instructions. Toolkit services are mocked in
adapter tests; they do not establish GUI correctness, device bootability or
physical wheel behavior. Seven existing inspection/container tests also passed.

Local outputs are in `work/m1plus-prototype-v0/` and remain ignored because the
patched application contains vendor code. No vendor firmware is pushed to GitHub.
Next hardware milestone: establish recovery and an opt-in boot launcher that
keeps an untouched stock application available, validate the update packaging,
then collect the physical input trace. The broader non-streaming feature port
remains work in progress.

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
tests or full firmware builds were performed during that inspection. The later
prototype emulator checks are described above. The repository asks for
`graphify update .`; it was attempted but graphify is not
installed and no graphify graph was present.

## Supporting projects

- [Shanling's M1 Plus specification](https://en.shanling.com/article/101246)
  confirms the Ingenic X2000 platform and 320×480 touchscreen.
- [shanling-m1plus-navidrome](https://github.com/shivaluma/shanling-m1plus-navidrome)
  targets the exact same M1 V2.1 firmware hash. It documents an AWTK extension,
  metadata-preserving packaging and owner-reported browsing/audio playback on
  one player. This is useful evidence that M1 extensions are possible, not proof
  that a Q2-pod port works. Its streaming feature is outside this port's scope.
  The home-carousel integration and recovered ABI informed this prototype;
  its MIT notice is retained in [targets/m1plus/NOTICE](../targets/m1plus/NOTICE).
  A read-only reference checkout is available locally in `F:\DAP\m1plus-reference`.
- [Upstream Q2-pod build documentation](building.md) and
  [internals](internals.md) describe the existing binary-patch architecture.
