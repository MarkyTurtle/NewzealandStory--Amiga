"""The tracks of the original disk that the game reads while it runs (its level data), found
from the program's own tables. Used by extract_files.py (which writes them to
disk/files/tracks/) and by enhanced/tools/build_disk.py (which stores them on the AmigaDOS disk).

The program reads the disk only through LoadTracks ($55BA, via JT_TrackRead):
  * at the start of each of the 20 levels (LevelTable, $5DBA, 16 bytes a level): 5 tracks of
    packed level data from +$C, and 1 track from +$E;
  * on some levels 2 more tracks (ExtraTracks, $418C: 152-159);
  * between levels, for the progress screen, 5 tracks from track 144 (move.w #$90,d0 at $43FE).

  * on level 4-4, when the kiwi reaches the cage, its second map ($45CC: untraced code, the
    world-4 entry of the bosses' table jtab_0AC58): 5 tracks of packed world data from track 63
    (moveq #$3F,d0 at $45CC) and 1 track from track 69 (moveq #$45,d0 at $45E4).

  python3 tools/disk/game_tracks.py [bin/main.bin]      lists them
"""
import os, struct, sys

LEVEL_TABLE, LEVELS = 0x5DBA, 20
EXTRA_TABLE = 0x418C
END_LOAD = 0x43FE                      # move.w #$90,d0
L44_DATA, L44_MAP = 0x45CC, 0x45E4      # moveq #$3F,d0 / moveq #5,d1; moveq #$45,d0 / moveq #1,d1
TRACK = 11 * 512


def file_offset(a):
    """file offset in the program (as loaded at $400) of a run address (block 1 runs 4 lower)"""
    return a - 0x400 + 4 if a < 0x3210 else a - 0x400


def loads(main):
    """[(what, first track, count)] every load the program makes"""
    rd16 = lambda a: struct.unpack_from('>H', main, file_offset(a))[0]
    out = []
    for k in range(LEVELS):
        e = LEVEL_TABLE + 16 * k
        out.append((f'level {k} data', rd16(e + 12), 5))
        out.append((f'level {k} track', rd16(e + 14), 1))
    for k in range(6):
        t = main[file_offset(EXTRA_TABLE + k)]
        if t:
            out.append((f'extra tracks {k}', t, 2))
    if rd16(END_LOAD) != 0x303C:
        raise SystemExit('game_tracks.py: the load at $43FE is not move.w #imm,d0 any more')
    out.append(('the progress screen', rd16(END_LOAD + 2), 5))
    for a, what in ((L44_DATA, 'level 15 second map data'), (L44_MAP, 'level 15 second map track')):
        op, cnt = rd16(a), rd16(a + 2)
        if op & 0xFF00 != 0x7000 or cnt & 0xFF00 != 0x7200:
            raise SystemExit(f'game_tracks.py: the load at ${a:X} is not moveq #t,d0 / moveq #n,d1 any more')
        out.append((what, op & 0xFF, cnt & 0xFF))
    return out


def tracks(main):
    return sorted({t + i for _, t, n in loads(main) for i in range(n)})


def runs(ts):
    out, s = [], ts[0]
    for a, b in zip(ts, ts[1:] + [None]):
        if b != a + 1:
            out.append(f'{s}-{a}' if a != s else f'{s}')
            s = b
    return out


if __name__ == '__main__':
    root = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    main = open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, 'bin/main.bin'), 'rb').read()
    for what, t, n in loads(main):
        print(f'  {what:<20} tracks {t}-{t + n - 1}')
    ts = tracks(main)
    print(f'{len(ts)} tracks: {", ".join(runs(ts))}')
