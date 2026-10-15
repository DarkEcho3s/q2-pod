#include "input.h"

static int index_of(unsigned key) {
    if (key == M1_POWER) return 0;
    if (key == M1_VOL_UP) return 1;
    if (key == M1_VOL_DOWN) return 2;
    return -1;
}
static int eligible(const struct m1_context *c) {
    return c->page && c->enabled && c->awake && c->unlocked && c->stable;
}
void m1_cancel_owned(struct m1_input *s) {
    int i;
    for (i = 0; i < 3; ++i)
        if (s->keys[i].active && s->keys[i].owned) s->keys[i].cancelled = 1;
}
int m1_route(struct m1_input *s, const struct m1_context *c,
             unsigned type, unsigned key) {
    int i = index_of(key), can = eligible(c), result;
    struct m1_press *p;
    if (i < 0 || (type != M1_DOWN && type != M1_UP && type != M1_LONG))
        return M1_PASS;
    p = &s->keys[i];
    if (p->active && (!can || p->page != c->page || p->generation != c->generation))
        p->cancelled = 1;
    if (type == M1_DOWN) {
        if (!p->active) {
            p->active = 1;
            p->owned = can;
            p->cancelled = p->long_press = 0;
            p->page = c->page;
            p->generation = c->generation;
        }
        return M1_PASS;
    }
    if (type == M1_LONG) {
        if (p->active) p->long_press = 1;
        return M1_PASS; /* the stock power dialog and its release latch survive */
    }
    if (!p->active) return M1_PASS; /* unpaired release: never guess a selection */
    result = M1_PASS;
    if (p->owned && !(i == 0 && p->long_press)) {
        result = M1_DROP;
        if (!p->cancelled && can && !p->long_press) {
            result = i == 0 ? M1_CONFIRM : (i == 1 ? M1_PREVIOUS : M1_NEXT);
            if (c->reversed && i) result = result == M1_PREVIOUS ? M1_NEXT : M1_PREVIOUS;
        }
    }
    p->active = 0;
    return result;
}
