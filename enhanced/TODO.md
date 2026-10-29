# Enhanced version: to do

Each item gets its own branch, is tested in WinUAE (A500 512K, an expanded A500, and 1MB / A1200
configurations), then merged into `main`. `README.md` describes everything done.

## Done

* **The machine's memory** (branch `feature/memory-config`): the bootblock's machine
  description (chip / slow / fast RAM, PAL / NTSC, CPU), and the memory shown on the title
  menu's options page (`README.md`, *The machine's memory*).
* **The source edited by hand** (branch `feature/scroller`): `src/nzs_game.s`, the debug monitor
  removed from block 1 and the enhanced code in its place; block 2 checked label by label.
* **The scroller** (branch `feature/scroller`): an interleaved display, a corkscrew with a
  vertical ring, double-buffered with a pristine buffer (`README.md`, *The scroller*).
  Identical to the original's display in the emulator; tested in WinUAE.
* **50 frames a second** (branch `feature/50hz`): the logic still once a pass (25 a second), an
  in-between frame drawn each pass with the camera and every object half-way; a busy pass drops
  to 25 Hz for that pass, never slower (`README.md`, *50 frames a second*). Tested in WinUAE.
* **Faster drawing** (branch `feature/fast-bobs`): the copper lists' copies, the ring's line
  lookups and the objects far off the screen (`README.md`, *50 frames a second*).
* **BOBs in one blit** (branch `feature/one-blit`, after `feature/mirror-cache`'s mirrored frames
  on demand, which it replaced): every main-bank frame, mirrored ones too, kept in a one-blit
  form: all built once with more than 512K of chip RAM; on 512K an 81 KB cache filled as each
  level starts (block 3, `src/frames.s`). 99.7 % of passes at 50 Hz in the emulator with the
  blitter timed, from 99.0 % (`README.md`, *BOBs in one blit*). Tested in WinUAE.
* **The title menu** (branch `feature/options-menu`): start game, options (the input setting,
  the cheat, the memory lines), a sound test; two-button joysticks (jump on up, jump on button 2,
  button 1 jumps and 2 fires) (`README.md`, *The title menu*). Tested in WinUAE.
* **The cheat** (branches `feature/fly-mode`, `feature/options-menu`): the original's typed code
  or the menu's switch; F1 flies (the original's unused fly mode), F2 skips a level (`README.md`,
  *The cheat*). Tested in WinUAE.
* **The level data as files, and a file cache** (branch `feature/file-cache`): each load the
  game makes is a file with just the bytes it uses (475 KB against the tracks' 555 KB), kept in a
  file cache in the largest memory beyond 512K of chip RAM: all of it in a trapdoor's 512K
  (`README.md`, *The game's disk reading*, *The machine's memory*). Tested in WinUAE on an
  expanded A500.
* **The A1200** (branch `feature/a1200`): above a 68000 the CPU's caches off and the vector base
  at 0, FMODE 0 on AGA (`README.md`, *Booting*). Tested in WinUAE.
* **Level 4-4's second map** (branch `fix/level-4-4`): reaching the cage on level 4-4 loads a
  second map (5 tracks from track 63, 1 from track 69: `$45CC`), a load `game_tracks.py` did not
  list, so the disk had no file for it and the game stopped with a fatal disk error. It is listed
  now, its tracks extracted, and the disk has the two files (`test_boot.py` reads them). Not yet
  tested in WinUAE.

## Next

A problem found while documenting the code (not yet fixed or tested in WinUAE):

* **The Copylock key** (`../original/docs/SELFMOD.md`): the game checks the key the original's
  Copylock left in the trace vector `$24` at every boss and every warp (`sub_0A742`), and if it
  is wrong breaks its own collision test: the kiwi can no longer be hurt, pick anything up or
  free the caged kiwi, so the level cannot be finished. This disk does not run Copylock, so the
  check fails. The fix: put `$F974DB7D` in `$24` as the game starts (`ext.s`).
* **Input test** (the title menu's options): the joystick's directions, both buttons and the
  last key, shown as they change.
* **Sprite test**: any BOB frame of the main bank (and its mirrored copy) drawn on the title.
* **50 Hz / 25 Hz** on the options page (`SmoothOn`), for comparing. Perhaps.
* **`test_jump.py`**: each input setting with up, button 2 and both, where up does something
  else (in water, on a ride); `test_menu.py` covers them on open ground.
* **Shared world data read once**: levels 4-7 share their world data, and so do levels 12-14,
  but the game reads it again at every level (it skips the load only when the same level
  restarts: `LoadedLevel`). With a file cache it comes from memory; on a plain 512K machine it is
  read from the disk each time. Skip the load when the world's data is still unpacked in place,
  and load just the map.
* **The level files packed**: the maps, boss frames and progress screen packed as the world data
  is (about 423 KB in all against 475 KB): a 1MB machine's file cache, after the BOB frames, would
  hold about 51 % of them instead of 45 %. Perhaps.
* **Real hardware**: so far WinUAE, FS-UAE and the emulators of the tests.

## Not doing

**The program in slow / fast RAM** (looked at on branch `feature/relocate`; decided against: the
game runs well as it is). The idea, as the Ghosts'n Goblins enhanced game does it: run the code
and tables (about 61 KB at `$400-$F33E`) from an expansion and give the chip RAM they free to the
BOB frames' cache. What stood in the way:
* chip-only data inside the code: `nzsemu`'s `dmacheck` found the game's own copper list
  (`$C2BA`) and an empty sprite (`$C22E`) read by the custom chips there;
* addresses as numbers: self-modifying code writes into instructions by numeric address
  (`$4EE8`-`$4EF4`, `$6F20`, `$7C6A`, `$B0AA`, `$B6CC`, `$B8DE`) and scripts are set from
  immediates (`move.l #$607E,$14(a5)`), and the data tables hold addresses as bytes: assembling
  twice finds only labels, so all of block 2's data would need going through by hand;
* block 2 calls block 1's jump table with short addresses (`jsr (JT_KeyTest).w`).
And it would bring little: a cold 512K frame cache already keeps 99.7 % of passes at 50 Hz, as
with 1MB of chip RAM; a trapdoor's slow RAM runs code no faster than chip RAM.

---

## Is everything preloaded, or loaded as needed? (the original game)

How the original does it - the enhanced game loads the same data, as files (*Done*, above), and
uses memory beyond 512K for the file cache and the BOB frames.

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
* Between levels: 5 tracks from track 144 (the progress screen: the map of New Zealand and the
  kiwis rescued so far).
* On level 4-4, when the kiwi reaches the cage: its second map, 5 tracks from track 63 and 1 from
  track 69 (`$45CC`).

These buffers are inside the program's own address range: `$3CAA6-$460A5` is part of the
loaded program, overwritten by each level's data. So the level data replaces memory rather than
adding to it. Chip RAM is close to full: the program up to `$52FA6`, then the game's variables
and objects (`$613A6`, `$641B8`, `$64380`), the disk / deinterleave buffer at `$68000`, the
extra BOBs at `$6C000` and the two screens at `$70000-$7FFFF`. (The enhanced game's 512K layout:
`README.md`, *The scroller* and *BOBs in one blit*.)
