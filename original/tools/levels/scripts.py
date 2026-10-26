"""Every animation script the code can give an object, and so every BOB frame each object type
can show - found statically from the code.

  python3 tools/levels/scripts.py [OUT.json]

An object's frame ($12) is written in one place only: the animation interpreter (sub_0B1C2,
$B2C0), from the object's script ($14) at its position ($22). BlitBob's other callers draw the
panel and effects. So the frames an object type can show are the frames of the scripts its code
can set:

  * the type's own script (dat_05854 +4);
  * every script the code reachable from the type's handler (dat_05854 +0) puts in $14 of an
    object, or passes in a0 to sub_0B4E4 (the object maker): `move.l #X,$14(aN)`,
    `lea X,a0`, `movea.l X(pc,dN),a0` (a table of scripts, 4 or 8 bytes apart), ...; a table
    put in $18 is a table of handlers, followed too (sub_085E6 turns an object into a random
    enemy: a table of handler, script pairs);
  * the scripts those scripts go to (`$801C` goto, `$802C-$8038` conditionals) and the code
    they call (`$804C`);
  A script ends in a restart ($8000), an end ($803C), a goto ($801C), or a stop ($8048: the
    speed cleared, so it never steps on); one put straight into an object's $14 may also just
    stop where the code that set it takes over.
  * the types the code creates (moveq #N,d6 / bsr sub_057E8) and the handlers it installs
    (`move.l #X,$18(aN)`, `lea X,a1` for sub_0B4E4) are followed too.

A script is often entered part-way: the object list's parameter and the code set its position
($22), and a script continues after a restart (`$8000`) with more steps reached that way. So a
script's frames are those of its whole block: from its start, past restarts and ends, up to the
next address that is itself a script some code refers to, or labelled in the source (other data),
or code, or a word that is neither a frame nor a command.

Types 10-21 (the enemies that ride) also take code and a script from dat_05A7C, by type - 10
(an indirect jump, at $6F64). Types 27-30 are not animated by a script: their handler ($6DA4) shows the first word as a
frame and reads the third as a time.

The code is the traced disassembly (tools/disasm/main_trace.json), decoded on the fly (capstone)
where the trace did not reach; a branch through a table (`jmp X(pc,dN)`) follows the table's
`bra` entries; other indirect jumps are not followed.
"""
import json, os, re, struct, sys
import capstone
HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import levels as L                                              # noqa: E402
from amiga_gfx import program                                   # noqa: E402

CODE_END = 0xF340                   # the code and its tables end before the sound samples
BOSS = 579                          # a world's extra bank (its boss): directory entries from $3BED6
NFRAMES = BOSS + 32                 # (frames 0-288 the main bank, 290-578 their mirrored copies)
MAKE = {0x57D8, 0x57E8}             # make an object of a type (d6)
FRAME_ONLY = {27, 28, 29, 30}       # types whose "script" is frame.w, 0, time.w (handler $6DA4)
RIDERS = 0x5A7C                     # types 10-21: code.l, script.l each, by type - 10 (jmp (a0) at $6F64)
ARGS = {0x04: 4, 0x08: 4, 0x0C: 4, 0x10: 4, 0x14: 4, 0x18: 4, 0x20: 4, 0x24: 2, 0x28: 4,
        0x2C: 8, 0x30: 8, 0x34: 8, 0x38: 8, 0x40: 2, 0x44: 6, 0x48: 2, 0x4C: 6}
HEX = re.compile(r'\$([0-9a-f]+)')
SPLIT = re.compile(r',\s*(?![^()]*\))')


class Code:
    """the program's instructions: traced, or decoded when first asked for"""
    def __init__(self, m):
        d = json.load(open(os.path.join(ORIG, 'tools', 'disasm', 'main_trace.json')))
        self.traced = {int(k, 16): v for k, v in d['insn'].items()}
        self.m = m
        self.md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
        self.decoded = {}
        # the code: traced, but not what the sweep took for code after a routine (it may be
        # data - the generator's door scripts at $6070 are disassembled as a routine)
        swept, cur = set(), None
        lines = open(os.path.join(ORIG, 'nzs_main.s')).read().split('\n')
        lab = re.compile(r'^([A-Za-z_]\w*):')
        adr = re.compile(r';\s*([0-9A-F]{5})\s*$')
        for ln in lines:
            mm = lab.match(ln)
            if mm:
                if 'found by the code sweep' in ln:
                    cur = True
                elif not mm.group(1).startswith('l_'):
                    cur = None
            a = adr.search(ln)
            if cur and a:
                swept.add(int(a.group(1), 16))
        self.code_set = set(self.traced) - swept
        # every label in the source with its address in its name: where a block of data ends
        self.labels = {int(x, 16) for x in re.findall(r'^(?:sub|l|dat|jtab)_([0-9A-F]{5}):', '\n'.join(lines), re.M)}

    def __call__(self, a):
        if a in self.traced:
            return self.traced[a]
        if a not in self.decoded:
            i = next(self.md.disasm(bytes(self.m[a:a + 10]), a), None) if 0x400 <= a < len(self.m) - 10 else None
            self.decoded[a] = [i.size, i.mnemonic, i.op_str, ''] if i else None
        return self.decoded[a]


def step(m, p):
    """one script word at p -> (frame or None, size, targets, code called), or None: not a script word"""
    if not 0x400 <= p < CODE_END:                        # (scripts are among the code and its tables)
        return None
    v = struct.unpack_from('>H', m, p)[0]
    if not v & 0x8000:
        return (v - 1 if v else None, 2, [], []) if v <= NFRAMES else None
    c = v & 0x7FFF
    if c in (0x00, 0x3C):
        return None, 2, [], []
    if c == 0x1C:
        return None, 6, [struct.unpack_from('>L', m, p + 2)[0]], []
    if c not in ARGS:
        return None
    if c in (0x2C, 0x30, 0x34, 0x38):
        return None, 8, [struct.unpack_from('>L', m, p + 4)[0]], []
    if c == 0x4C:
        return None, 6, [], [struct.unpack_from('>L', m, p + 2)[0]]
    return None, ARGS[c], [], []


def valid(m, s, depth=0, seen=None):
    """is s a script: a run of script words ending in a restart, an end or a goto, whose
    targets are scripts too"""
    seen = seen if seen is not None else set()
    if s in seen:
        return True
    seen.add(s)
    if not (0x400 <= s < CODE_END) or s & 1:
        return False
    p = s
    for _ in range(512):
        r = step(m, p)
        if r is None:
            return False
        f, size, tg, _ = r
        v = struct.unpack_from('>H', m, p)[0]
        for t in tg:
            if not valid(m, t, depth + 1, seen):
                return False
        if v in (0x8000, 0x803C, 0x801C, 0x8048):
            return True
        p += size
    return False


def refs(ops):
    out = []
    for part in [p.strip() for p in SPLIT.split(ops)]:
        mm = re.match(r'^#\$([0-9a-f]+)$', part)
        if mm:
            out.append((int(mm.group(1), 16), 'imm'))
            continue
        mm = re.match(r'^\$([0-9a-f]+)\(pc, [ad]\d\.[wl]\)$', part)
        if mm:
            out.append((int(mm.group(1), 16), 'table'))
            continue
        mm = re.match(r'^\$([0-9a-f]+)(\(pc\)|\.l|\.w)?$', part)
        if mm:
            out.append((int(mm.group(1), 16), 'abs'))
    return out


class Analysis:
    def __init__(self, m):
        self.m, self.code = m, Code(m)
        self.types = L.object_types(m)
        self.vmemo = {}
        self.reached = {}

    def is_script(self, s):
        if s not in self.vmemo:
            self.vmemo[s] = valid(self.m, s)
        return self.vmemo[s]

    def loose(self, s):
        """a script that need not end in a restart, an end or a goto: frames and commands up to
        code or a word that is neither (the code that set it stops it), at least one frame"""
        if not (0x400 <= s < CODE_END) or s & 1:
            return False
        p, n = s, 0
        while True:
            r = step(self.m, p)
            if r is None or (p != s and p in self.code.code_set):
                return n > 0
            n += r[0] is not None
            p += r[1]

    def table(self, a, ok):
        """a table at a of entries 4 or 8 bytes apart (8: the scripts and handlers of
        sub_085E6's table are interleaved): the longs while each passes ok"""
        best = []
        for stride in (4, 8):
            out = []
            for k in range(64):
                if a + stride * k + 4 > len(self.m):
                    break
                x = struct.unpack_from('>L', self.m, a + stride * k)[0]
                if x == 0:
                    continue
                if not ok(x):
                    break
                out.append(x)
            if len(out) > len(best):
                best = out
        return best

    def reach(self, root):
        """code from root -> (scripts set, handlers installed, types made)"""
        if root in self.reached:
            return self.reached[root]
        self.reached[root] = (set(), set(), set())
        scripts, handlers, made, seen, todo = set(), set(), set(), set(), [root]
        while todo:
            a = todo.pop()
            last_d6 = pending_a0 = None
            while a not in seen:
                i = self.code(a)
                if i is None:
                    break
                seen.add(a)
                size, mn, ops = i[0], i[1], i[2]
                parts = [p.strip() for p in SPLIT.split(ops)]
                d = parts[-1] if len(parts) > 1 else ''
                base = mn.split('.')[0]
                if base.startswith(('b', 'db')) and base not in ('btst', 'bchg', 'bclr', 'bset'):
                    pass
                else:
                    for x, how in refs(ops):
                        to_script = d.startswith('$14(a') or d in ('a0', 'a2', 'a3') or (d == 'a1' and base in ('lea', 'movea'))
                        if how == 'table' and d.startswith('$14(a'):
                            scripts.update(self.table(x, lambda v: self.is_script(v) or self.loose(v)))
                        elif how == 'table' and to_script:
                            scripts.update(self.table(x, self.is_script))
                        elif how == 'table' and d.startswith('$18(a'):
                            handlers.update(self.table(x, lambda v: v in self.code.code_set))
                        elif how in ('imm', 'abs') and d == 'a0' and base in ('lea', 'movea', 'move') and self.loose(x):
                            pending_a0 = x                  # (a script if sub_0B4E2 / 4 is called next)
                        if how in ('imm', 'abs') and (d.startswith('$18(a') or (base == 'lea' and d == 'a1' and x in self.code.traced)):
                            handlers.add(x)
                        if how in ('imm', 'abs') and to_script and self.is_script(x):
                            scripts.add(x)
                        elif how in ('imm', 'abs') and d.startswith('$14(a') and self.loose(x):
                            scripts.add(x)              # (put straight into an object: a script)
                if base == 'moveq' and d == 'd6':
                    last_d6 = int(HEX.search(ops).group(1), 16) if '#$' in ops else 0
                if base in ('rts', 'rte', 'illegal'):
                    break
                if base == 'jmp' and '(pc,' in ops:
                    t = int(HEX.search(ops).group(1), 16)
                    while self.code(t) and self.code(t)[1].startswith('bra'):
                        todo.append(t); t += self.code(t)[0]
                    break
                tgt = None
                if base in ('jmp', 'jsr'):
                    mm = re.match(r'^\$([0-9a-f]+)(\.[wl]|\(pc\))?$', ops)
                    tgt = int(mm.group(1), 16) if mm else None
                elif base.startswith(('b', 'db')) and base not in ('btst', 'bchg', 'bclr', 'bset'):
                    h = HEX.findall(ops)
                    tgt = int(h[-1], 16) if h else None
                if tgt is not None:
                    if base in ('bsr', 'jsr') and tgt in MAKE and last_d6 is not None:
                        made.add(last_d6)
                    if base in ('bsr', 'jsr'):
                        if tgt in (0xB4E2, 0xB4E4) and pending_a0 is not None:
                            scripts.add(pending_a0)
                        pending_a0 = None
                    todo.append(tgt)
                if base in ('bra', 'jmp'):
                    break
                a += size
        self.reached[root] = (scripts, handlers, made)
        return self.reached[root]

    def type_refs(self, t):
        """the scripts a type's code refers to, and the types it makes"""
        ty = self.types[t]
        scripts, roots, done, made = set(), {ty['handler']}, set(), set()
        if t not in FRAME_ONLY and self.is_script(ty['script']):
            scripts.add(ty['script'])
        if 10 <= t <= 21:                                   # the riders' table, indexed by type
            roots.add(L.L(self.m, RIDERS + 8 * (t - 10)))
            scripts.add(L.L(self.m, RIDERS + 8 * (t - 10) + 4))
        while True:
            for s in list(scripts):                         # code the scripts call
                for x in self.script_walk(s)[2]:
                    roots.add(x)
            new = roots - done
            if not new:
                break
            done |= new
            for r in new:
                s, h, mk = self.reach(r)
                scripts |= s; roots |= h; made |= mk
        if ty['linked'] and ty['linked'] < L.NTYPES:
            made.add(ty['linked'])
        made.discard(t)
        return scripts, {x for x in made if x < L.NTYPES}

    def script_walk(self, s):
        """the scripts reached from s by its gotos and conditionals -> (scripts, ..., code)"""
        seen, todo, calls = set(), [s], set()
        while todo:
            x = todo.pop()
            if x in seen:
                continue
            seen.add(x)
            p = x
            for _ in range(512):
                r = step(self.m, p)
                if r is None:
                    break
                f, size, tg, cl = r
                todo += tg; calls |= set(cl)
                if struct.unpack_from('>H', self.m, p)[0] in (0x8000, 0x803C, 0x801C):
                    break
                p += size
        return seen, None, calls

    def block_frames(self, s, starts):
        """the frames of the block from s: past restarts and ends up to the next script start,
        code or a word that is not a script word"""
        frames, p = set(), s
        for _ in range(1024):
            if p != s and (p in starts or p in self.code.code_set or p in self.code.labels):
                break
            r = step(self.m, p)
            if r is None:
                break
            if r[0] is not None:
                frames.add(r[0])
            p += r[1]
        return frames


def analyse(m):
    an = Analysis(m)
    per = {t: an.type_refs(t) for t in range(L.NTYPES)}
    # every script start the code refers to, and those they go to: the blocks' bounds
    starts = set()
    for t, (s, _) in per.items():
        for x in s:
            starts |= an.script_walk(x)[0]
    starts |= {ty['script'] for ty in an.types}
    out = {}
    for t, (s, made) in per.items():
        allsc = set()
        for x in s:
            allsc |= an.script_walk(x)[0]
        fr = set()
        for x in allsc:
            fr |= an.block_frames(x, starts)
        if t in FRAME_ONLY:
            fr.add(L.w(m, an.types[t]['script']) - 1)
        out[t] = dict(frames=sorted(fr), scripts=sorted(allsc), makes=sorted(made))
    for t in out:                       # with the types it makes, and those they make
        seen, todo = set(), [t]
        while todo:
            x = todo.pop()
            if x not in seen:
                seen.add(x); todo += out[x]['makes']
        out[t]['types'] = sorted(seen)
        out[t]['all_frames'] = sorted(set().union(*(set(out[x]['frames']) for x in seen)))
    return out, an, common(an, starts)


# drawn without a script, by sub_0B69A (frame d1 - 1) and BlitBob (frame d1) on the panel and the
# screens between levels: the kiwi icon ($4058 ...: d1 1), the lives ($5284: $23), the oxygen
# gauge ($5352: BlitBob $23, $24), the EXTEND letters collected ($4328, $74BE, $74F8: $CA + 0-5)
PANEL = {0, 34, 35, 36} | set(range(201, 207))


def common(an, starts):
    """the frames every level can show: the scripts the code reachable from the entry points and
    the interrupts sets (the kiwi, the score, ...), and the panel's"""
    d = json.load(open(os.path.join(ORIG, 'tools', 'disasm', 'main_trace.json')))
    roots = {int(k, 16) for k, v in d['labels'].items() if v == 'entry'}
    roots |= {int(x, 16) for v in d['vectors'].values() for x in v}
    scripts, done = set(), set()
    while roots - done:
        for r in list(roots - done):
            done.add(r)
            sc, h, _ = an.reach(r)
            scripts |= sc
            roots |= h
    fr = set(PANEL)
    for x in scripts:
        for y in an.script_walk(x)[0]:
            fr |= an.block_frames(y, starts)
    return sorted(fr)


def main():
    m = program()
    out, an, com = analyse(m)
    p = sys.argv[1] if len(sys.argv) > 1 else None
    if p:
        js = {str(k): dict(v, scripts=['%X' % x for x in v['scripts']]) for k, v in out.items()}
        json.dump(dict(types=js, common=com), open(p, 'w'), indent=1)
    print(f"common: {len(com)} frames")
    for t, v in out.items():
        print(f"type {t:2}: {len(v['frames']):3} frames ({len(v['all_frames']):3} with the types it makes "
              f"{v['makes']}), {len(v['scripts'])} scripts")
    print('code decoded beyond the trace:', sum(1 for v in an.code.decoded.values() if v), 'instructions')


if __name__ == '__main__':
    main()
