"""Which BOB frames each level needs, and what keeping only those would save.

  python3 tools/levels/frames.py OBSERVED.json OUT.json

Two sources, joined:
  * static: the animation scripts of the object types the level places (and their linked types),
    walked from the type's script with every jump and conditional followed (levels.script_frames);
  * observed: tools/levels/observe.py - the frames BlitBob actually drew while the level was played.
The static walk misses the frames that handlers choose in code (the kiwi, weapons, fruit, effects,
the panel); the observed sets miss what a play-through never reached. The union is the estimate.

Frames are counted in the main bank (289 frames, $22AA6); a mirrored frame is drawn as
frame + $122 and lives in the mirrored copies sub_0C52C builds at start-up.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import levels as L                                              # noqa: E402
from amiga_gfx import program                                   # noqa: E402
import bobs                                                     # noqa: E402

def frame_sizes(m):
    d, g, end = bobs.BANKS['main']
    out = {}
    for n, off, x, y, w, h, c, wd, ht in bobs.frames(m, d, g, end):
        out[n] = 4 + 10 * wd * ht                      # header, then mask + 4 planes of words
    return out


def main():
    obs = json.load(open(sys.argv[1]))
    outp = sys.argv[2]
    m = program()
    types = L.object_types(m)
    size = frame_sizes(m)
    static = {t['type']: L.script_frames(m, t['script'])[0] for t in types}
    nframes = len(size)
    res, all_n, all_m = {}, set(), set()
    worlds = {}
    for lv in range(L.LEVELS):
        info = L.level_data(m, lv)[0]
        placed = {o['type'] for o in info['objects']}
        placed |= {types[t]['linked'] for t in placed if t < L.NTYPES and types[t]['linked'] < L.NTYPES}
        st = set().union(*(static[t] for t in placed if t < L.NTYPES))
        o = obs.get(str(lv), {'frames': []})
        normal = {f for f in o['frames'] if f < L.MIRROR} | st
        mirrored = {f - L.MIRROR for f in o['frames'] if f >= L.MIRROR}
        all_n |= normal; all_m |= mirrored
        world = L.w(m, L.LEVEL_TABLE + 16 * lv + 12)
        wd = worlds.setdefault(world, dict(levels=[], normal=set(), mirrored=set()))
        wd['levels'].append(lv); wd['normal'] |= normal; wd['mirrored'] |= mirrored
        res[lv] = dict(placed_types=sorted(placed), normal=sorted(normal), mirrored=sorted(mirrored),
                       static_only=sorted(st - {f for f in o['frames'] if f < L.MIRROR}),
                       bytes_normal=sum(size.get(f, 0) for f in normal),
                       bytes_mirrored=sum(size.get(f, 0) for f in mirrored))
    total = sum(size.values())
    summary = dict(frames=nframes, bank_bytes=total,
                   used_normal=len(all_n), used_normal_bytes=sum(size[f] for f in all_n if f in size),
                   used_mirrored=len(all_m), used_mirrored_bytes=sum(size[f] for f in all_m if f in size),
                   worlds={str(k): dict(levels=v['levels'], normal=len(v['normal']), mirrored=len(v['mirrored']),
                                        bytes=sum(size.get(f, 0) for f in v['normal']) +
                                        sum(size.get(f, 0) for f in v['mirrored']))
                           for k, v in sorted(worlds.items())})
    json.dump(dict(summary=summary, levels={str(k): v for k, v in res.items()}), open(outp, 'w'), indent=1)
    print(f"main bank: {nframes} frames, {total} bytes; mirrored copies the same again")
    print(f"used anywhere: {summary['used_normal']} frames ({summary['used_normal_bytes']} bytes), "
          f"mirrored {summary['used_mirrored']} ({summary['used_mirrored_bytes']} bytes)")
    for lv, r in res.items():
        print(f"level {lv:2}: {len(r['normal']):3} frames {r['bytes_normal']:6} bytes, mirrored {len(r['mirrored']):3} "
              f"{r['bytes_mirrored']:6} bytes (static adds {len(r['static_only'])})")
    for k, v in summary['worlds'].items():
        print(f"world (track {k}) levels {v['levels']}: {v['normal']} + {v['mirrored']} mirrored, {v['bytes']} bytes")


if __name__ == '__main__':
    main()
