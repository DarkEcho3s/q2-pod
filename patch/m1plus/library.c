/* Native album callbacks and records, with the Pod three-column grid geometry. */
#include "../offsets.inc"
#include "../peq.h"
#include "stock.h"
#define TILE_W 102
#define TILE_H 148
#define COVER_FIRST (*(int *)0xa06670u)

/* M1 has an album page for artist/composer detail but no Songs tab. The Songs
 * button opens its native song table with the selected group's complete query.
 * Native navigation retains the Albums page and restores it on Back. */
static struct { int kind, unknown; char name[256]; } group;
static int group_open(void *unused, void *event) {
    (void)unused; (void)event;
    int cls=I(g_local_classinfo_save,0);
    if (cls!=0xff01 && cls!=0xff02) return 0;
    group.kind=cls;
    group.unknown=g_local_classinfo_save[cls==0xff01 ? 0xa : 0xb];
    tk_snprintf(group.name,sizeof group.name,"%s",g_local_classinfo_save+(cls==0xff01 ? 0x10d : 0x20d));
    return navigator_to_with_context("allmusic_page",(const void *)0xff21);
}
int m1_group_load(int cls) {
    if (cls!=0xff21) return -2;
    void *dir=P(tools_pdeq_directory,0), *out=P(p_deque_showlist,0);
    if (!dir || !out) return 0;
    deque_clear(dir); deque_clear(out);
    const char *name=group.unknown ? 0 : group.name;
    if (group.kind==0xff02) getMusicByComposer(name);
    else if (I(artist_type,0)==1) getMusicByAlbumArtist(name);
    else getMusicBySonger(name);
    for (unsigned i=0,n=deque_size(dir);i<n;++i) _deque_push_back(out,deque_at(dir,i));
    deque_clear(dir);
    /* Native allmusic_page copies this title immediately after loading. */
    tk_snprintf((char *)0xa0533cu,256,"%s",group.unknown ? "Songs" : group.name);
    return (int)deque_size(out);
}
int m1_album_page(void *win, void *ctx) {
    extern int stock_albumpage_trampoline(void *,void *);
    int result=stock_albumpage_trampoline(win,ctx), cls=I(g_local_classinfo_save,0);
    if (win && (cls==0xff01 || cls==0xff02)) {
        void *nav=widget_lookup(win,"view_navbar",1);
        if (nav) {
            void *b=button_create(nav,200,0,60,50);
            widget_set_name(b,"m1_group_songs");widget_set_text_utf8(b,"Songs");
            widget_on(b,EVT_CLICK,group_open,win);
            /* Keep the native back and Now Playing buttons available. */
            for(unsigned i=0,n=widget_count_children(nav);i<n;++i) {
                void *c=widget_get_child(nav,i);
                if(!tk_strcmp(widget_get_type(c),"hscroll_label") && I(c,W_X)<200)
                    widget_resize(c,200-I(c,W_X),I(c,W_H));
            }
        }
    }
    return result;
}

int m1_album_scroll(void *win, void *event) {
    (void)event;
    void *view = widget_lookup(win, "album_scrollview", 1);
    if (!view || !P(p_deque_showlist,0)) return 0;
    int y = widget_get_prop_int(view,"yoffset",0), at = (y>0 ? y/TILE_H : 0)*3;
    if (at != COVER_FIRST) {
        if (toolsGetSysMemFree() < 25601) image_manager_unload_all(image_manager());
        COVER_FIRST=at;
        batchadd_albumcover_task(at,12);
    }
    return 0;
}

int m1_album_grid(void *view) {
    unsigned n=widget_count_children(view);
    for (unsigned i=0;i<n;++i) {
        void *row=widget_get_child(view,i);
        widget_set_children_layout(row, "");
        widget_move_resize(row,2+(i%3)*TILE_W,(i/3)*TILE_H,TILE_W,TILE_H);
        for (unsigned j=0,count=widget_count_children(row);j<count;++j) {
            void *child=widget_get_child(row,j);
            const char *name=widget_get_prop_str(child,"name","");
            widget_set_self_layout(child, "");
            if (tk_str_start_with(name,"imgleftcover"))
                widget_move_resize(child,5,4,92,92);
            else if (tk_str_start_with(name,"listsscrlabel")) {
                widget_move_resize(child,4,100,94,24);
                widget_set_prop_int(child,"style:normal:font_size",14);
            } else if (tk_str_start_with(name,"listsscrartist")) {
                widget_move_resize(child,4,125,94,19);
                widget_set_prop_int(child,"style:normal:font_size",12);
            } else if (tk_str_start_with(name,"img_choice"))
                widget_move_resize(child,2,2,36,36);
            else if (!tk_strcmp(widget_get_type(child),"button"))
                widget_move_resize(child,0,0,TILE_W,TILE_H);
        }
    }
    int height=(int)((n+2)/3)*TILE_H;
    if (height<I(view,W_H))height=I(view,W_H);
    widget_set_prop_int(view,"virtual_h",height);
    void *scrollbar=widget_lookup(P(view,W_PARENT),"scroll_bar_m",1);
    if(scrollbar)widget_set_prop_int(scrollbar,"max",height);
    return 0;
}
