/* The M1 Plus's volume (docs/m1plus.md#volume). Its mclSetVol (0x5d4cb0) does what the Q2 splits in
 * two: the DAC's volume ioctl, then hciplayer's software volume ({mcl-setvol}), which the Q2's
 * mclSetBtVol alone sends for Bluetooth. The payload's absolute-volume sync (navigation.c
 * ringnav_btvol) takes the software half, as it takes mclSetBtVol on the Q2: with a headset that
 * follows AVRCP volume it sends 100 and lets the headset turn it down. The DAC half stays stock's. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"

#define DAC_FD (*(volatile int *)0xa0abf8u)    /* mclSetVol's ioctl fd: the DAC, 0 or -1 closed */
#define PLAYER_UP (*(volatile int *)0xa0abe8u) /* 1 while hciplayer takes commands (MCL_FD) */
#define DAC_SET_VOLUME 0xc0044d00u             /* the codec's left << 8 | right volume */
#define PLAYER_FD (*(volatile int *)MCL_FD)

extern int ringnav_btvol(int left, int right);

static int pack(int left, int right) { return (left << 8 & 0xffff) | (right & 0xff); }

/* The Q2's mclSetBtVol: hciplayer's software volume alone. */
int stock_btvol_trampoline(int left, int right) {
    if (PLAYER_UP != 1 || PLAYER_FD == -1) return 1;
    char s[32];
    snprintf(s, sizeof s, "{mcl-setvol\\%d}", pack(left, right));
    send(PLAYER_FD, s, strlen(s), 0);
    return 1;
}

/* mclSetVol: the DAC as stock sets it, the software volume through ringnav_btvol. */
int m1_setvol(int left, int right) {
    int v = pack(left, right);
    if (DAC_FD > 0) ioctl(DAC_FD, DAC_SET_VOLUME, &v);
    return ringnav_btvol(left, right);
}
