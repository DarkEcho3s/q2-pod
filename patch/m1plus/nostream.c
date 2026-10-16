/* The M1 Plus build has no streaming (Spotify, Internet Radio, Tidal): the Q2's spotify.c, radio.c
 * and tidal.c are not compiled (tools/m1plus.py SOURCES). The rest of the payload asks them whether
 * they own playback, hands them keys and paints, and stops them before local music; here nothing is
 * ever theirs, so every answer is "no" and every hand-over a no-op. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

int spot_status(void) { return 0; }
int radio_status(void) { return 0; }
unsigned spot_session(void) { return 0; }
unsigned radio_session(void) { return 0; }
void spot_set_playing(int playing) { (void)playing; }
void radio_set_playing(int playing) { (void)playing; }
int spot_media(unsigned key) { return (void)key, 0; }
int radio_media(unsigned key) { return (void)key, 0; }
int spot_key(void *top, unsigned key) { return (void)top, (void)key, 0; }
const char *radio_hold(void *top) { return (void)top, (const char *)0; }
void spot_poll(void) {}
void radio_poll(void) {}
void spot_yield(void) {}
void radio_stop(void) {}
void radio_search(void) {}
void spot_paint(void *w, void *canvas) { (void)w, (void)canvas; }
void *spot_art(void) { return (void *)0; }
int spot_open(void *ctx, void *event) { return (void)ctx, (void)event, 0; }
int radio_open(void *ctx, void *event) { return (void)ctx, (void)event, 0; }

/* headset.c's AAP connect check: the M1's demo imports no getsockopt, so the syscall itself (o32
 * 4173; the fifth argument stays at 16($sp), where the caller put it). -1 on error, as libc. */
__asm__(".set noreorder\n.globl getsockopt\ngetsockopt:\n"
        "li $v0, 4173\nsyscall\nbnez $a3, 1f\nnop\njr $ra\nnop\n"
        "1: jr $ra\nli $v0, -1\n.set reorder\n");
