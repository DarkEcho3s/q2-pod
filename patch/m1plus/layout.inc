/* The M1 Plus screen: 320x480 portrait, a 30px status bar over a 320x450 app window
 * (system_bar.bin; the stock pages are 320 wide, their lists end at y 450). The glass's corners are
 * square, so nothing needs CORNER clearance as on the Q2. The iPod build keeps the M1's own pages,
 * their 50px navigation bars (and on-screen back) and 64px rows (SET_*, as stock lays them out);
 * Home's list spans the width with the art panel under it (HOME_*, m1plus/home.c). */
#define SCREEN_W 320
#define SCREEN_H 480
#define BAR_H 30
#define APP_H 450

#define VOL_PANEL_X 20
#define VOL_PANEL_Y 300
#define VOL_PANEL_H 48
#define VOL_PANEL_PAD 20
#define VOL_PANEL_BAR 10
#define VOL_PANEL_TEXT 52
#define VOL_PANEL_PX 20
#define VOL_PANEL_TRACK 0x5a5a5a
#define CLOCK_EDGE 8
#define BATT_ROOM 94
#define HOME_FULL_ROW 320
#define HOME_LABEL_END 16
#define HOME_SPLIT_LABEL_END 16
#define HOME_DOT_X 12
#define HOME_DOT 6
#define HOME_DOT_GAP 8
#define HOME_SPLIT_W 320
#define HOME_ROW 40 /* Home's rows (tools/m1plus.py M1_HOME_ROW) */
#define HOME_TOP 8
#define HOME_ART_Y (HOME_TOP + 6 * HOME_ROW + 8) /* the art panel, under Home's six rows */
#define HOME_CLASSIC_ROW 320
#define HOME_CLASSIC_TEXT_X 16
#define HOME_CLASSIC_LABEL_END (CHEVRON_W - 10)
#define SET_ROW 64
#define SET_TOP 50
#define SET_ROWS 6
#define SET_ICON 40
#define SET_ICON_X 12
#define SET_GAP 8
#define SET_TEXT_X 12
#define SET_EDGE 12
#define SET_STOCK_ROW 64
#define SET_STOCK_BODY 64
#define SET_STOCK_X 0
#define SET_STOCK_W 320
#define SET_STOCK_ICON 40
#define SET_STOCK_TRAIL 251
#define SET_RIGHT_SIDE 150
/* Coverflow on the 320x450 window: the 160px covers on a 320x232 frame, the side covers closer in
 * than the Q2's 375px frame puts them, the caption under the reflections. */
#define CF_VIEW_W 320
#define CF_VIEW_H 232
#define CF_CX 160
#define CF_TOP 24
#define CF_EYE 300
#define CF_X1 98
#define CF_XS 40
#define CF_Z1 90
#define CF_ZS 20
#define CF_BRIGHT1 192
#define CF_BRIGHT2 128
#define CF_REFLECT 24
#define CF_REFLECT_TOP (IPOD ? 48 : 64)
#define CF_STRIDE 110
#define CF_TEXT_Y 250
/* Photos: four 80px columns, five rows under the 48px title; the viewer fills the window. */
#define PH_COLS 4
#define PH_GRID_X 0
#define PH_TILE_W 80
#define PH_TILE_H 80
#define PH_THUMB_W 72
#define PH_THUMB_H 72
#define PH_SHOT_W 320
#define PH_SHOT_H 450
#define PH_GRID_H 400
