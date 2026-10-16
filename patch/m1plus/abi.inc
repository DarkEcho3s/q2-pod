/* Shanling M1 Plus V2.1 values for the blocks of patch/offsets.inc marked !M1PLUS (docs/m1plus.md).
 * Each was read off the M1's own code, mostly by pairing a same-named function with the Q2's
 * (tools/m1plus.py audits the code words these rest on). The M1 runs an older AWTK (late 2021 to
 * early 2022): widget_t's fields from parent on sit 4 bytes lower, the canvas 8, and the event enum
 * differs (keys -1, paint/animation/window +2, value events in the widget range). A name defined as
 * M1_UNMAPPED is not mapped yet: code that uses it does not compile. */
#define M1_UNMAPPED m1_unmapped_value_used /* no such symbol: a compile error at the use */

/* widget_t: x, y, w, h as the Q2; parent, children, emitter, children_layout and vt sit 4 lower
 * (widget_get_window, widget_get_child, widget_off_by_func, widget_set_children_layout). */
#define W_X 0x00
#define W_Y 0x04
#define W_W 0x08
#define W_H 0x0c
#define W_FOCUS 0x24
#define W_PARENT 0x44
#define W_EMITTER 0x5c
#define W_CHILDREN_LAYOUT 0x64
/* children_layouter_t vt @0xc; children_layouter_default x_margin @0x14, spacing @0x16
 * (children_layouter_default_create); its vtable, "default" @0x74a988, and list_view's. */
#define CHILDREN_LAYOUT_VTABLE 0x0c
#define DEFAULT_LAYOUT_X_MARGIN 0x14
#define DEFAULT_LAYOUT_SPACING 0x16
#define DEFAULT_LAYOUT_VTABLE 0x904924
/* emitter_item_t: no "working" byte yet, so pending_remove is @0x14 (emitter_remove_item). */
#define EMIT_TYPE 0x08
#define EMIT_PENDING_REMOVE 0x14
#define EMIT_NEXT 0x20
/* The widget classes' own fields start at 0x78 on both (widget_t is 0x78 here as on the Q2's build):
 * table_client_set_row_height/set_rows/set_yoffset, slide_menu_set_value,
 * text_selector_set_selected_index and scroll_view_set_offset read the same offsets. */
#define ROW_HEIGHT 0x78
#define ROW_INDEX 0x78
#define SLIDE_INDEX 0x78
#define TABLE_ROWS 0x7c
#define SELECTOR_INDEX 0x7c
#define VIEW_CONTENT_H 0x7c
#define SCROLL_X 0x80
#define TABLE_TOP 0x80
#define SCROLL_Y 0x84
#define VIEW_HORIZONTAL 0x90
#define VIEW_VERTICAL 0x91
#define VIEW_SNAP 0x92
#define TABLE_ANIMATOR 0xd0 /* table_client_stop_animator_scroll */
#define VIEW_ANIMATOR 0xe8
#define EVENT_TYPE 0x00
#define EVENT_KEY 0x18
#define EVENT_TARGET 0x10
#define EVENT_X 0x18
#define EVENT_Y 0x1c
/* Events: the pointer range matches the Q2's; keys are one lower; window events two higher. */
#define EVT_POINTER_DOWN 0x100 /* down before children: home_page_init's on_wm_before_tsdown_fun */
#define EVT_POINTER_MOVE_BEFORE 0x102
#define EVT_POINTER_UP_BEFORE 0x104
#define EVT_POINTER_ABORT 0x107
#define EVT_DESTROY 0x0c
#define EVT_KEY_DOWN 0x10f
#define EVT_KEY_DOWN_BEFORE 0x111
#define EVT_KEY_UP 0x113 /* home_page_init registers on_wm_keyup_fun for this type */
#define EVT_KEY_UP_BEFORE 0x114
#define EVT_WINDOW_BACKGROUND 0x12c
#define EVT_WINDOW_CLOSE 0x12e
#define PULL_SEARCH_PX 48
#define PULL_CLAIM_PX 8
#define QUICK_EDGE_PX 81 /* on_wm_tsmove_fun opens the pull-down from the top 81 px (the Q2's 31) */
#define EVT_CLICK 0x10c
#define EVT_FOCUS 0x10d
#define EVT_BLUR 0x10e
#define EVT_SCROLL 0x14e
#define EVT_SCROLL_END 0x14f
#define VIEW_ON_SCROLL 0x100
/* canvas_t: lcd @0x30, text alignment @0x28/0x2c (canvas_set_text_align); lcd_t's colors as the Q2's
 * (lcd_set_fill_color, lcd_set_stroke_color, lcd_set_text_color). */
#define CANVAS_X 0x00
#define CANVAS_Y 0x04
#define CANVAS_LCD 0x30
#define LCD_FILL_COLOR 0xbc
#define LCD_STROKE_COLOR 0xc0
#define LCD_TEXT_COLOR 0xb8
#define CANVAS_ALIGN_V 0x28
#define CANVAS_ALIGN_H 0x2c
#define WM_VT 0x88 /* window_manager_t's vtable (window_manager_paint @0x677b44) */
#define STYLE_COLOR_GRADIENT_RET M1_UNMAPPED

/* list_view: default_item_height @0x7c, its layouter's vtable @0x9047a0 (list_view @0x746718). */
#define LIST_DEFAULT_ITEM_HEIGHT 0x7c
#define LIST_VIEW_LAYOUT 0x60abb0
#define LIST_VIEW_LAYOUT_SLOT 0x9047a8
#define IMAGE_DRAW_SCALE_DOWN 5 /* AWTK image_draw_type_t, as the Q2's */
#define IMAGE_DRAW_CENTER 1

#define BAR_VALUE 0x7c /* scroll_bar_t value */
/* Keys, as the input threads map them (main_loop_init; the encoder is "md-rotary-knob" on
 * /dev/input/event2, the buttons "md-gpio-keys" on event1): the wheel's two directions, its press
 * (the power key, as on the Q2), Play/Pause, Previous and Next. There is no Return key: KEY_RETURN
 * is the payload's own code for Back (Previous in a menu, the on-screen back button), which no
 * stock handler knows (m1plus/input.c). */
#define KEY_CENTER 210 /* KEY_POWER 116 */
#define KEY_PREV 220   /* KEY_VOLUMEUP 115: the wheel rolled up */
#define KEY_NEXT 221   /* KEY_VOLUMEDOWN 114: the wheel rolled down */
#define KEY_PLAY 213   /* KEY_PLAYPAUSE 164 */
#define KEY_RETURN 0x2f00
#define KEY_BACK_BTN 214 /* KEY_PREVIOUSSONG 165 */
#define KEY_FWD_BTN 215  /* KEY_NEXTSONG 163 */
/* The Q2's touch wheel needed a lockout after the centre key; the M1's detents do not brush, but
 * a press can turn the knob, so the payload keeps its own short one (m1plus/input.c). These are
 * the payload's bytes, not stock's. */
#define KEY_LOCKOUT ((unsigned)&m1_key_lockout)
#define LOCKOUT_KEEP 2
#define HOLD_MS 1200
#define HOLD_MAX 8
#define HOLD_POLL_MS 16
#define WHEEL_TICK_UNITS 28 /* unused: the encoder posts whole detents */
#define WHEEL_POST M1_UNMAPPED
#define WHEEL_INFO_EVENT M1_UNMAPPED
#define WHEEL_INFO_KEY M1_UNMAPPED
#define BOOT_KEY_GUARD ((unsigned)&m1_boot_key_guard)
#define RETURN_RELEASE_LATCH ((unsigned)&m1_return_latch)
#ifndef __ASSEMBLER__
extern unsigned char m1_key_lockout, m1_boot_key_guard, m1_return_latch;
#endif

/* slide_menu_t: no spacer yet; xoffset @0x88, the scroll animator @0xb8. widget_animator_t's times
 * sit 4 higher (widget_animator_time_elapse), and the scroll animator's x_to @0x64
 * (widget_animator_scroll_set_params). */
#define SLIDE_SPACER M1_UNMAPPED
#define SLIDE_OFFSET 0x88
#define SLIDE_ANIMATOR 0xb8
#define ANIM_ELAPSED 0x14
#define ANIM_START_TIME 0x1c
#define ANIM_DURATION 0x24
#define ANIM_X_TO 0x64
#define SLIDE_EASING 8
#define EVT_ANIM_END 0x127

/* window_manager_default_t keeps its input_device_status_t @0xf8 (the dispatch's
 * input_device_status_on_input_event call, 0x68ffc8); its pressed_info[] @0x18. */
#define EVT_KEY_LONG 0x110
#define WM_INPUT_STATUS 0xf8
#define INPUT_KEYS 0x18
#define INPUT_KEY_SIZE 0x18
#define INPUT_KEY_COUNT 16
#define INPUT_KEY_TIME 0x08

/* stSongInfo: the same record as the Q2's (toolsFreeStSongInfo frees the same string fields, and
 * getMusicByAlbum's row callback, 0x4e9058, fills the same offsets as the Q2's 0x4fb8b8). */
#define REC_ID 0x00
#define REC_NAME 0x08
#define REC_PATH 0x0c
#define REC_TITLE 0x10
#define REC_ALBUM 0x14
#define REC_ARTIST 0x18
#define REC_ALBUM_ARTIST 0x24
#define REC_TYPE 0x34
#define REC_TRACK 0x3c
#define REC_DISC 0x40
#define REC_CUE_START 0x48
#define REC_CUE_END 0x4c
/* playsong_id3info, the Q2's g_play_id3_info (2716 bytes on both). */
#define ID3_ALBUM 0x404
#define ID3_ARTIST 0x504
#define ID3_TITLE 0x684
/* The library's class codes are the Q2's (0xf003 all albums, 0xff01 an artist's albums, ...). */
#define CLASS_ALBUMS 0xf003
#define CLASS_ARTIST_ALBUMS 0xff01
#define ALBUMINFO_ROW M1_UNMAPPED
/* Static mcl queue state, paired through mclNextSong, mclPrevSong, mclLoadPlayList, mclGetLastPos,
 * mclGetJumpFolder, mclGetGaplessMode and mclUsbAudioSetVol. */
#define MCL_POOL 0xa0aae8
#define MCL_LASTPOS 0xa0abc8
#define MCL_PREPOS 0xa0abcc
#define MCL_PRELOAD 0xa0abd0
#define MCL_TYPE 0xa0abd8
#define MCL_POS 0xa0abdc
#define MCL_MODE 0xa0abe0
#define MCL_JUMPFOLDER 0xa0ab88
#define MCL_GAPLESS 0xa0ab89
#define MCL_FD 0xa0abec
#define INITCONFIG_MODE_RET 0x4d8738 /* config_mplayer (the Q2's player_initconfig): its mclSetPlayMode call returns here */
#define CONFIG_INIT_MODE_RET 0x4e5974 /* config_init's boot mclSetPlayMode returns here (the Q2 has no such call) */
#define USB_MIXER 0xa0aba4
#define SORTSELECT_KEYUP M1_UNMAPPED
#define SORTSELECT_CLOSE M1_UNMAPPED

/* Value events are still widget events here (EVT_VALUE_CHANGED and _CHANGING after MOVE_RESIZE). */
#define EVT_VALUE_CHANGED 0x11c
#define EVT_VALUE_CHANGING 0x11d
#define BOOTVOL_SWITCH M1_UNMAPPED
#define BOOTVOL_DEC M1_UNMAPPED
#define BOOTVOL_ADD M1_UNMAPPED
#define BOOTVOL_CHANGING M1_UNMAPPED
#define BOOTVOL_CHANGED M1_UNMAPPED
/* dialog_scanmusic_dialog_init's thread handle and wait_scan's done flag. */
#define SCAN_THREAD 0xa03a44
#define SCAN_DONE 0xa03a40

#include "layout.inc" /* the 320x480 portrait screen */
