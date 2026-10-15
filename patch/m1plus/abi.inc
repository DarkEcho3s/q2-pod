/* M1 Plus V2.1 native ABI. Every address is tied to the stock executable SHA.
 * Offsets cite the native accessor used to establish the layout. */
#undef W_PARENT
#define W_PARENT 0x44 /* widget_get_window 66a9e0 */
#undef W_EMITTER
#define W_EMITTER 0x5c /* widget_on_with_tag 666cb0 */
#undef EMIT_PENDING_REMOVE
#define EMIT_PENDING_REMOVE 0x14 /* emitter removal helper 6f42f8 */
#undef W_CHILDREN_LAYOUT
#define W_CHILDREN_LAYOUT 0x64 /* widget_set_children_layout 656fb0 */
#undef CHILDREN_LAYOUT_VTABLE
#define CHILDREN_LAYOUT_VTABLE 0x0c /* children_layouter_default_create 63af2c */
#undef DEFAULT_LAYOUT_X_MARGIN
#define DEFAULT_LAYOUT_X_MARGIN 0x14 /* default set_param x at 63a1d4 */
#undef DEFAULT_LAYOUT_SPACING
#define DEFAULT_LAYOUT_SPACING 0x16 /* default set_param s at 63a1ec */
#undef CANVAS_LCD
#define CANVAS_LCD 0x30 /* canvas_set_fill_color 644248 */
#undef CANVAS_ALIGN_V
#define CANVAS_ALIGN_V 0x28 /* canvas_set_text_align 644534 */
#undef CANVAS_ALIGN_H
#define CANVAS_ALIGN_H 0x2c
#undef SLIDE_OFFSET
#define SLIDE_OFFSET 0x88 /* slide_menu xoffset getter 613910 */
#undef SLIDE_ANIMATOR
#define SLIDE_ANIMATOR 0xb8 /* slide_menu scroll_to 6122f4 */
#undef ANIM_ELAPSED
#define ANIM_ELAPSED 0x14 /* widget_animator_time_elapse 67375c */
#undef ANIM_START_TIME
#define ANIM_START_TIME 0x1c
#undef ANIM_DURATION
#define ANIM_DURATION 0x24
#undef ANIM_X_TO
#define ANIM_X_TO 0x64 /* widget_animator_scroll_set_params 68cd10 */
#undef INPUT_KEYS
#define INPUT_KEYS 0x18 /* input_device_status_abort_all_pressed_keys 6a4adc */
int m1_slide_spacing(void *);
#undef SLIDE_SPACING
#define SLIDE_SPACING(w) m1_slide_spacing(w)
#undef EVT_FOCUS
#define EVT_FOCUS 0x10d
#undef EVT_BLUR
#define EVT_BLUR 0x10e
#undef EVT_KEY_DOWN
#define EVT_KEY_DOWN 0x10f
#undef EVT_KEY_LONG
#define EVT_KEY_LONG 0x110
#undef EVT_KEY_DOWN_BEFORE
#define EVT_KEY_DOWN_BEFORE 0x111
#undef EVT_KEY_UP
#define EVT_KEY_UP 0x113
#undef EVT_KEY_UP_BEFORE
#define EVT_KEY_UP_BEFORE 0x114
#undef EVT_VALUE_CHANGED
#define EVT_VALUE_CHANGED 0x11c /* slider_set_value 6317d8 */
#undef EVT_VALUE_CHANGING
#define EVT_VALUE_CHANGING 0x11d
#undef EVT_ANIM_END
#define EVT_ANIM_END 0x127 /* native slide_menu animator 612310 */
#undef EVT_WINDOW_BACKGROUND
#define EVT_WINDOW_BACKGROUND 0x12c
#undef EVT_WINDOW_CLOSE
#define EVT_WINDOW_CLOSE 0x12e
/* Logical navigation keys are synthesized only after the M1 input policy owns
 * a release. Physical previous/next retain their media roles. */
#undef KEY_CENTER
#define KEY_CENTER 210
#undef KEY_PLAY
#define KEY_PLAY 213
#undef KEY_BACK_BTN
#define KEY_BACK_BTN 214
#undef KEY_FWD_BTN
#define KEY_FWD_BTN 215
/* loadLocalClassList: 0xf002 -> getAllHr, 0xf00a -> getAllFav. */
#undef MCL_POOL
#define MCL_POOL 0xa0aae8 /* mclResetRandomList 5d203c */
#undef MCL_LASTPOS
#define MCL_LASTPOS 0xa0abc8 /* mclResetRandomList 5d2030 */
#undef MCL_PREPOS
#define MCL_PREPOS 0xa0abcc /* mclNextSong 5d589c */
#undef MCL_PRELOAD
#define MCL_PRELOAD 0xa0abd0 /* mclAutoChange 5d6338 */
#undef MCL_TYPE
#define MCL_TYPE 0xa0abd8 /* mclGetPlayType 5d366c */
#undef MCL_POS
#define MCL_POS 0xa0abdc /* mclGetPlayPos 5d42a4 */
#undef MCL_MODE
#define MCL_MODE 0xa0abe0 /* mclGetPlayMode 5d363c */
#undef MCL_JUMPFOLDER
#define MCL_JUMPFOLDER 0xa0ab88 /* mclSetJumpFolder 5d447c */
#undef MCL_GAPLESS
#define MCL_GAPLESS 0xa0ab89 /* mclGetGaplessMode */
#undef MCL_FD
#define MCL_FD 0xa0abec /* mclOrderStop 5d2304 */
#undef USB_MIXER
#define USB_MIXER 0xa0aba4 /* mclUsbAudioSetVol 5d46e8 */
#undef DEFAULT_LAYOUT_VTABLE
#define DEFAULT_LAYOUT_VTABLE 0x904924 /* children_layouter_default_create */
#undef ALBUMINFO_ROW
#define ALBUMINFO_ROW 0xa06680 /* albuminfo_page_init stores context >>16 at 5268ec */
/* Q2's touch-ring lockout and Return-key release latches have no M1 hardware
 * equivalent. Keep their shared-code bookkeeping private to this payload. The
 * actual M1 wake/long-press rules are enforced before synthetic navigation. */
extern unsigned char m1_q2_latches[3];
#undef KEY_LOCKOUT
#define KEY_LOCKOUT ((unsigned)&m1_q2_latches[0])
#undef BOOT_KEY_GUARD
#define BOOT_KEY_GUARD ((unsigned)&m1_q2_latches[1])
#undef RETURN_RELEASE_LATCH
#define RETURN_RELEASE_LATCH ((unsigned)&m1_q2_latches[2])
#undef WM_VTABLE
#define WM_VTABLE 0x88 /* window_manager_paint 677b44 */
/* Unmapped private addresses fail at link time. The production build also
 * rejects any remaining symbol beginning m1_unmapped_. */
#include "m1_private.inc"
