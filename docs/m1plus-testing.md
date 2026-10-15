# M1 Plus V2.1 platform test

This kit tests installation, stock fallback and physical input. It does **not**
contain the full Q2-pod feature port. The original Shanling app, kernel and audio
player are retained. The optional SD application adds the portrait preview menu
and wheel-navigation toggle. The [port notes](https://github.com/DarkEcho3s/q2-pod/blob/m1plus-port/docs/m1plus-port.md)
track the remaining features and implementation evidence.

The owner confirmed an M1 Plus on V2.1 and a PC card reader. The normal updater,
boot timing, wheel events and sleep/wake still need hardware verification. This
small platform test is needed before expanding the custom interface and audio
features. Nothing in the kit installs itself or selects a drive automatically.

## Recovery limits — read before installation

There are two different fallback paths:

1. **Application fallback:** no SD card, `M1Pod/disable`, no `M1Pod/run-once`,
   or failed validation selects `/release/bin/demo`, the untouched stock app.
   The activation marker is consumed and synced before an experimental launch.
   The next boot selects stock, even if the experimental app hangs. A failed
   SD `execve` immediately tries stock. Runtime crashes use Shanling's existing
   watchdog/reboot behavior; no second app/audio engine is started concurrently.
2. **Firmware restoration:** `restore/update.bin` uses the normal on-device
   updater and restores the exact official V2.1 kernel and root filesystem. It
   changes only the update metadata label to `V2.1-M1P-restore`. This is necessary
   because the untouched V2.1 app rejects another package labelled simply V2.1.
   The untouched download is also included under `official-v2.1/` for backup.

**Neither path proves recovery if the device cannot boot the stock interface.**
No M1 Plus bootloader-button/USB unbrick procedure has been verified. This is an
experimental firmware installation with residual risk, despite byte-level
checks. Keeping the original kernel and fitting below the original filesystem
size reduces avoidable changes; it does not establish power-loss recovery.

Shanling's [manual](https://en.shanling.com/catlog/M1_Plus-V1.0.pdf) documents
holding Power for about ten seconds to force shutdown after a hang. That is a
reset, not a firmware recovery procedure. **Never do this or remove the card
while a firmware update is running.**

## A. Install bootstrap and verify stock boot first

1. Back up the card and use a fully charged M1 Plus. Keep this kit and the
   restore package on the PC. No formatting is needed. Power off the player
   before removing its card.
2. In the PC card reader, copy the **contents** of the kit's `sd/` folder to the
   card root. This creates `M1Pod/bin/demo`, `M1Pod/app.json`, `M1Pod/disable`,
   `M1Pod/diagnostics-enable`, and `m1pod-trace.enable`. Leave `disable` present.
   There must be no `M1Pod/run-once`. Do not merge an older experimental kit.
3. Copy `firmware/update.bin` to the card root as `update.bin`. Verify its
   SHA-256 against `bundle.json` (`files` → `firmware/update.bin`); on Windows,
   `Get-FileHash 'X:\update.bin' -Algorithm SHA256` reads the copied file. Replace
   `X:` with the card's actual drive letter. Safely eject the card.
4. Insert it into the M1 Plus and use **System settings → System Update → TF
   card update**, following [Shanling's instructions](https://en.shanling.com/download/118).
   Leave the card inserted and wait for the update and restart to finish.
   Do not bypass an error or repeatedly retry a failed update; record the exact
   message. The development label passes the stock app's emulated version gate,
   but the recovery updater has not been tested on this device.
5. Expect the normal Shanling interface. **About still says V2.1** because the
   stock application is unchanged. Check touch, a short local music playback
   at low volume, volume adjustment, short-click lock/wake and normal shutdown.
6. After shutdown, use the reader to collect `M1Pod/boot.txt`. Its first lines
   should identify `m1pod-boot-v1` and `one-shot-1`. This bounded log includes the
   actual partition table, mounts and input devices. Copy it to
   `F:\DAP\M1Plus-test-results\boot.txt` and report whether the checks passed.
   If it is missing, leave the experiment disabled and report that instead.
7. Remove the **card-root** `update.bin` after the successful test. Keep the
   PC copies. With the player powered off, remove the SD card and check that a
   normal power-on still reaches stock. A few seconds of extra boot delay is
   expected while the launcher checks for a card. Power off afterward.

Stop here and share the result before proceeding to B. This establishes the
fallback and actual hardware layout before the custom input handler runs.

## B. One experimental boot, after A is verified

These commands use Python 3.12+ and the explicit card letter; they never install
firmware. Run from the kit directory, replacing `X:\` with the card root:

```powershell
python .\m1plus_card.py status 'X:\'
python .\m1plus_card.py arm 'X:\'
```

If Python is not on PATH, this workspace's interpreter is available at
`C:\Users\dawso\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
For example, use `& 'C:\Users\dawso\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'`
in place of `python` in PowerShell. The card helper needs no additional packages.

Safely eject, insert the card while powered off, then start the M1 Plus. On the
stock home carousel, find **M1-pod preview** and open it with touch. If the
preview never appears, do not assume it ran: shutdown and inspect the logs.

Test in this order, initially with no headphones connected:

1. With wheel navigation off, turn the wheel one detent each way and short-click
   to lock/wake. Open the preview again with touch.
2. Turn **Wheel navigation** on with touch. Rotate one detent each way. Selection
   should move, without a volume popup or volume change. Short-click should
   confirm the selected row. Touch should still work.
3. Open Music/Folders and Now Playing. These native pages intentionally keep
   stock wheel handling in this prototype. Check volume on Now Playing.
4. Return to the preview. Start a wheel click, touch a different row, then
   release: the newly touched row must not also activate from that release.
   Hold Power until the normal power dialog appears; release must not confirm a
   menu item. Cancel the dialog using touch. Check lock/wake with both toggle states.
5. If turning the wheel changes volume while moving selection, a key repeats
   unexpectedly, touch stops responding, or a power hold fails, stop the input
   test. Capture what happened; do not keep trying the same action.
6. Shut down normally. Without rearming, power on again: it should use stock
   and the preview should be absent. `M1Pod/run-once` should have become
   `M1Pod/last-attempt`. The wheel setting may persist, but it cannot activate
   the experimental application on its own.
7. Copy the card-root `m1pod-input.log` and `M1Pod/boot.txt` into
   `F:\DAP\M1Plus-test-results\`. The input log is overwritten only on an
   experimental startup and capped at 256 records. Share the sequence you tried,
   clockwise/counterclockwise behavior, and any visible errors.

## If the experimental application hangs

Only after any firmware update has finished: try normal shutdown, then the
manual's ten-second Power hold if needed. Remove the card while powered off and
boot normally. The stock app should start. With the card in the PC reader, run:

```powershell
python .\m1plus_card.py disable 'X:\'
```

Alternatively create an empty file called `disable` inside `M1Pod`, and delete
`M1Pod/run-once` if present. Windows may hide `.txt` extensions: a file named
`disable.txt` is not the marker. Removing/renaming the whole `M1Pod` directory
while the card is in the PC reader also prevents activation.

## Restore official firmware contents

Start from a working stock interface (disable the experiment first). Copy the
kit's **`restore/update.bin`** to the card root, verify its SHA-256 using
`bundle.json`, safely eject, and run the normal TF-card update. After completion,
the kernel/rootfs are the exact original V2.1 bytes and the bootstrap is gone.
The About screen remains V2.1. This does not factory-reset personal settings,
remove the SD music library, or delete experimental log/setting files.

If stock cannot boot even with the card removed, stop and report the behavior.
This kit cannot promise recovery in that state. Do not use Q2 recovery button
combinations or Q2 firmware on the M1 Plus.
