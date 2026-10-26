# The graphics

Extracted by `tools/assets/make_assets.sh` into [`../assets/gfx`](../assets/gfx):

| | |
|---|---|
| `bobs_main.png` | all 289 frames of the main BOB bank on one numbered sheet |
| `main/frameNNN.png` | each frame, transparent where its mask is clear |
| `main/frameNNN.bin` | each frame exactly as it is stored (header long + interleaved data) |
| `bobs.json` | the frame directory (offset, hot-spot x/y, size) and the palette |

## The screen

The game screen is 320 pixels wide with 4 bitplanes (16 colours). The planes are `$2000` bytes
apart and double-buffered at `$70000`/`$78000`. The copper list (`CopperList`, `$C2BA`) holds the
bitplane pointers, then `COLOR00-15`, then a split at line `$DC`.

Palettes are 16 words, each stored as **half** the colour value. `SetPalette` (`$BEFE`) doubles
each word as it writes it into the copper list. The CIA-B interrupt fades between palettes.
The in-game palette is `GamePalette` (`$C1AA`), set at every level start (`$412A`).

## BOBs (blitter objects)

The main bank has a frame directory at `$39AA6` (`BobDirectory`) with 16 bytes per frame:

| Offset | |
|---|---|
| +0 long | offset of the frame in the bank's data (`BobData`, `$22AA6`) |
| +4 word | x of the top left relative to the object's position (signed) |
| +6 word | y |
| +8 word | width in pixels |
| +A word | height |
| +C word | 0 in the main bank |

Each frame starts with a long (width in words << 16 | height), followed by its graphics
**interleaved by word**: for each line, for each 16-pixel column, 5 words (the mask, then planes
0-3). At start-up (`$C526`), `DeinterleaveBobs` (`$4E92`) rearranges every frame in place into 5
separate blocks: the mask, then plane 0 ... plane 3, each width/8 × height bytes. It uses a
buffer at `$68000` and patches its own displacements. `BlitBob` (`$B6C4`) draws them in this
second form with the cookie-cut minterm `$CA` (A = mask, B = the plane, C = the screen).

The 4th level of worlds 1, 2, 3 and 5 loads 2 more tracks to `$6C000`: the boss's frames. Their
directory entries are appended at `$3BED6` (frames 579 on) with offsets rebased by `$3E900`,
deinterleaved the same way and copied to `$613A6`. They, the level maps and the tiles are
extracted by `tools/levels/levels.py` ([`LEVELS.md`](LEVELS.md)). The intro and title pictures
and the font are still to do.
