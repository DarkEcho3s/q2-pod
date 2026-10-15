/* Intentionally excluded streaming capabilities. Local media stays in headset.c. */
#include "../peq.h"
void dgram_send(int *sock, const char *path, const char *data, unsigned n) {
    struct { unsigned short family; char path[108]; } to = { 1, { 0 } };
    unsigned length = strlen(path);
    if (length >= sizeof to.path) return;
    if (*sock <= 0) *sock = socket(1, 1, 0);
    if (*sock < 0) return;
    memcpy(to.path, path, length+1);
    sendto(*sock, data, n, 0x40, &to, sizeof to);
}
void *label(void *parent, int x, int y, int w, int h, const char *style, int px, unsigned color) {
    void *l = text(parent, x, y, w, h);
    widget_use_style(l, style);
    widget_set_prop_int(l, "style:normal:font_size", px);
    widget_set_prop_int(l, "style:normal:text_color", (int)color);
    return l;
}
void spot_poll(void) {}
void spot_yield(void) {}
void spot_paint(void *w, void *c) { (void)w; (void)c; }
void *spot_art(void) { return 0; }
int spot_media(unsigned k) { (void)k; return 0; }
int spot_key(void *w, unsigned k) { (void)w; (void)k; return 0; }
int spot_open(void *w, void *e) { (void)w; (void)e; return 0; }
int spot_status(void) { return 0; }
unsigned spot_session(void) { return 0; }
void spot_set_playing(int p) { (void)p; }
void radio_poll(void) {}
void radio_stop(void) {}
int radio_media(unsigned k) { (void)k; return 0; }
int radio_open(void *w, void *e) { (void)w; (void)e; return 0; }
const char *radio_hold(void *w) { (void)w; return 0; }
void radio_search(void) {}
int radio_status(void) { return 0; }
unsigned radio_session(void) { return 0; }
void radio_set_playing(int p) { (void)p; }
