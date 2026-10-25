"""Shared helpers for the asset tools: the program image by run address, palettes from a
nzsemu snapshot's copper list, planar graphics to images."""
import os, struct
from PIL import Image

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
MAIN = os.path.join(ROOT, 'bin', 'main.bin')
END = 0x52FA7


def program():
    """the program as it is in memory after Relocate: bytearray indexed by run address"""
    d = open(MAIN, 'rb').read()
    mem = bytearray(0x80000)
    mem[0x400:0x3210] = d[4:0x2E14]
    mem[0x3214:0x3214 + len(d) - 0x2E14] = d[0x2E14:]
    return mem


GAME_PALETTE = 0xC1AA     # the in-game palette (dat_0C1AA, set with sub_0BEFE at each level start)


def palette(mem, addr=GAME_PALETTE, n=16):
    """a palette as the game stores it: n words of half the colour value (sub_0BEFE doubles each
    word into the copper list's COLORxx moves)"""
    return [(struct.unpack_from('>H', mem, addr + 2 * k)[0] * 2) & 0xFFF for k in range(n)]


def rgb(w):
    return ((w >> 8 & 15) * 17, (w >> 4 & 15) * 17, (w & 15) * 17)


def copper_palette(mem, cop, line=None, base=None):
    """the 32 colours set by a copper list (up to a display line, if given)"""
    pal = list(base or [0] * 32)
    pc = cop
    vpos = 0
    for _ in range(2000):
        w1, w2 = struct.unpack_from('>HH', mem, pc); pc += 4
        if w1 == 0xFFFF and w2 == 0xFFFE:
            break
        if w1 & 1 == 0:
            r = w1 & 0x1FE
            if 0x180 <= r < 0x1C0 and (line is None or vpos <= line):
                pal[(r - 0x180) // 2] = w2
        elif w2 & 1 == 0:
            vpos = max(vpos, w1 >> 8)
    return pal


def planar(data, w_bytes, h, planes, plane_size=None, row_bytes=None, mask=None):
    """planes one after another (plane_size apart), rows row_bytes apart -> list of rows of indices"""
    row_bytes = row_bytes or w_bytes
    plane_size = plane_size or row_bytes * h
    out = []
    for y in range(h):
        row = []
        for x in range(w_bytes * 8):
            c = 0
            for p in range(planes):
                b = data[p * plane_size + y * row_bytes + (x >> 3)]
                c |= (b >> (7 - (x & 7)) & 1) << p
            row.append(c)
        out.append(row)
    return out


def to_image(rows, pal, transparent=None, bg=(0, 0, 0, 0)):
    """indices -> RGBA image; where the mask (transparent) is 0 the pixel is left as bg"""
    h, w = len(rows), len(rows[0]) if rows else 0
    img = Image.new('RGBA', (max(w, 1), max(h, 1)), bg)
    px = img.load()
    for y, row in enumerate(rows):
        for x, c in enumerate(row):
            if transparent is not None and transparent[y][x] == 0:
                continue
            px[x, y] = rgb(pal[c]) + (255,)
    return img
