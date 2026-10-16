/* The M1 Plus's buttons and wheel (docs/m1plus.md#controls).
 *
 * The M1 has a detented volume wheel that presses in (the power key), Play/Pause, Previous and Next,
 * and no Return key. Its stock window manager registers no key filters before the pages see a key
 * (the Q2's on_wm_keydown_before_fun and on_wm_keyup_before_fun): only on_wm_keyup_fun after them,
 * which turns the wheel into the volume, the press into the screen toggle and the buttons into
 * playback. So the payload adds its own key-down and key-up before-children callbacks to the window
 * manager once Home is built (m1_home), and does there what the Q2's stock filter did before
 * ringnav() ran (m1_keyup_filter):
 *
 *   wheel (KEY_PREV, KEY_NEXT)   the selection, as the Q2's touch wheel; the volume on Now Playing
 *                                and with the screen off, where stock keeps it
 *   wheel press (KEY_CENTER)     open the selected row; a double press turns the screen off
 *   Previous                     Back in every menu (KEY_RETURN); on Now Playing the previous track
 *   Previous, held               Now Playing from anywhere, and back again (compact_now_playing)
 *
 * Every key still resets the auto-off timer as stock's on_wm_keyup_fun does, also one the payload
 * consumes. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

extern int ringnav(void *ctx, void *event), ringnav_keydown(void *ctx, void *event);
extern int compact_now_playing(void);
extern int stock_home_trampoline(void *win, void *ctx), ringnav_keylong(void *, void *);

unsigned char m1_key_lockout __attribute__((section(".scratch")));
unsigned char m1_boot_key_guard __attribute__((section(".scratch")));
unsigned char m1_return_latch __attribute__((section(".scratch")));
static struct {
    int bound;
    unsigned lockout_at;  /* when the centre key last set the lockout */
    unsigned held_back;   /* Previous fired its hold: its release is not a Back */
} in __attribute__((section(".scratch")));

/* A centre release drops wheel ticks for 800 ms, counted down every 100 ms, as the Q2's stock did
 * (KEY_LOCKOUT); ringnav() keeps only the first LOCKOUT_KEEP x 100 ms of it. */
static void lockout_tick(void) {
    if (!m1_key_lockout) return;
    unsigned spent = (unsigned)time_now_ms() - in.lockout_at;
    m1_key_lockout = spent >= 800 ? 0 : (unsigned char)(8 - spent / 100);
}

static const char *top_name(void) {
    void *top = window_manager_get_top_window(window_manager());
    return top ? widget_get_prop_str(top, "name", "") : "";
}

/* Previous is Back everywhere but Now Playing, where it stays the previous track. */
static int back_key(unsigned key) {
    return key == KEY_BACK_BTN && strcmp(top_name(), "playing_page");
}

/* What the Q2's on_wm_keyup_before_fun did before ringnav() saw a release: the auto-off timer, the
 * centre key's wheel lockout (set here, dropping wheel ticks while it lasts) and the latch a long
 * Return arms (its release goes nowhere). Returns 11 (RET_STOP) for a release to drop. */
int m1_keyup_filter(void *ctx, void *event) {
    (void)ctx;
    unsigned key = (unsigned)I(event, EVENT_KEY);
    reset_poweroptions_timer(1, 1, 1);
    lockout_tick();
    if (key == KEY_CENTER) {
        m1_key_lockout = 8;
        in.lockout_at = (unsigned)time_now_ms();
        return 0;
    }
    if ((key == KEY_PREV || key == KEY_NEXT) && m1_key_lockout > 0 && g_backlight_status) return 11;
    if (key == KEY_RETURN && m1_return_latch) {
        m1_return_latch = 0;
        return 11;
    }
    return 0;
}

/* Q2POD WHEELREVERSE (Display's Wheel row, crossfade.c): 1 swaps the wheel's two directions. */
static int reverse_read, reverse;
int m1_wheel_reverse(void) {
    if (!reverse_read) {
        char v[8] = "";
        toolsReadConfig("/mnt/data/config.ini", "Q2POD", "WHEELREVERSE", v, "0");
        reverse = v[0] == '1';
        reverse_read = 1;
    }
    return reverse;
}
void m1_wheel_reverse_set(int on) {
    reverse = on != 0;
    reverse_read = 1;
    write_int_config(reverse, "Q2POD", "WHEELREVERSE");
}
static void wheel_turn(void *event) {
    unsigned key = (unsigned)I(event, EVENT_KEY);
    if ((key == KEY_PREV || key == KEY_NEXT) && m1_wheel_reverse())
        I(event, EVENT_KEY) = key == KEY_PREV ? KEY_NEXT : KEY_PREV;
}

static int m1_keyup(void *ctx, void *event) {
    wheel_turn(event);
    unsigned key = (unsigned)I(event, EVENT_KEY);
    if (key == KEY_BACK_BTN && in.held_back) { /* the hold went to Now Playing */
        in.held_back = 0;
        return 11;
    }
    if (!back_key(key)) return ringnav(ctx, event);
    I(event, EVENT_KEY) = KEY_RETURN; /* the window manager's own copy of the release */
    int result = ringnav(ctx, event);
    if (result || !g_backlight_status) return result ? result : 11;
    /* Nothing took the Back: leave the page, as the on-screen back button does. Home has none. */
    if (strcmp(top_name(), "home_page")) navigator_back();
    return 11;
}

/* ringnav_keydown runs the stock key-down filter for what it does not take; the M1 has none. */
int stock_keydown_trampoline(void *ctx, void *event) {
    (void)ctx, (void)event;
    return 0;
}

static int m1_keydown(void *ctx, void *event) {
    wheel_turn(event);
    unsigned key = (unsigned)I(event, EVENT_KEY);
    if (back_key(key)) return 11; /* no page sees the press of a Back */
    return ringnav_keydown(ctx, event);
}

/* on_wm_keylong_fun (stock: the power key's hold, Shut Down?). Previous held opens Now Playing,
 * or leaves it, once; its release is then dropped. Every other hold goes to ringnav_keylong (the
 * Play/Pause queue menu), which runs the stock body for what it does not take. */
int m1_keylong(void *ctx, void *event) {
    if (event && (unsigned)I(event, EVENT_KEY) == KEY_BACK_BTN && g_backlight_status) {
        in.held_back = 1;
        compact_now_playing();
        return 11;
    }
    return ringnav_keylong(ctx, event);
}

/* home_page_init: stock builds Home and registers the window manager's own key and pointer
 * callbacks; the payload's key filters join them once. */
int m1_home(void *win, void *ctx) {
    int result = stock_home_trampoline(win, ctx);
    void *wm = window_manager();
    if (wm && !in.bound) {
        in.bound = widget_on(wm, EVT_KEY_DOWN_BEFORE, m1_keydown, (void *)0) &&
                   widget_on(wm, EVT_KEY_UP_BEFORE, m1_keyup, (void *)0);
    }
    return result;
}
