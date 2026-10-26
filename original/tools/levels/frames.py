"""Which BOB frames each level can show, and what keeping only those would save.

  python3 tools/levels/frames.py OUT.json [OBSERVED.json]

The frames a level can show, statically (scripts.py): the common frames (the kiwi, the score,
the panel: every level) and those of the object types it has - the types its object list
places, those its generators (type 3) let out, and every type their code makes in turn.

OBSERVED.json (observe.py: each level played in the emulator) checks it: every frame drawn
there must be in the level's static set.

Frames are counted in the main bank (289 frames, $22AA6); a mirrored frame is drawn as
frame + $122 from the mirrored copies sub_0C52C builds at start-up. Frames from 579 are the
world's boss bank (2 tracks at $6C000, on the 4th level of worlds 1, 2, 3 and 5), not counted.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import levels as L                                              # noqa: E402
import scripts as SC                                            # noqa: E402
from amiga_gfx import program                                   # noqa: E402
import bobs                                                     # noqa: E402


def frame_sizes(m):
    d, g, end = bobs.BANKS['main']
    return {n: 4 + 10 * wd * ht for n, off, x, y, w, h, c, wd, ht in bobs.frames(m, d, g, end)}


def level_types(m, info, per):
    """the types a level can have: placed, let out by its generators, and all they make"""
    t0 = {0} | {o['type'] for o in info['objects']}
    for o in info['objects']:
        t0 |= set(o.get('makes', []))
    out = set()
    for t in t0:
        out |= set(per[t]['types']) if t < L.NTYPES else {t}
    return out


def main():
    outp = sys.argv[1]
    obs = json.load(open(sys.argv[2])) if len(sys.argv) > 2 else None
    m = program()
    size = frame_sizes(m)
    nf = len(size)
    per, an, com = SC.analyse(m)
    bank = sum(size.values())
    res, worlds, problems = {}, {}, []
    for lv in range(L.LEVELS):
        info = L.level_data(m, lv)[0]
        types = level_types(m, info, per)
        fr = set(com).union(*(set(per[t]['all_frames']) for t in types if t < L.NTYPES))
        main_fr = {f for f in fr if f < nf}
        r = dict(types=sorted(types), frames=sorted(main_fr), boss_frames=sorted(f for f in fr if f >= SC.BOSS),
                 bytes=sum(size[f] for f in main_fr))
        if obs:
            o = obs[str(lv)]
            drawn = {f % L.MIRROR for f in o['frames'] if f < 2 * L.MIRROR}
            r['observed'] = len(drawn)
            r['observed_mirrored'] = sorted({f - L.MIRROR for f in o['frames'] if L.MIRROR <= f < 2 * L.MIRROR})
            miss = sorted(drawn - main_fr)
            r['observed_not_static'] = miss
            if miss:
                problems.append(f'level {lv}: drawn but not found statically: {miss}')
        res[lv] = r
        wk = L.w(m, L.LEVEL_TABLE + 16 * lv + 12)
        wd = worlds.setdefault(wk, dict(levels=[], frames=set()))
        wd['levels'].append(lv)
        wd['frames'] |= main_fr
    allf = set().union(*(set(r['frames']) for r in res.values()))
    summary = dict(bank_frames=nf, bank_bytes=bank, common=len([f for f in com if f < nf]),
                   used=len(allf), used_bytes=sum(size[f] for f in allf),
                   never=sorted(set(range(nf)) - allf),
                   worlds={str(k): dict(levels=v['levels'], frames=len(v['frames']),
                                        bytes=sum(size[f] for f in v['frames'])) for k, v in sorted(worlds.items())})
    json.dump(dict(summary=summary, levels={str(k): v for k, v in res.items()}, common=com), open(outp, 'w'), indent=1)
    print(f"main bank: {nf} frames, {bank} bytes (and its mirrored copies the same again)")
    print(f"common to every level: {summary['common']} frames; used on some level: {len(allf)} "
          f"({summary['used_bytes']} bytes); never: {summary['never']}")
    for lv, r in res.items():
        extra = f", observed {r['observed']}" if obs else ''
        print(f"level {lv:2}: {len(r['frames']):3} frames {r['bytes']:6} bytes{extra}")
    for k, v in summary['worlds'].items():
        print(f"world (tracks from {k}) levels {v['levels']}: {v['frames']} frames, {v['bytes']} bytes")
    print('\n'.join(problems) if problems else 'every frame observed is in its level\'s static set')
    return not problems


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
