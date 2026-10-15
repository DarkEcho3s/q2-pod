/* The M1 Plus screen: 320x480 portrait, a 30px status bar over a 320x450 app window
 * (system_bar.bin; the stock pages are 320 wide, their lists end at y 450). The glass's corners are
 * square, so nothing needs CORNER clearance as on the Q2. Values the iPod screens have not been laid
 * out for yet are M1_UNMAPPED. */
#define SCREEN_W 320
#define SCREEN_H 480
#define BAR_H 30
#define APP_H 450

#define VOL_PANEL_X M1_UNMAPPED
#define VOL_PANEL_Y M1_UNMAPPED
#define VOL_PANEL_H M1_UNMAPPED
#define VOL_PANEL_PAD M1_UNMAPPED
#define VOL_PANEL_BAR M1_UNMAPPED
#define VOL_PANEL_TEXT M1_UNMAPPED
#define VOL_PANEL_PX M1_UNMAPPED
#define VOL_PANEL_TRACK M1_UNMAPPED
#define CLOCK_EDGE M1_UNMAPPED
#define BATT_ROOM M1_UNMAPPED
#define HOME_FULL_ROW M1_UNMAPPED
#define HOME_LABEL_END M1_UNMAPPED
#define HOME_SPLIT_LABEL_END M1_UNMAPPED
#define HOME_DOT_X M1_UNMAPPED
#define HOME_DOT M1_UNMAPPED
#define HOME_DOT_GAP M1_UNMAPPED
#define HOME_SPLIT_W M1_UNMAPPED
#define HOME_CLASSIC_ROW M1_UNMAPPED
#define HOME_CLASSIC_TEXT_X M1_UNMAPPED
#define HOME_CLASSIC_LABEL_END M1_UNMAPPED
#define SET_ROW M1_UNMAPPED
#define SET_TOP M1_UNMAPPED
#define SET_ROWS M1_UNMAPPED
#define SET_ICON M1_UNMAPPED
#define SET_ICON_X M1_UNMAPPED
#define SET_GAP M1_UNMAPPED
#define SET_TEXT_X M1_UNMAPPED
#define SET_EDGE M1_UNMAPPED
#define SET_STOCK_ROW M1_UNMAPPED
#define SET_STOCK_BODY M1_UNMAPPED
#define SET_STOCK_X M1_UNMAPPED
#define SET_STOCK_W M1_UNMAPPED
#define SET_STOCK_ICON M1_UNMAPPED
#define SET_STOCK_TRAIL M1_UNMAPPED
#define SET_RIGHT_SIDE M1_UNMAPPED
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
