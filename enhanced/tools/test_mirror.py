"""The mirror cache (src/mirror.s) on a 512K machine against all the frames mirrored at start-up
(the original's way, the enhanced game with more chip RAM): what the cache costs in play.

  python3 enhanced/tools/test_mirror.py [--levels N] [--passes N] [--seed S]

Each level is played as in test_scroller.py (from the start-up, the level poked in, N passes
with a random joystick) five times in the study emulator (original/tools/nzsemu):
  * the cache (the machine's chip RAM left at 0: 512K), logging each frame built in play
    (MirMiss: not those built as the level starts), and then where each pass's drawing ends
    (sub_0BC8C, the flip);
  * the same with MirWarm cleared ("cold": nothing built as the level starts, all in play - the
    worst case, as for a level drawing frames never seen in the plays the list came from);
  * all frames mirrored at start-up (the machine description poked to 1MB of chip RAM): where
    each pass's drawing ends.
A pass is held to 2 frames (624 lines); one whose drawing ends later than that has overrun. The
emulator's blitter takes no time, so the lines are the CPU's alone: building a frame is CPU work,
counted in full, but on a real A500 the blits leave less room.

Writes enhanced/build/test_mirror/summary.txt.
"""
import os, re, subprocess, sys, tempfile, struct
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ORIG, 'tools', 'assets'))
import build_disk                                           # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(ENH, 'build', 'test_mirror')
FIRE = 'joy f\nframes 8\njoy\n'
FLIP = 0xBC8C                       # sub_0BC8C: the pass's drawing done, the screens flipped
LINES = 312


def run(syms, lv, passes, seed, trace, chip, tmp, cold=False):
    tag = f'l{lv}_{trace:x}_{chip:x}_{int(cold)}'
    log = os.path.join(tmp, tag + '.log')
    machine = syms['EnhMachine'] + 4 + 12          # (block 1 is stored 4 bytes higher) MI_CHIP+4
    s = f'poke {machine} {chip} l\n'
    if cold:                                        # no frames built as the level starts
        z = os.path.join(tmp, 'zero.bin')
        open(z, 'wb').write(bytes(20 * 37))
        s += f'load {z} {syms["MirWarm"] + 4}\n'
    s += ('setd1 0xBE04 0xFFFFFFFF\nframes 200\n' + FIRE +
         f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
         f'log {log}\ntrace {trace}\npasses {passes} {seed} 0x42CE 0 {tmp}/x\n')
    p = os.path.join(tmp, tag + '.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), p],
                   check=True, stdout=subprocess.DEVNULL)
    out = []
    for ln in open(log):
        m = re.match(r'frame (\d+) line (\d+): pc \$\w+ d0 \$(\w+)', ln)
        if m:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3), 16) & 0xFFFF))
    return out


def ends(trace):
    """the lines from each pass's start (the frame after the last flip) to its flip; not the
    passes longer than 4 frames: a pause (the kiwi lost, the level started again)"""
    out, start = [], None
    for f, ln, _ in trace:
        t = f * LINES + ln
        if start is not None and t - start <= 4 * LINES:
            out.append(t - start)
        start = (f + 1) * LINES                     # (the next pass starts with the next frame)
    return out


def main():
    args = sys.argv[1:]
    n = int(args[args.index('--levels') + 1]) if '--levels' in args else 20
    passes = int(args[args.index('--passes') + 1]) if '--passes' in args else 240
    seed = int(args[args.index('--seed') + 1]) if '--seed' in args else 1000
    syms = build_disk.symbols(os.path.join(ENH, 'build', 'nzs_game.lst'))
    sys.path.insert(0, os.path.join(ORIG, 'tools', 'levels'))
    import frames as F
    from amiga_gfx import program
    size = F.frame_sizes(program())
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    jobs = []
    for lv in range(n):
        jobs += [(lv, syms['MirMiss'], 0, False), (lv, FLIP, 0, False), (lv, FLIP, 0x100000, False),
                 (lv, syms['MirMiss'], 0, True), (lv, FLIP, 0, True)]
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        res = list(ex.map(lambda j: run(syms, j[0], passes, seed + j[0], j[1], j[2], tmp, j[3]), jobs))
    lines = [f'{n} levels, {passes} passes each: the cache (512K) against all frames mirrored at start-up (1MB).',
             'warm: the level\'s frames built as it starts (as the game does); cold: none (all built in play)',
             'level: built in play: frames (bytes; most in a pass) warm | cold;  drawing done by line, the latest '
             '(of 624): all | warm | cold;  overruns: all | warm | cold']
    tot = dict(nw=0, bw=0, nc=0, bc=0, oa=0, ow=0, oc=0, mc=0)

    def built(b):
        per = {}
        for f, ln, d0 in b:
            per[f // 2] = per.get(f // 2, 0) + size[d0 - 0x122]
        return len(b), sum(per.values()), max(per.values()) if per else 0

    for k in range(n):
        bw, fw, fa, bc, fc = res[5 * k:5 * k + 5]
        nw, sw, mw = built(bw)
        nc, sc, mc = built(bc)
        ew, ea, ec = ends(fw), ends(fa), ends(fc)
        ov = [sum(1 for x in e if x > 2 * LINES) for e in (ea, ew, ec)]
        tot['nw'] += nw; tot['bw'] += sw; tot['nc'] += nc; tot['bc'] += sc
        tot['oa'] += ov[0]; tot['ow'] += ov[1]; tot['oc'] += ov[2]; tot['mc'] = max(tot['mc'], mc)
        lines.append(f'{k:2}: {nw:3} ({sw:6}; {mw:5}) | {nc:3} ({sc:6}; {mc:5});  '
                     f'{max(ea, default=0):4} | {max(ew, default=0):4} | {max(ec, default=0):4};  '
                     f'{ov[0]} | {ov[1]} | {ov[2]}')
    lines.append(f"all: built in play {tot['nw']} frames ({tot['bw']} bytes) warm, {tot['nc']} ({tot['bc']} bytes, "
                 f"at most {tot['mc']} in a pass) cold; overruns {tot['oa']} all, {tot['ow']} warm, {tot['oc']} cold")
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    open(os.path.join(OUT, 'summary.txt'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return tot['ow'] <= tot['oa']


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
