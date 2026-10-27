"""Build the AmigaDOS-format disk image of The New Zealand Story: enhanced/build/nzs.adf.

  python3 enhanced/tools/build_disk.py

An ordinary 880K disk (80 cylinders x 2 heads x 11 sectors of 512 bytes, standard AmigaDOS MFM
with the $4489 sync) with no filesystem - nothing on it is copy-protected, so any emulator or
real drive reads it, and it can be written to a floppy with any ADF tool:

  $000  the bootblock (src/boot_4489.s): 'DOS',0, checksum, root block 880, then the code
  $400  the file table: 'NZSF', version.w, count.w, 8 bytes zero, then per file id
        (index) its offset on the disk and its length, longs
  $600  the files, one after another in DISK_ORDER, each on an even offset

The files (ids: FID_ in boot_4489.s):
  0  the game, packed: src/nzs_game.s (the hand-edited source, made from original/nzs_main.s
     by tools/fork_source.py; it includes src/diskload.s and src/enhanced.s), packed by
     original/tools/disk/pack.py in the original's format; the extension module unpacks it
     to $400
  1  the loading screen: the original file (original/disk/files/t091-093_loading_screen.bin)
  2  the tracks of the original disk that the game reads while it runs (level data:
     original/disk/files/tracks/, found by original/tools/disk/game_tracks.py), one after
     another; the game's TrackRead (diskload.s) finds each through TrackMap
     (enhanced/build/trackmap.i, written here)
  3  the extension module (src/ext.s, assembled at EXT_BASE): the rest of the boot, the
     machine's memory on the title, the track cache; loaded by the bootblock
"""
import json, hashlib, os, re, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
OUT = os.path.join(ENH, 'build')
ADF = os.path.join(OUT, 'nzs.adf')
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ORIG, 'tools', 'disk'))
import pack, game_tracks                                 # noqa: E402

TRACK = 11 * 512
DISK = 80 * 2 * TRACK
FT_OFFSET, FILES_START, FT_ENTRIES = 0x400, 0x600, 16
EXT_BASE = 0x65400              # (src/ext.i)
DISK_ORDER = [1, 2, 3, 0]          # file ids in disk order: the game last, so the others' offsets (which the
                                # game holds: TRACKS_OFFSET) do not depend on its packed size
MAIN_SHA1 = '74d3f9924c56270c5fc2a4231be035c9157851a1'     # the original program (original/bin/main.bin)

run_addr = game_tracks.file_offset     # file offset in the program (as loaded at $400) of a run address


def assemble(src, out, cwd, incdirs=(), listing=None):
    cmd = ['vasmm68k_mot', '-Fbin', '-m68000', '-no-opt', '-quiet'] + [f'-I{d}' for d in incdirs] + ['-o', out, src]
    if listing:
        cmd[1:1] = ['-L', listing]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if r.returncode:
        sys.stdout.write(r.stdout + r.stderr)
        raise SystemExit(f'{src}: assembly failed')
    return open(out, 'rb').read()


def bootblock_checksum(bb):
    """AmigaDOS bootblock: the long at 4 makes the add-with-carry sum of all 256 longs $FFFFFFFF."""
    bb = bytearray(bb)
    bb[4:8] = bytes(4)
    s = 0
    for (v,) in struct.iter_unpack('>I', bb):
        s += v
        if s > 0xFFFFFFFF:
            s = (s & 0xFFFFFFFF) + 1
    bb[4:8] = struct.pack('>I', (~s) & 0xFFFFFFFF)
    return bytes(bb)


def write_trackmap(tracks, tracks_offset):
    m = [0xFF] * 160
    for i, t in enumerate(tracks):
        m[t] = i
    L = ['; the original disk\'s tracks on the AmigaDOS disk (written by enhanced/tools/build_disk.py)',
         f'TRACKS_OFFSET\tequ\t${tracks_offset:X}\t\t; where the stored tracks start on the disk',
         '; per original track (0-159): its place among the stored tracks, $FF = not on the disk']
    for r in range(0, 160, 16):
        L.append('\tdc.b\t' + ','.join(f'${v:02X}' for v in m[r:r + 16]) + f'\t; tracks {r}-{r + 15}')
    open(os.path.join(OUT, 'trackmap.i'), 'w').write('\n'.join(L) + '\n')
    open(os.path.join(OUT, 'tracks.i'), 'w').write(
        '; written by enhanced/tools/build_disk.py\n'
        f'TRACKS_STORED\tequ\t{len(tracks)}\t\t; the original disk\'s tracks on this disk (the game reads them)\n')


BOB_DIRECTORY, BOB_FRAMES, MIR_FIRST = 0x39AA6, 289, 0x122
ONE_FRAMES = MIR_FIRST + BOB_FRAMES             # frames 0-288, mirrored 290-578 (src/frames.s)
ONE_LIVE = 0x24                                 # the oxygen meter's frame: the game redraws it, never copied
ONE_CACHE = int(re.search(r'^BLOCK3\s+equ\s+\$(\w+)', open(os.path.join(ENH, 'src', 'enhanced.s')).read(),
                          re.M).group(1), 16) - 0x4A3A6     # the 512K cache: dat_4A3A6 to BLOCK3 (src/enhanced.s)
ONE_WARM_SHARE = 0.85                           # of it filled as a level starts (the rest: for misses)
COUNTS = os.path.join(HERE, 'frame_counts.json')


def one_sizes(orig_main):
    """each main-bank frame's one-blit size (frames.s: 16 x its width in words x its height),
    for frames 0-578 (289: none; the mirrored ones the size of their unmirrored frame)"""
    rd = lambda a: struct.unpack_from('>H', orig_main, run_addr(a))[0]
    size = {}
    for f in range(BOB_FRAMES):
        e = BOB_DIRECTORY + 16 * f
        data = 0x22AA6 + struct.unpack_from('>L', orig_main, run_addr(e))[0]
        size[f] = size[f + MIR_FIRST] = 16 * rd(data) * rd(data + 2)
    return size


def warm_list(lv, size, obs, counts):
    """the frames to build as level lv starts on a 512K machine: those it is known to draw, the
    most drawn (tools/frame_counts.json, from the emulator) first, as many as fit in ONE_WARM_SHARE
    of the cache"""
    seen = {f for f in obs[str(lv)]['frames'] if f in size} - {ONE_LIVE, ONE_LIVE + MIR_FIRST}
    c = counts.get(str(lv), {})
    seen |= {int(f) for f in c if int(f) in size}
    order = sorted(seen, key=lambda f: (-c.get(str(f), 0), f))
    out, used = [], 0
    for f in order:
        if used + size[f] > ONE_CACHE * ONE_WARM_SHARE:
            continue
        out.append(f)
        used += size[f]
    return out, used


def write_frames(orig_main):
    """frames.i: ONE_ALL (all the one-blit frames' bytes) and OneWarm (per level, the frames
    built into the 512K cache as it starts: a bit each, frame 0 the first byte's bit 7)"""
    obs = json.load(open(os.path.join(ORIG, 'assets', 'levels', 'observed.json')))
    counts = json.load(open(COUNTS)) if os.path.exists(COUNTS) else {}
    size = one_sizes(orig_main)
    L = ['; written by enhanced/tools/build_disk.py (src/frames.s)',
         f'ONE_ALL\tequ\t{sum(size.values())}\t\t; every main-bank frame in one-blit form, mirrored too',
         '; per level, the frames built into the 512K cache as it starts (a bit each, frame 0 the',
         '; first byte\'s bit 7): those it is known to draw, the most drawn as many as fit',
         'OneWarm:']
    for lv in range(20):
        fs, used = warm_list(lv, size, obs, counts)
        bits = bytearray((ONE_FRAMES + 7) // 8)
        for f in fs:
            bits[f // 8] |= 0x80 >> (f % 8)
        L.append('\tdc.b\t' + ','.join(f'${b:02X}' for b in bits) + f'\t; level {lv}: {len(fs)} frames, {used} bytes')
    L += ['OneWarmEnd:', '\teven']
    open(os.path.join(OUT, 'frames.i'), 'w').write('\n'.join(L) + '\n')


def game(tracks_offset, tracks, orig_main):
    write_trackmap(tracks, tracks_offset)
    write_frames(orig_main)
    return assemble(os.path.join(ENH, 'src', 'nzs_game.s'), os.path.join(OUT, 'nzs_game.bin'), OUT,
                    [OUT, os.path.join(ENH, 'src'), ORIG], listing=os.path.join(OUT, 'nzs_game.lst'))


def symbols(listing):
    """{name: value} from a vasm listing's symbol table"""
    out, on = {}, False
    for ln in open(listing, errors='replace'):
        if ln.startswith('Symbols by name:'):
            on = True
            continue
        if ln.startswith('Symbols by value:'):
            break
        if on and ':' in ln:                            # NAME   section:VALUE (E: an equate)
            name, val = ln.rsplit(None, 1)[0].strip(), ln.rsplit(None, 1)[1]
            sec, _, v = val.partition(':')
            if sec != 'E':
                try:
                    out[name] = int(v, 16)
                except ValueError:
                    pass
    return out


BLOCK2, PROGRAM_END = 0x3214, 0x52FA7


def layout(main, orig_main):
    """the program's layout as the original's: the same length up to block 3 (stored after it),
    and every label of block 2 and
    after ($3214-) that the enhanced source still has at the same address (block 1 is the
    enhanced game's own: the code there may move, as long as block 1 keeps its size). The
    program's data and much of its code are reached at fixed addresses (self-modifying code,
    tables built at run time beyond its end), so nothing there may move.
    -> (ok, the labels compared, the ones that moved)"""
    o = symbols(os.path.join(OUT, 'main_orig.lst'))
    e = symbols(os.path.join(OUT, 'nzs_game.lst'))
    common = [n for n, v in o.items() if BLOCK2 <= v < PROGRAM_END and n in e and not n.startswith('.')]
    moved = [n for n in common if e[n] != o[n]]
    block3 = e['Block3_End'] - e['Block3']              # block 3 (src/frames.s) stored after it
    return e['Block3_Stored'] in (PROGRAM_END, PROGRAM_END + 1) and \
        len(main) == e['Block3_Stored'] - 0x400 + block3 and not moved, len(common), moved


def inplace_ok(packed, n):
    """ext.s's Unpack, step for step on a copy of memory: the packed file loaded at the
    program's start, moved up (its length counts the 8-byte header, from just after it) to end
    where the program will, then unpacked forwards from the start -> whether that gives the
    program (the output must not overwrite packed bytes not yet read)"""
    d3, d1 = struct.unpack_from('>LL', packed, 0)
    size = max(n, len(packed)) + 16
    mem = bytearray(size)
    mem[0:len(packed)] = packed
    a1, a0 = 8 + d1 + 1, d3 + 1
    while True:                             # .up: move.b -(a1),-(a0); subq.l #1,d1; bpl
        a1 -= 1; a0 -= 1
        mem[a0] = mem[a1]
        d1 -= 1
        if d1 < 0:
            break
    a1, a0 = a0, 0
    esc = mem[a1]; a1 += 1
    while True:
        b = mem[a1]; a1 += 1
        if b == esc:
            v, c = mem[a1], mem[a1 + 1]; a1 += 2
            for _ in range(c + 1):
                mem[a0] = v; a0 += 1; d3 -= 1
            if d3 < 0:
                break
        else:
            mem[a0] = b; a0 += 1; d3 -= 1
            if d3 < 0:
                break
    return bytes(mem[:n])


def original_track(t):
    return open(os.path.join(ORIG, 'disk', 'files', 'tracks', f't{t:03d}.bin'), 'rb').read()


def build():
    os.makedirs(OUT, exist_ok=True)
    orig_main = assemble('nzs_main.s', os.path.join(OUT, 'main_orig.bin'), ORIG, listing=os.path.join(OUT, 'main_orig.lst'))
    if hashlib.sha1(orig_main).hexdigest() != MAIN_SHA1:
        print('  (original/nzs_main.s no longer assembles to the original program)')
    tracks = game_tracks.tracks(orig_main)
    track_data = b''.join(original_track(t) for t in tracks)
    screen = open(os.path.join(ORIG, 'disk/files/t091-093_loading_screen.bin'), 'rb').read()
    offsets, off = {}, FILES_START
    for i, n in ((1, len(screen)), (2, len(track_data))):
        offsets[i] = off
        off = (off + n + 1) & ~1
    main = game(offsets[2], tracks, orig_main)
    ext = assemble(os.path.join(ENH, 'src', 'ext.s'), os.path.join(OUT, 'ext.bin'), OUT, [OUT, os.path.join(ENH, 'src')])
    offsets[3] = off
    off = (off + len(ext) + 1) & ~1
    offsets[0] = off
    packed = pack.pack(main)
    if pack.unpack(packed) != main:
        raise SystemExit('build_disk.py: packing the game went wrong')
    got = inplace_ok(packed, len(main))
    if got != main:
        bad = [i for i in range(len(main)) if got[i] != main[i]]
        raise SystemExit(f'build_disk.py: the game does not unpack in place (ext.s: Unpack): '
                         f'{len(bad)} bytes wrong from ${0x400 + bad[0]:X}')
    end = (off + len(packed) + 1) & ~1
    if end > DISK:
        raise SystemExit(f'the files do not fit on the disk: {end} bytes')
    files = {0: ('FID_MAIN', packed, 0x400, 'the game, packed (enhanced/build/nzs_game.s)'),
             1: ('FID_SCREEN', screen, 0x70000, 'the loading screen (byte-run, decoded to $78000)'),
             2: ('FID_TRACKS', track_data, None, f'{len(tracks)} tracks of the original disk the game reads'),
             3: ('FID_EXT', ext, EXT_BASE, 'the extension module (src/ext.s)')}
    boot = assemble(os.path.join(ENH, 'src', 'boot_4489.s'), os.path.join(OUT, 'boot.bin'), os.path.join(ENH, 'src'))
    if len(boot) != 1024:
        raise SystemExit(f'bootblock is {len(boot)} bytes')
    adf = bytearray(DISK)
    adf[0:1024] = bootblock_checksum(boot)
    table = bytearray(16 + 8 * FT_ENTRIES)
    table[0:8] = b'NZSF' + struct.pack('>HH', 1, len(files))
    for i, (name, data, load, desc) in files.items():
        adf[offsets[i]:offsets[i] + len(data)] = data
        struct.pack_into('>LL', table, 16 + 8 * i, offsets[i], len(data))
    adf[FT_OFFSET:FT_OFFSET + len(table)] = table
    open(ADF, 'wb').write(adf)

    print(f'{os.path.relpath(ADF, os.path.join(ENH, ".."))}: {DISK} bytes, sha1 {hashlib.sha1(adf).hexdigest()}')
    print(f'  {"id":>2}  {"file":<11} {"offset":>8} {"bytes":>8}  {"tracks":<8} {"loaded to":>9}')
    for i in DISK_ORDER:
        name, data, load, desc = files[i]
        o, n = offsets[i], len(data)
        ld = f'${load:06X}' if load is not None else '(by track)'
        print(f'  {i:>2}  {name:<11} ${o:06X} {n:>8}  {o // TRACK:>3}-{(o + n - 1) // TRACK:<4} {ld:>10}  {desc}')
    print(f'  free from ${end:06X}: {DISK - end} bytes')
    print(f'  the original tracks the game reads: {", ".join(game_tracks.runs(tracks))}')
    ok, n, moved = layout(main, orig_main)
    print(f'  game: {len(main)} bytes unpacked (the original: {len(orig_main)}); {n} labels of block 2 on '
          f'compared with the original: ' + ('all in place' if ok else f'MOVED: {", ".join(moved[:10])}'))
    if not ok:
        raise SystemExit('build_disk.py: the game\'s layout differs from the original\'s')
    return ADF


if __name__ == '__main__':
    build()
