"""The scroller against the original: both programs run in the study emulator
(original/tools/nzsemu) with the same input, and what each shows is compared pixel for pixel
(original/tools/display.py follows each one's copper list) at frames all through a session.

  python3 enhanced/tools/test_scroller.py [--levels N] [--every P] [--passes N] [--seed S] [--chip BYTES] [--keep]

--chip: the enhanced game's machine description given that much chip RAM (default: none
recorded, as on a 512K machine; 0x100000 for 1MB: the mirrored frames all built at start-up
rather than the cache, src/mirror.s).

The session: the attract mode, then for each level (the level number poked in as the level
starts, as tools/nzsemu/coverage.py does) N passes of the game loop (default 240) with a
random joystick (from seed S + the level), a snapshot every P passes (default 5). The two programs stay in step pass
for pass rather than frame for frame (the enhanced game's first pass after a level starts can
take a frame more): the joystick changes between passes (nzsemu's passes, at the loop's call of
the background, $42DE, the same address in both), the snapshots are taken there, and the
vertical blank's addition to the random seed is cancelled (setd1 $BE04 -1: it adds d1, which
is whatever the interrupted code had), so both draw the same random numbers.

The game logic can still drift apart: CIA-B timer B counts down (a6) (the level's time) and the
vertical blank the screen shake ($64(a6)), which the passes see at a different phase. So a
frame is compared only while the two games' state (the globals but (a6), and the objects:
$641BA-$653FF) is the same, and each level is played in a run of its own from the start-up.

Writes enhanced/build/test_scroller/: the first differences as side-by-side pictures (original
left), and a summary. Needs nzsemu built (original/tools/nzsemu/build.sh) and the disk built
(build_disk.py: build/nzs_game.bin).
"""
import os, subprocess, sys, tempfile, random
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
sys.path.insert(0, os.path.join(ORIG, 'tools'))
import display                                              # noqa: E402
from PIL import Image, ImageChops                           # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(ENH, 'build', 'test_scroller')
FIRE = 'joy f\nframes 8\njoy\n'
STATE = (0x641BA, 0x65400)          # the game's globals (but (a6), CIA-B timer B's count) and objects


def script(tmp, tag, lv, every, passes, seed, pre=''):
    """one level, from the start-up (each level in a run of its own: the same state in both)"""
    s = (pre + 'setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
         f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
         f'passes {passes} {seed} 0x42CE {every} {tmp}/{tag}_l{lv:02d} 0x42DE\n')
    return s, [f'{tag}_l{lv:02d}_{k:04d}' for k in range(1, passes // every + 1)]


def run(binary, text, tmp, tag):
    p = os.path.join(tmp, f'{tag}.txt')
    open(p, 'w').write(text)
    subprocess.run([EMU, binary, os.path.join(ORIG, 'disk', 'files', 'tracks'), p], check=True,
                   stdout=subprocess.DEVNULL)


def main():
    args = sys.argv[1:]
    n = int(args[args.index('--levels') + 1]) if '--levels' in args else 20
    every = int(args[args.index('--every') + 1]) if '--every' in args else 5
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1000
    passes = int(args[args.index('--passes') + 1]) if '--passes' in args else 240
    levels = list(range(n))
    pre = ''
    if '--chip' in args:                            # the machine's chip RAM (default: 512K)
        sys.path.insert(0, HERE)
        import build_disk
        machine = build_disk.symbols(os.path.join(ENH, 'build', 'nzs_game.lst'))['EnhMachine'] + 4 + 12
        pre = f'poke {machine} {int(args[args.index("--chip") + 1], 0)} l\n'   # (block 1 is stored 4 higher)
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    shots = []
    from concurrent.futures import ThreadPoolExecutor
    jobs = []
    for lv in levels:
        so, sh = script(tmp, 'o', lv, every, passes, seed + lv)
        se, _ = script(tmp, 'e', lv, every, passes, seed + lv, pre)
        shots += sh
        jobs += [(os.path.join(ORIG, 'bin', 'main.bin'), so, f'o{lv}'), (os.path.join(ENH, 'build', 'nzs_game.bin'), se, f'e{lv}')]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        list(ex.map(lambda j: run(j[0], j[1], tmp, j[2]), jobs))
    same = differ = apart = 0
    first = []
    for name in shots:
        if not os.path.exists(os.path.join(tmp, name + '.mem')) or not os.path.exists(os.path.join(tmp, 'e' + name[1:] + '.mem')):
            apart += 1                                       # (one game was over: they had gone apart)
            continue
        ma, ra = display.load(os.path.join(tmp, name))
        mb, rb = display.load(os.path.join(tmp, 'e' + name[1:]))
        if ma[STATE[0]:STATE[1]] != mb[STATE[0]:STATE[1]]:
            apart += 1                                       # the games have gone apart
            continue
        a, b = display.render(ma, ra), display.render(mb, rb)
        box = ImageChops.difference(a, b).getbbox()
        if box is None:
            same += 1
        else:
            differ += 1
            if len(first) < 8:
                img = Image.new('RGB', (640, max(a.height, b.height)))
                img.paste(a, (0, 0)); img.paste(b, (320, 0))
                p = os.path.join(OUT, name[2:] + '.png')
                img.save(p)
                first.append(f'{name[2:]}: differs in {box} -> {os.path.relpath(p, os.path.join(ENH, ".."))}')
    if '--keep' not in args:
        for f in os.listdir(tmp):
            os.remove(os.path.join(tmp, f))
        os.rmdir(tmp)
    else:
        print('snapshots kept in', tmp)
    lines = [f'{same + differ} frames compared over {len(levels)} levels: {same} identical, {differ} different '
             f'({apart} more not compared: the two games had gone apart)'] + first
    open(os.path.join(OUT, 'summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return differ == 0


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
