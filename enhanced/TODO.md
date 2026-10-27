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
  buffer. Identical to the original's display in the emulator; tested in WinUAE.
* **50 frames a second** (branch `feature/50hz`): the logic still once a pass (25 a second), an
  in-between frame drawn each pass with the camera and every object half-way; a busy pass drops
  to 25 Hz for that pass, never slower (`README.md`, *50 frames a second*). Tested in WinUAE.
* **Mirrored frames on demand** (branch `feature/mirror-cache`): on a 512K machine the mirrored
  BOB frames are built when first drawn into a 48 KB ring cache, a level's known ones built as it
  starts; 43 KB of chip RAM freed (`$563A6-$611B0`), no cost in play in the emulator
  (`README.md`, *The mirrored frames*). Tested in WinUAE.

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

Done (branch `feature/50hz`): 50 frames a second by drawing an in-between frame each pass
(`README.md`, *50 frames a second*). Left: the passes busy enough to drop to 25 Hz (about 1 in
30 on an A500, more on the busiest levels) - drawing the BOBs in one blit (above) is the way to
fewer.

### Title menu, two-button joysticks and a cheat

Along the lines of the enhanced Ghosts'n Goblins' title menu (`enhanced/docs/SCROLLER.md` there,
*The title menu*, *Two-button joysticks*, *The test page's tests*). Each on its own branch.

**The title menu.** The title screen (the text `dat_0C0A2`, printed by `sub_0C6A8` from `$404C`,
now through `EnhTitleText`; the wait for fire or the time-out in `sub_0B9F0`) keeps its logo,
credits and copyright lines and gets a menu under the kiwi:

| Page | Items |
|---|---|
| title | `START GAME`, `OPTIONS`, `TEST MENU` |
| options | `INPUT - JUMP ON UP` / `JUMP ON BUTTON 2`, `CHEAT OFF` / `ON`, `EXIT` |
| test | the machine's memory line (moved from the title), the track / mirror cache line, `SOUND TEST`, `INPUT TEST`, `SPRITE TEST`, `EXIT` |

* Up / down move (round from the last item to the first), fire chooses; left, right and fire
  switch a setting. The chosen item shows as `> ... <`. Moves and fire count when newly pressed
  (against the last reading), so a held button does not repeat - and fire on `START GAME` must
  start the game on the same frame as the original's fire did, so the comparisons with the
  original (`test_scroller.py`) stay in step.
* A move or a change redraws the title and restarts its time-out to the attract sequence; the
  options and test pages have no time-out.
* The original's cheat, typed on the title, keeps working (below).
* Settings last until the machine is reset.

**Two-button joysticks.** The original jumps on up and fires (the kiwi's arrows) on the button.
The second button (port 2, pin 9: a two-button stick or a Sega-style pad) as jump:
* *Reading it:* the vertical blank's joystick reading (`ReadJoystick`, `$2A6C`, kept at
  `$63DB0` by `$BE24`) also sets a spare bit when `POTINP` bit 14 (DATRY) is low; `POTGO`
  written so pin 9 is driven high and a pressed button pulls it low (the game already writes
  `POTGO` `$FF00` at `$C452`: to check against the mouse port's use). Nothing else reads the new
  bit, so with jump on up the game is as before.
* *The kiwi's jump:* find where his handler (type 0, `$91D4`) turns up into a jump, and with jump
  on button 2 take the jump from the button instead; up then only climbs / swims as the game
  does elsewhere (to check: what up does in water, on a ride, on a ladder, if he has one).
* The option: `INPUT` on the options page (and a key, as J in Ghosts'n Goblins). Jump on up
  stays the default: the original's controls, and what the comparisons use.

**Cheat on / off.** The original has a cheat: `MOTHERFUCKENKIWIBASTARD` typed on the title.
`sub_0B9F0` checks each key (raw key codes, `dat_045B4`, each eor `$41`, `$BE` ends) while the
title waits; each right key plays a sound, the whole code plays tune 10 and sets the game's
starting lives (the immediate at `l_04F46+2`, normally 3) to 1,000. That number is also the
cheat's switch:
* in play, the game loop (`$43C0`) tests the HELP key (raw `$5F`, worked out from the 1,000)
  and skips to the next level (`l_054AE`);
* `sub_0900A` would turn F1 (raw `$50`, held: `sub_0903A`) into a free-moving kiwi through the
  walls (`sub_08FD4`: his handler swapped, 4 pixels a step with the joystick) and back - but
  nothing calls it: left in, unused.

`CHEAT` on the options page sets the same immediate (1,000 or 3), so the menu and the typed code
agree, and both features come with it; shown on the title when on. Perhaps also: `sub_0900A`
called from the kiwi's handler, so the original's own fly mode works with the cheat on.

**The test page's tests.**
* *Sound test:* the 12 songs and the 18 effects by number (`PlaySong`, `PlaySample`), fire
  plays, `MUSIC OFF` stops the tune.
* *Input test:* the joystick's directions, both buttons and the last key, shown as they change.
* *Sprite test:* any BOB frame of the main bank (and its mirrored copy) drawn on the title.

**Perhaps also on the options page:** `DISPLAY 50 HZ / 25 HZ` (`SmoothOn`), for comparing.

*Testing:* a `test_menu.py` as Ghosts'n Goblins': from one saved state of the title, starting a
game from the menu, moving round, each switch, the pages and `EXIT`, the time-out; and a
`test_jump.py`: each input setting with up, button 2 and both, on open ground and where up does
something else. `nzsemu` needs the second button (`POTINP`) in its `joy` command.

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
