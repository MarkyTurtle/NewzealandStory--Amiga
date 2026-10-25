"""Extract the files from The New Zealand Story (Amiga, Ocean/Choice 1989) game-disk ADF.

  python3 tools/disk/extract_files.py GAME.adf [--loader T90.bin] [--unpacked MAIN.bin] [--out DIR]

Writes (under original/, or --out):
  disk/files/   every file the loaders read, named by track, plus SHA1SUMS
  disk/files/tracks/tNNN.bin  the tracks the game itself reads while it runs (level data;
                tools/disk/game_tracks.py finds them from the program's tables)
  bin/main.bin  the main program unpacked (as it sits in memory at $400): what nzs_main.s rebuilds
  render/out/loadscreen.png

The disk has no filesystem; the game loader on track 90 reads whole tracks:
  track 0  $000-$3FF  bootblock                 1024 bytes
  track 90            game loader               5632 bytes  (loaded $400, runs $76000)
  tracks 91-93        loading screen           16896 bytes  (loaded $70000)
  tracks 94-143       main program, packed     50 tracks    (loaded and unpacked at $400)

Every file is checked against its known size; the loader and the unpacked main program are
also compared with captured binaries when given. Exits non-zero if any check fails.
"""
import argparse, hashlib, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

TRACK = 11 * 512                      # 5632 bytes per track in an ADF
DISK = 160 * TRACK                    # 901120

LOADER_TRACK = 90
SCREEN_TRACK, SCREEN_TRACKS = 91, 3
MAIN_TRACK, MAIN_TRACKS = 94, 50

KNOWN_UNPACKED_M1 = 0x52BA6           # header long 0: unpacked length - 1
KNOWN_PACKED_M1 = 0x43511             # header long 1: packed length - 1

failures = []


def check(ok, msg):
    print(('  ok    ' if ok else '  FAIL  ') + msg)
    if not ok:
        failures.append(msg)
    return ok


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def tracks(adf, first, count):
    return adf[first * TRACK:(first + count) * TRACK]


def bootblock_checksum_ok(bb):
    """AmigaDOS bootblock: add-with-carry sum of all 256 longs must be $FFFFFFFF."""
    s = 0
    for (v,) in struct.iter_unpack('>I', bb):
        s += v
        if s > 0xFFFFFFFF:
            s = (s & 0xFFFFFFFF) + 1
    return s == 0xFFFFFFFF


def unpack_main(data):
    """Python copy of the unpacker at $B22 in track 90 (68000 semantics).

    data = the bytes as loaded at a0: header (2 longs) then packed bytes.
      d3 = unpacked length - 1, d1 = packed length - 1.
      The packed bytes (d1+1 of them, from a0+8) are moved so they end at a0+d3+1, then
      unpacked forward from a0. First packed byte = escape byte d2.
      byte != d2 -> literal, d3--, loop while d3 >= 0
      d2, v, n   -> write v (n+1) times (dbra), d3-- each, then loop while d3 >= 0
    Note: the packer's "packed length" counts the 8-byte header too, so the routine moves
    8 bytes past the real stream (zero padding on this disk) that are never read.

    Runs twice: once reading from a separate copy of the packed bytes, and once exactly as
    the 68000 does it, moving and unpacking inside one buffer, so any self-overwrite would
    show up as a difference. Returns (output, in_place_output, packed_bytes_consumed).
    """
    d3, d1 = struct.unpack('>II', data[:8])
    unpacked_len, moved_len = d3 + 1, d1 + 1
    if len(data) < 8 + moved_len:
        raise ValueError(f'packed data truncated: have {len(data) - 8}, need {moved_len}')

    def run(mem, rd):
        """Unpack from mem[rd:] to mem[0:] (mem may be the same buffer). Returns (out end, rd consumed)."""
        start, wr, cnt = rd, 0, d3
        esc = mem[rd]; rd += 1
        while True:
            b = mem[rd]; rd += 1
            if b != esc:
                mem[wr] = b; wr += 1; cnt -= 1        # subq.l #1,d3 / bpl
                if cnt < 0: break
            else:
                v, n = mem[rd], mem[rd + 1]; rd += 2
                for _ in range(n + 1):                 # dbra d1 (count+1 times)
                    mem[wr] = v; wr += 1; cnt -= 1
                if cnt < 0: break                      # tst.l d3 / bpl
        return wr, rd - start

    # 1. separate source buffer
    mem = bytearray(unpacked_len + 256 * 256 + moved_len)   # room for a run overshooting d3
    mem[len(mem) - moved_len:] = data[8:8 + moved_len]      # source where nothing writes
    end, consumed = run(mem, len(mem) - moved_len)
    clean = bytes(mem[:end])

    # 2. in place, as the 68000 does it: header+packed loaded at a0 (= mem[0]),
    #    then move.b -(a1),-(a0) copies the d1+1 bytes so they end at a0+d3+1
    mem = bytearray(max(unpacked_len, 8 + moved_len) + 256 * 256)
    mem[:8 + moved_len] = data[:8 + moved_len]
    mem[unpacked_len - moved_len:unpacked_len] = data[8:8 + moved_len]
    end2, _ = run(mem, unpacked_len - moved_len)
    in_place = bytes(mem[:end2])
    return clean, in_place, consumed


def decode_screen(data):
    """Loading screen as decoded by $AB0 in track 90.
    Returns (palette of 16 RGB4 words, list of 4 planes of 8000 bytes, bytes consumed)."""
    pal = [(w * 2) & 0xFFF for (w,) in struct.iter_unpack('>H', data[2:0x22])]
    planes = [bytearray(0x2000) for _ in range(4)]
    pos, plane, line, col = 0x22, 0, 0, 0

    def put(byte):
        nonlocal plane, line, col
        planes[plane][line * 40 + col] = byte
        col += 1
        if col == 40:
            col = 0; plane += 1
            if plane == 4:
                plane = 0; line += 1
        return line == 200

    done = False
    while not done:
        n = data[pos]; pos += 1
        if n == 0x80:
            continue
        if n & 0x80:
            cnt = ((-n) & 0x7F) + 1
            v = data[pos]; pos += 1
            for _ in range(cnt):
                if put(v): done = True; break
        else:
            cnt = (n & 0x7F) + 1
            for _ in range(cnt):
                v = data[pos]; pos += 1
                if put(v): done = True; break
    return pal, planes, pos


def save_png(pal, planes, path):
    from PIL import Image
    img = Image.new('RGB', (320, 200))
    px = img.load()
    for y in range(200):
        for x in range(320):
            byte, bit = y * 40 + (x >> 3), 7 - (x & 7)
            c = sum(((planes[p][byte] >> bit) & 1) << p for p in range(4))
            w = pal[c]
            px[x, y] = ((w >> 8 & 15) * 17, (w >> 4 & 15) * 17, (w & 15) * 17)
    img.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('adf')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'),
                    help='folder to write disk/, bin/ and render/ into (default: original/)')
    ap.add_argument('--loader', help='captured track 90 game loader to compare against')
    ap.add_argument('--unpacked', help='captured unpacked main program (memory at $400) to compare against')
    a = ap.parse_args()

    adf = open(a.adf, 'rb').read()
    root = os.path.normpath(a.out)
    for d in ('disk/files', 'bin', 'render/out'):
        os.makedirs(os.path.join(root, d), exist_ok=True)
    written = []

    def write(name, data):
        open(os.path.join(root, name), 'wb').write(data)
        written.append((name, len(data), sha1(data)))

    print('Disk')
    check(len(adf) == DISK, f'ADF size {len(adf)} == {DISK}')

    print('Bootblock (track 0, $000-$3FF)')
    boot = adf[:0x400]
    check(boot[:4] == b'DOS\0', 'starts "DOS\\0"')
    check(bootblock_checksum_ok(boot), 'bootblock checksum valid')
    write('disk/files/t000_bootblock.bin', boot)

    print('Game loader (track 90)')
    loader = tracks(adf, LOADER_TRACK, 1)
    check(len(loader) == 5632, f'size {len(loader)} == 5632')
    check(loader[:2] == b'\x60\x00' and 0x400 + 2 + struct.unpack('>h', loader[2:4])[0] == 0xF92,
          'entry bra.w $F92')
    if a.loader:
        cap = open(a.loader, 'rb').read()
        check(loader == cap, f'identical to captured {os.path.basename(a.loader)} (SHA-1 {sha1(cap)[:12]})')
    write('disk/files/t090_game_loader.bin', loader)

    print('Loading screen (tracks 91-93)')
    screen = tracks(adf, SCREEN_TRACK, SCREEN_TRACKS)
    check(len(screen) == 16896, f'size {len(screen)} == 16896')
    pal, planes, used = decode_screen(screen)
    check(used <= len(screen), f'byte-run data ends at +${used:X} (inside the {len(screen)}-byte file)')
    print(f'        palette (doubled): {" ".join(f"{w:03X}" for w in pal)}')
    write('disk/files/t091-093_loading_screen.bin', screen)
    try:
        save_png(pal, planes, os.path.join(root, 'render/out/loadscreen.png'))
        print('        render/out/loadscreen.png written')
    except ImportError:
        print('        (PIL not installed: loadscreen.png skipped)')

    print('Main program, packed (tracks 94-143)')
    raw = tracks(adf, MAIN_TRACK, MAIN_TRACKS)
    check(len(raw) == MAIN_TRACKS * TRACK, f'{MAIN_TRACKS} tracks = {len(raw)} bytes')
    unp_m1, pk_m1 = struct.unpack('>II', raw[:8])
    check(unp_m1 == KNOWN_UNPACKED_M1, f'header unpacked length - 1 = ${unp_m1:X} (expect ${KNOWN_UNPACKED_M1:X})')
    check(pk_m1 == KNOWN_PACKED_M1, f'header packed length - 1 = ${pk_m1:X} (expect ${KNOWN_PACKED_M1:X})')
    file_len = 8 + pk_m1 + 1
    check(file_len <= len(raw), f'header + packed data = {file_len} bytes fits in {len(raw)}')
    slack = raw[file_len:]
    nz = sum(1 for b in slack if b)
    print(f'        {len(slack)} bytes after the packed data in track {MAIN_TRACK + file_len // TRACK} onwards '
          f'({nz} non-zero)')
    write('disk/files/t094-143_main_packed.bin', raw[:file_len])

    print('Main program, unpacked (loaded at $400)')
    out, in_place, consumed = unpack_main(raw)
    print(f'        escape byte ${raw[8]:02X}; stream {consumed} bytes; output {len(out)} bytes (${len(out):X})')
    pad = raw[8 + consumed:file_len]
    check(consumed == pk_m1 + 1 - 8 and pad == bytes(8),
          f'stream = header packed length - 8 (the length counts the header); '
          f'the 8 bytes after it are zero padding, never read')
    check(len(out) == unp_m1 + 1, f'output length == header unpacked length ${unp_m1 + 1:X}')
    check(in_place == out, 'in-place emulation (move then unpack in one buffer) gives the same bytes')
    check(out[:2] == b'\x60\x00' and 0x400 + 2 + struct.unpack('>h', out[2:4])[0] == 0x3218,
          'entry bra.w $3218')
    if a.unpacked:
        cap = open(a.unpacked, 'rb').read()
        name = os.path.basename(a.unpacked)
        if out == cap:
            check(True, f'identical to captured {name}')
        else:
            common = min(len(out), len(cap))
            diff = next((k for k in range(common) if out[k] != cap[k]), None)
            if diff is None:
                check(True, f'first {common} bytes identical to captured {name} '
                            f'(capture {len(cap)} bytes, unpacked {len(out)})')
                if len(out) > len(cap):
                    tail = out[len(cap):]
                    print(f'        unpacked has {len(tail)} more byte(s) at ${0x400 + len(cap):X}: {tail.hex()} '
                          f'(capture ends one short of the header length)')
                else:
                    print(f'        capture has {len(cap) - len(out)} more byte(s) at ${0x400 + len(out):X}')
            else:
                ndiff = sum(1 for k in range(common) if out[k] != cap[k])
                check(False, f'differs from captured {name}: first at file ${diff:X} '
                             f'(runtime ${0x400 + diff:X}), {ndiff} bytes differ')
    write('bin/main.bin', out)

    print('Tracks the game reads (level data)')
    import game_tracks
    ts = game_tracks.tracks(out)
    os.makedirs(os.path.join(root, 'disk/files/tracks'), exist_ok=True)
    for t in ts:
        write(f'disk/files/tracks/t{t:03d}.bin', tracks(adf, t, 1))
    print(f'        {len(ts)} tracks: {", ".join(game_tracks.runs(ts))}')

    with open(os.path.join(root, 'disk/SHA1SUMS'), 'w') as f:
        for name, size, h in written:
            f.write(f'{h}  {name}\n')
    print('\nFiles')
    for name, size, h in written:
        print(f'  {name:<30} {size:>7}  {h}')
    print(f'\n{len(failures)} check(s) failed' if failures else '\nAll checks passed')
    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
