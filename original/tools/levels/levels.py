"""The levels: their data decoded, their maps rendered with the objects placed on them.

  python3 tools/levels/levels.py OUTDIR

Writes OUTDIR/levelNN.png (the whole map, each object the level places drawn where it starts,
with its type number), OUTDIR/levelNN_map.png (the map alone), OUTDIR/levels.json and
OUTDIR/types.png (each object type's first frame).

The data (docs/LEVELS.md):

  LevelTable ($5DBA), 20 levels of 16 bytes:
    +0  long  the level's tile attributes: a word a tile (collision), $AAAA ends (sub_0C5C0 makes
              the collision map at $462A6 from it and the map)
    +4  long  the level's object list (sub_05AD4)
    +8  long  (a word before the tile attributes)
    +C  word  the first of the 5 tracks of its world data: packed as the main program; unpacked
              at $3CAA6: '01', 16 colours (half value), ...; the 16 x 16 tiles from +$80,
              128 bytes each (16 lines of the 4 planes' words in turn)
    +E  word  the track of its map, at $44AA6: '01', width.w (columns), height.w (rows), ...;
              from +$80, rows of 64 bytes (a byte a tile) - the top row last: row R (from the
              top) is at +$80 + (height - 1 - R) x 64
  The camera's limits (sub_0C5C0): x up to width x 16 - $130, y up to (height - 11) x 16; level
  15 ($8 = $F0) is 32 columns wide whatever its map says.

  The object list: time.w (the level's time, at least $28: (a6)), a byte, the kiwi's start
  (x, y in tiles), a byte; then objects: type.b (negative ends), x.b, y.b (tiles: placed at
  x x 16 + 4, y x 16), then a byte: negative none; for type 3 a path (dat_05C0A); otherwise
  bit 7 moves it 8 pixels right and the rest is where its animation script starts ($22).

  Object types (dat_05854), 12 bytes each: handler.l (the object's $18), animation script.l
  ($14), d2.w (frames a step), linked type.w (an object created with it, e.g. what it rides).
"""
import json, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ORIG, 'tools', 'assets'))
sys.path.insert(0, os.path.join(ORIG, 'tools', 'disk'))
from amiga_gfx import program, rgb, planar, to_image          # noqa: E402
import pack                                                   # noqa: E402
import bobs                                                   # noqa: E402
from PIL import Image, ImageDraw                              # noqa: E402

LEVEL_TABLE, LEVELS = 0x5DBA, 20
TYPES, NTYPES = 0x5854, 46
TRACK = 5632
MIRROR = 0x122                      # the mirrored frames' numbers: + the main bank's count ($88(a6))


def w(m, a): return struct.unpack_from('>H', m, a)[0]
def sw(m, a): return struct.unpack_from('>h', m, a)[0]
def L(m, a): return struct.unpack_from('>L', m, a)[0]


def track(t):
    return open(os.path.join(ORIG, 'disk', 'files', 'tracks', f't{t:03d}.bin'), 'rb').read()


def object_types(m):
    return [dict(type=k, handler=L(m, TYPES + 12 * k), script=L(m, TYPES + 12 * k + 4),
                 speed=w(m, TYPES + 12 * k + 8), linked=w(m, TYPES + 12 * k + 10)) for k in range(NTYPES)]


def script_frames(m, start, limit=400):
    """the frames an animation script shows from its start (1-based in the script; 0 = none),
    following its jumps: -> (frames, scripts reached, code it calls, mirrors?)"""
    frames, seen, todo, code, mirror = set(), set(), [start], set(), False
    while todo:
        s = todo.pop()
        if s in seen or not 0x400 <= s < 0x52FA0:
            continue
        seen.add(s)
        p = s
        for _ in range(limit):
            v = w(m, p)
            if not v & 0x8000:
                if v:
                    frames.add(v - 1)
                p += 2
                continue
            c = v & 0x7FFF
            if c == 0x00 or c == 0x3C:                      # restart / end
                break
            if c in (0x04, 0x08, 0x0C, 0x10, 0x14, 0x18, 0x28):
                p += 4
            elif c == 0x1C:                                 # goto
                todo.append(L(m, p + 2)); break
            elif c in (0x2C, 0x30, 0x34, 0x38):             # compare, then a script: if / else on
                todo.append(L(m, p + 4)); p += 8
            elif c == 0x20:                                 # loop count
                p += 4
            elif c == 0x24:                                 # loop
                p += 2
            elif c == 0x40:                                 # mirror toggled
                mirror = True; p += 2
            elif c == 0x44:                                 # a field set
                if w(m, p + 2) == 0x10:
                    mirror = True
                p += 6
            elif c == 0x48:
                p += 2
            elif c == 0x4C:                                 # code called
                code.add(L(m, p + 2)); p += 6
            else:
                break                                       # (not a command: the end of the data)
    return frames, seen, code, mirror


def level_data(m, lv):
    e = LEVEL_TABLE + 16 * lv
    attrs, objs, extra, t5, tmap = L(m, e), L(m, e + 4), L(m, e + 8), w(m, e + 12), w(m, e + 14)
    world = pack.unpack(b''.join(track(t5 + k) for k in range(5)))
    mp = track(tmap)
    width, height = w(mp, 2), w(mp, 4)
    if lv == 15:
        width = 32
    pal = [(w(world, 2 + 2 * k) * 2) & 0xFFF for k in range(16)]
    # the object list
    p = objs
    time = w(m, p); p += 2
    p += 1
    kiwi = (m[p] * 16 + 4, m[p + 1] * 16); p += 2
    p += 1
    placed = []
    while m[p] < 0x80:
        t, x, y = m[p], m[p + 1] * 16 + 4, m[p + 2] * 16
        prm = m[p + 3]
        p += 4
        o = dict(type=t, x=x, y=y)
        if prm < 0x80 or (t != 3 and prm & 0x80 and prm != 0xFF):
            pass
        if prm != 0xFF and prm < 0x80:
            if t == 3:
                o['path'] = prm
            else:
                o['script_start'] = prm * 2
        elif prm != 0xFF and prm >= 0x80 and t != 3:
            o['x'] += 8
            o['script_start'] = (prm & 0x7F) * 2
        placed.append(o)
    return dict(level=lv, tracks=[t5, t5 + 4], map_track=tmap, width=width, height=height,
                camera_max=[width * 16 - 0x130, (height - 11) * 16], time=time, kiwi=kiwi,
                objects=placed, attributes=attrs, object_list=objs, palette=['%03X' % c for c in pal]), world, mp, pal


def tile_image(world, t, pal):
    d = world[0x80 + 128 * t:0x80 + 128 * (t + 1)]
    if len(d) < 128:
        d = d + bytes(128 - len(d))
    rows = planar(d, 2, 16, 4, plane_size=2, row_bytes=8)
    return to_image(rows, pal).convert('RGB')


def render_map(world, mp, info, pal):
    W, H = info['width'], info['height']
    img = Image.new('RGB', (W * 16, H * 16))
    cache = {}
    for r in range(H):
        for c in range(W):
            t = mp[0x80 + (H - 1 - r) * 64 + c] if 0x80 + (H - 1 - r) * 64 + c < len(mp) else 0
            if t not in cache:
                cache[t] = tile_image(world, t, pal)
            img.paste(cache[t], (c * 16, r * 16))
    return img


def first_frame(m, script, start=0):
    p = script + start
    for _ in range(64):
        v = w(m, p)
        if v and not v & 0x8000:
            return v - 1
        if v & 0x8000:
            c = v & 0x7FFF
            if c == 0x1C:
                p = L(m, p + 2); continue
            p += {0x04: 4, 0x08: 4, 0x0C: 4, 0x10: 4, 0x14: 4, 0x18: 4, 0x28: 4, 0x20: 4, 0x24: 2,
                  0x40: 2, 0x44: 6, 0x48: 2, 0x4C: 6, 0x2C: 8, 0x30: 8, 0x34: 8, 0x38: 8}.get(c, 2)
            if c in (0x00, 0x3C):
                return None
        else:
            p += 2
    return None


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    m = program()
    types = object_types(m)
    gpal = [(w(m, 0xC1AA + 2 * k) * 2) & 0xFFF for k in range(16)]
    d, g, end = bobs.BANKS['main']
    fr = bobs.frames(m, d, g, end)
    def bob(n, pal):
        if n is None or n >= len(fr):
            return None
        return bobs.frame_image(m, g, fr[n], pal)[0]
    # the types' sheet
    tw = 64
    sheet = Image.new('RGBA', (12 * tw, ((NTYPES + 11) // 12) * (tw + 12)), (40, 40, 48, 255))
    dr = ImageDraw.Draw(sheet)
    for t in types:
        t['first_frame'] = first_frame(m, t['script'])
        x0, y0 = (t['type'] % 12) * tw, (t['type'] // 12) * (tw + 12)
        im = bob(t['first_frame'], gpal)
        if im:
            sheet.alpha_composite(im.crop((0, 0, min(im.width, tw), min(im.height, tw))), (x0 + 2, y0 + 12))
        dr.text((x0 + 2, y0), f"{t['type']}", fill=(220, 220, 120, 255))
    sheet.save(os.path.join(out, 'types.png'))
    levels = []
    for lv in range(LEVELS):
        info, world, mp, pal = level_data(m, lv)
        img = render_map(world, mp, info, pal)
        img.save(os.path.join(out, f'level{lv:02d}_map.png'))
        im = img.convert('RGBA')
        dr = ImageDraw.Draw(im)
        for o in info['objects'] + [dict(type=0, x=info['kiwi'][0], y=info['kiwi'][1])]:
            t = types[o['type']] if o['type'] < NTYPES else None
            f = first_frame(m, t['script'], o.get('script_start', 0)) if t else None
            b = bob(f, pal)
            if b:
                im.alpha_composite(b, (max(0, min(o['x'], im.width - b.width)), max(0, min(o['y'], im.height - b.height))))
            dr.rectangle((o['x'], o['y'], o['x'] + 15, o['y'] + 15), outline=(255, 255, 0, 255))
            dr.text((o['x'] + 1, o['y'] - 10), str(o['type']), fill=(255, 255, 0, 255))
        im.convert('RGB').save(os.path.join(out, f'level{lv:02d}.png'))
        levels.append(info)
        print(f"level {lv:2}: {info['width']}x{info['height']} tiles, {len(info['objects'])} objects, kiwi at {info['kiwi']}")
    json.dump(dict(levels=levels, types=types), open(os.path.join(out, 'levels.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
