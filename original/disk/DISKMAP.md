# The original disk, track by track

80 cylinders x 2 heads (track = cylinder x 2 + head). The IPF also has cylinders 80-83, which
are unformatted. Every track but track 1 is standard AmigaDOS MFM: 11 sectors of 512 bytes,
`$4489` sync, every checksum valid - but there is no filesystem (block 880 is not a root block).

| Track | Contents | Read by |
|---|---|---|
| 0, `$000-$3FF` | the bootblock | Kickstart |
| 0, `$400-$15FF` | Rob Northen's protection loader (Copylock), to `$60000` | the bootblock (`trackdisk.device`) |
| 1 | the Copylock track: custom MFM, a long track, 11 custom sync words | the protection loader, and again the game loader |
| 2-89 | level data (below); tracks 64-67 and 69 are not read | the game (`LoadTracks`) |
| 90 | the game loader, to `$400` | the second-stage bootblock (in the protection loader's payload) |
| 91-93 | the loading screen, to `$70000` | the game loader |
| 94-143 | the main program, packed (275,738 bytes: it ends in track 142), to `$400` | the game loader |
| 144-148 | data read at the end of the game, to `$3CAA6` | the game |
| 149-151 | not read | - |
| 152-159 | 2-track blocks read on some levels, to `$6C000` | the game |

## What the game reads (`tools/disk/game_tracks.py`)

At the start of each level `LoadTracks` (`$55BA`) reads, from `LevelTable` (`$5DBA`, 16 bytes a
level): 5 tracks of packed level data to `$3CAA6`, unpacked in place (`UnpackLevel`, the main
program's packed format), and 1 track to `$44AA6`. The 5-track windows overlap: each level's
packed data is shorter than 5 tracks. Then, on some levels, 2 tracks from `ExtraTracks`
(`$418C`) to `$6C000`. At the end of the game, 5 tracks from track 144 to `$3CAA6`.

| Level | 5 tracks | 1 track | Level | 5 tracks | 1 track |
|---|---|---|---|---|---|
| 0 | 2-6 | 18 | 10 | 39-43 | 50 |
| 1 | 6-10 | 19 | 11 | 44-48 | 51 |
| 2 | 11-15 | 20 | 12 | 52-56 | 56 |
| 3 | 14-18 | 21 | 13 | 52-56 | 57 |
| 4 | 22-26 | 25 | 14 | 52-56 | 58 |
| 5 | 22-26 | 26 | 15 | 59-63 | 68 |
| 6 | 22-26 | 27 | 16 | 70-74 | 79 |
| 7 | 22-26 | 28 | 17 | 74-78 | 80 |
| 8 | 29-33 | 48 | 18 | 81-85 | 88 |
| 9 | 34-38 | 49 | 19 | 84-88 | 89 |

2-track blocks: 158-159, 156-157, 154-155, 152-153 (`ExtraTracks` entries 0, 1, 2 and 4, chosen
by the level). 96 tracks in all: 2-63, 68, 70-89, 144-148, 152-159 (`disk/files/tracks/`).
