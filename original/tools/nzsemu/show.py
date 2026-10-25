"""Draw a nzsemu snapshot (PREFIX.mem, PREFIX.regs) by following its copper list (tools/screen.py).

  python3 tools/nzsemu/show.py PREFIX OUT.png [top lines]
"""
import os, struct, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import screen


def regs(prefix):
    r = open(prefix + '.regs', 'rb').read()
    return {2 * i: struct.unpack_from('>H', r, 2 * i)[0] for i in range(0x100)}


def show(prefix, out, top=0x2C, lines=256):
    mem = open(prefix + '.mem', 'rb').read()
    rg = regs(prefix)
    cop = (rg[0x80] << 16 | rg[0x82]) & 0x7FFFE
    custom = {k: v for k, v in rg.items() if 0x100 <= k < 0x1C0 or k in (0x108, 0x10A)}
    img = screen.render(mem, cop, custom=custom, top=top, lines=lines)
    img.save(out)
    return cop


if __name__ == '__main__':
    a = sys.argv
    cop = show(a[1], a[2], *(int(x, 0) for x in a[3:5]))
    print(f'copper list at ${cop:X} -> {a[2]}')
