/* The M1 Plus's Home cards (docs/m1plus.md#home).
 *
 * Stock Home is a grid of cards, one per HOMEMENU id in the user's chosen order (pdeq_choicemenu),
 * each an image named by its id whose click (home_card_click, 0x533b80) opens that id's page. The
 * two streaming cards, HiFi Music (0) and TIDAL (1), are Coverflow and More instead: the builder
 * points their names in the HOMEMENU table (get_homemenu_showinfo's) at m1_card_names, which are
 * also their labels (no translation has them) and, in Home's theme, their styles' names
 * (home_Coverflow_style and home_More_style, stock's two renamed with their images; tools/m1plus.py).
 * Home's menu editor lists them by the same names. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

extern int stock_card_trampoline(void *ctx, void *event), coverflow_open(void *ctx, void *event),
    m1_more_open(void);

const char m1_card_coverflow[] = "Coverflow", m1_card_more[] = "More";

/* ctx is the card's image (sub_533d8c binds it so). */
int m1_card_click(void *ctx, void *event) {
    const char *name = ctx ? widget_get_prop_str(ctx, "name", "") : "";
    if (!strcmp(name, "0")) return coverflow_open(ctx, event);
    if (!strcmp(name, "1")) return m1_more_open();
    return stock_card_trampoline(ctx, event);
}
