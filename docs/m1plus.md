# Shanling M1 Plus

Q2 Pod also builds for the Shanling M1 Plus, from its stock V2.1 firmware. The M1 Plus runs an older branch of the Q2's firmware: the same X2000 SoC, kernel, updater and AWTK toolkit (an older AWTK), with its own app build and a 320x480 portrait screen. `tools/m1plus.py` reuses the Q2 payload sources, compiled with `-DM1PLUS=1`. `patch/m1plus/` holds what differs.

The M1 build has no streaming features (Spotify, Internet Radio, TIDAL, HiFi Music) and no Rockbox.

## Build

```sh
python3 tools/m1plus.py 'M1 Plus Firmware V2.1/update.bin' --out /tmp/m1-ipod             # iPod UI
python3 tools/m1plus.py 'M1 Plus Firmware V2.1/update.bin' --out /tmp/m1-legacy --legacy  # stock look
```

The input must be the audited stock `update.bin`, SHA-256 `1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925`. The output's `update.bin` installs the way stock updates do: copy it to the card's root and run System Setting → System Update. To go back, install stock V2.1 the same way.

The version tag keeps V2.1's four characters: `P` and the three version digits for a release (1.1.9 is `P119`), `D` and a three-digit base-36 build number for `--dev`. About shows it as **FW. Version**, with a **CFW. Version** row under it.

Requirements are the Q2 build's (clang, lld, llvm-objcopy, squashfs-tools), and Pillow only to redraw the two Home card icons (`tools/m1icons.py`; the PNGs are committed).

## Controls

The M1 Plus has a detented volume wheel that presses in (the power key), Play/Pause, Previous and Next, and a touch screen. It has no Return key.

| Control | Menus | Now Playing | Screen off |
| --- | --- | --- | --- |
| Wheel | moves the selection | volume | volume |
| Wheel press | opens the selected row; with nothing selected, screen off (stock) | screen off (stock) | wakes |
| Previous | Back | previous track (Back while the rating picker is up) | previous track |
| Previous, held | Now Playing, and back again | back to where you were | |
| Next, Play/Pause | stock | stock | stock |

Every page keeps an on-screen back button: stock pages have their own, and the payload's pages (More, Music, Coverflow lists, the PEQ editor, Shuffle, Ratings, Most Played, Long Songs) carry the stock navigation bar's.

Display settings has **Wheel: Normal / Reversed**, which swaps the wheel's two directions in menus.

## What the port covers

Both builds:

- Wheel navigation on every audited page (`patch/m1plus/contexts.inc`), with position memory, wrapping lists and pickers that open on their current option.
- Home's HiFi Music and TIDAL cards become **Coverflow** and **More**. More opens Shuffle (Songs, Albums, Folders), Ratings, Most Played, Long Songs, the card's Podcasts, Audiobooks, Photos and Books folders, and Upload Scrobbles. In the Legacy build the wheel walks Home's card pages, and the page follows the selection.
- Coverflow, with its album pages, rating and sort.
- Q2 Pod's queue (shuffle albums/folders, advanced repeat, the saved queue and its resume), per-folder playback speed, crossfade, gapless handling and scrobbling, through the M1's own `mcl*` player client (the same routines as the Q2's).
- The 30-band PEQ editor in place of stock's EQ page, and the PEQ filter, MP3 seek and ID3 fixes in `hciplayer` (`M1_PLAYER`).
- Now Playing's heart: hold it to rate the song (1 to 5 hearts).
- Settings rows: Playback Setting gains Year Order, Artists, Artist Album Order and Crossfade; Display gains Artist Albums and Wheel; Idle (its second page) gains Charge Limit, Low Power and Wake.
- Albums sharing a name are split by artist; an album's page lists that album alone.

iPod build, in addition:

- Home is a list: **Now Playing**, **Music** (the whole library in one list: Artists, Albums, Songs, Genres, Composers, Playlists, Ratings, Recently Added, Recently Played, Most Played, Frequently Played, Hi-Res, Long Songs, media folders, CD Ripper, Upload Scrobbles), **Coverflow**, **Folders**, **Shuffle** and **Settings** (Playback, System, Update Library, sliding into the list's place). The playing track's art fills the panel under the list.
- The iPod themes (Minimal and Classic) colour the selection, text and icons on every page.

## Not yet ported

- The lock screen's wallpapers and large clock, and Bluetooth's Resume on Connect row: both need their M1 page builders mapped.
- The Q2's iPod restyling of individual stock pages (status bar, Now Playing layout, quick settings, the confirm and volume pop-ups). The M1's own pages are already portrait and list-based, so the iPod build keeps them, with the iPod selection and colours.
- Scrubbing from Now Playing with the wheel press is iPod code that m1sim cannot exercise (it has no player). On the device it may need adjusting.
- Key Tone: the M1 has no buzzer.

## Mapping

Each stock routine the payload hooks or calls was paired with the Q2's by its callees, strings and data references (`tools/m1plus.py` `M1_NAMES`, `M1_HOOKS`), and its prologue is checked at build time. The M1's ABI differences (older AWTK structure offsets, event numbers and window manager layout) are in `patch/m1plus/abi.inc`, and its screen layout in `patch/m1plus/layout.inc`. Q2 style and image names the payload uses map to the M1 theme's in `patch/m1plus/compat.c`.

## m1sim

`test/m1sim/` runs the real M1 `demo` under qemu-mipsel user mode, with a preloaded shim for the framebuffer, input devices, tslib, shell commands and the factory record. See its README. Library scans work in it, so Coverflow, the library pages and the queue can be exercised. Audio, Bluetooth and the DAC cannot.
