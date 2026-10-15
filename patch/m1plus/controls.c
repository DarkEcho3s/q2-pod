/* Own only completed wheel gestures on an eligible foreground page. The native
 * AWTK dispatcher still accounts for every key press and release. */
#include "input.h"
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

#define CONFIG "/mnt/data/m1pod-wheel-nav"
#define STOP 11
extern int stock_application_trampoline(void), stock_input_trampoline(void *, void *);
extern int stock_widget_keyup_trampoline(void *, void *);
extern int ringnav(void *, void *), ringnav_keylong(void *, void *), ringnav_m1_supported(void *);
extern int ringnav_m1_held_release(void);
extern int ringnav_m1_wake(void *);
extern int compact_now_playing(void);
extern int video_on(void);
extern void ringnav_m1_activity(void);
extern void *list_row(void *, const char *, int (*)(void *, void *), void *);

static struct m1_input input;
static int enabled = 1, loaded, tracing;
static unsigned generation = 1, suppress_key, suppress_active, keyup_seen, trace_count;
static unsigned video_power_at;
static unsigned shortcut_key;

static void read_setting(void) {
    if (loaded) return;
    loaded = 1;
    char v[3];
    void *f = fopen(CONFIG, "rb");
    if (f) {
        enabled = fread(v, 1, 3, f) == 2 && v[0] == '1' && v[1] == '\n';
        fclose(f);
    }
    f = fopen("/mnt/mmc/m1pod-trace.enable", "rb");
    if (f) { tracing = 1; fclose(f); }
}
static void row_text(void *label) {
    widget_set_text_utf8(label, enabled ? "Wheel Navigation: On" : "Wheel Navigation: Off");
}
static int toggle(void *label, void *event) {
    (void)event;
    char v[2] = {enabled ? '0' : '1', '\n'};
    void *f = fopen(CONFIG ".tmp", "wb");
    if (!f) return 0;
    int ok = fwrite(v, 1, 2, f) == 2 && !fflush(f) && !fsync(fileno(f));
    if (fclose(f)) ok = 0;
    if (ok && !rename(CONFIG ".tmp", CONFIG)) {
        enabled = !enabled; ++generation; m1_cancel_owned(&input); row_text(label);
    }
    return 0;
}
void m1_controls_row(void *view) {
    read_setting();
    void *label = list_row(view, "system_display", 0, 0);
    if (!label) return;
    row_text(label);
    widget_on(P(label, W_PARENT), EVT_CLICK, toggle, label);
}
int m1_ui_application(void) {
    read_setting();
    return stock_application_trampoline();
}
static struct m1_context context(void *wm) {
    void *top = window_manager_get_top_window(wm);
    struct m1_context c = {0};
    c.page = ringnav_m1_supported(top) ? (unsigned)top : 0;
    c.generation = generation; c.enabled = enabled;
    c.awake = g_backlight_status != 0;
    c.unlocked = !m1_keylock_flag && !g_lockscreen_pageflag;
    c.stable = !g_poweroff_state && !m1_boot_guidestep && !window_manager_is_animating(wm);
    c.reversed = m1_rotate_mode == 1;
    return c;
}
int m1_ui_long(void *ctx, void *event) {
    struct m1_context c = context(window_manager());
    if (event) m1_route(&input, &c, M1_LONG, I(event, EVENT_KEY));
    unsigned key=event ? (unsigned)I(event,EVENT_KEY) : 0;
    /* M1 has no Back key. Keep short presses as media controls and provide
     * navigation holds while the optional wheel navigation mode is enabled. */
    if(c.enabled && c.awake && c.unlocked && c.stable &&
       (key==KEY_BACK_BTN || key==KEY_FWD_BTN)) {
        shortcut_key=key; ++generation; m1_cancel_owned(&input);
        if(key==KEY_BACK_BTN) navigator_back(); else compact_now_playing();
        return STOP;
    }
    return ringnav_keylong(ctx, event);
}
int m1_ui_keyup(void *widget, void *event) {
    if (event && suppress_active && I(event, EVENT_TYPE) == M1_UP &&
        (unsigned)I(event, EVENT_KEY) == suppress_key) {
        keyup_seen = 1;
        return STOP;
    }
    return stock_widget_keyup_trampoline(widget, event);
}
static void log_event(unsigned type, unsigned key, int action, int seen, int before) {
    if (!tracing || trace_count >= 256) return;
    char line[128];
    int n = tk_snprintf(line, sizeof line, "%u type=%u key=%u action=%d suppressed=%d volume=%d/%d\n",
                        ++trace_count, type, key, action, seen, before, g_volume);
    if (n <= 0 || (unsigned)n >= sizeof line) return;
    void *f = fopen("/mnt/mmc/m1pod-input.log", "ab");
    if (!f) { tracing = 0; return; }
    if (fwrite(line, 1, (unsigned)n, f) != (unsigned)n) tracing = 0;
    if (fclose(f)) tracing = 0;
}
int m1_ui_dispatch(void *wm, void *event) {
    if (!wm || !event) return stock_input_trampoline(wm, event);
    unsigned type = I(event, EVENT_TYPE);
    if (ringnav_m1_wake(event)) return 0;
    ringnav_m1_activity();
    if (video_on()) {
        /* The helper owns the framebuffer. Tap to leave; hold the wheel click
         * to leave without touching the screen. Other buttons retain media roles. */
        unsigned key = I(event, EVENT_KEY);
        if (type == M1_DOWN && key == M1_POWER) video_power_at = time_now_ms();
        if (type == M1_UP) {
            if (key == M1_VOL_UP) key = KEY_NEXT;
            else if (key == M1_VOL_DOWN) key = KEY_PREV;
            else if (key == M1_POWER && (unsigned)time_now_ms()-video_power_at >= 700) key = KEY_RETURN;
            video_key(key);
        } else if (type == 0x103) video_key(KEY_RETURN); /* native pointer-up */
        return 0;
    }
    if (type == 0xff) { ++generation; m1_cancel_owned(&input); }
    if (type != M1_DOWN && type != M1_UP) return stock_input_trampoline(wm, event);
    unsigned key = I(event, EVENT_KEY);
    struct m1_context c = context(wm);
    unsigned old_active = suppress_active, old_key = suppress_key, old_seen = keyup_seen;
    int action = m1_route(&input, &c, type, key), before = g_volume;
    if(type==M1_UP && key==shortcut_key) { shortcut_key=0;action=M1_DROP; }
    if (type == M1_UP && key == KEY_PLAY && ringnav_m1_held_release()) action = M1_DROP;
    suppress_key = key; suppress_active = action != M1_PASS; keyup_seen = 0;
    int result = stock_input_trampoline(wm, event), seen = keyup_seen;
    suppress_active = old_active; suppress_key = old_key; keyup_seen = old_seen;
    log_event(type, key, action, seen, before);
    if (action != M1_PASS && seen) {
        reset_poweroptions_timer(1, 1, 1);
        if (before != g_volume) { enabled = 0; ++generation; return result; }
        if (c.page && c.page == (unsigned)window_manager_get_top_window(wm) &&
            action >= M1_PREVIOUS) {
            unsigned release[16] = {0};
            release[EVENT_TYPE/4] = EVT_KEY_UP;
            release[EVENT_KEY/4] = action == M1_CONFIRM ? KEY_CENTER : action == M1_NEXT ? KEY_NEXT : KEY_PREV;
            ringnav(0, release);
            ++generation;
        }
    }
    return result;
}
