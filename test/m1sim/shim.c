/* m1sim's device shim (test/m1sim/README.md): LD_PRELOADed into the M1 Plus's demo under
 * qemu-mipsel. The framebuffer is a plain file (FB_FILE) the host reads for screenshots; the pan
 * offset AWTK flips its two pages with goes to PAN_FILE. Input devices are FIFOs opened read-write,
 * so their open never blocks and their read never sees end of file. Everything else passes to libc.
 * No MIPS sysroot: glibc 2.28's declarations, MIPS o32 numbers. */
typedef unsigned long size_t;
#define RTLD_NEXT ((void *)-1l)
#define O_RDWR 2
#define O_CREAT 0x100
#define O_TRUNC 0x200
#define W 320
#define H 480
#define FB_FILE "/tmp/m1sim/fb"
#define PAN_FILE "/tmp/m1sim/pan"
#define BLANK_FILE "/tmp/m1sim/blank" /* 1 while the panel is off (FBIOBLANK) */
#define SYSTEM_LOG "/tmp/m1sim/system.log"

void *dlsym(void *, const char *);
int strcmp(const char *, const char *), strncmp(const char *, const char *, size_t);
void *memset(void *, int, size_t);
long write(int, const void *, size_t), pwrite(int, const void *, size_t, long);
int ftruncate(int, long), getpid(void);
int snprintf(char *, size_t, const char *, ...);
size_t strlen(const char *);
long read(int, void *, size_t);
typedef void *(*popen_fn)(const char *, const char *);

typedef int (*open_fn)(const char *, int, ...);
typedef int (*ioctl_fn)(int, unsigned long, ...);
static int fb_fds[8] = { -1, -1, -1, -1, -1, -1, -1, -1 }, pan_fd = -1, blank_fd = -1;

static int is_fb(int fd) {
    for (int i = 0; i < 8; ++i)
        if (fd >= 0 && fb_fds[i] == fd) return 1;
    return 0;
}

struct bitfield { unsigned offset, length, msb_right; };
struct var {
    unsigned xres, yres, xres_virtual, yres_virtual, xoffset, yoffset, bits_per_pixel, grayscale;
    struct bitfield red, green, blue, transp;
    unsigned nonstd, activate, height, width, accel_flags, pixclock, left_margin, right_margin,
        upper_margin, lower_margin, hsync_len, vsync_len, sync, vmode, rotate, colorspace, reserved[4];
};
struct fix {
    char id[16];
    unsigned long smem_start;
    unsigned smem_len, type, type_aux, visual;
    unsigned short xpanstep, ypanstep, ywrapstep;
    unsigned line_length;
    unsigned long mmio_start;
    unsigned mmio_len, accel;
    unsigned short capabilities, reserved[2];
};
_Static_assert(sizeof(struct var) == 160, "fb_var_screeninfo");
_Static_assert(sizeof(struct fix) == 68, "fb_fix_screeninfo");

static unsigned yoffset;

static int redirect(const char *path, int flags, int mode, int *fb) {
    open_fn real = (open_fn)dlsym(RTLD_NEXT, "open");
    *fb = 0;
    if (!strcmp(path, "/dev/fb0")) {
        *fb = 1;
        int fd = real(FB_FILE, O_RDWR | O_CREAT, 0644);
        if (fd >= 0) ftruncate(fd, W * H * 4 * 2);
        if (pan_fd < 0) pan_fd = real(PAN_FILE, O_RDWR | O_CREAT | O_TRUNC, 0644);
        return fd;
    }
    if (!strncmp(path, "/dev/input/event", 16)) return real(path, O_RDWR, 0);
    return real(path, flags, mode);
}

int open(const char *path, int flags, int mode) {
    int fb, fd = redirect(path, flags, mode, &fb);
    for (int i = 0; fb && fd >= 0 && i < 8; ++i)
        if (fb_fds[i] < 0 || fb_fds[i] == fd) {
            fb_fds[i] = fd;
            break;
        }
    return fd;
}

int close(int fd) {
    for (int i = 0; i < 8; ++i)
        if (fb_fds[i] == fd) fb_fds[i] = -1;
    return ((int (*)(int))dlsym(RTLD_NEXT, "close"))(fd);
}
int open64(const char *path, int flags, int mode) { return open(path, flags | 0x2000, mode); }

static void pan(unsigned y) {
    char s[16];
    yoffset = y;
    int n = snprintf(s, sizeof s, "%u\n", y);
    if (pan_fd >= 0) pwrite(pan_fd, s, (size_t)n, 0);
}

int ioctl(int fd, unsigned long request, void *arg) {
    if (!is_fb(fd)) return ((ioctl_fn)dlsym(RTLD_NEXT, "ioctl"))(fd, request, arg);
    switch (request) {
    case 0x4600: { /* FBIOGET_VSCREENINFO */
        struct var *v = arg;
        memset(v, 0, sizeof *v);
        v->xres = v->xres_virtual = W;
        v->yres = H;
        v->yres_virtual = 2 * H;
        v->yoffset = yoffset;
        v->bits_per_pixel = 32;
        v->red = (struct bitfield){ 16, 8, 0 };
        v->green = (struct bitfield){ 8, 8, 0 };
        v->blue = (struct bitfield){ 0, 8, 0 };
        v->transp = (struct bitfield){ 24, 8, 0 };
        v->width = 41, v->height = 61; /* mm */
        return 0;
    }
    case 0x4601: /* FBIOPUT_VSCREENINFO */
    case 0x4606: /* FBIOPAN_DISPLAY */
        pan(((struct var *)arg)->yoffset);
        return 0;
    case 0x4602: { /* FBIOGET_FSCREENINFO */
        struct fix *f = arg;
        memset(f, 0, sizeof *f);
        f->id[0] = 'm', f->id[1] = '1';
        f->smem_len = W * H * 4 * 2;
        f->visual = 2; /* FB_VISUAL_TRUECOLOR */
        f->ypanstep = 1;
        f->line_length = W * 4;
        return 0;
    }
    case 0x4611: { /* FBIOBLANK: 0 on, else off */
        char c = (long)arg ? '1' : '0';
        if (blank_fd < 0) blank_fd = ((open_fn)dlsym(RTLD_NEXT, "open"))(BLANK_FILE, O_RDWR | O_CREAT | O_TRUNC, 0644);
        if (blank_fd >= 0) pwrite(blank_fd, &c, 1, 0);
        return 0;
    }
    default: /* FBIO_WAITFORVSYNC and the rest: done */
        return 0;
    }
}

/* Touch: tslib on /dev/input/event3 (demo's tslib_run). Its input module asks the device for its
 * axes, which a FIFO cannot answer, so tslib itself is replaced: ts_read takes one sample at a
 * time from the FIFO as three ints, x, y and pressure (0 lifts). */
struct ts { int fd; };
struct ts_sample { int x, y; unsigned pressure; long sec, usec; };
static struct ts touch = { -1 };
void *ts_open(const char *dev, int nonblock) {
    (void)nonblock;
    if (touch.fd < 0) touch.fd = ((open_fn)dlsym(RTLD_NEXT, "open"))(dev, O_RDWR, 0);
    return touch.fd < 0 ? (void *)0 : &touch;
}
int ts_config(void *ts) { return (void)ts, 0; }
int ts_close(void *ts) { return (void)ts, 0; }
int ts_read(void *ts, struct ts_sample *samp, int nr) {
    int v[3];
    long got = 0;
    if (ts != &touch || nr < 1) return -1;
    while (got < (long)sizeof v) {
        long r = read(touch.fd, (char *)v + got, sizeof v - (size_t)got);
        if (r <= 0) return -1;
        got += r;
    }
    memset(samp, 0, sizeof *samp);
    samp->x = v[0], samp->y = v[1], samp->pressure = (unsigned)v[2];
    return 1;
}

/* Shell commands demo runs (cmd_mcu, killall, mount, reboot...) would run on the host: each is
 * logged and reported done instead. popen gets an empty stream. */
static void logged(const char *cmd) {
    static int fd = -1;
    if (fd < 0) fd = ((open_fn)dlsym(RTLD_NEXT, "open"))(SYSTEM_LOG, O_RDWR | O_CREAT | 0x8 /* O_APPEND */, 0644);
    if (fd < 0 || !cmd) return;
    write(fd, cmd, strlen(cmd));
    write(fd, "\n", 1);
}
/* The factory record authcode_fun reads from mtd5: a serial, M1PODSIM000001, and the code the app
 * derives from it, laid out where it reads them (otherwise Home is an "SN Error" page). */
#define AUTH_RECORD "xex10266xxf0a4fxxa510cxxM1PODSIM000001"
int system(const char *cmd) {
    logged(cmd);
    /* The card checks (mount > file, then a search for /mnt/mmc): the card is in. */
    if (cmd && !strncmp(cmd, "mount > ", 8)) {
        static const char mounts[] = "/dev/mmcblk0p1 /mnt/mmc vfat rw,relatime 0 0\n";
        int fd = ((open_fn)dlsym(RTLD_NEXT, "open"))(cmd + 8, O_RDWR | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) write(fd, mounts, sizeof mounts - 1), close(fd);
    }
    if (cmd && !strncmp(cmd, "mtd_debug read /dev/mtd5 ", 25)) {
        int fd = ((open_fn)dlsym(RTLD_NEXT, "open"))("/tmp/asssco.ini", O_RDWR | O_CREAT | O_TRUNC, 0644);
        if (fd >= 0) write(fd, AUTH_RECORD, sizeof AUTH_RECORD), close(fd);
    }
    return 0;
}
void *popen(const char *cmd, const char *mode) {
    logged(cmd);
    return ((popen_fn)dlsym(RTLD_NEXT, "popen"))("true", mode);
}

/* No bluetoothd, no system bus: libbtctl's server would wait for them for ever. Bluetooth is off. */
int btctl_start_server(void *loop) { return (void)loop, 0; }
int btctl_create_daemon_thread(void *thread) { return (void)thread, 0; }

/* The host's directory offsets and inode numbers are 64-bit (ext4 hashes, overlayfs), which the
 * guest's 32-bit readdir rejects with EOVERFLOW, ending every listing after its first entries: the
 * entry comes from readdir64 and is truncated into a 32-bit dirent instead, as on the device. */
struct dirent32 { unsigned d_ino; int d_off; unsigned short d_reclen; unsigned char d_type; char d_name[256]; };
struct dirent64 { unsigned long long d_ino; long long d_off; unsigned short d_reclen; unsigned char d_type; char d_name[256]; };
struct dirent32 *readdir(void *dir) {
    static struct dirent32 out; /* readdir's own static entry, as glibc's per stream; demo reads it at once */
    struct dirent64 *e = ((struct dirent64 * (*)(void *)) dlsym(RTLD_NEXT, "readdir64"))(dir);
    if (!e) return 0;
    out.d_ino = (unsigned)e->d_ino | 1;
    out.d_off = (int)(e->d_off & 0x7fffffff);
    out.d_reclen = sizeof out;
    out.d_type = e->d_type;
    unsigned i = 0;
    for (; i < sizeof out.d_name - 1 && e->d_name[i]; ++i) out.d_name[i] = e->d_name[i];
    out.d_name[i] = 0;
    return &out;
}
