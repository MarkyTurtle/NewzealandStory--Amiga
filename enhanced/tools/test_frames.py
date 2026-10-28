"""The BOB frames in one blit (src/frames.s): what the 512K cache costs in play, against all
frames built once (more chip RAM).

  python3 enhanced/tools/test_frames.py [--levels N] [--passes N] [--seed S]

Each level is played as in test_scroller.py (from the start-up, the level poked in, N passes
with a random joystick; default 240) in the study emulator (original/tools/nzsemu) with the
blitter timed (blittime: the CPU waits for it as on an A500), three times:
  * 512K (the machine's chip RAM left at 0): the cache, filled as the level starts with the
    frames it is known to draw (OneWarm), logging each frame built in play (OneMiss);
  * the same with OneWarm cleared ("cold": every frame built in play - the worst case, as for a
    level drawing frames the lists never saw);
  * 1MB of chip RAM (the machine description poked): all frames built once.
For each: the frames built in play (count, bytes, the most in one pass) and the in-between frames
(50 frames a second, src/smooth.s) drawn and left out for lack of time.

Writes enhanced/build/test_frames/summary.txt.
"""
import os, re, struct, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
sys.path.insert(0, HERE)
import build_disk                                           # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(ENH, 'build', 'test_frames')
FIRE = 'joy f\nframes 8\njoy\n'


def run(syms, lv, passes, seed, mode, tmp):
    tag = f'l{lv}_{mode}'
    log = os.path.join(tmp, tag + '.log')
    s = 'blittime 1\n'
    if mode == '1mb':
        s += f'poke {syms["EnhMachine"] + 4 + 12} {0x100000} l\n'   # (block 1 stored 4 higher) MI_CHIP+4
    s += ('setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
          f'until 0x40F8 60000\n')
    if mode == 'cold':                              # nothing built as the level starts (block 3 is
        z = os.path.join(tmp, 'zero.bin')           #   in place by now: its run address)
        open(z, 'wb').write(bytes(syms['OneWarmEnd'] - syms['OneWarm']))
        s += f'load {z} {syms["OneWarm"]}\n'
    s += (f'poke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
          f'snap {tmp}/{tag}_a\nlog {log}\ntrace {syms["OneMiss"]}\npasses {passes} {seed} 0x42CE 0 {tmp}/x\n'
          f'snap {tmp}/{tag}_b\n')
    p = os.path.join(tmp, tag + '.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ENH, 'build', 'loads'), p],
                   check=True, stdout=subprocess.DEVNULL)
    a, b = (open(os.path.join(tmp, f'{tag}_{x}.mem'), 'rb').read() for x in 'ab')
    d = lambda sym: struct.unpack_from('>L', b, syms[sym])[0] - struct.unpack_from('>L', a, syms[sym])[0]
    per = {}
    if os.path.exists(log):
        for ln in open(log):
            m = re.match(r'frame (\d+) line \d+: pc \$\w+ d0 \$(\w+)', ln)
            if m:
                per[int(m.group(1)) // 2] = per.get(int(m.group(1)) // 2, 0) + 1
    return dict(built=d('OneMisses'), bytes=d('OneMissBytes'), most=max(per.values(), default=0),
                mids=d('SmoothMids'), skips=d('SmoothSkips'))


def main():
    args = sys.argv[1:]
    n = int(args[args.index('--levels') + 1]) if '--levels' in args else 20
    passes = int(args[args.index('--passes') + 1]) if '--passes' in args else 240
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1000
    syms = build_disk.symbols(os.path.join(ENH, 'build', 'nzs_game.lst'))
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    modes = ('512k', 'cold', '1mb')
    jobs = [(lv, m) for lv in range(n) for m in modes]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        res = list(ex.map(lambda j: run(syms, j[0], passes, seed + j[0], j[1], tmp), jobs))
    lines = [f'{n} levels, {passes} passes each, the blitter timed: the 512K cache (warm: filled as the '
             'level starts, as the game does; cold: nothing built ahead) against all frames built once (1MB)',
             'level: built in play: frames (bytes; most in a pass) warm | cold;  in-between frames left out: '
             'warm | cold | 1MB']
    tot = {m: dict(built=0, bytes=0, most=0, mids=0, skips=0) for m in modes}
    for k in range(n):
        r = dict(zip(modes, res[3 * k:3 * k + 3]))
        for m in modes:
            for f in ('built', 'bytes', 'mids', 'skips'):
                tot[m][f] += r[m][f]
            tot[m]['most'] = max(tot[m]['most'], r[m]['most'])
        w, c, o = r['512k'], r['cold'], r['1mb']
        lines.append(f"{k:2}: {w['built']:3} ({w['bytes']:6}; {w['most']}) | {c['built']:3} ({c['bytes']:6}; "
                     f"{c['most']});  {w['skips']:2} | {c['skips']:2} | {o['skips']:2}")
    pct = lambda m: 100 * tot[m]['mids'] / max(1, tot[m]['mids'] + tot[m]['skips'])
    lines.append(f"all: built in play {tot['512k']['built']} frames ({tot['512k']['bytes']} bytes, at most "
                 f"{tot['512k']['most']} in a pass) warm, {tot['cold']['built']} ({tot['cold']['bytes']} bytes) cold; "
                 f"at 50 Hz: {pct('512k'):.1f}% warm, {pct('cold'):.1f}% cold, {pct('1mb'):.1f}% 1MB")
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    open(os.path.join(OUT, 'summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return True


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
