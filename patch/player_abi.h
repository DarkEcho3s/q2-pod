#ifndef Q2_PLAYER_ABI_H
#define Q2_PLAYER_ABI_H
/* Only this address table varies between the audited player binaries. The M1
 * values are generated from its pinned target; the ordinary Q2 build retains
 * its original addresses. Never select a target at runtime by device name. */
#ifdef M1PLUS
#include "m1_player_abi.h"
#else
#define PLAYER_MPCTX 0xaf9e30u
#define PLAYER_PTS 0x44641cu
#define PLAYER_LENGTH 0xb10e84u
#define PLAYER_ID3 0x48e6b0u
#define PLAYER_DICT_SET 0x6ea744u
#define PLAYER_DICT_FREE 0x6eabfcu
#define PLAYER_RG_EXPORT 0x538764u
#define PLAYER_SEEK 0x48d1acu
#define PLAYER_HR_MP3_SEEK 0xb152b8u
#endif
#endif
