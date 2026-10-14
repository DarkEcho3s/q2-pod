# q2remote: a remote shell to view and drive the Q2

Rebuilt on 2026-10-14 from Claude session `4b93aaa5` (14 Oct, around 07:26). That session never wrote a plan file, so this is put together from what it said and from the code it left behind.

## Goal (from todo.txt)

- An AI agent that can see and drive the Q2 live, over Wi-Fi or USB.
- Then: update the repo artwork and user guide, once real screenshots can be taken.

## Design chosen: a shell gated by a key on the card

- **On-device helper `patch/remote.c`** (binary `q2remote`):
  - Listens on TCP **2302**.
  - Each connection sends the key, a newline, a command and another newline.
  - The key has to match `/mnt/mmc/q2remote.key` on the card and be at least 16 characters long.
  - If the key matches, it runs `sh -c COMMAND` as root, with the socket as stdin and stdout.
- **Build (`tools/build.py`)**:
  - Compiles `q2remote` into the rootfs.
  - Starts it from `S90play` after dbus (the `REMOTE_HOOK`).
  - The build fails if `S90play` doesn't look as expected.
- **Tests (`test/build.py`)**: checks that the `q2remote` binary is there and that `S90play` was edited.
- **Host client `tools/q2remote.py`**:
  - Connects, sends the key and the command, and reads the output back.
  - Screenshots and input are shell commands sent through it.
  - The draft was cut off partway and won't run, so it has to be rewritten.

## Facts from the device it relies on

- **Input:** keys, the wheel and the touch screen can all be driven by writing input events to `/dev/input/eventN`, so demo doesn't need changing.
- **Screenshots:** read `/dev/fb0`, then rotate the image 90° anticlockwise to get it upright.
- **USB:** the kernel has RNDIS (networking over USB) built in, so a USB link is possible later. Wi-Fi is simpler to start with.

## Alternatives that were considered

1. **Fixed commands only** (the session's recommendation). There's no general shell: the helper only takes screenshots, presses keys, turns the wheel, taps and dumps input events. It still checks the card key, but it can't read logs or run `ps`.
2. **Key-gated shell.** This is the design above, and the one you picked.
3. **Shell over USB later.** Build the fixed commands over Wi-Fi first, then add a shell only over USB RNDIS (point-to-point, not on the LAN).

## Status: stopped

- Auto mode blocked `remote.c` as a remote root shell, and you then chose the key-gated shell anyway.
- A safety classifier then stopped the work on the host client.
- To carry on, either:
  - allow it explicitly (with a permission rule) or write `tools/q2remote.py` yourself, or
  - switch to the fixed-commands helper.
- Nothing has been built, flashed or tried on a device yet.

## Where the code is now

All of it is in **`git stash@{0}`** ("promo, q2remote, build hooks, graph-review"), together with unrelated promo files:

- `patch/remote.c` (new)
- `tools/q2remote.py` (new, cut off)
- `tools/build.py` and `test/build.py` (edited)

To look at it without touching the tree:

```
git show 'stash@{0}:patch/remote.c'
git diff 'stash@{0}^1' 'stash@{0}' -- tools/build.py test/build.py
```

## Next steps (once the build is finished)

1. Choose: key-gated shell or fixed commands.
2. Restore only the q2remote files from the stash, not the promo files:
   ```
   git checkout 'stash@{0}' -- patch/remote.c
   git checkout 'stash@{0}' -- tools/build.py test/build.py
   ```
3. Write the host client.
4. Do a dev build and run the tests, then flash.
5. Power the Q2 on with Wi-Fi up, write the key to `/mnt/mmc/q2remote.key`, then connect, take a screenshot and send input.
