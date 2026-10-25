"""Disassembly engine shared by the program configs (main_cfg.py, loader_cfg.py, boot_cfg.py).

A program is a binary plus a list of segments: (file start, file end, run address). The NZS
main program and the track 90 loader both copy their first block to another address before
running it, so every address used here is a RUN address, and the generated source puts each
segment under its own `org` inside one section (vasm then writes the bytes contiguously, with no
padding, while the labels take the run addresses).

  trace     follow the code from the entry points (capstone, 68000), collecting instructions,
            labels, data references and the indirect jumps that need seeds
  verify    assemble every traced instruction in numeric form with vasm and compare its bytes;
            an instruction that vasm encodes differently is written as dc.w with the
            disassembly as a comment, so the source always reassembles byte-identical
  generate  write the source: labels, hardware register names, comments and headers from
            the config, data as dc.b/dc.w/strings
"""
import json, os, re, subprocess, sys, tempfile
import capstone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hw import CUSTOM, CIAA, CIAB

HEX = re.compile(r'\$([0-9a-f]+)')
BRANCH_NOT = ('btst', 'bchg', 'bclr', 'bset', 'bkpt')
VECTOR_NAMES = {0x08: 'BusError', 0x0C: 'AddressError', 0x10: 'IllegalInstr', 0x14: 'ZeroDivide',
                0x18: 'ChkInstr', 0x1C: 'TrapvInstr', 0x20: 'PrivilegeViol', 0x24: 'Trace',
                0x28: 'LineA', 0x2C: 'LineF', 0x60: 'Spurious', 0x64: 'Level1', 0x68: 'Level2',
                0x6C: 'Level3', 0x70: 'Level4', 0x74: 'Level5', 0x78: 'Level6', 0x7C: 'Level7'}
for _n in range(16):
    VECTOR_NAMES[0x80 + 4 * _n] = f'Trap{_n}'


NOT_68000 = {'extb', 'cas', 'cas2', 'chk2', 'cmp2', 'divsl', 'divul', 'mulsl', 'mulul', 'rtd', 'movec', 'moves',
             'pack', 'unpk', 'callm', 'rtm', 'bkpt', 'trapcc', 'tpf'}


def is_68000(m, op):
    base = m.split('.')[0]
    if '[' in op or '*' in op or base in NOT_68000 or base.startswith(('bf', 'trap') if base != 'trap' else ('bf',)):
        return False
    if base in ('link',) and m.endswith('.l'):
        return False
    if m in ('dc.w', '.byte', '.short') or base.startswith('f') or base.startswith('p') and base not in ('pea',):
        return False
    return True


def is_branch(base):
    return base in ('bra', 'bsr') or base.startswith('db') or (base.startswith('b') and base not in BRANCH_NOT)


class Program:
    def __init__(self, cfg):
        self.cfg = cfg
        here = os.path.dirname(os.path.abspath(cfg.__file__))
        self.root = os.path.normpath(os.path.join(here, '..', '..'))
        self.data = open(os.path.join(self.root, cfg.BINARY), 'rb').read()
        self.segs = cfg.SEGMENTS                # [(file_start, file_end, run_addr)]
        self.md = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
        self.ins = {}            # addr -> [size, mnemonic, ops, hex]
        self.labels = {}         # addr -> 'sub' | 'lbl' | 'jtab' | 'entry'
        self.refs = {}           # addr -> 'dat' (data references found in operands)
        self.indirect = []
        self.vectors = {}        # vector address -> handler
        self.bad = set()         # instructions vasm encodes differently: emitted as dc.w
        self.state_file = os.path.join(here, cfg.NAME + '_trace.json')

    # ---- address mapping
    def seg_of(self, a):
        for s, e, r in self.segs:
            if r <= a < r + (e - s):
                return s, e, r
        return None

    def inside(self, a):
        return self.seg_of(a) is not None

    def get(self, a, n):
        sg = self.seg_of(a)
        if not sg:
            return b''
        s, e, r = sg
        o = s + (a - r)
        return self.data[o:min(o + n, e)]

    def dis1(self, a):
        for i in self.md.disasm(self.get(a, 10), a):
            return i
        return None

    # ---- trace
    def trace(self):
        cfg = self.cfg
        entries = list(getattr(cfg, 'ENTRIES', []))
        self.ptrtabs = {}                       # table addr -> [targets]  (dc.l code pointers)
        self.reltabs = {}                       # table addr -> [targets]  (dc.w target-*)
        for t, n in getattr(cfg, 'SELFREL_TABLES', {}).items():
            offs = [int.from_bytes(self.get(t + 2 * k, 2), 'big', signed=True) for k in range(n)]
            tg = [t + 2 * k + o if o else None for k, o in enumerate(offs)]     # 0 = no entry
            self.reltabs[t] = tg
            entries += [x for x in tg if x is not None and x not in entries]
        for t, n in getattr(cfg, 'PTRTABLES', {}).items():
            tg = [int.from_bytes(self.get(t + 4 * k, 4), 'big') for k in range(n)]
            self.ptrtabs[t] = tg
            for x in tg:
                if x not in entries:
                    entries.append(x)
        work = []
        self.came_from = {}
        self.bad_paths = []
        self.swept = []
        for e in entries:
            self.labels[e] = 'entry'
            work.append(e)
        self._follow(work)
        # addresses seen executing (tools/nzsemu coverage): traced from, without labels
        self.hints = sorted(self.load_hints())
        self._follow([h for h in self.hints if h not in self.ins])
        if getattr(cfg, 'SWEEP', False):
            self.sweep()
        self._refs()

    def _follow(self, work):
        cfg = self.cfg
        no_follow = set(getattr(cfg, 'NO_FOLLOW', []))
        stops = set(getattr(cfg, 'STOP_AFTER', []))   # instructions after which flow does not continue (e.g. a bsr that never returns)
        while work:
            a = work.pop()
            while True:
                if a in self.ins or not self.inside(a) or self.in_table(a):
                    break
                i = self.dis1(a)
                if i is None or not is_68000(i.mnemonic, i.op_str):
                    self.bad_paths.append((a, self.came_from.get(a), (i.mnemonic + ' ' + i.op_str) if i else '?'))
                    break
                m, op = i.mnemonic, i.op_str
                if m.split('.')[0] == 'btst' and op.startswith('#') and '(pc' in op:
                    # capstone bug: with an immediate bit number the pc-relative base is the
                    # second extension word, so the real target is 2 bytes further on
                    op = re.sub(r'\$([0-9a-f]+)\(pc', lambda mm: f'${int(mm.group(1), 16) + 2:x}(pc', op)
                self.ins[a] = [i.size, m, op, i.bytes.hex()]
                base = m.split('.')[0]
                tgt = None
                if is_branch(base):
                    tgt = int(HEX.findall(op)[-1], 16)
                if base in ('jmp', 'jsr'):
                    mm = re.match(r'^\$([0-9a-f]+)(\.[wl])?$', op)
                    if mm:
                        tgt = int(mm.group(1), 16)
                    elif re.match(r'^\$([0-9a-f]+)\(pc\)$', op):
                        tgt = int(HEX.findall(op)[0], 16)
                    elif re.match(r'^\$([0-9a-f]+)\(pc, d\d\.w\)$', op) and self.bra_table(int(HEX.findall(op)[0], 16), work):
                        pass
                    else:
                        self.indirect.append((a, m, op))
                # immediate stored into an object field that holds a code pointer
                mm = re.match(r'^#\$([0-9a-f]+), \$([0-9a-f]+)\((a\d)\)$', op)
                if mm and m.endswith('.l') and base in ('move', 'cmpi') and int(mm.group(2), 16) in getattr(cfg, 'CODE_FIELDS', ()):
                    v = int(mm.group(1), 16)
                    if self.inside(v):
                        self.labels.setdefault(v, 'sub')
                        self.came_from.setdefault(v, a)
                        work.append(v)
                # immediate address stored to an exception vector: an interrupt/exception handler
                mm = re.match(r'^#\$([0-9a-f]+), \$([0-9a-f]+)\.[wl]$', op)
                if base == 'move' and m.endswith('.l') and mm:
                    v, dst = int(mm.group(1), 16), int(mm.group(2), 16)
                    if 8 <= dst < 0xC0 and self.inside(v):
                        self.vectors.setdefault(dst, set()).add(v)
                        self.labels.setdefault(v, 'sub')
                        work.append(v)
                if tgt is not None and a not in no_follow:
                    if self.inside(tgt):
                        if base in ('bsr', 'jsr'):
                            self.labels[tgt] = 'sub' if self.labels.get(tgt) != 'entry' else 'entry'
                        else:
                            self.labels.setdefault(tgt, 'lbl')
                        self.came_from.setdefault(tgt, a)
                        work.append(tgt)
                if m == 'trap' and int(HEX.findall(op)[0], 16) in getattr(cfg, 'NORETURN_TRAPS', ()):
                    break
                if base in ('bra', 'jmp', 'rts', 'rte', 'rtr') or m == 'illegal' or a in stops:
                    break
                self.came_from.setdefault(a + i.size, a)
                a += i.size

    def load_hints(self):
        fn = getattr(self.cfg, 'COVERAGE', None)
        if not fn:
            return []
        path = os.path.join(os.path.dirname(os.path.abspath(self.cfg.__file__)), fn)
        out = []
        for ln in open(path):
            ln = ln.split('#')[0].strip()
            out += [int(x, 16) for x in ln.split()]
        return [a for a in out if self.inside(a)]

    def coverage_conflicts(self):
        """executed addresses that the trace has inside an instruction, or not as code at all"""
        return [a for a in self.hints if a in self.within or a not in self.ins]

    def sweep(self):
        """Find code nothing traced reaches: try each gap that starts right after an instruction
        ending the flow (rts/rte/bra/jmp) and keep what it reaches only if every path decodes as
        68000 code and overlaps nothing already traced. Repeats until nothing more is found."""
        flow_end = ('rts', 'rte', 'bra', 'jmp', 'rtr')
        skip = set(getattr(self.cfg, 'NOT_CODE', []))
        limit = getattr(self.cfg, 'SWEEP_LIMIT', None)
        tried = set()
        self.sweep_owner = {}
        skip |= getattr(self, 'reject', set())
        while True:
            found = False
            for a in sorted(self.ins):
                sz, m, op, hx = self.ins[a]
                g = a + sz
                if m.split('.')[0] not in flow_end or g in self.ins or g in tried or not self.inside(g):
                    continue
                if limit and g >= limit:
                    continue
                while self.get(g, 2) == b'\0\0' and g not in self.ins:     # padding
                    g += 2
                if g in self.ins or g in tried or g in skip or self.in_table(g) or g in self.refs_now() or not self.inside(g):
                    continue
                tried.add(g)
                snap = (dict(self.ins), dict(self.labels), dict(self.came_from), len(self.bad_paths),
                        len(self.indirect), {k: set(v) for k, v in self.vectors.items()})
                self.labels.setdefault(g, 'sub')
                self._follow([g])
                new = [x for x in self.ins if x not in snap[0]]
                ok = len(self.bad_paths) == snap[3] and len(new) >= 3
                if ok:
                    span = {}
                    for x, (z, *_r) in self.ins.items():
                        for k in range(z):
                            if x + k in span:
                                ok = False
                                break
                            span[x + k] = x
                        if not ok:
                            break
                if ok and any(self.ins[x][3].startswith('0000') for x in new):   # ori.b #0,d0: zero data
                    ok = False
                if not ok:
                    self.ins, self.labels, self.came_from = snap[0], snap[1], snap[2]
                    del self.bad_paths[snap[3]:]
                    del self.indirect[snap[4]:]
                    self.vectors = snap[5]
                else:
                    self.swept.append(g)
                    for x in new:
                        self.sweep_owner[x] = g
                    found = True
            if not found:
                break

    def refs_now(self):
        if not hasattr(self, '_refcache') or self._refcache[0] != len(self.ins):
            r = set()
            for a, (sz, m, op, hx) in self.ins.items():
                for mm in re.finditer(r'\$([0-9a-f]+)\(pc', op):
                    r.add(int(mm.group(1), 16))
                for mm in re.finditer(r'(?<![#\w-])\$([0-9a-f]+)\.[wl]', op):
                    r.add(int(mm.group(1), 16))
            self._refcache = (len(self.ins), r)
        return self._refcache[1]

    def _refs(self):
        cfg = self.cfg
        # operand references to the program
        for a, (sz, m, op, hx) in self.ins.items():
            for mm in re.finditer(r'\$([0-9a-f]+)\(pc', op):
                self.addref(int(mm.group(1), 16))
            for mm in re.finditer(r'(?<![#\w-])\$([0-9a-f]+)\.[wl]', op):
                self.addref(int(mm.group(1), 16))
            if self.imm_is_addr(a, m, op):
                self.addref(int(HEX.match(op[1:]).group(1), 16))
        for a in getattr(cfg, 'LABELS', []):
            self.addref(a)
        for t, tg in list(self.ptrtabs.items()) + list(self.reltabs.items()):
            self.addref(t)
            for x in tg:
                if x is not None:
                    self.labels.setdefault(x, 'sub')
        self.check_overlaps()

    def bra_table(self, t, work):
        """jmp t(pc,dN.w) into a list of bra.w: label each entry and trace its target."""
        k = 0
        tg = []
        while True:
            q = t + 4 * k
            if tg and q >= min(tg):
                break
            w = self.get(q, 4)
            if len(w) < 4 or w[:2] != b'\x60\x00':
                break
            tg.append(q + 2 + int.from_bytes(w[2:], 'big', signed=True))
            k += 1
        if not k:
            return False
        self.labels.setdefault(t, 'jtab')
        for j in range(k):
            work.append(t + 4 * j)
        return True

    def in_table(self, a):
        return (any(t <= a < t + 4 * len(v) for t, v in self.ptrtabs.items())
                or any(t <= a < t + 2 * len(v) for t, v in self.reltabs.items()))

    def imm_is_addr(self, a, m, op):
        """#imm operands treated as addresses of the program (move.l/lea/pea/cmpa.l/adda.l #addr)."""
        if a in getattr(self.cfg, 'IMM_NUMERIC', ()):
            return False
        mm = re.match(r'^#\$([0-9a-f]+)', op)
        if not mm or not m.endswith('.l'):
            return False
        base = m.split('.')[0]
        if base not in ('move', 'movea', 'cmpa', 'adda', 'suba', 'cmpi', 'cmp'):
            return False
        v = int(mm.group(1), 16)
        return v >= getattr(self.cfg, 'IMM_MIN', 0x400) and self.inside(v)

    def addref(self, v):
        if self.inside(v):
            self.refs.setdefault(v, 'dat')

    def check_overlaps(self):
        inside = {}
        for a, (sz, *_r) in self.ins.items():
            for k in range(1, sz):
                inside[a + k] = a
        ov = [a for a in self.ins if a in inside]
        if ov:
            print('  OVERLAPPING instructions at', ' '.join(f'${x:X}' for x in sorted(ov)[:20]), file=sys.stderr)
        self.within = inside

    # ---- verify each instruction's encoding with vasm
    def numeric(self, m, op):
        o = op
        base = m.split('.')[0]
        if base == 'moveq':
            mm = re.match(r'#\$([0-9a-f]+), (d\d)', o)
            v = int(mm.group(1), 16)
            if v > 127:
                o = f'#{v - 256}, {mm.group(2)}'
        if base in BRANCH_NOT:
            m = base
        return m, o.replace(', ', ',')

    def verify(self):
        addrs = sorted(self.ins)
        src = ['\tsection\tv,code']
        lines = {}
        for a in addrs:
            sz, m, op, hx = self.ins[a]
            mn, o = self.numeric(m, op)
            src.append(f'\torg\t${a:X}')
            src.append(f'\t{mn}\t{o}')
            lines[len(src)] = a
        with tempfile.TemporaryDirectory() as td:
            s = os.path.join(td, 'v.s'); lst = os.path.join(td, 'v.lst')
            open(s, 'w').write('\n'.join(src) + '\n')
            errlines = set()
            while True:
                r = subprocess.run(['vasmm68k_mot', '-Fbin', '-m68000', '-no-opt', '-quiet', '-nowarn=62',
                                    '-L', lst, '-o', os.path.join(td, 'v.bin'), s], capture_output=True, text=True)
                new = set(int(x) for x in re.findall(r'error \d+ in line (\d+) of', r.stderr)) - errlines
                if not new:
                    break
                errlines |= new                      # comment out the failing lines and assemble again
                for n in new:
                    src[n - 1] = ';' + src[n - 1]
                open(s, 'w').write('\n'.join(src) + '\n')
            got = {}
            cur = None
            for ln in open(lst, errors='replace') if os.path.exists(lst) else []:
                # "00:00000400 23FC00001CB00000<tab>     3: <source>", then "00:00000408 0064" for the rest
                mm = re.match(r'^\d\d:[0-9A-F]{8} ([0-9A-F]+) *(?:\t *(\d+):)?', ln)
                if mm:
                    if mm.group(2):
                        cur = int(mm.group(2))
                        got[cur] = mm.group(1)
                    elif cur in got:
                        got[cur] += mm.group(1)
                    continue
                if re.match(r'^\s*\t\s*\d+:', ln):
                    cur = None
        self.bad = set()
        for ln, a in lines.items():
            hx = self.ins[a][3].upper()
            if ln in errlines or got.get(ln, '') != hx:
                self.bad.add(a)
        return self.bad

    # ---- names
    def all_labels(self):
        names = getattr(self.cfg, 'NAMES', {})
        out = set(self.refs) | set(self.labels) | {a for a in names if self.inside(a)}
        return {a for a in out if a not in self.within}

    def lname(self, a):
        names = getattr(self.cfg, 'NAMES', {})
        if a in names:
            return names[a]
        k = self.labels.get(a)
        if a not in self.ins:
            return f'dat_{a:05X}'
        if k in ('sub', 'entry') or a in self.vecs_inv:
            return f'sub_{a:05X}'
        if k == 'jtab':
            return f'jtab_{a:05X}'
        return f'l_{a:05X}'

    def sym(self, v):
        """Symbol for a program address (label, or label+n inside an instruction/data)."""
        if not self.inside(v):
            return None
        if v in self.labset:
            return self.lname(v)
        if v in self.within and self.within[v] in self.labset:
            b = self.within[v]
            return f'{self.lname(b)}+{v - b}'
        return None

    # ---- operand conversion
    def convert(self, a, m, op):
        mn, o = self.numeric(m, op)
        base = mn.split('.')[0]
        ovr = getattr(self.cfg, 'OPERANDS', {}).get(a)
        if ovr is not None:
            return mn, ovr
        if is_branch(base):
            t = int(HEX.findall(o)[-1], 16)
            s = self.sym(t)
            if s:
                o = re.sub(r'\$[0-9a-f]+$', s, o)
            return mn, o
        if base in ('jmp', 'jsr'):
            mm = re.match(r'^\$([0-9a-f]+)(\.[wl])$', o)
            if mm:
                s = self.sym(int(mm.group(1), 16))
                if s:
                    return mn, f'({s}){mm.group(2)}'

        def pcsub(mm):
            v = int(mm.group(1), 16)
            s = self.sym(v)
            return (s if s else mm.group(0)[:-3]) + '(pc'
        o = re.sub(r'\$([0-9a-f]+)\(pc', pcsub, o)

        def abssub(mm):
            v = int(mm.group(1), 16); sz = mm.group(2)
            if v == 0xDFF000 and sz == '.l':
                return 'CUSTOM'
            if 0xDFF000 <= v < 0xDFF200 and (v - 0xDFF000) in CUSTOM and sz == '.l':
                return f'(CUSTOM+{CUSTOM[v - 0xDFF000]}).l'
            if 0xBFE001 <= v < 0xBFF000 and (v - 0xBFE000) in CIAA and sz == '.l':    # CIAA keys: offsets from $BFE000
                return f'({CIAA[v - 0xBFE000]}).l'
            if 0xBFD000 <= v < 0xBFE000 and (v - 0xBFD000) in CIAB and sz == '.l':
                return f'({CIAB[v - 0xBFD000]}).l'
            if v in getattr(self.cfg, 'MEM', {}):
                self.mem_used.add(v)
                return f'({self.cfg.MEM[v]}){sz}'
            lo, hi = getattr(self.cfg, 'MEM_AUTO', (None, None))
            if lo is not None and lo <= v < hi and not self.inside(v):
                self.mem_used.add(v)
                return f'(mem_{v:05X}){sz}'
            s = self.sym(v)
            if s:
                return f'({s}){sz}'
            if sz == '.w' and v in VECTOR_NAMES:
                return f'(V_{VECTOR_NAMES[v]}).w'
            return mm.group(0)
        o = re.sub(r'(?<![#\w-])\$([0-9a-f]+)(\.[wl])', abssub, o)
        if self.imm_is_addr(a, mn, o):
            mm = re.match(r'^#\$([0-9a-f]+)', o)
            s = self.sym(int(mm.group(1), 16))
            if s:
                o = '#' + s + o[mm.end():]
        if re.match(r'^#\$dff000,', o) or o.startswith('#$dff000'):
            o = o.replace('#$dff000', '#CUSTOM', 1)
        # custom chip offsets from a register loaded with $DFF000
        if a in self.custom_regs:
            r = self.custom_regs[a]

            def regoff(mm):
                off = int(mm.group(1), 16)
                return f'{CUSTOM[off]}({mm.group(2)})' if off in CUSTOM and mm.group(2) in r else mm.group(0)
            o = re.sub(r'(?<![\w$-])\$([0-9a-f]+)\((a[0-6])\)', regoff, o)
        return mn, o

    def track_custom(self):
        """Which address registers hold $DFF000 at each instruction (straight-line tracking only)."""
        self.custom_regs = {}
        cur = set()
        prev_end = None
        for a in sorted(self.ins):
            sz, m, op, hx = self.ins[a]
            if a != prev_end or a in self.labset:
                cur = set(getattr(self.cfg, 'CUSTOM_AT', {}).get(a, ()))
            self.custom_regs[a] = set(cur)
            base = m.split('.')[0]
            mm = re.match(r'^(?:#)?\$dff000(?:\.l)?, (a\d)$', op)
            if base in ('lea', 'movea') and mm:
                cur.add(mm.group(1))
            else:
                dst = op.split(', ')[-1] if ', ' in op else op
                for r in re.findall(r'\b(a[0-7])\b', dst):
                    if re.fullmatch(r'a\d', dst) or re.search(r'\(' + r + r'\)\+|-\(' + r + r'\)', dst):
                        cur.discard(r)
                if base in ('exg', 'movem') and 'a' in op:
                    cur = set()
            if base in ('rts', 'rte', 'bra', 'jmp'):
                cur = set()
            prev_end = a + sz

    # ---- data
    def emit_data(self, a, e):
        cfg = self.cfg
        fmt = getattr(cfg, 'DATAFMT', {})
        out = []
        p = a
        while p < e:
            seg = self.get(p, e - p)
            r = 1
            while r < len(seg) and seg[r] == seg[0]:
                r += 1
            if r >= 32:                         # a run of one value
                out.append(f'\tdcb.b\t{r},${seg[0]:02X}')
                p += r
                continue
            k = 0
            while k < len(seg) and 32 <= seg[k] < 127 and seg[k] not in (0x27, 0x3B, 0x5C):
                k += 1
            if k >= 6:
                out.append(f"\tdc.b\t'{seg[:k].decode()}'")
                p += k
                continue
            q = min(e, p + 16)
            j = p
            while j < q:                       # stop before a string or a long run so they get their own line
                s3 = self.get(j, 32)
                if j > p and len(s3) == 32 and s3.count(s3[0]) == 32:
                    break
                s2 = self.get(j, e - j); k2 = 0
                while k2 < len(s2) and 32 <= s2[k2] < 127 and s2[k2] not in (0x27, 0x3B, 0x5C):
                    k2 += 1
                if k2 >= 6 and j > p:
                    break
                j += 1
            q = j
            b = self.get(p, q - p)
            if fmt.get(a) == 'w' and len(b) % 2 == 0 and p % 2 == 0:
                out.append('\tdc.w\t' + ','.join(f'${int.from_bytes(b[i:i + 2], "big"):04X}' for i in range(0, len(b), 2)))
            else:
                out.append('\tdc.b\t' + ','.join(f'${x:02X}' for x in b))
            p = q
        return out

    # ---- generate
    def generate(self):
        cfg = self.cfg
        self.labset = self.all_labels()
        self.mem_used = set()
        self.vecs_inv = {h for hs in self.vectors.values() for h in hs}
        self.track_custom()
        hdrs = getattr(cfg, 'HEADERS', {})
        cmts = getattr(cfg, 'COMMENTS', {})
        blocks = getattr(cfg, 'DATA_BLOCKS', {})    # addr -> (end, [lines])
        out = [l for l in cfg.PROLOGUE.strip('\n').split('\n')]
        orph = set(getattr(cfg, 'ORPHANS', [])) | set(self.swept)
        for si, (s, e, r) in enumerate(self.segs):
            out.append('')
            out.append(cfg.SEGMENT_TEXT[si].rstrip('\n'))
            a, end = r, r + (e - s)
            while a < end:
                if a in hdrs:
                    out.append('')
                    out.append(';' + '-' * 79)
                    for l in hdrs[a].strip('\n').split('\n'):
                        out.append('; ' + l if l else ';')
                    out.append(';' + '-' * 79)
                if a in blocks:
                    e2, bl = blocks[a]
                    out.extend(bl)
                    a = e2
                    continue
                if a in self.reltabs:
                    tg = self.reltabs[a]
                    if a in self.labset:
                        out.append(f'{self.lname(a)}:')
                    for k, x in enumerate(tg):
                        if k and a + 2 * k in self.labset:
                            raise SystemExit(f'label inside table ${a:X} at ${a + 2 * k:X}')
                        v = f'{self.sym(x)}-*' if x is not None else '0'
                        out.append(f'\tdc.w\t{v}'.expandtabs(8).ljust(48) + f'; {a + 2 * k:05X}')
                    a += 2 * len(tg)
                    continue
                if a in self.ptrtabs:
                    tg = self.ptrtabs[a]
                    if a in self.labset:
                        out.append(f'{self.lname(a)}:')
                    for k, x in enumerate(tg):
                        if k and a + 4 * k in self.labset:
                            raise SystemExit(f'label inside pointer table ${a:X} at ${a + 4 * k:X}')
                        out.append(f'\tdc.l\t{self.sym(x) or f"${x:X}"}'.expandtabs(8).ljust(48) + f'; {a + 4 * k:05X}')
                    a += 4 * len(tg)
                    continue
                if a in self.labset:
                    extra = '\t\t; (no references found: found by the code sweep)' if a in orph else ''
                    out.append(f'{self.lname(a)}:{extra}')
                if a in self.ins:
                    sz, m, op, hx = self.ins[a]
                    mn, o = self.numeric(m, op)
                    c = cmts.get(a, '')
                    if a in self.bad:
                        line = '\tdc.w\t' + ','.join(f'${hx[i:i + 4].upper()}' for i in range(0, len(hx), 4))
                        c = f'{mn} {o}' + (f'  {c}' if c else '')
                    else:
                        mn, o = self.convert(a, m, op)
                        line = f'\t{mn}\t{o}'
                    line = line.expandtabs(8)
                    line = line.ljust(48) + f'; {a:05X}' + (f'  {c}' if c else '')
                    out.append(line)
                    a += sz
                else:
                    e2 = a + 1
                    while e2 < end and e2 not in self.ins and e2 not in self.labset and e2 not in hdrs and e2 not in blocks:
                        e2 += 1
                    out.extend(self.emit_data(a, e2))
                    a = e2
        epi = getattr(cfg, 'EPILOGUE', '')
        if epi:
            out.extend(epi.strip('\n').split('\n'))
        return out

    def save_trace(self):
        json.dump({'insn': {f'{k:X}': v for k, v in sorted(self.ins.items())},
                   'labels': {f'{k:X}': v for k, v in sorted(self.labels.items())},
                   'indirect': [(f'{a:X}', m, o) for a, m, o in self.indirect],
                   'vectors': {f'{k:X}': sorted(f'{x:X}' for x in v) for k, v in sorted(self.vectors.items())}},
                  open(self.state_file, 'w'), indent=0)

    def stats(self):
        code = sum(v[0] for v in self.ins.values())
        total = sum(e - s for s, e, r in self.segs)
        print(f'  {len(self.ins)} instructions, {code} code bytes of {total}; {len(self.labels)} code labels, '
              f'{len(self.refs)} data refs; {len(self.bad)} encoded as dc.w; {len(self.swept)} routines found by the sweep')
        if self.vectors:
            print('  vectors: ' + ', '.join(f'${k:X}->' + '/'.join(f'${x:X}' for x in sorted(v)) for k, v in sorted(self.vectors.items())))
        if getattr(self, 'hints', None):
            conf = self.coverage_conflicts()
            print(f'  coverage: {len(self.hints)} executed addresses, {len(conf)} in conflict with the trace'
                  + (': ' + ' '.join(f'${a:X}' for a in conf[:20]) if conf else ''))
            sw = set(getattr(self, 'swept', []))
            print(f'  sweep: {sum(1 for a in sw if a in set(self.hints))} of {len(sw)} routines found by the sweep seen executing')
        if self.bad_paths:
            print(f'  {len(self.bad_paths)} paths ran into non-68000 code (data?):')
            for a, f, t in self.bad_paths:
                print(f'    ${a:05X}  {t:<32} reached from ' + (f'${f:05X}' if f is not None else 'an entry'))
        if self.indirect:
            print(f'  {len(self.indirect)} indirect jumps/calls:')
            for a, m, o in self.indirect:
                print(f'    ${a:05X}  {m} {o}')


def equates(p):
    """nzs_equates.i: the memory outside the program image that the code addresses absolutely."""
    cfg = p.cfg
    names = getattr(cfg, 'MEM', {})
    notes = getattr(cfg, 'MEM_NOTES', {})
    L = [l for l in getattr(cfg, 'EQUATES_HEADER', '').strip('\n').split('\n')]
    L += ['', '; ---- Memory outside the program image (names from tools/disasm/main_cfg.py MEM;',
          ';      mem_XXXXX = not yet identified)']
    for v in sorted(p.mem_used | set(names)):
        n = names.get(v, f'mem_{v:05X}')
        c = notes.get(v, '')
        L.append(f'{n:<24}equ\t${v:05X}' + (f'\t\t; {c}' if c else ''))
    return '\n'.join(L) + '\n'


def build(cfg, out_path, check_sha1=None):
    reject = set()
    while True:
        p = Program(cfg)
        p.reject = reject
        p.trace()
        p.verify()
        owners = {p.sweep_owner[a] for a in p.bad if a in getattr(p, 'sweep_owner', {})}
        if not owners:
            break
        reject |= owners          # a swept routine with an instruction vasm can't reproduce is data
    lines = p.generate()
    open(out_path, 'w').write('\n'.join(lines) + '\n')
    eq = getattr(cfg, 'EQUATES_FILE', None)
    if eq:
        open(os.path.join(p.root, eq), 'w').write(equates(p))
    p.save_trace()
    p.stats()
    return p
