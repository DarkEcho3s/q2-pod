#!/bin/sh
# One boot only. No marker, a disabled/incomplete payload, or any validation
# failure starts the untouched stock app. Never retries an experimental boot.
if [ "${M1POD_HOST_TEST:-}" = 1 ]; then
    m1_card=${M1POD_TEST_CARD:?}
    m1_stock=${M1POD_TEST_STOCK:?}
    m1_exec=${M1POD_TEST_EXEC:?}
    m1_mounts=${M1POD_TEST_MOUNTS:?}
    m1_proc=${M1POD_TEST_PROC:?}
else
    m1_card=/mnt/mmc/M1Pod
    m1_stock=/release/bin/demo
    m1_exec=/usr/bin/m1pod-exec
    m1_mounts=/proc/mounts
    m1_proc=/proc
fi

# mdev mounts the card independently of demo. A late/unavailable card is safe:
# this boot uses stock, and the user can try a later boot without reflashing.
for m1_i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
    grep -q ' /mnt/mmc ' "$m1_mounts" 2>/dev/null && break
    [ "${M1POD_HOST_TEST:-}" = 1 ] || usleep 200000
done
grep -q ' /mnt/mmc ' "$m1_mounts" 2>/dev/null || exec "$m1_stock"
[ -d "$m1_card" ] && [ ! -L "$m1_card" ] || exec "$m1_stock"

# Optional bounded hardware snapshot, also available with the test app disabled.
# Only fixed proc files are read; no card-supplied script is executed.
if [ -f "$m1_card/diagnostics-enable" ] &&
   [ ! -L "$m1_card/diagnostics-enable" ] &&
   [ ! -e "$m1_card/boot.txt" -o -f "$m1_card/boot.txt" ] &&
   [ ! -e "$m1_card/boot.txt.tmp" -o -f "$m1_card/boot.txt.tmp" ] &&
   [ ! -L "$m1_card/boot.txt" ] && [ ! -L "$m1_card/boot.txt.tmp" ]; then
    (
        printf 'format=m1pod-boot-v1\nlauncher=one-shot-1\n'
        for m1_name in version cmdline mtd meminfo cpuinfo mounts bus/input/devices; do
            printf '\n[%s]\n' "$m1_name"
            head -c 8192 "$m1_proc/$m1_name" 2>/dev/null
            printf '\n'
        done
    ) > "$m1_card/boot.txt.tmp" 2>/dev/null &&
        mv -f "$m1_card/boot.txt.tmp" "$m1_card/boot.txt" 2>/dev/null
fi

[ ! -e "$m1_card/disable" ] && [ ! -L "$m1_card/disable" ] || exec "$m1_stock"
m1_arm="$m1_card/run-once"
m1_last="$m1_card/last-attempt"
m1_app="$m1_card/bin/demo"
[ -f "$m1_arm" ] && [ ! -L "$m1_arm" ] &&
    [ -d "$m1_card/bin" ] && [ ! -L "$m1_card/bin" ] &&
    [ -f "$m1_app" ] && [ ! -L "$m1_app" ] && [ -x "$m1_app" ] &&
    [ ! -L "$m1_last" ] &&
    [ ! -e "$m1_last" -o -f "$m1_last" ] || exec "$m1_stock"
[ "$(wc -c < "$m1_arm")" -eq 65 ] 2>/dev/null || exec "$m1_stock"
IFS= read -r m1_expected < "$m1_arm" || exec "$m1_stock"
case "$m1_expected" in ''|*[!0-9a-f]*) exec "$m1_stock" ;; esac
[ "${#m1_expected}" -eq 64 ] || exec "$m1_stock"
m1_actual=$(sha256sum "$m1_app") || exec "$m1_stock"
[ "${m1_actual%% *}" = "$m1_expected" ] || exec "$m1_stock"
[ -f "$m1_exec" ] && [ -x "$m1_exec" ] || exec "$m1_stock"

# Consume and persist the authorization BEFORE any experimental instructions.
# A crash or hang cannot opt into the payload again on the next power-on.
mv -f "$m1_arm" "$m1_last" 2>/dev/null || exec "$m1_stock"
sync || exec "$m1_stock"
[ ! -e "$m1_arm" ] && [ ! -L "$m1_arm" ] || exec "$m1_stock"
exec "$m1_exec"
