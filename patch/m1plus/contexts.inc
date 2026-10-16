/* The M1 Plus's audited top windows (patch/contexts.inc explains the classes and flags). The names
 * are the M1 V2.1 UI assets' window names; tools/m1plus.py rejects one that is not. The M1 has no
 * Local Music hub, artist page, stream page or sleep timer page; its Home is a grid of the stock
 * menu's cards, Settings is a card on it, and its date and time share one page. */
{ "home_page", CTX_DYNAMIC, DRILL },
{ "folder_page", CTX_FOLDER, RING },
{ "album_page", CTX_LOCAL, 0 },
{ "albuminfo_page", CTX_LOCAL, RING },
{ "allmusic_page", CTX_LOCAL, RING },
{ "localclass_page", CTX_LOCAL, RING },
{ "playlist_page", CTX_LOCAL, RING | DRILL },
{ "search_page", CTX_DYNAMIC, 0 },
{ "playerjumpinfo_page", CTX_DYNAMIC, 0 },
{ "coverflow_page", CTX_DYNAMIC, 0 }, /* runtime window (patch/coverflow.c) */
{ "photos_page", CTX_DYNAMIC, 0 },    /* runtime window (patch/photos.c) */
{ "books_page", CTX_DYNAMIC, 0 },     /* runtime window (patch/books.c) */
{ "mostplayed_page", CTX_FIXED, 0 },  /* runtime window (patch/navigation.c); fixed: the hold menu */
{ "shuffle_page", CTX_DYNAMIC, 0 },   /* runtime window (patch/navigation.c) */
{ "ratings_page", CTX_DYNAMIC, 0 },   /* runtime window (patch/navigation.c) */
{ "rated_page", CTX_FIXED, 0 },       /* runtime window (patch/navigation.c); fixed: the hold menu */
{ "longsongs_page", CTX_FIXED, 0 },   /* runtime window (patch/navigation.c); fixed: the hold menu */
/* Now Playing's More and Queue, Home's menu editor, the sort picker */
{ "playmore_dialog", CTX_DYNAMIC, 0 },
{ "playqueue_dialog", CTX_DYNAMIC, 0 },
{ "homemenu_dialog", CTX_DYNAMIC, 0 },
{ "sortselect_dialog", CTX_DYNAMIC, CHOICE },
/* Playback settings */
{ "playset_page", CTX_FIXED, 0 },
{ "audiosetting_page", CTX_FIXED, 0 },
{ "equalizer_page", CTX_DYNAMIC, 0 }, /* PEQ list editor */
{ "filter_page", CTX_FIXED, CHOICE },
{ "memplay_page", CTX_FIXED, CHOICE },
{ "playmode_page", CTX_FIXED, CHOICE },
{ "replaygain_page", CTX_FIXED, CHOICE },
/* System settings */
{ "sysset_page", CTX_FIXED, 0 },
{ "system_page", CTX_FIXED, 0 },
{ "about_page", CTX_FIXED, 0 },
{ "autosynctime_page", CTX_FIXED, CHOICE },
{ "bluetooth_page", CTX_DYNAMIC, 0 },
{ "btquality_page", CTX_FIXED, CHOICE },
{ "display_page", CTX_FIXED, 0 },
{ "dsdmode_page", CTX_FIXED, CHOICE },
{ "fwupdate_page", CTX_FIXED, 0 },
{ "keylock_page", CTX_FIXED, CHOICE },
{ "language_page", CTX_FIXED, CHOICE },
{ "lighttime_page", CTX_FIXED, CHOICE },
{ "netservice_page", CTX_FIXED, 0 },
{ "powermanager_page", CTX_FIXED, 0 },
{ "reset_page", CTX_FIXED, 0 },
{ "screenrotate_page", CTX_FIXED, CHOICE },
{ "specfolder_page", CTX_DYNAMIC, 0 },
{ "synclink_page", CTX_FIXED, 0 },
{ "theme_page", CTX_FIXED, CHOICE },
{ "typedatetime_page", CTX_FIXED, CHOICE },
{ "updatemusic_page", CTX_FIXED, 0 }, /* Update Library */
{ "usbset_page", CTX_FIXED, CHOICE },
{ "usbvolmode_page", CTX_FIXED, CHOICE },
{ "wifi_page", CTX_DYNAMIC, 0 },
{ "wifiset_page", CTX_DYNAMIC, 0 },
/* Confirm prompts: their two buttons are the rows (the Legacy build too: the M1 has no Return
 * key, so the wheel and its press are the only way to answer one without touching it). */
{ "confirminfo_dialog", CTX_DYNAMIC, BUTTONS },
