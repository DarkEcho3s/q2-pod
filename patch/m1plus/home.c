/* The M1 Plus's Home (docs/m1plus.md#home).
 *
 * Stock Home is a grid of cards, one per HOMEMENU id in the user's chosen order (pdeq_choicemenu),
 * each an image named by its id whose click (home_card_click, 0x533b80) opens that id's page. The
 * two streaming cards, HiFi Music (0) and TIDAL (1), are Coverflow and More instead: the builder
 * points their names in the HOMEMENU table (get_homemenu_showinfo's) at m1_card_names, which are
 * also their labels (no translation has them) and, in Home's theme, their styles' names
 * (home_Coverflow_style and home_More_style, stock's two renamed with their images; tools/m1plus.py).
 * Home's menu editor lists them by the same names.
 *
 * iPod Home is a list over the playing track's art (tools/m1plus.py m1_ipod_home; coverflow.c lays
 * it out): Now Playing, Music (the whole Library, navigation.c m1_more_open), Coverflow, Folders,
 * Shuffle and Settings, whose list (Playback, System, Update Library) slides into the list's
 * place. Stock still builds its card grid, hidden under them. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

extern int stock_card_trampoline(void *ctx, void *event), coverflow_open(void *ctx, void *event),
    m1_more_open(int music), shuffle_open(void), compact_now_playing(void);

const char m1_card_coverflow[] = "Coverflow", m1_card_more[] = "More";

/* ctx is the card's image (sub_533d8c binds it so). */
int m1_card_click(void *ctx, void *event) {
    const char *name = ctx ? widget_get_prop_str(ctx, "name", "") : "";
    if (!strcmp(name, "0")) return coverflow_open(ctx, event);
    if (!strcmp(name, "1")) return m1_more_open(0);
    return stock_card_trampoline(ctx, event);
}

/* A HOMEMENU id's page, as its card opens it: stock's click reads only the card's name (atoi of
 * widget_t's name, @0x10), so a stand-in names the id. */
int m1_card_open(int id) {
    char name[4];
    void *card[8] = { 0 };
    tk_snprintf(name, sizeof name, "%d", id);
    card[4] = name;
    return stock_card_trampoline(card, (void *)0);
}

#if IPOD
static int card_row(void *ctx, void *event) {
    (void)event;
    return m1_card_open((int)(long)ctx);
}
static int music_row(void *ctx, void *event) {
    (void)ctx, (void)event;
    return m1_more_open(1);
}
static int playing_row(void *ctx, void *event) {
    (void)ctx, (void)event;
    if (mclGetPlayStatus() < 0 || !P(mcl_pdeqplaylist, 0) || !deque_size(P(mcl_pdeqplaylist, 0)))
        return toast("Nothing playing"), 0;
    return compact_now_playing();
}
static int shuffle_row(void *ctx, void *event) {
    (void)ctx, (void)event;
    return shuffle_open();
}

/* Home's rows, as tools/m1plus.py names them (img_<row>, the row's tap target). Coverflow and
 * Settings bind in coverflow.c, as on the Q2. */
void m1_home_bind(void *win) {
    static const struct {
        const char *name;
        int (*click)(void *, void *);
        long ctx;
    } rows[] = {
        { "img_playing", playing_row, 0 }, { "img_music", music_row, 0 },
        { "img_folder", card_row, 4 },     { "img_shuffle", shuffle_row, 0 },
        { "img_playset", card_row, 16 },   { "img_sysset", card_row, 17 },
        { "img_update", card_row, 2 },
    };
    for (unsigned i = 0; i < sizeof rows / sizeof *rows; ++i) {
        void *w = widget_lookup(win, rows[i].name, 1);
        if (w) widget_on(w, EVT_CLICK, rows[i].click, (void *)rows[i].ctx);
    }
}
#endif
