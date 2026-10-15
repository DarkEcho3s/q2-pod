#ifndef POD_DISPLAY_H
#define POD_DISPLAY_H
/* Logical coordinates after the vendor's framebuffer rotation. These describe
 * the UI, not the stored boot JPEG or the Linux framebuffer's native stride. */
#ifdef M1PLUS
#define POD_SCREEN_W 320
#define POD_SCREEN_H 480
#else
#define POD_SCREEN_W 375
#define POD_SCREEN_H 320
#endif
#define POD_STATUS_H 30
#define POD_CLIENT_H (POD_SCREEN_H - POD_STATUS_H)
#endif
