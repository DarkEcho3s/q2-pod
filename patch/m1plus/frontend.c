/* M1-specific page routing and the Q2 Pod Home/Library widget trees. Native
 * library queries receive M1 class IDs and native page contexts. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

extern int ringnav_localmusic(void *, void *);
extern void *list_row(void *, const char *, int (*)(void *, void *), void *);

static void *library;
static int back(void *ctx, void *event);
void *m1_value_editor(void) {
    void *win = window_create(0, 0, 0, 0, 0);
    if (!win) return 0;
    widget_set_name(win, "bootvol_page");
    widget_set_prop_str(win, "style:normal:bg_color", "#000000");
    void *nav = view_create(win, 0, 0, POD_SCREEN_W, 50);
    widget_set_name(nav, "view_navbar");
    void *title = label_create(nav, 40, 0, POD_SCREEN_W-80, 50);
    widget_use_style(title, "s_label_white20c");
    void *b = button_create(nav, 0, 0, 40, 50);
    widget_set_text_utf8(b, "<"); widget_on(b, EVT_CLICK, back, win);
    void *sw = image_create(win, 132, 62, 56, 32);
    widget_set_name(sw, "img_bootswitch"); widget_set_prop_int(sw, "clickable", 1);
    void *view = view_create(win, 0, 110, 320, 300);
    widget_set_name(view, "view_bootvol");
    void *value = label_create(view, 60, 0, 200, 48);
    widget_set_name(value, "label_vol"); widget_use_style(value, "s_label_white20c");
    void *slider = widget_factory_create_widget(widget_factory(), "slider", view, 20, 62, 280, 60);
    widget_set_name(slider, "slider_bootvol");
    b = button_create(view, 40, 150, 64, 64); widget_set_name(b, "img_dec"); widget_set_text_utf8(b, "-");
    b = button_create(view, 216, 150, 64, 64); widget_set_name(b, "img_add"); widget_set_text_utf8(b, "+");
    return win;
}
static int back(void *ctx, void *event) {
    (void)event;
    if (ctx) window_close(ctx); else navigator_back();
    return 0;
}
static int library_gone(void *ctx, void *event) {
    (void)event;
    if (library == ctx) library = 0;
    return 0;
}

void *m1_lookup(void *parent, const char *name, int recursive) {
    void *w = m1_native_widget_lookup(parent, name, recursive);
    if (w || !name) return w;
    static const char *const aliases[][2] = {
        {"view_navbar", "navigationbar_view"}, {"img_return", "btn_return"},
        {"img_fav", "btn_fav"}, {"img_more", "btn_more"}, {"img_playmode", "btn_playmode"},
        {"img_cover", "img_playcover"},
        {"scroll_view_display", "display_scrollview"}, {"scroll_view_sysset", "sysset_scrollview"},
        {"scroll_view_playset", "playset_scrollview"}, {"scroll_view_bluetooth", "bluetooth_scrollview"},
        {"scroll_view_album", "album_scrollview"}, {"scroll_view_playlist", "playlist_scrollview"},
        {"scroll_view_standby", "standby_scrollview"},
        {"table_client_localclass", "localclass_table_client"},
        {"view_bootvol", "bootvol_view"}, {"slider_bootvol", "vol_slider"},
        {"img_dec", "btn_dec"}, {"img_add", "btn_add"},
        {"clock_time", "dclock_time"}, {"clock_date", "dclock_date"},
        {"scroll_view", "scrollview_sortselect"}, {"scrlabel_title", "hscroll_label"},
        {"img_return", "button_return"}, {"img_bt", "img_btclass"}, {"img_state", "img_playstate"},
    };
    for (unsigned i = 0; i < sizeof aliases / sizeof *aliases; ++i)
        if (!strcmp(name, aliases[i][0])) {
            w = m1_native_widget_lookup(parent, aliases[i][1], recursive);
            if (w) return w;
        }
    if (tk_str_start_with(name, "scroll_view_")) {
        char native[80];
        tk_snprintf(native, sizeof native, "%s_scrollview", name+12);
        w = m1_native_widget_lookup(parent, native, recursive);
        if (w) return w;
    }
    if (tk_str_start_with(name, "table_client_")) {
        char native[80];
        tk_snprintf(native, sizeof native, "%s_table_client", name+13);
        w = m1_native_widget_lookup(parent, native, recursive);
        if (w) return w;
    }
    return 0;
}

static const char *native_path(const char *path) {
    if (!path) return path;
    if (!strcmp(path, "dialog/updatemusic_dialog")) return "dialog/scanmusic_dialog";
    if (!strcmp(path, "localmusic/artistinfo_page")) return "album_page";
    if (tk_str_start_with(path, "localmusic/")) return path+11;
    return path;
}

static int library_open(void) {
    if (library) return 0;
    void *win = window_create(0, 0, 0, 0, 0);
    if (!win) return 0x10;
    library = win;
    widget_set_name(win, "localmusic_page");
    widget_set_prop_str(win, "style:normal:bg_color", "#000000");
    widget_on(win, EVT_DESTROY, library_gone, win);
    ringnav_localmusic(win, 0);
    return 0;
}

int m1_navigate(const char *path) {
    if (path && !strcmp(path, "localmusic_page")) return library_open();
    return m1_native_navigator_to(native_path(path));
}
int m1_navigate_context(const char *path, const void *ctx) {
    if (path && !strcmp(path, "localmusic_page")) return library_open();
    return m1_native_navigator_to_with_context(native_path(path), ctx);
}

static void *list(void *win, const char *name, int y, int height, int row) {
    char n[64];
    void *v = list_view_create(win, 0, y, POD_SCREEN_W, height);
    tk_snprintf(n, sizeof n, "list_view_%s", name); widget_set_name(v, n);
    widget_set_prop_int(v, "item_height", row);
    widget_set_prop_str(v, "style:normal:bg_color", "#00000000");
    void *s = scroll_view_create(v, 0, 0, POD_SCREEN_W, height);
    tk_snprintf(n, sizeof n, "scroll_view_%s", name); widget_set_name(s, n);
    widget_set_prop_str(s, "self_layout", "default(x=0,y=0,w=100%,h=100%)");
    widget_set_prop_int(s, "yslidable", 1);
    return s;
}

static int library_click(void *ctx, void *event) {
    (void)event;
    unsigned row = (unsigned)ctx;
    static const unsigned classes[] = {0, 0xf001, 0xf003, 0xf004, 0xf006,
                                       0xf002, CLASS_FAVORITES, 0xf008, 0xf007, 0xf009};
    if (!row) return navigator_to("dialog/scanmusic_dialog");
    if (row == 10) return navigator_to("playlist_page");
    if (row == 2) {
        const unsigned context[2] = {CLASS_ALBUMS, 0};
        return navigator_to_with_context("album_page", context);
    }
    return navigator_to_with_context(row == 3 || row == 4 ? "localclass_page" : "allmusic_page",
                                      (const void *)classes[row]);
}

/* Shared Library augmentation expects the eleven base rows in this order. */
int stock_localmusic_trampoline(void *win, void *ctx) {
    (void)ctx;
    if (!win) return 0x10;
    void *nav = view_create(win, 0, 0, POD_SCREEN_W, 48);
    widget_set_name(nav, "view_navbar");
    void *title = label_create(nav, 48, 0, POD_SCREEN_W-96, 48);
    widget_set_text_utf8(title, "Library"); widget_use_style(title, "s_label_white20c");
    void *b = button_create(nav, 0, 0, 48, 48);
    widget_set_text_utf8(b, "<"); widget_on(b, EVT_CLICK, back, win);
    void *view = list(win, "localmusic", 48, POD_CLIENT_H-48, 64);
    static const char *const titles[] = {"Update Library", "All Songs", "Albums", "Artists", "Genres",
        "Hi-Res", "Favorites", "Frequent", "Recently Played", "Recently Added", "Playlists"};
    static const char *const icons[] = {"local_update", "local_allmusic", "local_album", "local_artist",
        "local_genre", "local_hires", "local_fav", "local_frequentplay", "local_recentplay", "local_recentadd", "local_playlist"};
    for (unsigned i = 0; i < 11; ++i) {
        void *label = list_row(view, icons[i], library_click, (void *)i);
        widget_set_text_utf8(label, titles[i]);
    }
    return 0;
}

static int home_click(void *ctx, void *event) {
    (void)event;
    const char *path = ctx;
    if (!strcmp(path, "playing_page")) {
        static const int context[4] = {0, 0, 0xff, 2};
        return navigator_switch_to_with_context(path, context, 0);
    }
    return navigator_to(path);
}
static int home_back_click(void *ctx, void *event) {
    (void)ctx; (void)event;
    extern int m1_ui_back(void);
    return m1_ui_back();
}
static void home_rows(void *win, const char *name, const char *const *names,
                      const char *const *titles, const char *const *paths, unsigned n) {
    void *s = list(win, name, 30, POD_CLIENT_H-60, 56);
    for (unsigned i = 0; i < n; ++i) {
        char key[64];
        void *row = view_create(s, 0, (int)i*56, POD_SCREEN_W, 56);
        tk_snprintf(key, sizeof key, "btn_%s", names[i]); widget_set_name(row, key);
        void *label = hscroll_label_create(row, HOME_DOT_X+HOME_DOT+HOME_DOT_GAP, 0, 250, 56);
        tk_snprintf(key, sizeof key, "label_%s", names[i]); widget_set_name(label, key);
        widget_use_style(label, "s_scrlabel_white20l"); widget_set_text_utf8(label, titles[i]);
        set_hscroll_label_attribute(label);
        void *tap = image_create(row, 0, 0, POD_SCREEN_W, 56);
        tk_snprintf(key, sizeof key, "img_%s", names[i]); widget_set_name(tap, key);
        widget_set_prop_int(tap, "clickable", 1);
        if (paths[i]) widget_on(tap, EVT_CLICK, home_click, (void *)paths[i]);
    }
}

void m1_home_create(void *win) {
    if (!win || m1_native_widget_lookup(win, "list_view_home", 1)) return;
    /* Native timers retain their own hidden widgets for playback/boot state. */
    for (unsigned i = 0, n = widget_count_children(win); i < n; ++i) {
        void *w = widget_get_child(win, i);
        widget_set_visible(w, 0, 0); widget_set_sensitive(w, 0);
    }
    widget_set_prop_str(win, "style:normal:bg_color", "#000000");
    void *art = image_create(win, 0, 0, POD_SCREEN_W, POD_CLIENT_H);
    widget_set_name(art, "img_homeart"); widget_set_prop_str(art, "draw_type", "fill");
    static const char *const names[] = {"playing", "localmusic", "coverflow", "folder", "rockbox", "settings"};
    static const char *const titles[] = {"Now Playing", "Library", "Coverflow", "Folders", "Favorites", "Settings"};
    static const char *const paths[] = {"playing_page", "localmusic_page", 0, "folder_page", 0, 0};
    home_rows(win, "home", names, titles, paths, 6);
    static const char *const snames[] = {"homeback", "playset", "sysset"},
                            *const stitles[] = {"Back to Home", "Playback", "System"},
                            *const spaths[] = {0, "playset/playset_page", "systemset/sysset_page"};
    home_rows(win, "homeset", snames, stitles, spaths, 3);
    widget_on(widget_lookup(win, "img_homeback", 1), EVT_CLICK, home_back_click, 0);
    widget_set_visible(widget_lookup(win, "list_view_homeset", 1), 0, 0);
}
