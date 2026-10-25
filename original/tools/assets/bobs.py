"""The BOB (blitter object) banks: a frame directory of 16 bytes a frame
  +0 long  offset of the frame's graphics in the bank's data
  +4 word  x offset of the top left from the object's position (signed)
  +6 word  y offset
  +8 word  width in pixels, +$A word height
  +$C word (0 in the main bank)
and per frame: long (width in words << 16 | height), then the graphics, stored interleaved by
word: for each line, for each 16-pixel column, 5 words - the mask, then planes 0-3. At start-up
(and for a level's extra graphics) sub_04E92 rearranges each frame in place into 5 separate
blocks (mask, plane 0 ... plane 3, each width x 2 x height bytes), the form sub_0B6C4 draws with
the cookie-cut minterm $CA into a 320 x 4-plane screen whose planes are $2000 apart.

  python3 tools/assets/bobs.py OUTDIR

Writes OUTDIR/bobs_NAME.png (every frame, numbered, on a sheet), OUTDIR/NAME/frameNNN.png
(transparent where the mask is clear) and frameNNN.bin (the frame as stored), and bobs.json.
"""
import os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amiga_gfx import program, palette, planar, to_image, rgb
import json
from PIL import Image, ImageDraw

BANKS = {'main': (0x39AA6, 0x22AA6, 0x3CAA6)}       # directory, data, directory end


def frames(mem, d, g, end):
    out = []
    n = 0
    while d + 16 * n < end:
        e = mem[d + 16 * n:d + 16 * n + 16]
        off, x, y, w, h, c = struct.unpack('>LhhHHH', e[:14])
        if off > 0x40000 or (n and e == bytes(16)):
            break
        ww, hh = struct.unpack_from('>HH', mem, g + off)
        out.append((n, off, x, y, w, h, c, ww, hh))
        n += 1
    return out


def deinterleave(stored, ww, hh):
    """the stored frame (5 words per column per line) -> mask + 4 planes, as sub_04E92 makes it"""
    ps = ww * 2 * hh
    out = bytearray(5 * ps)
    k = 0
    for y in range(hh):
        for x in range(ww):
            for p in range(5):
                o = p * ps + (y * ww + x) * 2
                out[o:o + 2] = stored[k:k + 2]
                k += 2
    return bytes(out)


def frame_image(mem, g, f, pal, stored=True):
    """stored = True: the program image (interleaved); False: memory after start-up (planar)"""
    n, off, x, y, w, h, c, ww, hh = f
    ps = ww * 2 * hh
    raw = bytes(mem[g + off + 4:g + off + 4 + 5 * ps])
    planes = deinterleave(raw, ww, hh) if stored else raw
    mask = planar(planes[:ps], ww * 2, hh, 1)
    rows = planar(planes[ps:], ww * 2, hh, 4, plane_size=ps)
    return to_image(rows, pal, transparent=mask), bytes(mem[g + off:g + off + 4]) + raw


def main():
    out = sys.argv[1]
    mem = program()
    pal = palette(mem)
    info = {}
    for name, (d, g, end) in BANKS.items():
        fs = frames(mem, d, g, end)
        os.makedirs(os.path.join(out, name), exist_ok=True)
        imgs = []
        for f in fs:
            img, raw = frame_image(mem, g, f, pal)
            open(os.path.join(out, name, f'frame{f[0]:03d}.bin'), 'wb').write(raw)
            img.save(os.path.join(out, name, f'frame{f[0]:03d}.png'))
            imgs.append(img)
        info[name] = dict(directory=d, data=g, frames=[dict(frame=f[0], offset=f[1], x=f[2], y=f[3], width=f[4],
                                                              height=f[5], word=f[6]) for f in fs])
        cols, cw, ch = 16, max(i.width for i in imgs) + 4, max(i.height for i in imgs) + 14
        sheet = Image.new('RGBA', (cols * cw, ((len(imgs) + cols - 1) // cols) * ch), (40, 40, 48, 255))
        dr = ImageDraw.Draw(sheet)
        for k, img in enumerate(imgs):
            x0, y0 = (k % cols) * cw + 2, (k // cols) * ch + 2
            sheet.alpha_composite(img, (x0, y0 + 10))
            dr.text((x0, y0), str(k), fill=(160, 160, 170, 255))
        sheet.save(os.path.join(out, f'bobs_{name}.png'))
        print(f'{name}: {len(fs)} frames -> {out}/bobs_{name}.png, {name}/frameNNN.png/.bin')
    json.dump(dict(palette=['%03X' % c for c in pal], banks=info), open(os.path.join(out, 'bobs.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
