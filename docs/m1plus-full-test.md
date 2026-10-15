# M1 Pod full feature test 2

Target: **Shanling M1 Plus, based on stock V2.1**. Package label:
**V2.1-M1P-full2**. This retains the complete non-streaming feature build and
fixes the input problems reported from full1 on the physical M1 Plus:

- Menu wheel navigation no longer mistakes the saved screen-off button-lock
  preference for an active lock while the screen is on.
- Home's Settings submenu now has a visible **Back to Home** row.
- Holding Previous exits that submenu correctly. Previous/Next navigation
  holds also work when Wheel Navigation is Off.

Full1 was accepted by the updater and reached the interface and Settings on
the device. These fixes pass offline execution tests; full2 needs device testing.

## Install

1. With the player shut down, use your card reader to copy this build's
   **update.bin** to the microSD card root. Keep its filename unchanged.
2. Eject the card, insert it into the M1 Plus and start the player.
3. Open **System settings → System Update → TF card update** (the card-update
   option in V2.1). Keep adequate charge and leave the card installed until
   the update completes and the player restarts.
4. The player should open the Pod Home interface. No SD activation markers
   or separate application installation are required.
5. Run **Library → Update Library** for the music on the card.

The included SHA256SUMS.txt identifies the exact image. On Windows you can
check it with `Get-FileHash .\update.bin -Algorithm SHA256`.

## Controls

Wheel Navigation defaults to **On**. Its toggle is under
**Settings → System → Display**.

| Control | Behavior |
| --- | --- |
| Turn wheel in a supported menu | Move selection or adjust the active editor |
| Click wheel in a supported menu | Confirm selected item |
| Turn wheel on Now Playing | Native volume adjustment |
| Click wheel on Now Playing | Native screen/power-click behavior |
| Tap Back to Home in Home's Settings submenu | Return to the main Home list |
| Short Play/Pause, Previous, Next | Native media controls |
| Hold Play/Pause on a library row or Now Playing | Track/queue actions and rating options |
| Hold Previous while awake and unlocked | Back, including out of Home's Settings submenu |
| Hold Next while awake and unlocked | Open Now Playing; hold again returns |
| Long wheel/power hold | Native power handling |
| Wheel Navigation Off | Native wheel volume/click behavior; touch and navigation holds remain available |

Screen-off/lock states retain native volume/media behavior. The optional
Double-press Wake setting filters accidental power clicks. During video,
turn the wheel for volume; click it to toggle seek mode, then turn to seek;
hold it or tap the screen to leave. Touch controls remain available elsewhere.

## Full feature test

For this revision, first open **Settings**, tap **Back to Home**, then try
turning and clicking the wheel on Home, in Settings and in Library. Check the
Display page's **Wheel Navigation: On** setting. Verify that menu scrolling
does not change volume, and that the wheel still adjusts volume on Now Playing.
Try holding Previous from the two-choice Settings submenu and a deeper page.

For the remaining full-feature test, report the first failure with the page,
actions and whether touch still works. A photo or short video is useful for
layout/input failures.

1. **Update and first boot:** updater accepts the package, Home appears,
   Settings opens, and About has the M1 Pod full test row.
2. **Wheel:** move through Home and Library, click to open, hold Previous to
   return, and verify menu scrolling does not change volume. Play a song, open
   Now Playing, and verify the wheel changes volume there. Toggle navigation
   Off and On; restart once to check persistence.
3. **Library:** scan, Songs, Albums grid, Artists/album artists, Genres,
   Favorites, playlists and search. Open artist albums and its Songs button.
   Try two albums sharing a name, missing tags and long names. Check
   Coverflow, play/add-next/add-to-queue actions, ratings and play counts.
4. **Audio:** test normal headphone playback at a low initial volume, then
   your usual balanced/Bluetooth/USB output if used. Check pause, seek,
   previous/next, gapless, shuffle/repeat, crossfade and paused boot resume.
   Test Simple EQ, PEQ preset import and bypass; DSD should bypass PCM DSP.
5. **UI:** Home split/full, Minimal/Classic, each accent, battery choices,
   Now Playing art/text/progress/lyrics, four visualizers and large cover art.
6. **Local media:** add small samples under Podcasts/, Audiobooks/, Photos/,
   Books/ and Videos/ at the card root. Test resume, speed, M4B art, viewer
   controls and video audio/orientation. Put EQ presets in EQ/.
7. **Power/headsets:** screen off/on, standby/resume, lock screen, wallpaper,
   clock, double-press wake, charge limit and Low Power. Test Bluetooth resume,
   volume sync and AirPods stem/ear detection if you use them. Scrobbling uses
   the existing Q2 Pod account setup and is included.

Custom boot-logo images use **320x480 baseline JPEG**, or 480x320 to rotate
clockwise. Use the card path **Q2Pod/boot/boot-logo.jpg**. It is picked up
when the card mounts. Existing settings, ratings and resume data use the
upstream persistent formats on internal storage.

## Optional input trace

Copy the included empty **m1pod-trace.enable** file to the card root and reboot
to enable the optional input log. This is useful during the full2 input retest.
After reproducing a wheel problem, shut down and read **m1pod-input.log** with
the card reader. Each application run appends at most 256 event records,
including key, action, suppression, volume before/after, page and navigation
eligibility flags. The marker is also detected after a late card mount.
Delete the marker and restart to disable tracing; delete the log before another clean capture. The marker
only enables logging and is not needed to boot this build.

The package includes build-validation.json, component manifests and
filesystem-validation.json. They establish the offline evidence; real panel,
wheel, audio output, standby and updater acceptance remain device tests.
