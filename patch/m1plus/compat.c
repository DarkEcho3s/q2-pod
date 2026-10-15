/* Small semantic adapters for toolkit APIs absent from M1's exported ABI. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

unsigned char m1_q2_latches[3];
/* Only synthesized, policy-approved releases enter ringnav on M1. Its native
 * key-up handler runs on every unowned physical release in the stock dispatcher. */
int stock_keyup_trampoline(void *ctx, void *event) { (void)ctx; (void)event; return 0; }

int config_playmode(int mode, int notify) {
    extern int ringnav_mode(int);
    int result = ringnav_mode(mode);
    write_int_config(mode, "PLAYSET", "PLAYMODE");
    if (notify) m1_notify_playmode(mode);
    return result;
}

int tk_strcmp(const char *a, const char *b) {
    if (a == b) return 0;
    if (!a) return -1;
    if (!b) return 1;
    return strcmp(a, b);
}
int tk_str_end_with(const char *s, const char *suffix) {
    if (!s || !suffix) return 0;
    unsigned a = strlen(s), b = strlen(suffix);
    return a >= b && !memcmp(s+a-b, suffix, b);
}
void set_hscroll_label_attribute(void *w) {
    if (!w) return;
    widget_set_prop_str(w, "speed", "0.1");
    widget_set_prop_int(w, "lull", 2000);
    hscroll_label_set_ellipses(w, 1);
}
char *window_manager_get_input_device_status(void *wm) {
    /* window_manager_default dispatch passes wm+0xf8 at 68ffc8. */
    return wm ? (char *)wm+0xf8 : 0;
}
int m1_slide_spacing(void *w) { return widget_get_prop_int(w, "_pod_spacer", 0); }
int slide_menu_set_spacer(void *w, int spacing) {
    return widget_set_prop_int(w, "_pod_spacer", spacing);
}
int slide_menu_item_width(void *w) { return w ? I(w, W_H) : 0; }
int slide_menu_on_scroll_done(void *w, void *event) {
    (void)event;
    int n = (int)widget_count_children(w), stride = slide_menu_item_width(w)+SLIDE_SPACING(w);
    if (n <= 0 || stride <= 0) return 0x10;
    int offset = I(w, SLIDE_OFFSET);
    int steps = (offset + (offset < 0 ? -stride/2 : stride/2)) / stride;
    int index = (I(w, SLIDE_INDEX)-steps) % n;
    I(w, SLIDE_OFFSET) = 0;
    P(w, SLIDE_ANIMATOR) = 0;
    return slide_menu_set_value(w, index < 0 ? index+n : index);
}
int slide_menu_scroll_to_next(void *w) {
    unsigned n = widget_count_children(w);
    return n ? slide_menu_set_value(w, (I(w, SLIDE_INDEX)+1) % n) : 0x10;
}
int slide_menu_scroll_to_prev(void *w) {
    int n = (int)widget_count_children(w);
    return n > 0 ? slide_menu_set_value(w, (I(w, SLIDE_INDEX)+n-1) % n) : 0x10;
}

/* M1 has no album-artist-only query export. Reuse its native song parser and
 * container copy/destructor operations, retaining exactly matching records. */
int getMusicByAlbumArtist(const char *artist) {
    int result = getAllMusic(0);
    void *list = P(tools_pdeq_directory, 0);
    if (!list) return result;
    void *copy = _create_deque("stSongInfo");
    if (!copy) return -1;
    deque_init_copy(copy, list);
    deque_clear(list);
    for (unsigned i = 0, n = deque_size(copy); i < n; ++i) {
        void *r = deque_at(copy, i);
        const char *tag = P(r, REC_ALBUM_ARTIST);
        if (artist ? tag && !tk_strcmp(tag, artist) : !tag || !*tag) _deque_push_back(list, r);
    }
    deque_destroy(copy);
    return (int)deque_size(list);
}
