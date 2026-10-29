"""How often each frame of the main BOB bank is drawn on each level, from plays in the study
emulator: enhanced/tools/frame_counts.json, which build_disk.py reads to choose the frames built
into the 512K cache as each level starts (src/frames.s: OneWarm) - the most drawn first.

  python3 enhanced/tools/frame_counts.py [--plays N] [--passes N]

Each level is played N times (default 4, each with its own random joystick; seeds 5000 on, apart
from the tests' 1000 on) for the given passes (default 400), as in test_scroller.py: from the
start-up, the level poked in. Every frame BlitBob is asked to draw is counted (the trace at
$B7CC: d1 = the frame; the in-between frames' drawing too, as it draws the same frames).
Frames 0-578: the main bank's (290-578 mirrored); the boss's own (579 on) are left out.
"""
import json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(HERE, 'frame_counts.json')
FIRE = 'joy f\nframes 8\njoy\n'
FRAMES = 579


def play(lv, seed, passes, tmp):
    log = os.path.join(tmp, f'{lv}_{seed}.log')
    s = ('setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
         f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
         f'log {log}\ntrace 0xB7CC\npasses {passes} {seed} 0x42CE 0 {tmp}/x\n')
    p = os.path.join(tmp, f'{lv}_{seed}.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ENH, 'build', 'loads'), p],
                   check=True, stdout=subprocess.DEVNULL)
    c = {}
    for ln in open(log):
        m = re.search(r' d1 \$(\w+) ', ln)
        if m:
            f = int(m.group(1), 16) & 0xFFFF
            if f < FRAMES:
                c[f] = c.get(f, 0) + 1
    os.remove(log)
    os.remove(p)
    return lv, c


def main():
    args = sys.argv[1:]
    plays = int(args[args.index('--plays') + 1]) if '--plays' in args else 4
    passes = int(args[args.index('--passes') + 1]) if '--passes' in args else 400
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    jobs = [(lv, 5000 + 100 * lv + k) for lv in range(20) for k in range(plays)]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        res = list(ex.map(lambda j: play(j[0], j[1], passes, tmp), jobs))
    counts = {str(lv): {} for lv in range(20)}
    for lv, c in res:
        for f, n in c.items():
            counts[str(lv)][str(f)] = counts[str(lv)].get(str(f), 0) + n
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    json.dump({'about': f'frames drawn per level (BlitBob, $B7CC): {plays} plays of {passes} passes each '
                        '(enhanced/tools/frame_counts.py)', **counts}, open(OUT, 'w'), indent=0, sort_keys=True)
    for lv in range(20):
        print(f'level {lv}: {len(counts[str(lv)])} frames drawn')


if __name__ == '__main__':
    main()
