/* Q2 routines the M1 Plus firmware lacks, under the Q2's names (tools/m1plus.py M1_SHIMS): AWTK
 * helpers its older toolkit predates, and two of the Q2 app's own. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

/* AWTK's tk_strcmp: NULL sorts first, as an empty string would not. */
int tk_strcmp(const char *a, const char *b) {
    if (a == b) return 0;
    if (!a) return -1;
    if (!b) return 1;
    return strcmp(a, b);
}

int tk_str_end_with(const char *s, const char *end) {
    if (!s || !end) return 0;
    unsigned n = strlen(s), m = strlen(end);
    return n >= m && !memcmp(s + n - m, end, m);
}

/* The default window manager keeps its input_device_status_t inline (WM_INPUT_STATUS). */
char *window_manager_get_input_device_status(void *wm) {
    return wm ? (char *)wm + WM_INPUT_STATUS : (char *)0;
}

/* The Q2's row label setup (0x4e80b0): a 2 s pause at each end of its scroll and an ellipsis; the
 * speed stays the label's default. */
void set_hscroll_label_attribute(void *label) {
    if (!label) return;
    hscroll_label_set_lull(label, 2000);
    hscroll_label_set_ellipses(label, 1);
}

/* Only the Legacy outline strokes rounded rects; non-zero falls back to its square strokes. */
int canvas_stroke_rounded_rect(void *c, const void *r, const void *s, const void *color,
                               unsigned radius, unsigned width) {
    (void)c, (void)r, (void)s, (void)color, (void)radius, (void)width;
    return 1;
}

/* A zeroed stand-in for the Q2 state the M1 does not keep (tools/m1plus.py maps those names here):
 * its test mode, the album page's grid/list mode. */
unsigned char m1_zeros[1024] __attribute__((section(".scratch")));

/* slide_menu (the M1's older AWTK): items are as wide as the menu is high, without spacing, and
 * stepping a card is stock's own static scroll_to (0x612278) by that width, as its keys do. */
int slide_menu_item_width(void *w) { return w ? I(w, W_H) : 0; }
#define slide_menu_scroll_to ((int (*)(void *, int))0x612278u)
int slide_menu_scroll_to_next(void *w) { return slide_menu_scroll_to(w, I(w, SLIDE_OFFSET) - I(w, W_H)); }
int slide_menu_scroll_to_prev(void *w) { return slide_menu_scroll_to(w, I(w, SLIDE_OFFSET) + I(w, W_H)); }

/* The Q2's Local Songs search button (0x5241c4) opens its search dialog; the M1's search is a page,
 * as its own search buttons open it (0x523304). */
int stock_search(void *page, void *event) {
    (void)page, (void)event;
    return navigator_to("search_page");
}

/* The Q2's config_playmode (0x4f3fe8): the player's mode, saved as the Play mode page saves it. */
int config_playmode(int mode, int save) {
    int result = mclSetPlayMode(mode);
    if (save) write_int_config(mode, "PLAYSET", "PLAYMODE");
    return result;
}

/* The M1's charger (toolsSetChargeSwitch writes /sys/class/power_supply/battery/charger) and its
 * state (toolsGetChargeStatus: 1 or 2 while charging, as the Q2's g_power_chargestate). */
int switch_charge_enable(int on) { return toolsSetChargeSwitch(on ? 1 : 0); }

/* The Q2's getMusicByAlbumArtist (0x4ff3d4): getMusicBySonger's query on the album artist, which the
 * M1 has only within an album (getMusicByAlbumAndAlbumSonger). The same rows reach the same
 * callback (0x4e9058, getMusicBySonger's), into tools_pdeq_directory. */
#define song_row ((int (*)(void *, int, char **, char **))0x4e9058u)
int getMusicByAlbumArtist(const char *name) {
    char sql[1024], quoted[600];
    if (!name || !*name)
        snprintf(sql, sizeof sql, "select * from %s where albumsonger=\"\"", "songtable");
    else {
        snprintf(quoted, sizeof quoted - 64, "%s", name);
        toolsReplceQuote(quoted, strlen(quoted));
        snprintf(sql, sizeof sql, "select * from %s where albumsonger like '%s'", "songtable", quoted);
    }
    return toolsQueryDbTable("/mnt/data/database.db", sql, song_row, 0);
}

/* libcstl's deque_init_copy and deque_pop_back, which the M1's demo does not import: an initialised
 * copy (deque_assign copies each element with the deque's own type, as init_copy does), and the
 * last element erased through the iterators it does import. A libcstl iterator is 7 words, passed
 * and returned by value (clearBtLinkItem's deque_erase call). */
void deque_init_copy(void *dst, const void *src) {
    deque_init(dst);
    deque_assign(dst, src);
}
void deque_pop_back(void *dq) {
    unsigned n = dq ? deque_size(dq) : 0;
    if (!n) return;
    m1_iterator it = deque_begin(dq);
    while (--n) it = iterator_next(it);
    deque_erase(dq, it);
}

/* The Q2 theme's style names the payload uses, as the M1 theme's nearest (styles/default.bin): its
 * rows are list_item_style's dark cards and its labels srlabel_* (hscroll_label) or label_* and
 * navbar_* (label). Any other name passes through. */
static const char *const m1_styles[][2] = {
    { "s_listitem_black", "list_item_style" },
    { "s_scrlabel_white20l", "srlabel_leftwhite20_style" },
    { "s_scrlabel_white24l", "srlabel_leftwhite22_style" },
    { "s_scrlabel_white20c", "srlabel_msgwhite_style" },
    { "s_scrlabel_white20r", "srlabel_item_right_gray16_styl" },
    { "s_label_white20l", "navbar_leftlabel_white" },
    { "s_label_white20c", "label_centerwhite20_style" },
    { "s_label_white18c", "label_centerwhite20_style" },
    { "s_btn_listitem", "btn_tablerow_style" },
};
int widget_use_style(void *w, const char *style) {
    for (unsigned i = 0; style && i < sizeof m1_styles / sizeof *m1_styles; ++i)
        if (!strcmp(style, m1_styles[i][0])) {
            style = m1_styles[i][1];
            break;
        }
    return stock_widget_use_style(w, style);
}

/* The Q2 images the payload names, as the M1's (images/xx). */
static const char *const m1_images[][2] = {
    { "play_fav", "p_fav" },        { "play_unfav", "p_unfav" },
    { "list_into", "right_arrow" }, { "default_album_big", "defaultcover" },
    { "switch_on", "sset_on" },     { "switch_off", "sset_off" },
    { "select", "selected" },
};
int image_base_set_image(void *w, const char *name) {
    for (unsigned i = 0; name && i < sizeof m1_images / sizeof *m1_images; ++i)
        if (!strcmp(name, m1_images[i][0])) {
            name = m1_images[i][1];
            break;
        }
    return stock_image_base_set_image(w, name);
}
