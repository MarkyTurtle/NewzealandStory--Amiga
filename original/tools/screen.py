"""Render the Amiga display from a memory image by following the copper list, line by line:
MOVEs to the bitplane pointers, BPLCON0/1, the modulos, DIWSTRT and the colours, WAITs on the
vertical position. Enough for the game's screens (lowres, up to 5 planes + dual playfield not
modelled; sprites drawn separately when asked).

  from screen import render; img = render(mem, cop1lc)        # PIL image 320 x 256
  python3 tools/screen.py SNAP.bin COP1LC out.png
"""
import struct, sys


def render(mem, cop, custom=None, width=320, top=0x2C, lines=256):
    from PIL import Image
    r16 = lambda a: mem[a] << 8 | mem[a + 1]
    regs = dict(custom or {})
    regs.setdefault(0x100, 0x0200)
    events = []                     # (vpos, reg, value) in copper order
    pc = cop & 0x1FFFFE
    vpos = 0
    for _ in range(4000):
        w1, w2 = r16(pc), r16(pc + 2); pc += 4
        if w1 & 1 == 0:
            events.append((vpos, w1 & 0x1FE, w2))
        else:
            if w1 == 0xFFFF and w2 == 0xFFFE: break
            if w2 & 1 == 0:                          # WAIT
                v = w1 >> 8
                if v < (vpos & 0xFF) and vpos >= 0xFF: v += 0x100
                elif vpos >= 0x100: v += 0x100
                vpos = max(vpos, v)
            # SKIP ignored
    img = Image.new('RGB', (width, lines))
    px = img.load()
    ptr = [0] * 6
    ei = 0
    cur = dict(regs)
    for y in range(lines):
        line = top + y
        while ei < len(events) and events[ei][0] <= line:
            _, reg, val = events[ei]; ei += 1
            cur[reg] = val
            if 0xE0 <= reg <= 0xF6:
                i = (reg - 0xE0) // 4
                if reg & 2: ptr[i] = (ptr[i] & 0xFFFF0000) | val
                else: ptr[i] = (ptr[i] & 0xFFFF) | (val << 16)
        con0 = cur.get(0x100, 0)
        n = (con0 >> 12) & 7
        pal = [cur.get(0x180 + 2 * i, 0) for i in range(32)]
        for x in range(width):
            c = 0
            for p in range(n):
                a = ptr[p] + (x >> 3)
                if a < len(mem) and mem[a] >> (7 - (x & 7)) & 1: c |= 1 << p
            col = pal[c & 31]
            px[x, y] = ((col >> 8 & 15) * 17, (col >> 4 & 15) * 17, (col & 15) * 17)
        bw = width // 8
        for p in range(n):
            mod = cur.get(0x108 if p % 2 == 0 else 0x10A, 0)
            if mod & 0x8000: mod -= 0x10000
            ptr[p] += bw + mod
    return img


if __name__ == '__main__':
    mem = open(sys.argv[1], 'rb').read()
    render(mem, int(sys.argv[2], 0)).save(sys.argv[3])
