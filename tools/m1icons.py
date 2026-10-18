#!/usr/bin/env python3
"""Draw the M1 Plus Home cards the payload adds (assets/icons/m1/): Coverflow and More, in the stock
cards' look, a 66px flat disc with a white line glyph; each _down variant at half brightness with a
grey glyph, as stock's pressed cards. Run once; the PNGs are committed."""
import pathlib
from PIL import Image, ImageDraw

OUT = pathlib.Path(__file__).resolve().parents[1]/'assets/icons/m1'
S, K = 66, 8  # final size, supersampling


def card(color, glyph, down):
    big = Image.new('RGBA', (S*K, S*K), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    fill = tuple(c // 2 for c in color) if down else color
    d.ellipse([0, 0, S*K - 1, S*K - 1], fill=fill + (255,))
    glyph(d, (128, 128, 128, 255) if down else (255, 255, 255, 255))
    return big.resize((S, S), Image.LANCZOS)


def px(v): return int(v * K)


def coverflow(d, ink):
    w = px(2.2)
    # two receding covers either side of a front cover
    d.polygon([(px(13), px(24)), (px(22), px(21)), (px(22), px(45)), (px(13), px(42))], outline=ink, width=w)
    d.polygon([(px(53), px(24)), (px(44), px(21)), (px(44), px(45)), (px(53), px(42))], outline=ink, width=w)
    d.rectangle([px(24), px(19), px(42), px(47)], outline=ink, width=w)
    d.line([px(17), px(51), px(49), px(51)], fill=ink, width=w)


def more(d, ink):
    for x in (20, 33, 46):
        d.ellipse([px(x - 3.6), px(33 - 3.6), px(x + 3.6), px(33 + 3.6)], fill=ink)


if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    for name, color, glyph in (('Coverflow', (141, 64, 169), coverflow), ('More', (226, 158, 30), more)):
        for down in (0, 1):
            card(color, glyph, down).save(OUT/f'{name}{"_down" if down else ""}.png', optimize=True)
