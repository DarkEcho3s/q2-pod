# Shanling M1 Plus port assessment

Status as of 2026-10-15: the M1 audio payload builds from the shared DSP sources
and passes 11 checks, including execution of the compiled MIPS code. Shared UI
geometry now supports 320×480; 11 UI modules compile for both display targets,
and the actual EQ paint code passes bounds checks at both sizes. The complete UI
hook/asset integration is still unfinished. There is **no full-port update.bin**
yet, and no custom build has run on a player.

The owner's current instruction supersedes the earlier bootstrap plan: build the
full non-streaming port, boot it directly, and omit recovery and stock fallback
work. The owner handles recovery. The previous bootstrap kit and
[platform-test instructions](m1plus-testing.md) are historical development
artifacts, not a required stage or the requested deliverable. Hardware testing
is deferred until there is an integrated feature build to test.

Development branch: [DarkEcho3s/q2-pod:m1plus-port](https://github.com/DarkEcho3s/q2-pod/tree/m1plus-port).
The local `origin` points to this fork, `upstream` to DiamondBond/q2-pod, and
`m1plus-port` tracks `origin/m1plus-port`.

The user has an M1 Plus on V2.1 and a PC card reader for staged hardware testing.
The desired scope
is Q2-pod's interface, theme and non-streaming features, without Rockbox or
network streaming sources. Host inspection cannot establish bootability or full
feature parity.

## Audio and portrait-layout checkpoint

`tools/build_m1plus_player.py` accepts only the original V2.1 `hciplayer`. Its
target is `targets/m1plus/player-v2.1.json`. Twelve pinned regions establish the
filter descriptor/ABI, sample-rate gates, duration load, MP3 routines and
ReplayGain dictionary calls; seven individual words are replaced. The builder
checks the entire input hash and a byte allowlist, and records a source hash.
The Q2 addresses remain in `patch/player_abi.h` for the original target; the M1
build generates its own address header.

The shared implementation includes 30-band PEQ, 3-band EQ, preamp, channel
balance, crossfade, the visualizer PCM tap, Xing MP3 seeking and ID3 ReplayGain
handling. This describes linked audio code, not completed on-device UI support.
Two fresh builds produced the same local player bytes:
`4780c84f09d4f18fa9163e92373c43c9f4d367b68ce05e6bbe5c50b70e88aabf`.
The injected payload is 12,096 bytes. M1's player declares ISA revision 5 with
the same O32/FP64/FP-ABI-6/NAN2008 calling convention as the injected r2 subset.
Imports include both its ordinary GOT and its PLT GOT; the latter requires the
slot address in `$t8` for lazy resolution.

`test/m1plus_player.py` executes the actual target code on Unicorn's P5600 CPU
model, retaining the emulator's default CP0 status bits and enabling CU1/FR.
Checks cover filter allocation/cleanup, invalid channel counts, flat PCM at
8/44.1/48/96/192/384 kHz, bit-identical DSD/DoP passthrough, preamp and channel
balance, a +6 dB peaking filter, M1's high-resolution MP3 seek flag and vendor
seek call, unseekable ID3 streams, exact patched bytes, and rejection of wrong
inputs. Linux, the DAC, Bluetooth and actual track transitions are not emulated.

`patch/display.h` and `patch/m1plus/layout.inc` provide portrait dimensions for
the EQ, Cover Flow, photos, books, visualizer, queue menus and lock-screen clock.
Photos use three columns of 106 pixels; Cover Flow uses a 320×370 frame above its
captions. Existing Q2 dimensions remain unchanged. This is geometry preparation:
it does not make the Q2 toolkit structure offsets or native hooks usable on M1.
`test/m1plus_layout.py` deliberately uses mock addresses, compiles 11 shared UI
modules for each size, and executes the real EQ painter. It checks 301 drawing
bounds per size, verifies all controls were painted, and checks thumbnail and
Cover Flow extents. Its ELF files are test harnesses, never firmware payloads.

Reproduction (Python with pyelftools and Unicorn, Zig 0.15.2):

```text
python tools/build_m1plus_player.py --stock-player work/m1plus-analysis/m1/analysis-files/usr/bin/hciplayer --out work/player-new --zig <zig.exe>
python test/m1plus_player.py --build work/player-new --stock-player work/m1plus-analysis/m1/analysis-files/usr/bin/hciplayer -v
python test/m1plus_layout.py --out work/layout-new --zig <zig.exe>
```

Remaining integration includes native library/menu hooks and object layouts,
portrait theme assets and Now Playing, all-page wheel routing, media helpers,
removal of streaming/Rockbox entries, and packaging the integrated app/player
for direct boot. `tools/port_match.py` generates relocation-insensitive research
candidates only; similarity is not sufficient evidence to patch a function.

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
The bootstrap packaging and stock-app fallback are now implemented. Normal stock
restoration has an offline-validated package, but a recovery procedure for a
device that cannot boot remains unverified.

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
The launcher described below now supplies one-boot activation and stock fallback.
The next hardware milestone is stock boot and mount/partition diagnostics,
followed by a bounded physical input trace. The broader non-streaming feature
port remains work in progress.

## Bootstrap, restoration and test kit

`tools/build_m1plus_firmware.py` accepts only the pinned official V2.1 container.
It changes one existing path (`etc/init.d/S90play`) and adds
`usr/bin/m1pod-launch` and `usr/bin/m1pod-exec`. All other original file contents
and metadata are preserved, including the stock demo, hciplayer, bluealsa,
libraries, hardware configuration and drivers. The kernel bytes are unchanged;
the update contains no bootloader payload.

The shell launcher waits at most approximately three seconds for the existing
mdev card mount. Missing/invalid SD content selects stock. A regular `run-once`
file must contain the exact SD executable SHA-256 plus LF; `disable` overrides
it. The marker is renamed to `last-attempt` and synced before execution. The
static MIPS shim preserves `argv[0]=/release/bin/demo` for Shanling's watchdog,
and retries the original app only if `execve` fails. Runtime crashes/hangs are
handled through reboot/power-off and the next stock boot, not by starting a
second audio engine. Actual card durability and boot timing need hardware tests.

The optional `M1Pod/diagnostics-enable` marker writes `M1Pod/boot.txt`, limited
to seven fixed proc files, each capped at 8 KiB. No SD script is executed.
`tools/m1plus_card.py` stages a disabled payload, verifies checksums, explicitly
arms one boot, or disables it. It does not copy an update or flash anything.

Filesystem transport goes directly from SquashFS to a metadata-preserving tar
stream, including owners, modes, timestamps, symlinks, hardlinks and device
nodes. It never repacks the Windows analysis extraction. The rebuilt filesystem
must match the expected inventory, preserve all original hardlink relationships,
use LZO/128 KiB blocks, and fit within the original image size; no growth override
exists. The real build validates 3,742 paths, 3,017 regular-file paths and 494
symlinks, retaining 208 hardlink groups. Its 55,717,888-byte rootfs is 20,480 bytes
smaller than the original 55,738,368-byte image. This does not establish actual
flash capacity or guarantee update recovery.

The official app's `update_firmware` checks the model at `0x4e10dc`, requires a
version containing `V` at `0x4e10fc`, and rejects the exact current `V2.1` string
at `0x4e1114..0x4e1144`. Therefore simply retaining the official download is not
enough for normal restoration from this unchanged app. The kit includes:

- `firmware/update.bin`, label `V2.1-M1P-dev1`, with the bootstrap rootfs.
- `restore/update.bin`, label `V2.1-M1P-restore`, with the **exact original**
  kernel and compressed rootfs; only `firmware_v20.info` is changed.
- `official-v2.1/update.bin`, the untouched official container for backup.
- `sd/`, a disabled SD preview, checksum manifest and bounded log markers.
- `m1plus_card.py`, `TESTING.md`, `bundle.json` and the build validation report.

The development and restore labels pass execution of that exact stock
model/version gate in Unicorn. This does not emulate flash writes, recovery
updater behavior or a complete device boot. The About screen remains V2.1 while
using the stock app because its executable and version string are untouched.

[Shanling documents normal SD updates](https://en.shanling.com/download/118).
Its [M1 Plus manual](https://en.shanling.com/catlog/M1_Plus-V1.0.pdf) documents a
ten-second Power hold to force shutdown after a hang. Neither establishes a
bootloader recovery procedure. Stock fallback protects against many application
failures; it cannot guarantee recovery from failed flashing or a rootfs that
does not boot. See the test instructions for these limits and restore steps.

Install `requirements-m1plus.txt`. On Windows,
`python tools/m1plus_windows_tools.py` obtains pinned official MSYS2 packages,
checks SHA-256, and extracts build executables locally under ignored `work/`.
It makes no system installation. The application uses Zig 0.15.2; packaging
uses sqfstar 4.7.5. Example build commands, with actual compiler/packer paths:

```powershell
python tools/build_m1plus_firmware.py --original '..\M1 Plus Firmware V2.1\M1 Plus Firmware V2.1\update.bin' --out work/bootstrap-new --zig F:\DAP\.build-deps\ziglang\zig.exe --sqfstar work/tools/msys/usr/bin/sqfstar.exe
python test/m1plus_boot.py --bash 'C:\Program Files\Git\usr\bin\bash.exe' --shim work/bootstrap-new/m1pod-exec --stock-demo work/m1plus-analysis/m1/analysis-files/release/bin/demo -v
python test/m1plus_card.py -v
python tools/bundle_m1plus.py --firmware work/bootstrap-new --app work/m1plus-prototype-v0 --out work/test-kit-new
```

The initial Windows packer settings produced identical filesystem records but
variable placement of large-file tails in fragment blocks. The final settings
use LZO level 9, one worker and `-no-tailends`; three runs produced the same
compressed filesystem bytes without changing original file metadata. Final
local build: `work/m1plus-bootstrap-v0/`; kit: `work/m1plus-test-kit-v0/`.

| Final local artifact | SHA-256 |
| --- | --- |
| Bootstrap update.bin | `a8069912a8c3c904edff6ed461c1b1dedad3f1542558a0e0f2484492838a6ebe` |
| Compressed bootstrap rootfs | `289e0d49960d7fc9631fff36b7cd5b4677604526812532ece810b7ac392acf4c` |
| Stock restore update.bin | `7cad9712fd399ac03405212e6450c285c4493c1117fc048caeed764fdeb09c86` |

Vendor-derived artifacts remain local and ignored. Only source, tests and
documentation are committed to the fork. `graphify update .` was attempted
again after these changes, but graphify is not installed on this host.

Seventeen bootstrap tests pass: marker/hash/disable decisions, simulated write
and sync failures, bounded diagnostics, real MIPS exec syscalls and the stock
updater version gate. One additional host symlink test is skipped because this
Windows account cannot create symlinks. Nine card-helper tests pass, including
interrupted arming and corrupt payload rejection. The 27 application emulator
tests and seven container checks also pass. These are host checks, not hardware
qualification. The original Q2 source digest now ignores target subdirectories,
so adding `patch/m1plus/` does not make its old builder try to hash a directory.

### Remaining feature work

| Area | Current state |
| --- | --- |
| Stock M1 hardware support and local playback | Original firmware bytes retained; regression checks on device pending |
| Startup/fallback/restore | Offline implementation and tests complete; first hardware verification pending |
| Portrait preview and wheel toggle | Built and emulator-tested; physical wheel source/direction/sequence pending |
| Full iPod theme, native library lists, queue/playlist/search enhancements | Not ported; original Q2 widget layouts/private offsets need M1 mapping |
| Coverflow, lyrics/lockscreen improvements, themes and settings UI | Not ported |
| Parametric EQ, ReplayGain/seeking improvements, crossfade and visualizers | Not ported; M1 hciplayer differs and needs separate checked hooks |
| Photos, books, video and ancillary non-streaming tools | Not ported |
| Bluetooth enhancements and optional scrobbling | Not ported |
| Rockbox and custom streaming modules | Excluded from M1 payload; stock UI still contains its original entries during bring-up |

The full-feature preference remains the target. The small platform check is a
prerequisite to validating input ownership and fallback, rather than a claim of
feature completion. No percentage of completion is inferred from symbol matches.

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
