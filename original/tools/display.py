"""What the Amiga shows, from a memory image and the custom registers: the copper list followed
line by line, with the display window (DIWSTRT/DIWSTOP), the data fetch (DDFSTRT/DDFSTOP), the
fine scroll (BPLCON1, each playfield's own delay), the modulos and the bitplane pointers
(reloaded wherever the copper writes them). Lowres, up to 5 planes; no sprites, no dual
playfield. Used to compare the original game's display with the enhanced game's, whose memory
layout differs completely (tools/nzsemu snapshots).

  from display import render; img = render(mem, regs)    # regs: {register offset: value}
  python3 tools/display.py SNAPSHOT_PREFIX OUT.png        (a nzsemu snapshot: .mem, .regs)

The image covers horizontal positions $81-$1C0 (320 pixels) and the lines of the display window
(DIWSTRT to DIWSTOP); outside the window is COLOR00.
"""
import struct, sys

H0 = 0x81                                   # the image's first horizontal position


def copper_events(mem, cop):
    """[(line, register, value)] in the copper list's order, with the line from which each
    applies (WAITs: the vertical position; $FFDF: line 255, the waits after it are 256 and on)"""
    r16 = lambda a: mem[a] << 8 | mem[a + 1]
    out, pc, vpos, high = [], cop & 0x1FFFFE, 0, False
    for _ in range(8000):
        w1, w2 = r16(pc), r16(pc + 2); pc += 4
        if not w1 & 1:
            out.append((vpos, w1 & 0x1FE, w2))
        elif w1 == 0xFFFF and w2 == 0xFFFE:
            break
        elif not w2 & 1:                                       # WAIT (the horizontal part ignored)
            if w1 == 0xFFDF:
                high, v = True, 0xFF
            else:
                v = (w1 >> 8) + (0x100 if high else 0)
            vpos = max(vpos, v)
    return out


def render(mem, regs, first=None, last=None):
    from PIL import Image
    r16 = lambda a: mem[a] << 8 | mem[a + 1]
    cur = dict(regs)
    events = copper_events(mem, (cur.get(0x80, 0) << 16 | cur.get(0x82, 0)))
    diw0, diw1 = cur.get(0x8E, 0x2C81), cur.get(0x90, 0xF4C1)
    vstart = diw0 >> 8
    vstop = (diw1 >> 8) | (0 if diw1 & 0x8000 else 0x100)
    first = vstart if first is None else first
    last = vstop if last is None else last
    img = Image.new('RGB', (320, last - first))
    px = img.load()
    ptr = [0] * 6
    for k in range(6):
        ptr[k] = (cur.get(0xE0 + 4 * k, 0) << 16 | cur.get(0xE2 + 4 * k, 0)) & 0x1FFFFE
    ei = 0
    for line in range(0, last):
        while ei < len(events) and events[ei][0] <= line:
            _, reg, val = events[ei]; ei += 1
            cur[reg] = val
            if 0xE0 <= reg <= 0xF6:
                i = (reg - 0xE0) // 4
                ptr[i] = (ptr[i] & 0xFFFF) | (val << 16) if not reg & 2 else (ptr[i] & 0xFFFF0000) | val
                ptr[i] &= 0x1FFFFE
        if not vstart <= line < vstop:
            continue
        con0, con1 = cur.get(0x100, 0), cur.get(0x102, 0)
        n = (con0 >> 12) & 7
        ddf0, ddf1 = cur.get(0x92, 0x38) & 0xFC, cur.get(0x94, 0xD0) & 0xFC
        words = (ddf1 - ddf0) // 8 + 1
        h0 = 2 * ddf0 + 0x11                                   # where the first fetched pixel shows
        dh0, dh1 = cur.get(0x8E, diw0) & 0xFF, (cur.get(0x90, diw1) & 0xFF) | 0x100
        pal = [cur.get(0x180 + 2 * i, 0) for i in range(32)]
        rows = []
        for p in range(n):
            rows.append(bytes(mem[(ptr[p] + k) & 0x1FFFFF] for k in range(2 * words)))
        y = line - first
        if 0 <= y < last - first:
            for x in range(320):
                h = H0 + x
                c = 0
                if dh0 <= h < dh1:
                    for p in range(n):
                        d = con1 & 15 if p % 2 == 0 else con1 >> 4 & 15
                        i = h - h0 - d
                        if 0 <= i < 16 * words and rows[p][i >> 3] >> (7 - (i & 7)) & 1:
                            c |= 1 << p
                col = pal[c & 31]
                px[x, y] = ((col >> 8 & 15) * 17, (col >> 4 & 15) * 17, (col & 15) * 17)
        for p in range(n):
            mod = cur.get(0x108 if p % 2 == 0 else 0x10A, 0)
            if mod & 0x8000:
                mod -= 0x10000
            ptr[p] = (ptr[p] + 2 * words + mod) & 0x1FFFFE
    return img


def load(prefix):
    mem = open(prefix + '.mem', 'rb').read()
    r = open(prefix + '.regs', 'rb').read()
    regs = {2 * i: struct.unpack_from('>H', r, 2 * i)[0] for i in range(0x100)}
    return mem, regs


if __name__ == '__main__':
    mem, regs = load(sys.argv[1])
    render(mem, regs).save(sys.argv[2])
