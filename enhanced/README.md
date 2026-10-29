# The New Zealand Story on an ordinary AmigaDOS disk

> The game rebuilt from the disassembly in [`../original`](../original) onto a standard
> AmigaDOS-format disk that boots with the
> [4489_byteloader](https://github.com/MarkyTurtle/4489_byteloader) instead of Rob Northen's
> Copylock-protected boot chain, with improvements: a scroller that updates only what moves (a
> corkscrew with a vertical ring, double-buffered, with a pristine buffer), and the machine's
> memory used for a cache of the level files, the sprites (BOBs) drawn in one blit each from frames kept
> ready for it (on a 512K machine in a cache filled level by level), and 50 frames a second in play. Nothing on it is copy-protected: any emulator or real drive
> reads it, and it can be written to a real floppy with any ADF tool.

```
python3 enhanced/tools/build_disk.py      # -> enhanced/build/nzs.adf
python3 enhanced/tools/test_boot.py       # boots it in an emulator and checks it
python3 enhanced/tools/test_scroller.py   # the display against the original's, frame by frame
python3 enhanced/tools/test_frames.py     # what the one-blit frames' 512K cache costs in play
python3 enhanced/tools/test_smooth.py --blittime   # how much of the game runs at 50 Hz
```

(`../BUILDING.md` has what to install.) Tested in FS-UAE as an A500 with FS-UAE's built-in AROS
Kickstart replacement: it boots to the loading screen, then the attract sequence, and the game
plays, loading its level data from the disk. Tested in WinUAE: the scroller, the mirror cache
(now the one-blit frames: still to be tried) and 50 frames a second in play, the progress screens and the return to the title. Still to be
tried: real hardware.

| File | What it is |
|---|---|
| `src/nzs_game.s` | **The game's source**, edited by hand since October 2026 (made from `original/nzs_main.s` by `tools/fork_source.py`): the original's, with the debug monitor removed and jumps put over the start of the routines the enhanced code takes over (each marked `enhanced:`) |
| `src/enhanced.s` | The enhanced game's own code, in block 1 where the monitor was: the file cache, the title's memory lines, the entries for the routines taken over |
| `src/scroller.s` | The scroller (below) |
| `src/menu.s` | The title menu (start, options: input, cheat) and the joystick's second button |
| `src/smooth.s` | 50 frames a second: the in-between frame drawn each pass (below) |
| `src/frames.s` | The BOB frames in one-blit form, mirrored ones too: all built once with more than 512K of chip RAM, or on a 512K machine a cache filled level by level (below); block 3 of the program |
| `src/diskload.s` | The game's disk reading on this disk, in place of the original's `TrackWrite` / `TrackRead`, reading the level files, with the file cache in front of the disk |
| `src/boot_4489.s` | The bootblock: surveys the machine's memory, finds the boot drive, loads the extension module and goes on in it |
| `src/ext.s`, `src/ext.i` | The extension module: the part of the boot the bootblock has no room for (loading screen, program, the machine description handed to the game) |
| `src/byteloader.i` | The 4489_byteloader, as published (used by both) |
| `tools/build_disk.py` | Builds the disk; checks that every label of block 2 on is where the original has it |
| `tools/test_boot.py` | Boots the disk in an emulator (Unicorn) from Kickstart's call to the game's start, on four memory configurations, then calls the game's `TrackRead` as the game does, twice (the second time from the cache when it fits) |
| `tools/test_scroller.py` | Runs the original and the enhanced game side by side in `original/tools/nzsemu` and compares their displays pixel for pixel (`original/tools/display.py`); `--chip` for the machine's chip RAM |
| `tools/test_menu.py` | The title menu, its settings and the joystick's input settings in play |
| `tools/test_fly.py` | The cheat's fly mode on F1, with and without the cheat |
| `tools/test_smooth.py` | Plays every level at 50 Hz and at 25 Hz: how many in-between frames are drawn, and that the game keeps its speed; `--blittime` makes the emulator's CPU wait for the blitter as an A500's does |
| `tools/test_frames.py` | Plays every level with the 512K frame cache, with it cold, and with all frames built once (1MB), the blitter timed: the frames built in play and the in-between frames left out |
| `tools/frame_counts.py` | How often each frame is drawn on each level, from plays in the emulator: `tools/frame_counts.json`, which chooses the frames the 512K cache is filled with |
| `tools/fork_source.py` | How `src/nzs_game.s` was made (kept for the record) |
| `tools/floppy.py` | The floppy drive the boot test uses (from the Ghosts'n Goblins project) |

## The disk

80 cylinders x 2 heads x 11 sectors of 512 bytes (901,120 bytes), standard AmigaDOS MFM with
the `$4489` sync, no filesystem (Workbench shows it as NDOS):

| Disk offset | Bytes | |
|---|---:|---|
| `$00000` | 1,024 | the bootblock: `'DOS',0`, checksum, root block 880, then the code |
| `$00400` | 144 | the file table: `'NZSF'`, version.w (1), count.w, 8 bytes zero, then for each file id its disk offset and length (longs) |
| `$00600` | 16,896 | file 1: the loading screen (the original file) |
| `$04800` | 455,490 | file 2: the 40 level files, one after another: each load the game makes while it runs, cut from the original disk's tracks (*The game's disk reading*) |
| `$73B42` | 432 | file 3: the extension module (`src/ext.s`), loaded to `$65400` |
| after it | about 276 KB | file 0: the game, packed in the original's format |
| | about 147 KB | free |

(`build_disk.py` prints the exact offsets.)

The game is stored packed: unpacked (338,855 bytes) it would leave only about 3 KB free. It is
packed by `original/tools/disk/pack.py`, which reproduces the original's tracks 94-143 byte for
byte from the original program.

## Booting (`src/boot_4489.s`, `src/ext.s`)

Together they do what the original's five stages (`../original/docs/BOOT.md`) did, minus the
protection. The bootblock:

1. surveys the machine while Kickstart is intact (`MemDetect`): from exec's memory list the chip
   RAM, slow RAM (`$C00000-$DBFFFF`) and fast RAM regions, PAL / NTSC and the CPU - the
   *machine description* (`ext.i`; the layout of the Ghosts'n Goblins enhanced game's, with the
   magic `NZSM`);
2. finds the drive booted from: opens `trackdisk.device`'s units 3 to 0 until one is the boot
   IORequest's unit (DF0 if none is). Kickstart 1.3 boots only from DF0; 2.0 and later from any
   drive. Every load reads that drive, here and in the game;
3. takes the machine over (interrupts and DMA off, supervisor mode) and copies its loader, with
   the machine description, to `$63100`;
4. reads the file table, loads the extension module (file 3) to `$65400` and goes on in it
   (`ExtBoot`), handing it its loader (`LoadIt`), the description and the file table.

The module (`ExtBoot`) then:

5. keeps the machine description in its header; above a 68000 (exec's AttnFlags) turns the CPU's
   caches off (on a 68040 / 68060 written back first) and sets the vector base to 0: the game
   changes its own code as it runs (BlitBob's minterm before each BOB, `DeinterleaveBobs`'
   displacements), which a 68020's instruction cache would not see, and writes its vectors at 0.
   On an A1200 it also sets FMODE to 0 (the bitplanes and sprites fetched as on an A500);
6. shows the loading screen as the track 90 loader did: black, 4 planes at `$78000` (`$2000`
   apart), `BPLCON0 $4200`, `DDFSTRT $38`, `DDFSTOP $D0`, `DIWSTRT $3C81`, `DIWSTOP $04C1`, the
   same copper list; the file loaded to `$70000` and decoded there, its colours doubled;
7. loads the game to `$400` and unpacks it in place, as the track 90 loader's `Unpack`; writes
   the machine description and the boot drive into the game's header (`EnhHeader`, `$426`);
8. enters the game at `$400` with `d0 = a0 = $400`, as the track 90 loader did. The game's
   start-up (`Init`) sets up the file cache and the title's memory lines (`EnhInit`).

A load that fails is tried again; after 8 failures COLOR00 turns red while it goes on trying.
Memory while loading: the game `$400-$52FA6`, the loader and its buffers `$60000-$63FFF`
(MFM buffer `$60000`, file table `$63000`, the loader `$63100`, stack below `$64000`), the
module `$65400-`, the screen file `$70000`, the screen `$78000-$7FF3F`.

## The machine's memory

The original uses 512K of chip RAM and nothing else. The enhanced game looks at what the machine
has (the bootblock's description) and uses the largest of:

| Memory | Machines |
|---|---|
| chip RAM above 512K | A500+, A600, A1200, an A500 with a 1MB Agnus |
| slow RAM (`$C00000-$DBFFFF`) | an A500 with a trapdoor expansion |
| fast RAM (any other region) | a CPU card, a side expansion, an A1200 with fast RAM |

for the **file cache** (`FileGet` / `FilePut` in `enhanced.s`, called by `TrackRead`): every
level file the game reads from the disk (*The game's disk reading*) is kept there while there is
room, first come, first served, and read from memory the next time. A level played again (after
a game over, the next game) reads nothing from the disk; the levels that share their world data
(4-7, 12-14) read only their map. All the level files are 445 KB, so 512K of slow or fast RAM
holds every one of them (the track cache before it held 93 of the 96 tracks, 528 KB); a 1MB
machine without other memory has 216 KB after the BOB frames (*BOBs in one blit*). With no memory
beyond 512K of chip RAM, the game reads every level from the disk as the original did.

The title menu's **options page** shows the machine and what the game makes of it, above the kiwi
(the title itself showed it until the menu came: *The title menu*):

```
CHIP 512K  SLOW 512K  FAST 0K
FILE CACHE 444K IN SLOW RAM
```

(`FILE CACHE 216K OF 444K IN CHIP RAM` on a 1MB machine, where it holds part of them; `NO FILE
CACHE` on a plain 512K machine). The game's title text call (`$404C`) calls
`EnhTitleText`, which prints the original's text and then these two lines with the game's own
printer (`sub_0C6A8`).

**Where the module lives.** `$65400`, in 11 KB between the game's object slots (which end at
`$65396`) and its disk / deinterleave buffer at `$68000`, which the original never uses:
`original/nzs_main.s` has no absolute reference into it, and in `original/tools/nzsemu` nothing
writes to it over 12 games and all 20 levels started in turn. It is needed only while booting;
the scroller's buffers start there.

**One program for every machine**, as decided for Ghosts'n Goblins: the same disk on every
Amiga, scaling up at run time. The chip RAM above 512K also holds the BOB frames in one-blit form
(*BOBs in one blit*), the file cache taking what they leave. Next (`TODO.md`): moving the
program itself into slow / fast RAM to free chip RAM on an expanded A500.

## The scroller (`src/scroller.s`)

The original redraws the whole playfield on every pass of its game loop (`sub_0B55C`): 20 x 11
tiles of 16 x 16, each copied as 4 blits of one word, about 880 blits, then the BOBs over them.
The enhanced game keeps three buffers that change only where the view moves:

* the **pristine buffer**: the background alone. When the view moves into a new tile column or
  row, only that column or row is drawn, from the level's map;
* **display buffers A and B**, shown alternately: each brings itself to the view by copying the
  new column (one blit) or row (one blit) from the pristine buffer, has the BOBs drawn over it,
  and before it is drawn again has each BOB's rectangle copied back from the pristine buffer
  (one blit each). No background is ever saved.

**The layout.** Every buffer is line-interleaved - each line holds the 4 planes' rows of 21
words, 168 bytes - so a tile is one blit (the original's tiles are already stored a line of 4
planes at a time) and so is a rectangle's restore.
* **Horizontally, a corkscrew:** world tile column C is at byte 2C of a plane's row. The 20 words
  fetched start at the camera's tile column, so scrolling right by a tile moves the bitplane
  pointers on one word, and the column that leaves on the left is the memory of the one that
  comes in on the right (the 21st word). Nothing is ever moved.
* **Vertically, a ring** of 192 lines (12 tile rows; the playfield shows 176): world line Y is
  ring line Y mod 192. Where the ring wraps inside the playfield, the copper list waits for that
  line and reloads the pointers with ring line 0.
* The same mapping in every buffer, so a rectangle copies to the same offset in another one.
* **The panel** (lives, score, oxygen: the 24 lines under the playfield) is a buffer of its own
  for each display buffer; at the original's split line (`$EC`, where it sets BPLCON1 to `$77`)
  the copper list points the bitplanes at it.

| Memory (during play) | | |
|---|---:|---|
| `$65400`, `$66300` | 2 x 3,840 | the panels of A and B (24 lines of 160 bytes) |
| `$67200` | 32,384 | the pristine buffer (192 x 168 + 128: 64 columns of corkscrew) |
| `$6F080`, `$76F00` | 2 x 32,384 | display buffers A and B |
| `$7ED80`, `$7EF00` | 2 x 384 | their copper lists |
| `$7F080`, `$7F600` | 2 x 1,400 | their lists of rectangles to restore (175 each) |

That is the original's two screens (`$70000-$7FFFF`) and the buffers it uses only while loading
or between games (its disk and BOB-deinterleave buffer at `$68000`, the boot's module at
`$65400`), so it fits in 512K of chip RAM.

**When it is on.** From the first pass of the game loop (`ScrEnter`: the panels taken from the
game's screens, everything drawn in full) until the game clears its screens or sets up another
display (`sub_0BB76`, `sub_0BCDA`) or reads the disk (`ScrLeave`). The title, the story pages,
the high scores and the level start's READY screen are the game's own display, unchanged.

**The game's drawing, translated.** The jumps put over the start of the routines it takes over
(`nzs_game.s`, marked `enhanced:`) go to `enhanced.s`, which in the game's own display does
what they did and in the scroller's goes to `scroller.s`:

| Game routine | In the scroller's display |
|---|---|
| `sub_0B55C` (the playfield, after the fine scroll) | `EnhScroll`: the buffers brought to the camera, the back buffer's rectangles restored |
| `sub_0B8B4` (a BOB's 4 blits) | `ScrBob`: the same cookie-cut blits, into the back buffer's ring (split where it wraps) or panel; the rectangle marked for restoring |
| `sub_0C744`, `sub_0C84C` (the text printers), `sub_04C78` (a panel fill) | `ScrPrintCol`, `ScrPrintPix`, `ScrFill`: the same pixels, written into both display buffers as the game writes both screens |
| `sub_0BC8C`'s end (a frame ready) | `EnhFlip`: the copper list for the buffer just drawn |
| the level 6 interrupt (the frame taken) | `EnhL6`: that copper list from the next frame |
| the level 3 interrupt | `EnhVBL`: the frame count, the game list's colours and sprites copied into the scroller's lists; `EnhDIW`: the ring's wrap follows the screen shake's display window |
| `sub_0BCD0` (wait for the frame to be taken) | `EnhWaitFlip`: the same, and at least 2 frames a pass |

The screen addresses the game computes stay as they were for the two screens (`$20(a6)`:
`$70000` or `$78000`), with the line table (`mem_63E94`) made virtual - 64 bytes a line - so
that a screen address always tells its line and byte (with the original's 40 bytes a line, a
BOB's word just left of a line is the previous line's last), and the translation does the
rest.

**Speed.** The original's game loop takes 2 frames a pass (25 frames a second) and its logic
runs once a pass, so the enhanced game holds each pass to 2 frames: the game runs at the
original's speed, without its slow-downs (and at 50 frames a second, below). In the emulator a pass now makes
about 50 blits instead of about 1,000 (the BOBs, drawn as the original draws them, are most of
what is left).

**Tested** (`tools/test_scroller.py`): the original and the enhanced game run side by side in
`original/tools/nzsemu`, each level from the start-up with the same random joystick (changed
between passes, and given to the game at once, so the two stay in step pass for pass), and
what each shows is rendered from its own memory and copper list (`original/tools/display.py`)
and compared every 5 passes: identical in every frame compared, on all 20 levels with four
different joysticks. The comparison stops where the two games' state goes apart, which it
eventually does because the CIA timer that counts the level's time ticks at a different phase
from the passes. Tested in WinUAE (the play, the progress screen between levels, the title
after a game); not yet on real hardware.

## 50 frames a second (`src/smooth.s`)

The original's logic runs once a pass of its loop, and a pass takes 2 frames: 25 frames a
second, each shown twice. Every speed and timer in the game is counted in passes, so the logic
stays as it is; instead each pass now draws two frames:

* **M**, the in-between frame: the camera and every object half-way between where they were in
  the last pass's frame and where they are now. The screen shows each pass one frame (20 ms)
  later than before; the animation frames still change at the original's rate.
* **S**, the pass's own frame, as before.

How a pass goes (`l_04298`): the logic, then `EnhWaitFlip` (`sub_0BCD0`) waits until the last S
has been taken and calls `SmoothMid`: the objects' animation is run there (`sub_0B1C2` without
its drawing: `EnhAnim`, `EnhAnimEnd`), every object and the camera moved half-way, M drawn with
the game's own routines (the background `sub_0B55C`, the BOBs `l_0B14E`, the flip `sub_0BC8C`),
everything moved back, and the positions kept for the next pass. Then the loop draws S as
before.

**Time.** A frame is taken at the split (the level 6 interrupt) and shown from the next frame.
With the last S taken at split t, M must be taken at split t+1 and S at t+2; S is never flipped
before frame t+2 begins (`SmoothPace`), which holds the game to 2 frames a pass whether M was
drawn or not. M has the rest of the frame after the logic, about 270 lines: `SmoothMid` measures
what M took and leaves it out when it would not fit in time - that pass shows S twice, as
before. Never slower. Also left out: the first pass in the display, and when the camera jumps;
an object that jumped or is new is drawn where it is.

**The panel** is drawn into, not redrawn: BOBs drawn there (the oxygen gauge, lives, the EXTEND
letters) go into both display buffers' panels, so it is the same in M and S.

**Faster drawing.** Profiled in the emulator (`nzsemu`'s `profile`), the drawing's time was the
CPU's more than the blitter's, and much of it was not drawing:
* the copy of the game's colours and sprite pointers into both copper lists at every vertical
  blank (`EnhVBL`), and into each list as it is built (`ScrCopper`), went entry by entry: the
  block's layout never changes, so it is now copied as 34 longs (15 lines a frame to 3);
* the ring line (`ScrAddr`, `ScrRingLeft`, `ScrCopper`) is found with 3 compares instead of a
  division, and its offset from a table;
* `BlitBob` is called for every object with a frame, most of them far off the screen, only to
  clip them away (its fields set for the logic's collisions on the way). M (`SmoothObjects`) no
  longer passes objects more than 256 pixels off the screen to it: S, drawn next, sets their
  fields for the logic as the game does.

**Performance** (`tools/test_smooth.py`, every level for 240 passes):

| The emulator | In-between frames drawn | Frames for 240 passes (50 Hz / 25 Hz, all levels) |
|---|---|---|
| the CPU timed (before the faster drawing) | 99.0 % | 10,501 / 10,474 |
| the CPU and the blitter timed (`--blittime`), before | 96.4 % (83 % on level 2-1) | 10,527 / 10,501 |
| the CPU and the blitter timed, now | **99.0 %** (93 % at worst, level 1-2; all of them on 12 levels) | 10,524 / 10,501 |

The emulator does not count the bitplanes' share of chip memory, which slows an A500's blitter
during the display a little more: WinUAE will tell.

**Tested** (`tools/test_scroller.py`): every S frame pixel for pixel the same as the original's
frame for that pass, on all 20 levels (709 compared). M frames (`tools/test_smooth.py`, levels 1
and 4, every frame for 120 passes): 6,367 positions of objects on the screen half-way between
the S frames either side, 41 not - an object turning, whose new frame has its own offset.

## BOBs in one blit (`src/frames.s`)

The original draws a BOB with 4 cookie-cut blits, one a plane, from a frame stored as its mask
and its 4 planes one after another (`DeinterleaveBobs`), and the scroller drew them the same
way into its interleaved buffers (each line the 4 planes' rows), waiting for each blit before
starting the next. Profiled with the blitter timed, drawing the BOBs was about 27 % of the CPU's
time in play, and the waits for the 4 blits and their setting up 8-15 %.

The buffers being interleaved, a BOB can be **one blit** if its frame is stored the same way.
The mask must be repeated for each plane's row (the A channel's modulo cannot read a row 4
times), so a frame in one-blit form is:

* the mask block: for each line, the mask's row 4 times;
* the plane block: for each line, the rows of planes 0, 1, 2 and 3.

8 rows a line against the original's 5: 1.6 times the memory. Both blocks keep the frame's
rows as stored, so a clipped BOB reads them with BlitBob's own modulo and offsets times 4
(`ScrBob`: a part of L lines is one blit of 4L rows, the screen's modulo the planes' distance).
The CPU goes on to the next object while the blitter draws. In the game's own display (the
title, the story; planes `$2000` apart) the same frames are drawn with 4 blits reading every
4th row (`OneBob4`).

**The mirrored frames** (an object facing left) are made in the same form, mirrored as they are
copied, so the original's mirrored copies (`sub_0C52C`: 94 KB at each new game) are never built.
Their directory entries are made as the original makes them but point at the unmirrored frame,
which has the same size, so BlitBob clips with it. The frames of the other banks (the boss's,
the ending's, the story's) are drawn as the original draws them, and so is the oxygen gauge's:
the game writes the oxygen level into that frame's mask every pass (`sub_052C4`), so a copy of
it would not change.

**Where they are** depends on the machine (`OneInit`):

* **More than 512K of chip RAM, with room for them all** (`ONE_ALL`, 296 KB; A500+, A600,
  A1200): all built once, at the first new game (about 0.7 seconds), from `$80000`. The track
  cache gets the chip RAM after them, if that is the largest memory (a 1MB machine: 216 KB of
  the 445 KB of level files).
* **512K:** a cache from `$4A3A6` (where the original built its mirrored copies) to block 3,
  81 KB. It is a ring: a frame goes at the next free place and the oldest frames in its way are
  dropped (no search, nothing to fragment). As a level starts (`EnhLevelStart`, at `$41FE`) the
  cache is emptied and filled with the frames that level is known to draw (`OneWarm`), the most
  drawn first, as many as fit in 85 % of it (`build_disk.py`, from `tools/frame_counts.json`:
  4 plays of 400 passes a level in the emulator, and the frames seen in
  `../original/assets/levels/observed.json`). A frame drawn and not in the cache is built there
  and then (`OneMiss`). Nothing is built there before the first game starts: the program's
  own tail at `$4A3A6` holds the intro's mirrored frames (the walrus carrying off the kiwis),
  which the original leaves alone until then, so the title draws its frames as the original
  does.

**Building a frame** (`OneCopy`): the blitter lays it out, 8 blits (A to D): the mask 4 times,
each to every 4th row of the mask block, then each plane to every 4th row of the plane block.
A mirrored frame is first mirrored by the CPU into a buffer below `$611B0` (`MirCopy`, as the
original's `sub_0C52C`: its bytes in the reverse order, each byte's bits reversed by a table),
then laid out from there: about 3.5 ms for a typical frame on a 68000, against a fraction of a
millisecond for one that is not mirrored. (Done by the CPU alone, with rows of 2 to 8 bytes,
the call for each row cost more than the copying: all of them took 1.6 seconds.)

**Block 3.** Block 1 had no room for this (about 240 bytes were free). The new code and its
tables are block 3: assembled to run at `$5E800` (in the memory the original's mirrored copies
took, which nothing else uses; the buffer for mirroring above it, to `$611B0`), stored after
block 2, and copied there by `Relocate`
when the game starts (in 26 bytes of padding there). The program is unpacked in place when it
loads (`ext.s`: `Unpack`), and the end of a packed stream that compresses badly would overwrite
its own unread bytes, so block 3 ends with its zero tables (`OneTab`, `OneQueue`), and
`build_disk.py` runs `Unpack` step by step on the packed program and stops if it would not
give the program back. Block 1 has 1.5 KB free again (the old `mirror.s` moved out).

**Performance** (`tools/test_frames.py`, every level for 240 passes, the blitter timed):

| | In-between frames drawn (50 Hz) | Frames built in play |
|---|---|---|
| before (4 blits a BOB; `main`) | 99.0 % (48 of 4,775 left out) | - |
| one blit, 1MB of chip RAM (all built once) | **99.7 %** (12 left out) | - |
| one blit, 512K, the cache filled as each level starts | **99.7 %** | 9 in all (at most 1 in a pass) |
| one blit, 512K, the cache cold (the worst case) | 99.7 % | 515 (244 KB) |

**Tested** (`tools/test_scroller.py`): pixel for pixel the same display as the original's on
all 20 levels at 512K, and with 1MB of chip RAM; the title and the game's own display the same
as before. `tools/test_boot.py`: the file cache after the frames on a 1MB machine.

## The title menu and two-button joysticks (`src/menu.s`)

The title keeps its text, the kiwi and the credits; under the kiwi, between his feet and the
credits, where the original has nothing, a menu (4 lines, 9 apart):

| Page | Items |
|---|---|
| title | `START GAME`, `OPTIONS` |
| options | `INPUT: JUMP ON UP` / `JUMP ON BUTTON 2` / `JUMP 1 FIRE 2`, `CHEAT: OFF` / `ON`, `SOUND TEST`, `EXIT`; above the kiwi, the machine's memory lines (*The machine's memory*) |
| sound test | `MUSIC: 01`-`12`, `EFFECT: 01 KIWI JUMP`-`12 EXPLOSION`, `MUSIC OFF`, `EXIT` |

Up and down move (round), fire chooses; on `INPUT` and `CHEAT` left, right and fire change the
setting. The chosen item shows as `> ... <` in white. `EnhTitleWait` takes the place of the
title's wait (`sub_0B9F0`, from `$406C`): it keeps the original's time-out to the attract
sequence (not on the options page) and the typed cheat code; `START GAME` starts the game as the
original's fire did. The menu reads the joystick from the hardware, so it works the same
whatever the input setting.

**The input setting** (`JoyMode`) changes what `ReadJoystick` gives the game (`EnhJoy`): the
second button is port 2's pin 9 (`POTINP` bit 14, low when pressed; `POTGO` `$FF00`).
* `JUMP ON UP`: the original's controls (the default).
* `JUMP ON BUTTON 2`: button 2 is up - it jumps, and swims up; the stick's up does nothing.
* `JUMP 1 FIRE 2`: button 1 jumps, button 2 fires.

**The sound test**: on `MUSIC` and `EFFECT` left and right choose the tune (the driver's 12,
`PlaySong`) or the effect (the 12 IFF 8SVX effects, `PlaySample`; names from their files,
`../original/docs/SOUND.md`) and fire plays it; `MUSIC OFF` stops the tune (`StopSong` with
d0 = 0: every voice), and so does `EXIT`. No time-out on this page either.

**The cheat** setting is the original's own (*The cheat*, below): on, 1,000 lives, tune 10;
off, 3. Typing the code on either page turns it on as well. The settings last until the machine
is reset.

To make room in block 1, the 50 Hz buffers moved to the scroller's free memory after its
restore lists (`$7FB80`).

**Tested** (`tools/test_menu.py`, 34 cases, the sound test's included: the numbers going round,
the tune playing (`Music_Voices`) and stopping, the effect on channel 3): starting a game, moving round, each setting and
`EXIT`, the title's time-out and none on the options page, the typed code on both pages, and in
play each input setting with up, button 1 and button 2 (what the game reads at `$63DB0`).
`nzsemu`'s `joy 2` holds the second button.

## The cheat

The original's cheat - `MOTHERFUCKENKIWIBASTARD` typed on the title screen - starts the game
with 1,000 lives, and in play the HELP key skips to the next level - in the enhanced game **F2**
does instead (pressed, not held: one level a press), and HELP does nothing. The original also has a fly
mode for it that nothing calls (`sub_0900A`): the enhanced game calls it at the end of each pass
of the game loop (`EnhCheatKeys`, at `$43C0`, where the original tests HELP). With the cheat on,
**F1** makes the kiwi fly: he moves 4 pixels a step with the joystick, in any direction, through
the scenery (`sub_08FD4` takes his handler's place, kept at `$5C(a6)`); F1 again lands him (his
handler back: in the air he falls). He is not invulnerable while flying: an enemy still kills
him (1,000 lives...).

**Tested** (`tools/test_menu.py`): with the cheat F2 goes to the next level, HELP does not;
without it F2 does nothing. (`tools/test_fly.py`): with the cheat, F1 then up flies him up through the scenery
and F1 again gives his handler back; without it F1 does nothing. (In WinUAE: type the code on
the title, start, press F1.)

## The game's disk reading (`src/diskload.s`)

The original game reads its level data from the disk at the start of each level (5 tracks of
packed world data and 1 more, 2 more on some levels) and at the end of the game, by **track
number** through the jump table's `TrackRead` (`../original/disk/DISKMAP.md`): whole tracks, of
which a load uses part - the world data's packed stream fills 12-27 KB of its 28 KB, a map
1-4 KB of its 5.5 KB, and the rest is what happened to be on the disk (some loads even overlap:
levels 4-7's maps are in level 4's world data tracks). `diskload.s` takes the place of the
original's `TrackWrite` and `TrackRead`.

**The level files** (`build_disk.py`: `level_files`). Each distinct load the game makes (40 of
them, from `original/tools/disk/game_tracks.py`) is a file on this disk with just the bytes the
game uses:
* a level's world data: its packed stream - the length in its header - and the 8 bytes after
  it, which `UnpackLevel` moves with it;
* a level's map: its 128-byte header and its rows of 64 tiles;
* a boss's frames and the ending: the tracks without their trailing zeros.

445 KB against the tracks' 528 KB. `build/loadtable.i` (`LoadTable`) lists for each file the
first track and count the game asks for, its offset on the disk and its length.

* `TrackRead`: same arguments and results (d0 = track, d1 = count, a0 = where; d0 = 0 if read,
  -1 if not). The load is looked up in `LoadTable` (-1 for one the disk has no file for), taken
  from the file cache if it is there (`FileGet`), otherwise read with the byteloader from the
  drive booted from, through the MFM buffer at `$68000` where the original read its tracks, and
  offered to the cache (`FilePut`); the rest of the tracks asked for is filled with zeros. All
  registers are kept; the byteloader leaves the interrupts, CIA timers, blitter and copper
  alone, so the music and display go on while a level loads;
* `TrackWrite` returns -1: only the built-in debug monitor's `W` command used it.

**Tested.** The boss frames and the ending come back exactly as the original's (their tails were
zeros). For the world data and maps, the bytes after them were what the disk had: to check that
the game never reads them, `build_disk.py --poison N` fills them with N in the emulator's copies
of the loads (`build/loads/`, from which `original/tools/nzsemu` now answers a load - the tests
play the enhanced game with what it really loads), and `nzsemu`'s new `readwatch` logged no
read of them on any of the 20 levels in 240 passes each; `tools/test_scroller.py` with `$A5`
there: every frame the same as the original's, and the two games in step as long as with zeros.
`tools/test_boot.py`: the eight loads through the real `TrackRead` and the byteloader, each its
file and zeros, and from the cache the second time, on every memory configuration.

## The source

`src/nzs_game.s` was made from `original/nzs_main.s` (`tools/fork_source.py`) and is edited by
hand. The original's block 1 held a debug monitor (commands, a 68000 disassembler, its own
screen output: about 9 KB) that the game never uses - the start-up and every exception go
straight to `GameStart` - so it was removed, and the enhanced code (`enhanced.s`, which includes
`scroller.s`, `smooth.s` and `menu.s`) is in its place, block 1 padded to keep its size (about
1.5 KB is still free). Block 3 (`frames.s`) is stored after block 2 and copied to `$5F000` as
the game starts (*BOBs in one blit*).

Block 2 (`$3214` on) keeps every byte where the original has it: much of it is reached at fixed
addresses (self-modifying code writes into instructions by address, tables are built beyond the
program's end), so the routines the enhanced code takes over get a `jmp` over their first
instructions and nothing moves. `build_disk.py` compares the address of every label of block 2
on with the original's (1,495 of them) and stops if one has moved.

## Next

Improvements go here, each on its own branch, built and tested in WinUAE before merging. The
list is in [`TODO.md`](TODO.md).
