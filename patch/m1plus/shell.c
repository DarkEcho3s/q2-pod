/* Experimental M1 Plus V2.1 UI adapter. See docs/m1plus-port.md.
 * Stock AWTK, decoding, audio, power and storage remain in charge.
 * No Q2 widget structures, streaming modules or player patches are linked. */
#include "input.h"
#include "m1_platform.h"

#define NIL ((void *)0)
#define CLICK 0x10c
#define DESTROY 12
#define STOP 11
#define CONFIG "/mnt/data/m1pod-wheel-nav"
#define TRACE_MARKER "/mnt/mmc/m1pod-trace.enable"
#define TRACE_LOG "/mnt/mmc/m1pod-input.log"
#define ROWS 6

extern int stock_application_init(void);
extern int stock_window_manager_dispatch_input_event(void *, void *);
extern int stock_widget_on_keyup(void *, void *);
extern int stock_on_wm_keylong_fun(void *, void *);

static struct m1_input input;
static void *menu, *rows[ROWS], *footer;
static unsigned generation = 1, selected, suppress_key, suppress_active, keyup_seen;
static int wheel_enabled, tracing;
static unsigned trace_count;
static const char *titles[ROWS] = {
    "Music", "Folders", "Now Playing", "Audio Settings", "Wheel navigation: Off", "Stock home"
};

static unsigned event_word(void *event, unsigned index) {
    return ((const unsigned *)event)[index];
}
static struct m1_context context(void *wm) {
    struct m1_context c;
    c.page = menu && window_manager_get_top_window(wm) == menu ? (unsigned)menu : 0;
    c.generation = generation;
    c.enabled = wheel_enabled;
    c.awake = stock_backlight_status != 0;
    c.unlocked = !stock_keylock_flag && !stock_lockscreen_pageflag;
    c.stable = !stock_standby_mode && !stock_boot_guidestep && !window_manager_is_animating(wm);
    c.reversed = stock_rotate_mode == 1;
    return c;
}
static void prop(void *w, const char *name, const char *value) {
    if (w) widget_set_prop_str(w, name, value);
}
static void text_style(void *w, const char *background, const char *foreground) {
    prop(w, "style:normal:bg_image", "");
    prop(w, "style:normal:bg_color", background);
    prop(w, "style:normal:text_color", foreground);
    prop(w, "style:normal:font_size", "21");
    prop(w, "style:normal:border", "0");
    prop(w, "style:normal:round_radius", "0");
    prop(w, "style:pressed:bg_color", "#2868B7");
    prop(w, "style:pressed:text_color", "#FFFFFF");
    prop(w, "style:over:bg_color", background);
    prop(w, "style:over:text_color", foreground);
}
static void repaint(void) {
    unsigned i;
    for (i = 0; i < ROWS; ++i) {
        text_style(rows[i], i == selected ? "#2868B7" : "#F8F8F8",
                   i == selected ? "#FFFFFF" : "#171717");
        widget_set_state(rows[i], "normal");
    }
    widget_set_text_utf8(rows[4], wheel_enabled ? "Wheel navigation: On" : "Wheel navigation: Off");
}
static int save_setting(int enabled) {
    char value[2];
    int ok;
    void *f = fopen(CONFIG ".tmp", "wb");
    if (!f) return 0;
    value[0] = enabled ? '1' : '0'; value[1] = '\n';
    ok = fwrite(value, 1, 2, f) == 2;
    if (ok) ok = fflush(f) == 0;
    if (ok) ok = fsync(fileno(f)) == 0;
    if (fclose(f)) ok = 0;
    return ok && rename(CONFIG ".tmp", CONFIG) == 0;
}
static void activate(unsigned row) {
    if (!menu || row >= ROWS) return;
    selected = row;
    ++generation;
    if (row == 4) {
        if (save_setting(!wheel_enabled)) {
            wheel_enabled = !wheel_enabled;
            widget_set_text_utf8(footer, "Wheel scrolls this menu.\nNow Playing keeps volume control.");
        } else widget_set_text_utf8(footer, "Could not save wheel setting.");
        repaint();
        return;
    }
    if (row == 5) { window_close(menu); return; }
    repaint();
    if (row == 0) navigator_to("localclass_page");
    if (row == 1) navigator_to("folder_page");
    if (row == 2) on_backtoplayer_onclick(NIL, NIL);
    if (row == 3) navigator_to("playset/playset_page");
}
static int clicked(void *ctx, void *event) {
    (void)event;
    activate((unsigned)ctx);
    return 0;
}
static int destroyed(void *ctx, void *event) {
    unsigned i;
    (void)event;
    if (menu == ctx) {
        menu = footer = NIL;
        for (i = 0; i < ROWS; ++i) rows[i] = NIL;
        ++generation;
    }
    return 0;
}
static int open_menu(void *ctx, void *event) {
    unsigned i;
    void *w, *title;
    (void)ctx; (void)event;
    if (menu) return 0;
    w = window_create(NIL, 0, 0, 0, 0);
    if (!w) return 0;
    if (widget_get_prop_int(w, "w", 0) != 320 || widget_get_prop_int(w, "h", 0) < 440) {
        window_close(w); return 0;
    }
    menu = w;
    if (!widget_on(w, DESTROY, destroyed, w)) { menu = NIL; window_close(w); return 0; }
    widget_set_name(w, "m1pod_menu");
    prop(w, "style:normal:bg_color", "#F8F8F8");
    title = label_create(w, 0, 0, 320, 52);
    if (!title) goto failed;
    text_style(title, "#E5E5E5", "#171717");
    widget_set_text_utf8(title, "M1-pod · Preview");
    for (i = 0; i < ROWS; ++i) {
        rows[i] = button_create(w, 0, 54 + (int)i*52, 320, 52);
        if (!rows[i] || !widget_on(rows[i], CLICK, clicked, (void *)i)) goto failed;
        widget_set_text_utf8(rows[i], titles[i]);
        prop(rows[i], "style:normal:text_align_h", "left");
        prop(rows[i], "style:normal:margin_left", "18");
    }
    footer = label_create(w, 8, 378, 304, 60);
    if (!footer) goto failed;
    text_style(footer, "#F8F8F8", "#555555");
    prop(footer, "style:normal:font_size", "14");
    widget_set_text_utf8(footer, "Wheel scrolls this menu.\nNow Playing keeps volume control.");
    selected = 0; ++generation;
    repaint();
    return 0;
failed:
    window_close(w);
    return 0;
}
static int install_entry(const void *unused) {
    void *home, *slides, *indicator, *page, *button;
    (void)unused;
    if (stock_boot_guidestep) return 8;
    home = widget_lookup(window_manager(), "home_page", 1);
    if (!home || widget_lookup(home, "m1pod_entry", 1)) return 8;
    slides = widget_lookup(home, "home_sview", 1);
    indicator = widget_lookup(home, "home_sindicator", 1);
    if (!slides || !indicator) return 8;
    page = view_create(slides, 0, 0, 320, 364);
    if (!page) return 8;
    button = button_create(page, 12, 100, 296, 140);
    if (!button || !widget_on(button, CLICK, open_menu, NIL)) { widget_destroy(page); return 8; }
    text_style(button, "#2868B7", "#FFFFFF");
    widget_set_text_utf8(button, "M1-pod preview");
    widget_set_name(page, "m1pod_entry");
    slide_indicator_set_max(indicator, (unsigned)widget_count_children(slides));
    return 8;
}
int m1_application_init(void) {
    int result = stock_application_init();
    char b[3];
    void *f;
    if (result) return result;
    f = fopen(CONFIG, "rb");
    if (f) {
        wheel_enabled = fread(b, 1, 3, f) == 2 && b[0] == '1' && b[1] == '\n';
        fclose(f);
    }
    f = fopen(TRACE_MARKER, "rb");
    if (f) {
        fclose(f);
        f = fopen(TRACE_LOG, "wb");
        if (f) { tracing = fclose(f) == 0; }
    }
    timer_add(install_entry, NIL, 500);
    return result;
}
int m1_keylong(void *ctx, void *event) {
    struct m1_context c = context(window_manager());
    if (event) m1_route(&input, &c, M1_LONG, event_word(event, 6));
    return stock_on_wm_keylong_fun(ctx, event);
}
int m1_keyup(void *widget, void *event) {
    if (event && suppress_active && event_word(event, 0) == M1_UP &&
        event_word(event, 6) == suppress_key) {
        keyup_seen = 1;
        return STOP;
    }
    return stock_widget_on_keyup(widget, event);
}
static void log_event(unsigned type, unsigned key, unsigned page, int action, int seen, int before) {
    char line[128];
    int n;
    void *f;
    if (!tracing || trace_count >= 256) return;
    ++trace_count;
    n = snprintf(line, sizeof line, "%u type=%u key=%u menu=%u action=%d suppressed=%d volume=%d/%d\n",
                 trace_count, type, key, page != 0, action, seen, before, stock_volume);
    if (n <= 0 || (unsigned)n >= sizeof line) return;
    f = fopen(TRACE_LOG, "ab");
    if (!f) { tracing = 0; return; }
    if (fwrite(line, 1, (unsigned)n, f) != (unsigned)n) tracing = 0;
    if (fclose(f)) tracing = 0;
}
int m1_dispatch(void *wm, void *event) {
    struct m1_context c;
    unsigned type, key, old_active = suppress_active, old_key = suppress_key, old_seen = keyup_seen;
    int action, result, seen, before;
    if (!wm || !event) return stock_window_manager_dispatch_input_event(wm, event);
    type = event_word(event, 0);
    /* A touch during a held wheel click must not activate a newly touched row
     * when the wheel is released, even if the page identity has not changed. */
    if (type == 0xff) m1_cancel_owned(&input);
    if (type != M1_DOWN && type != M1_UP) return stock_window_manager_dispatch_input_event(wm, event);
    key = event_word(event, 6);
    c = context(wm);
    action = m1_route(&input, &c, type, key);
    suppress_key = key; suppress_active = action != M1_PASS; keyup_seen = 0;
    before = stock_volume;
    result = stock_window_manager_dispatch_input_event(wm, event);
    seen = keyup_seen;
    suppress_active = old_active; suppress_key = old_key; keyup_seen = old_seen;
    log_event(type, key, c.page, action, seen, before);
    if (action != M1_PASS && seen) {
        reset_poweroptions_timer(1, 1, 1);
        /* A different volume path invalidates the interception assumption.
         * Disable navigation for this session, and preserve the trace. */
        if (before != stock_volume) {
            wheel_enabled = 0; ++generation;
            if (menu) { repaint(); widget_set_text_utf8(footer, "Wheel routing needs verification."); }
            return result;
        }
        if (c.page && menu && window_manager_get_top_window(wm) == menu) {
            if (action == M1_PREVIOUS || action == M1_NEXT) {
                selected = action == M1_PREVIOUS ? (selected+ROWS-1)%ROWS : (selected+1)%ROWS;
                ++generation; repaint();
            } else if (action == M1_CONFIRM) activate(selected);
        }
    }
    return result;
}
