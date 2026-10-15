/* Resolve audited extra imports from the already-loaded stock libraries.
 * MIPS lazy GOT slots cannot be used to infer a library's load address. The
 * loader's public r_debug/link_map ABI supplies that address without forcing an
 * unrelated library call. Both pinned M1 libc and libcstl carry DT_HASH. */
#include "m1_loader.h"

typedef unsigned u32;
struct dyn { int tag; u32 value; };
struct map { u32 base; const char *name; const struct dyn *dynamic; struct map *next, *prev; };
struct sym { u32 name, value, size; unsigned char info, other; unsigned short section; };

static int same(const char *a, const char *b) {
    unsigned n = 0;
    while (a[n] && a[n] == b[n] && n < 128) ++n;
    return n < 128 && a[n] == b[n];
}
static u32 elf_hash(const char *s) {
    u32 h = 0, g;
    while (*s) {
        h = (h << 4) + (unsigned char)*s++;
        if ((g = h & 0xf0000000u)) h ^= g >> 24;
        h &= ~g;
    }
    return h;
}
static u32 pointer(u32 base, u32 value) {
    return base && value < base ? base + value : value;
}

void *m1_resolve(const char *name) {
    /* MIPS glibc fills RLD_MAP, not the generic DT_DEBUG value. */
    u32 *debug = *(u32 *volatile *)M1_RLD_MAP;
    struct map *m = debug ? (struct map *)debug[1] : 0;
    for (unsigned module = 0; m && module < 128; m = m->next, ++module) {
        const u32 *hash = 0;
        const struct sym *symbols = 0;
        const char *strings = 0;
        u32 string_size = 0;
        for (unsigned i = 0; m->dynamic && i < 256 && m->dynamic[i].tag; ++i) {
            u32 v = m->dynamic[i].value;
            switch (m->dynamic[i].tag) {
            case 4: hash = (const u32 *)pointer(m->base, v); break;
            case 5: strings = (const char *)pointer(m->base, v); break;
            case 6: symbols = (const struct sym *)pointer(m->base, v); break;
            case 10: string_size = v; break;
            }
        }
        if (!hash || !symbols || !strings || !hash[0] || hash[0] > 65536 || hash[1] > 65536) continue;
        const u32 *bucket = hash+2, *chain = bucket+hash[0];
        u32 index = bucket[elf_hash(name) % hash[0]];
        for (unsigned n = 0; index && index < hash[1] && n < hash[1]; index = chain[index], ++n) {
            const struct sym *s = symbols+index;
            if (s->section && s->value && s->name < string_size &&
                ((s->info >> 4) == 1 || (s->info >> 4) == 2) &&
                (s->info & 15) == 2 && same(strings+s->name, name))
                return (void *)(m->base+s->value);
        }
    }
    return 0;
}
