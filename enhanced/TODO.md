# Enhanced version: to do

Each item gets its own branch, is tested in WinUAE (A500 512K, and 1 MB / A1200 configurations),
then merged.

## Done

* **The machine's memory** (branch `feature/memory-config`): the bootblock's machine
  description (chip / slow / fast RAM, PAL / NTSC, CPU), an extension module in memory the
  original never uses, a track cache in the largest memory beyond 512K of chip RAM, and the
  memory shown on the title screen (`README.md`, *The machine's memory*).

## Memory: next uses

* Chip RAM above 512K: the pre-masked interleaved BOBs (below), all of them at start-up.
* Slow / fast RAM on an A500: move the program (code and tables) there, as the Ghosts'n Goblins
  enhanced game does (`EnhRelocate`: assembled at two addresses to make a relocation table), and
  use the chip RAM it frees for masks; the cache takes the rest of the region.
* The extension module grows past its 11 KB: give it a home in the memory the program frees.

## Interleaved display

Change the screen from separate bitplanes (`$2000` apart) to an interleaved screen: each line
holds its 4 planes one after another, 160 bytes a line, with `BPL1MOD`/`BPL2MOD` = 120.

**Why:** fewer blits for the background, which the game redraws completely on every pass
(`sub_0B55C`; see the answer on scrolling below).
* The original copies each 16×16 tile as 4 blits of 1 word × 16 lines, one per plane. That is
  about 20 × 12 × 4 ≈ 960 blits per pass, each with its own register setup and wait.
* On an interleaved screen, one blit of 1 word × 64 lines (A modulo 0, D modulo 38) copies the
  whole tile: about 240 blits, a quarter of the setups and waits.
* **The tiles need no conversion.** They are already stored line-interleaved (each tile is 128
  bytes; each line holds the 4 planes' words in turn, which is why the original blits them with
  A modulo 6). Only the blit parameters change.
* Possible further step: draw only the parts that change, keeping a clean background buffer
  that scrolls by its bitplane pointers. This is the Ghosts'n Goblins "pristine buffer" idea,
  adapted to an 8-way scroll. It is a larger change and worth weighing once the interleaved
  version works.

**Assets and code to convert:**
* BOBs. The stored frames are interleaved by word column (mask, p0-p3 per 16 pixels).
  `DeinterleaveBobs` (`$4E92`) turns them into mask + 4 planes at start-up. For an interleaved
  screen they need to be line-interleaved (p0-p3 per line), and the mask has to be repeated for
  each plane line (mask × 4): the A channel's modulo can't re-read one mask line 4 times. This
  can be done offline (a tool converts the bank and the per-level banks), or by a replacement for
  `DeinterleaveBobs` at load time. Then `BlitBob` (`$B6C4`) does one blit per BOB instead of one
  per plane. Clipping and the hot spots (`BobDirectory`) are unaffected.
* Every routine that assumes the `$2000` plane stride. There are 14 references in
  `nzs_main.s` (`#l_02000` / `$2000(aN)`): the tile and BOB blits, the panel/score/text drawing
  (`$C7C6`, `$C8D4`, `$C92E` …), the screen clears and copies (`$B0BC`, `$B8F8` …), and the
  pictures and screens drawn at `$44CE`, `$4948`, `$49F4`, `$4DD4`, `$5068`, `$BFA8`.
* The copper lists: the bitplane pointers (`$C27A`/`$C29A`/`CopperList`) become 40 bytes apart,
  and the modulos are set.
* Full-screen pictures (the intro, title and end pictures, and the font if it is drawn per
  plane): converted offline, or line-interleaved as they are loaded.
* Fine horizontal scroll (BPLCON1), the panel split at line `$DC` and the window-squeeze effect
  are unaffected.

**Sprite masks: memory.** The main bank is 94,208 bytes (`$22AA6-$39AA6`), of which the masks
are about 18.8 KB. Repeating each mask 4 times costs about 56 KB more, plus the same for the
per-level banks. Options:
1. *1 MB machines:* pre-mask everything at load time and keep it in memory.
2. *512K:* as in the enhanced Ghosts'n Goblins, a cache of masked frames. Pre-build the
   frames that are always on screen (the kiwi, his arrows, common enemies) and build the rest
   on demand into a fixed-size cache, evicting the least recently used.
3. Fallback: draw a BOB whose interleaved mask isn't built with the old one-blit-per-plane
   method (the masks as they are, using per-plane blits on the interleaved screen with D
   modulo 158). Slower, but needs no extra memory.

The blitter only reaches chip RAM. On an A500 with a trapdoor 512K (slow RAM at `$C00000`), a
cache there would need a CPU copy into chip RAM before blitting. That RAM is better used as a
file cache (below), freeing chip RAM for the masks.

One program for every machine: work out the memory at boot (the bootblock) and scale back at
run time, as decided for Ghosts'n Goblins.

## Loading

How it works now (see the next section): each level reads 5 tracks of world data, 1 track for
its map and sometimes 2 tracks of extra BOBs.
* Several levels share the same 5 tracks (levels 4-7 all use tracks 22-26, and levels 12-14
  use 52-56), but the game reads them again at every new level. It skips the load only when the
  same level restarts (`LoadedLevel`). Skip it when the world's data is already in memory, and
  load just the 1-track map.
* On 1 MB machines, cache files in the extra RAM (the whole level data is 528 KB on disk, packed
  and unpacked in place), so later loads become a copy.

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
* On some levels, 2 more tracks to `$6C000`: extra BOB frames for that level (which
  creatures they are is still to be extracted). Their directory entries are appended to the main bank's at `$3BED6`, deinterleaved,
  and copied to `$613A6`.
* At the end of the game: 5 tracks from track 144 (the ending).

These buffers are inside the program's own address range: `$3CAA6-$460A5` is part of the
loaded program, overwritten by each level's data. So the level data replaces memory rather than
adding to it. Chip RAM is close to full: the program up to `$52FA6`, then the game's variables
and objects (`$613A6`, `$641B8`, `$64380`), the disk / deinterleave buffer at `$68000`, the
extra BOBs at `$6C000` and the two screens at `$70000-$7FFFF`. This is why the masks above need
care on 512K.
