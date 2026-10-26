"""Which BOB frames each level draws, observed: every level played in tools/nzsemu with a random
joystick, the kiwi moved to each object the level places in turn (so that every one comes on
screen; not to the caged kiwi, which would end the level), 99 lives; every call of BlitBob
logged with the frame and, for an object's, its type, mirror flag and script. Only what is drawn
while the level is still the one started counts: if the level is finished anyway (the time, a
warp), the next level's drawing is left out.

  python3 tools/levels/observe.py OUT.json [SEEDS]

Writes {level: {"frames": [...], "by_type": {type: [frames]}, "scripts": {type: [scripts]}}};
frames >= $122 are the mirrored copies (frame + $122). Used by frames.py to check the static
analysis (scripts.py).
"""
import json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import levels                                                   # noqa: E402
from amiga_gfx import program                                   # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
KIWI = 0x643BA                      # the kiwi's object: x.w, y.w
FIRE = 'joy f\nframes 8\njoy\n'


def run(lv, objs, seed, tmp):
    log = os.path.join(tmp, f'l{lv}_{seed}.log')
    s = (f'frames 200\n' + FIRE + f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 99 w\n'
         f'frames 120\n' + FIRE + f'frames 100\nlog {log}\ntrace 0xB6C4\nrandom 600 {seed}\n')
    for k, o in enumerate(o for o in objs if o['type'] not in (1, 2)):
        s += (f'poke {KIWI} {o["x"]} w\npoke {KIWI + 2} {max(0, o["y"] - 16)} w\npoke 0x641D2 99 w\n'
              f'random 150 {seed * 1000 + k}\n')
    p = os.path.join(tmp, f'l{lv}_{seed}.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ORIG, 'bin', 'main.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), p],
                   check=True, stdout=subprocess.DEVNULL)
    out, scr = {}, {}
    for ln in open(log):
        m = re.search(r'pc \$B6C4 d0 \$\w+ d1 \$(\w+) .* type \$(\w+) mirror \$\w+ script \$(\w+) level \$(\w+)', ln)
        if m and int(m.group(4), 16) == lv * 16:
            f, t = int(m.group(1), 16) & 0xFFFF, int(m.group(2), 16)
            out.setdefault(t, set()).add(f)
            if t != 0xFFFE:                                 # (not the panel)
                scr.setdefault(t, set()).add(int(m.group(3), 16))
    return lv, out, scr


def main():
    outp = sys.argv[1]
    seeds = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    m = program()
    tmp = tempfile.mkdtemp()
    jobs = []
    for lv in range(levels.LEVELS):
        info = levels.level_data(m, lv)[0]
        for sd in range(1, seeds + 1):
            jobs.append((lv, info['objects'], sd))
    res, rsc = {}, {}
    with ThreadPoolExecutor(os.cpu_count() or 2) as ex:
        for lv, out, scr in ex.map(lambda j: run(*j, tmp), jobs):
            r = res.setdefault(lv, {})
            for t, fs in out.items():
                r.setdefault(t, set()).update(fs)
            q = rsc.setdefault(lv, {})
            for t, ss in scr.items():
                q.setdefault(t, set()).update(ss)
    js = {str(lv): {'frames': sorted(set().union(*r.values())) if r else [],
                    'by_type': {str(t): sorted(fs) for t, fs in sorted(r.items())},
                    'scripts': {str(t): ['%X' % x for x in sorted(ss)] for t, ss in sorted(rsc[lv].items())}}
          for lv, r in sorted(res.items())}
    json.dump(js, open(outp, 'w'), indent=0)
    for lv in sorted(res):
        print(lv, len(js[str(lv)]['frames']), 'frames')


if __name__ == '__main__':
    main()
