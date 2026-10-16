/* Helpers that Spotify, Internet Radio and the rest of the payload share (peq.h): the monotonic
 * clock, a datagram to a local socket, key=value state files and a styled label. Kept apart from
 * spotify.c so a build without streaming (tools/m1plus.py) still has them. */
#include "offsets.inc"
#include "peq.h"
#include "stock.h"

unsigned long long now_ms(void) { /* shared with radio.c; not now_ns() / 1e6: no __udivdi3 here */
    int ts[2];            /* o32 timespec */
    clock_gettime(1, ts); /* CLOCK_MONOTONIC, librespot's at= clock */
    return (unsigned long long)(unsigned)ts[0] * 1000 + (unsigned)ts[1] / 1000000;
}

/* c to the datagram socket at path, *sock opened on first use. Shared with radio.c. */
void dgram_send(int *sock, const char *path, const char *c, unsigned n) {
    if (*sock <= 0) *sock = socket(1, 1, 0); /* AF_UNIX, SOCK_DGRAM (MIPS numbering) */
    struct {
        unsigned short family;
        char path[108];
    } to = { 1, { 0 } };
    memcpy(to.path, path, strlen(path) + 1);
    sendto(*sock, c, n, 0x40, &to, sizeof to); /* MSG_DONTWAIT */
}

/* The value of key in raw into out (n bytes), "" without one. Shared with radio.c. */
void field(const char *raw, const char *key, char *out, unsigned n) {
    char k[16];
    tk_snprintf(k, sizeof k, "\n%s=", key);
    const char *v = strstr(raw, k), *e;
    unsigned len = 0;
    if (v)
        for (v += strlen(k), e = v; *e && *e != '\n' && len + 1 < n; ++e) ++len;
    if (len) memcpy(out, v, len);
    out[len] = 0;
}

unsigned long long number(const char *raw, const char *key) {
    char v[24];
    unsigned long long x = 0;
    field(raw, key, v, sizeof v);
    for (const char *c = v; *c >= '0' && *c <= '9'; ++c) x = x * 10 + (unsigned)(*c - '0');
    return x;
}

/* path's bytes into raw behind a '\n', as field() reads; their count, 0 for no file. Shared
 * with radio.c. */
unsigned state_read(const char *path, char *raw, unsigned size) {
    void *f = fopen(path, "rb");
    unsigned n = f ? fread(raw + 1, 1, size - 2, f) : 0;
    if (f) fclose(f);
    raw[0] = '\n';
    raw[n + 1] = 0;
    return n;
}

void *label(void *parent, int x, int y, int w, int h, const char *style, int px,
           unsigned color) {
    void *l = text(parent, x, y, w, h);
    widget_use_style(l, style);
    widget_set_prop_int(l, "style:normal:font_size", px);
    widget_set_prop_int(l, "style:normal:text_color", (int)color);
    return l;
}
