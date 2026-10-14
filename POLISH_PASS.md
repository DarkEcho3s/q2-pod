# Polish pass

A reusable prompt for a UI/UX polish pass on Q2 Pod. Paste everything below the line into a fresh session.

---

Lead a UI/UX polish pass on Q2 Pod, the iPod-classic firmware mod for the Shanling Q2. Treat it as Apple's iPod design team would: every screen, transition, label and interaction should feel deliberate, consistent and calm.

You are the lead. Sub-agents do all the work, one phase each: plan, implement, review, fix. You coordinate, pass each phase's report to the next, judge their findings, and talk to me. Only one sub-agent runs at a time, because they share the device and the build. Copy the ground rules and known traps below into every sub-agent prompt.

## Ground rules

- **Search.** Run `graphify query "<question>"` before searching the code, and `graphify update .` after editing it.
- **Repo.** Don't bump VERSION or publish a release. Put no testing notes in the repo. Don't commit or push.
- **Builder.** One builder at a time; parallel builds have nearly run the PC out of memory. Before building, run ListAgents. If a sibling q2-pod session is active, agree which one of you builds, and build from `git worktree add --detach /tmp/q2-commit HEAD` while a peer has half-finished files in the tree.
- **Build and test.**
  - `python tools/build.py --ipod --dev --out dist/dev-<name>-ipod "Q2 Firmware V1.32.zip"`
  - `~/tmp/q2-venv/bin/python test/patch.py <build>`, unskipped; every scenario must pass
  - `~/tmp/q2-venv/bin/python test/build.py --build <build>` and `test/playback.py <build>`
- **Device access.**
  - `export Q2_HOST=<ip> Q2_KEY="$(cat $XDG_RUNTIME_DIR/q2remote.key)"`, then `python3 tools/q2remote.py shot|key|wheel|tap|sh` (docs/remote.md).
  - Never print the key.
  - Take a screenshot about a second after every action and look at it before the next one.
  - Note the volume, theme, sort, lock screen, clock and queue before exploring, and restore any you change.
- **USB storage.** If the Q2 shows USB Connected, /mnt/mmc is read-only:
  - First check on the PC that the card isn't mounted (`findmnt`, `lsblk`).
  - Press `key centre` to wake the screen if it's off; a stale clock in the shot means it's off.
  - Then `key return` ends USB storage. Confirm `/mnt/mmc` is `rw` in `/proc/mounts` before writing.
  - Never swap the card while the Q2 is on.
- **Install over Wi-Fi.** Upload from Python, because the CLI's `sh` doesn't forward stdin and would leave an **empty** update.tar on the card:
  ```sh
  python3 -c '
  import sys; sys.path.insert(0, "tools"); import q2remote as q
  d = open(sys.argv[1], "rb").read()
  print(q.shell("cd /mnt/mmc && cat > update.tar.new && mv update.tar.new update.tar && sync && echo 3 > /proc/sys/vm/drop_caches && md5sum update.tar", d, timeout=600).decode())' <build>/update.tar
  ```
  - The md5 must match `md5sum <build>/update.tar`.
  - Then on the device: Settings → System → System Update → TF card update → OK.
  - Wait until `md5sum /release/bin/demo` matches `<build>/demo`.

## Known traps

- An AWTK timer callback gets `timer_info_t*`, not your context; keep pending state in the payload's `st`.
- Stock frees record strings with `free`, so swapping a heap-owned title is safe.
- A blanket rename can hit longer strings that contain it ("Display setting" inside "Display settings"); grep afterwards.
- Stock strings are renamed in the LABELS table in tools/build.py; it applies to the legacy build too.
- Before calling something a bug, check which build is installed: compare `md5sum /release/bin/demo` with `dist/*/demo`.

## 1. Plan (sub-agent)

The planner reads README.md, docs/ipod.md, docs/changelog.md and docs/remote.md for the vision. It then uses the Q2 as a real user would and covers everything: Home, Library, Coverflow, Folder, Now Playing and its pages, hold menus, Settings, Streaming, dialogs, toasts, the lock screen, and both the Minimal and Classic themes. It changes nothing in the repo.

It writes down every flaw it sees: inconsistent spacing, type, colour or alignment; raw or technical text (file names, stock strings, odd capitalisation); dead ends; slow or janky moments; missing feedback; anything that falls short of the original iPod.

It returns the flaws ranked by how much a user would notice, grouped as: seen every session / dead ends and missing feedback / visual consistency / lower impact. For each flaw it gives:
- the screen and what's wrong
- the screenshot path
- where in the code it comes from
- the proposed fix
- its size: a one-liner (LABELS or a string), a payload change, or bigger, needing my agreement

**Show me the ranked list and wait for my go-ahead and my answer on the bigger items.**

## 2. Implement (sub-agent)

Give the implementer the approved list. It fixes the items highest impact first. It should:
- keep each change conservative and follow stock firmware behaviour unless deliberately improving on it
- fix root causes in the shared function, not one caller
- update the emulator tests in test/patch.py for every behaviour change, and add one small check for each new piece of logic
- update docs/ipod.md, docs/internals.md, docs/manual/guide.html and README.md wherever a label or behaviour they describe changes
- build and run all three suites until they pass

It reports, item by item, what it changed (file:line), what it left alone and why, and the test counts.

## 3. Review (two sub-agents, read-only)

Run both on the working-tree diff. They edit nothing and don't build.
- **ponytail-review:** over-engineering, duplication and helpers that already exist. One line per finding: location, what to cut, what replaces it.
- **code-review:** correctness bugs, regressions and missed callers. For each finding: location, the failure scenario, and a fix.

Judge every finding yourself before passing it on, because reviewers can be wrong about firmware APIs (see the known traps). Drop the ones that don't hold up, and note why.

## 4. Fix (sub-agent)

Give the fixer the findings you accepted. It:
- applies them
- rebuilds and reruns all three suites until they pass
- installs the build over Wi-Fi
- takes a before and after screenshot of every fixed screen

It reports the build tag, the test counts, the screenshot paths, and the md5 match on the device.

## 5. Hand-off to me

Look at the after screenshots yourself, then tell me:
- **What changed:** one bullet per area (Hold menus, Wording, Song rows, …), in plain words a user would understand
- **What to look for on the device:** for each change, where to go and what I should see, for example "Hold Play/Pause on a song: three whole rows, none cut under the title"
- **Left alone:** each skipped item and why
- **Tests:** the build tag and scenario counts
- **Review:** what each reviewer found, and what was taken, rejected or skipped

Then wait for me to review on the device.

## 6. Ship (only when I say)

1. Add the "What changed" bullets to the next version's entry at the top of docs/changelog.md, without bumping VERSION.
2. Commit with an `area: what` title and push. Leave out transcripts, review notes and other untracked scratch files; move them to `~/tmp/`.
3. Build again from the pushed commit (`--dev`), so the build matches the commit hash.
4. Run `graphify update .`.
