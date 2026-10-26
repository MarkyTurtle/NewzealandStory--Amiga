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
import hashlib, os, struct, subprocess, sys

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


def game(tracks_offset, tracks):
    write_trackmap(tracks, tracks_offset)
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
    """the program's layout as the original's: the same length, and every label of block 2 and
    after ($3214-) that the enhanced source still has at the same address (block 1 is the
    enhanced game's own: the code there may move, as long as block 1 keeps its size). The
    program's data and much of its code are reached at fixed addresses (self-modifying code,
    tables built at run time beyond its end), so nothing there may move.
    -> (ok, the labels compared, the ones that moved)"""
    o = symbols(os.path.join(OUT, 'main_orig.lst'))
    e = symbols(os.path.join(OUT, 'nzs_game.lst'))
    common = [n for n, v in o.items() if BLOCK2 <= v < PROGRAM_END and n in e and not n.startswith('.')]
    moved = [n for n in common if e[n] != o[n]]
    return len(main) == len(orig_main) and not moved, len(common), moved


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
    main = game(offsets[2], tracks)
    ext = assemble(os.path.join(ENH, 'src', 'ext.s'), os.path.join(OUT, 'ext.bin'), OUT, [OUT, os.path.join(ENH, 'src')])
    offsets[3] = off
    off = (off + len(ext) + 1) & ~1
    offsets[0] = off
    packed = pack.pack(main)
    if pack.unpack(packed) != main:
        raise SystemExit('build_disk.py: packing the game went wrong')
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
