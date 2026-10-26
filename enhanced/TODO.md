# Enhanced version: to do

Each item gets its own branch, is tested in WinUAE (A500 512K, and 1 MB / A1200 configurations),
then merged.

## Done

* **The machine's memory** (branch `feature/memory-config`): the bootblock's machine
  description (chip / slow / fast RAM, PAL / NTSC, CPU), a track cache in the largest memory
  beyond 512K of chip RAM, and the memory shown on the title screen (`README.md`, *The
  machine's memory*).
* **The source edited by hand** (branch `feature/scroller`): `src/nzs_game.s`, the debug monitor
  removed from block 1 and the enhanced code in its place; block 2 checked label by label.
* **The scroller** (branch `feature/scroller`): an interleaved display, a corkscrew with a
  vertical ring, double-buffered with a pristine buffer (`README.md`, *The scroller*): a tile is
  one blit, a new column or row is drawn once and copied, BOBs are restored from the pristine
  buffer. Identical to the original's display in the emulator; to try in WinUAE.
* **Mirrored frames on demand** (branch `feature/mirror-cache`): on a 512K machine the mirrored
  BOB frames are built when first drawn into a 48 KB ring cache, a level's known ones built as it
  starts; 43 KB of chip RAM freed (`$563A6-$611B0`), no cost in play in the emulator
  (`README.md`, *The mirrored frames*). To try in WinUAE.

## Next

### BOBs in one blit

The BOBs are still drawn as the original draws them - one cookie-cut blit per plane, 4 a BOB,
from frames stored as a mask and 4 planes - and are now most of the blitting left. On the
interleaved buffers a BOB can be one blit if its frame is line-interleaved with its mask
repeated for each plane's row (the A channel's modulo can't read one mask row 4 times).
`DeinterleaveBobs` (`$4E92`) could make that form instead of mask + planes, at start-up and for
each level's extra BOBs.

**Sprite masks: memory.** The main bank is 94,208 bytes (`$22AA6-$39AA6`), of which the masks
are about 18.8 KB. Repeating each mask 4 times costs about 56 KB more, plus the same for the
per-level banks. Options:
1. *1 MB machines:* pre-mask everything at load time and keep it in memory.
2. *512K:* as in the enhanced Ghosts'n Goblins, a cache of masked frames. Pre-build the
   frames that are always on screen (the kiwi, his arrows, common enemies) and build the rest
   on demand into a fixed-size cache, evicting the least recently used.
3. Fallback: a BOB whose masked form isn't built is drawn as now (4 blits, the mask as it is).

On 512K the scroller's buffers fill `$65400-$7FFFF`; the mirror cache freed 43 KB at
`$563A6-$611B0` (the place for a cache of masked frames); beyond that the masks need the
program moved to slow / fast RAM (below) or chip RAM above 512K.

The blitter only reaches chip RAM. On an A500 with a trapdoor 512K (slow RAM at `$C00000`), a
cache there would need a CPU copy into chip RAM before blitting. That RAM is better used as a
file cache (below), freeing chip RAM for the masks.

One program for every machine: work out the memory at boot (the bootblock) and scale back at
run time, as decided for Ghosts'n Goblins.

### Memory on 512K: the BOB frames

Done: the mirrored frames on demand (above), 43 KB freed at `$563A6-$611B0`. Left: from the
code, a level can show 122-256 of the 289 frames (41-85 KB), so keeping only a level's or a
world's unmirrored frames would save little more (`../original/docs/LEVELS.md`). The freed
memory is for the pre-masked BOBs (*BOBs in one blit*, above).

### Memory: next uses

* Chip RAM above 512K: the pre-masked interleaved BOBs (above), all of them at start-up.
* Slow / fast RAM on an A500: move the program (code and tables) there, as the Ghosts'n Goblins
  enhanced game does (`EnhRelocate`: assembled at two addresses to make a relocation table), and
  use the chip RAM it frees for masks; the cache takes the rest of the region.

### Frame rate

The original's logic runs once a pass of its game loop, which takes 2 frames, so the enhanced
game holds the passes to 2 frames (`SCR_MIN_FRAMES`). 50 frames a second would need the logic
run twice in a pass's worth of time - every movement and timer in the game is per pass - or
frames drawn in between: a project of its own.

## Loading

How it works now (see the next section): each level reads 5 tracks of world data, 1 track for
its map and sometimes 2 tracks of extra BOBs.
* Several levels share the same 5 tracks (levels 4-7 all use tracks 22-26, and levels 12-14
  use 52-56), but the game reads them again at every new level. It skips the load only when the
  same level restarts (`LoadedLevel`). Skip it when the world's data is already in memory, and
  load just the 1-track map.
* The track cache (done) keeps whole tracks. A file cache - the level data split into files
  (world data, maps, extra BOBs, the ending; about 470-490 KB against the tracks' 528 KB) read
  by file id - would hold all of it in 512K of slow RAM, keep whole levels, and suit new data
  (pre-masked BOBs, edited levels).

---

## Is everything preloaded, or loaded as needed?

**A mix.** Everything common to the whole game is loaded once, at boot, with the main program.
Each level's graphics and map are loaded from disk when the level starts. Nothing uses memory
beyond the 512K of chip RAM.

**At boot:** the main program (275,738 bytes packed, 338,855 unpacked, at `$400-$52FA6`)
contains:
* all the code
* the music driver and all its songs
* all 18 sound effects and instruments
* the main BOB bank: 289 frames, the kiwi, the enemies, items, effects and panel pieces (94 KB)
* the palettes and copper lists

**At each level start** (`$412E`, `LoadTracks` through `TrackRead`; `../original/disk/DISKMAP.md`):
* 5 tracks of packed world data to `$3CAA6`, unpacked in place (`UnpackLevel`). This holds the
  16×16 tile set (from `$3CB26`, 128 bytes a tile) and the world's other data.
* 1 track to `$44AA6`: the level's map (from `$44B26`, one byte a tile, rows of 64).
* On the 4th level of worlds 1, 2, 3 and 5, 2 more tracks to `$6C000`: the boss's BOB frames
  (9-26 frames). Their directory entries are appended to the main bank's at `$3BED6`,
  deinterleaved, and copied to `$613A6`.
* At the end of the game: 5 tracks from track 144 (the ending).

These buffers are inside the program's own address range: `$3CAA6-$460A5` is part of the
loaded program, overwritten by each level's data. So the level data replaces memory rather than
adding to it. Chip RAM is close to full: the program up to `$52FA6`, then the game's variables
and objects (`$613A6`, `$641B8`, `$64380`), the disk / deinterleave buffer at `$68000`, the
extra BOBs at `$6C000` and the two screens at `$70000-$7FFFF`. This is why the masks above need
care on 512K.
