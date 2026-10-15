/* Geometry only. These overrides do not declare the toolkit ABI compatible:
 * private structure offsets and hook addresses require the M1 UI target. */
#undef HOME_FULL_ROW
#define HOME_FULL_ROW POD_SCREEN_W
#undef HOME_SPLIT_W
#define HOME_SPLIT_W (POD_SCREEN_W / 2)
#undef HOME_CLASSIC_ROW
#define HOME_CLASSIC_ROW (POD_SCREEN_W - 6)
#undef SET_STOCK_X
#define SET_STOCK_X 12
#undef SET_STOCK_W
#define SET_STOCK_W (POD_SCREEN_W - 24)
#undef SET_STOCK_ROW
#define SET_STOCK_ROW 64
#undef SET_STOCK_BODY
#define SET_STOCK_BODY 60
#undef SET_ROW
#define SET_ROW 64
#undef CF_VIEW_W
#define CF_VIEW_W POD_SCREEN_W
#undef CF_VIEW_H
#define CF_VIEW_H (POD_CLIENT_H - 80)
#undef CF_CX
#define CF_CX (POD_SCREEN_W / 2)
#undef CF_TOP
#define CF_TOP (13 + (POD_CLIENT_H - 290) / 2)
#undef CF_TEXT_Y
#define CF_TEXT_Y (CF_VIEW_H + 2)
#undef PH_COLS
#define PH_COLS 3
#undef PH_TILE_W
#define PH_TILE_W ((POD_SCREEN_W - 2 * PH_GRID_X) / PH_COLS)
#undef PH_THUMB_W
#define PH_THUMB_W (PH_TILE_W - 8)
#undef PH_SHOT_W
#define PH_SHOT_W POD_SCREEN_W
#undef PH_SHOT_H
#define PH_SHOT_H POD_CLIENT_H
