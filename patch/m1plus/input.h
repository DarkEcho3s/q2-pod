#ifndef M1_INPUT_H
#define M1_INPUT_H

/* M1 Plus V2.1 AWTK values. These are NOT Linux evdev key codes. */
enum { M1_DOWN = 0x10f, M1_LONG = 0x110, M1_UP = 0x113,
       M1_POWER = 210, M1_VOL_UP = 220, M1_VOL_DOWN = 221 };
enum { M1_PASS, M1_DROP, M1_PREVIOUS, M1_NEXT, M1_CONFIRM };

struct m1_context {
    unsigned page;       /* nonzero identity of the supported foreground page */
    unsigned generation; /* changes on touch selection, navigation or setting changes */
    int enabled, awake, unlocked, stable, reversed;
};
struct m1_press {
    unsigned page, generation;
    unsigned active, owned, cancelled, long_press;
};
struct m1_input { struct m1_press keys[3]; };

/* Called once per physical DOWN/UP at the input dispatcher. DOWN always passes
 * to the toolkit: it owns pressed-key tracking and the long-press timer.
 * An owned UP is suppressed later, at widget_on_keyup, so toolkit bookkeeping
 * still runs. Long presses are observed separately in the stock WM callback. */
int m1_route(struct m1_input *, const struct m1_context *, unsigned type, unsigned key);
void m1_cancel_owned(struct m1_input *);
#endif
