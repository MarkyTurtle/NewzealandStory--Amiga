"""50 frames a second (src/smooth.s): how often each level gets its in-between frames, and that the
game keeps its speed.

  python3 enhanced/tools/test_smooth.py [--levels N] [--passes N] [--seed S] [--chip BYTES] [--blittime]

Each level is played in the study emulator (original/tools/nzsemu) as in test_scroller.py - from
the start-up, the level poked in, N passes (default 240) with a random joystick - twice: at 50 Hz
and with the in-between frames turned off (SmoothOn 0, the 25 Hz scroller). For each: the frames
the N passes took (the same game speed: about 2 a pass in both), and at 50 Hz how many passes had
their in-between frame drawn (SmoothMids) or left out (SmoothSkips: not enough time, the camera
jumped, the first pass). The emulator counts the CPU's time; with --blittime the blitter's too
(the CPU waits for each blit as long as an A500's blitter takes; the bitplanes' share of chip
memory still not counted), nearer a real A500.

Then levels 1 and 4 again with a snapshot at each frame: every object M draws must be half-way
between where the S frames before and after it draw it (BlitBob's $8 / $A).

Writes enhanced/build/test_smooth/summary.txt.
"""
import os, re, struct, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
sys.path.insert(0, HERE)
import build_disk                                           # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(ENH, 'build', 'test_smooth')
FIRE = 'joy f\nframes 8\njoy\n'


def run(syms, lv, passes, seed, smooth, pre, tmp):
    tag = f'l{lv}_{int(smooth)}'
    s = pre + ('' if smooth else f'poke {syms["SmoothOn"] + 4} 0 b\n')
    s += ('setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
          f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
          f'snap {tmp}/{tag}_a\npasses {passes} {seed} 0x42CE 0 {tmp}/x\nsnap {tmp}/{tag}_b\n')
    p = os.path.join(tmp, tag + '.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), p],
                   check=True, stdout=subprocess.DEVNULL)
    a, b = (open(os.path.join(tmp, f'{tag}_{x}.mem'), 'rb').read() for x in 'ab')
    frames = struct.unpack_from('>H', b, syms['ScrFrames'])[0] - struct.unpack_from('>H', a, syms['ScrFrames'])[0]
    mids = struct.unpack_from('>L', b, syms['SmoothMids'])[0] - struct.unpack_from('>L', a, syms['SmoothMids'])[0]
    skips = struct.unpack_from('>L', b, syms['SmoothSkips'])[0] - struct.unpack_from('>L', a, syms['SmoothSkips'])[0]
    return frames & 0xFFFF, mids, skips


def midpoints(syms, lv, passes, seed, pre, tmp):
    """the level played with a snapshot at each pass's two frames: where the last S is shown
    (SmoothMid) and where M is (after it, $42DE). For every object drawn in S, M and the next S,
    its screen position as BlitBob drew it ($8, $A): M's must be half-way -> (half-way, not)"""
    out = []
    for tag, addr in (('s', syms['SmoothMid']), ('m', 0x42DE)):
        s = pre + ('setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
                   f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
                   f'passes {passes} {seed} 0x42CE 1 {tmp}/mp{lv}{tag} {addr:#x}\n')
        p = os.path.join(tmp, f'mp{lv}{tag}.txt')
        open(p, 'w').write(s)
        subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), p],
                       check=True, stdout=subprocess.DEVNULL)

    def objs(k, tag):
        f = os.path.join(tmp, f'mp{lv}{tag}_{k:04d}.mem')
        if not os.path.exists(f):
            return None
        m = open(f, 'rb').read()
        o = {}
        for i in range(71):
            a = 0x64380 + i * 0x3A
            if struct.unpack_from('>L', m, a + 0x18)[0] and struct.unpack_from('>H', m, a + 0x12)[0]:
                o[i] = struct.unpack_from('>hh', m, a + 8)
        return o
    good = bad = 0
    for k in range(2, passes):
        s0, mm, s1 = objs(k, 's'), objs(k, 'm'), objs(k + 1, 's')
        if not (s0 and mm and s1):
            continue
        for i in mm:
            if i in s0 and i in s1:
                for j in (0, 1):
                    a, b, c = s0[i][j], mm[i][j], s1[i][j]
                    if abs(c - a) > 40:
                        continue                    # (jumped: drawn where it is)
                    if abs(2 * b - a - c) <= 2:
                        good += 1
                    else:
                        bad += 1
    for f in os.listdir(tmp):
        if f.startswith(f'mp{lv}'):
            os.remove(os.path.join(tmp, f))
    return good, bad


def main():
    args = sys.argv[1:]
    n = int(args[args.index('--levels') + 1]) if '--levels' in args else 20
    passes = int(args[args.index('--passes') + 1]) if '--passes' in args else 240
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1000
    syms = build_disk.symbols(os.path.join(ENH, 'build', 'nzs_game.lst'))
    pre = ''
    if '--chip' in args:
        pre = f'poke {syms["EnhMachine"] + 4 + 12} {int(args[args.index("--chip") + 1], 0)} l\n'
    if '--blittime' in args:                        # the CPU waits for the blitter as on an A500
        pre += 'blittime 1\n'
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    jobs = [(lv, sm) for lv in range(n) for sm in (True, False)]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        res = list(ex.map(lambda j: run(syms, j[0], passes, seed + j[0], j[1], pre, tmp), jobs))
    lines = [f'{n} levels, {passes} passes each (the emulator: the CPU timed, '
             f'{"the blitter too" if "--blittime" in args else "the blitter not"})',
             'level: in-between frames drawn / left out | frames taken at 50 Hz / at 25 Hz']
    tm = ts = f50 = f25 = 0
    for k in range(n):
        (fa, mids, skips), (fb, _, _) = res[2 * k], res[2 * k + 1]
        tm += mids; ts += skips; f50 += fa; f25 += fb
        lines.append(f'{k:2}: {mids:3} / {skips:3} | {fa:4} / {fb:4}')
    for lv in (1, 4):
        g, b = midpoints(syms, lv, 120, seed + lv, pre, tmp)
        lines.append(f'level {lv}, M frames: {g} object positions half-way, {b} not (an animation frame\'s own '
                     f'offset changing: a turn)')
    lines.append(f'all: {tm} drawn, {ts} left out ({100 * tm / max(1, tm + ts):.1f}% at 50 Hz); '
                 f'{f50} frames at 50 Hz, {f25} at 25 Hz ({f50 / max(1, n * passes):.3f} / {f25 / max(1, n * passes):.3f} a pass)')
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    open(os.path.join(OUT, 'summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
