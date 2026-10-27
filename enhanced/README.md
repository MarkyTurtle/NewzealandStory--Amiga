# The New Zealand Story on an ordinary AmigaDOS disk

> The game rebuilt from the disassembly in [`../original`](../original) onto a standard
> AmigaDOS-format disk that boots with the
> [4489_byteloader](https://github.com/MarkyTurtle/4489_byteloader) instead of Rob Northen's
> Copylock-protected boot chain, with improvements: a scroller that updates only what moves (a
> corkscrew with a vertical ring, double-buffered, with a pristine buffer), and the machine's
> memory used for a track cache, on a 512K machine 43 KB of chip RAM freed by mirroring sprite frames
on demand, and 50 frames a second in play. Nothing on it is copy-protected: any emulator or real drive
> reads it, and it can be written to a real floppy with any ADF tool.

```
python3 enhanced/tools/build_disk.py      # -> enhanced/build/nzs.adf
python3 enhanced/tools/test_boot.py       # boots it in an emulator and checks it
python3 enhanced/tools/test_scroller.py   # the display against the original's, frame by frame
python3 enhanced/tools/test_mirror.py     # what the mirror cache costs in play
python3 enhanced/tools/test_smooth.py --blittime   # how much of the game runs at 50 Hz
```

(`../BUILDING.md` has what to install.) Tested in FS-UAE as an A500 with FS-UAE's built-in AROS
Kickstart replacement: it boots to the loading screen, then the attract sequence, and the game
plays, loading its level data from the disk. Tested in WinUAE: the scroller, the mirror cache
and 50 frames a second in play, the progress screens and the return to the title. Still to be
tried: real hardware.

| File | What it is |
|---|---|
| `src/nzs_game.s` | **The game's source**, edited by hand since October 2026 (made from `original/nzs_main.s` by `tools/fork_source.py`): the original's, with the debug monitor removed and jumps put over the start of the routines the enhanced code takes over (each marked `enhanced:`) |
| `src/enhanced.s` | The enhanced game's own code, in block 1 where the monitor was: the track cache, the title's memory lines, the entries for the routines taken over |
| `src/scroller.s` | The scroller (below) |
| `src/smooth.s` | 50 frames a second: the in-between frame drawn each pass (below) |
| `src/mirror.s` | The mirrored BOB frames: all built at start-up, or on a 512K machine built on demand into a cache (below) |
| `src/diskload.s` | The game's disk reading on this disk, in place of the original's `TrackWrite` / `TrackRead`, with the track cache in front of the disk |
| `src/boot_4489.s` | The bootblock: surveys the machine's memory, finds the boot drive, loads the extension module and goes on in it |
| `src/ext.s`, `src/ext.i` | The extension module: the part of the boot the bootblock has no room for (loading screen, program, the machine description handed to the game) |
| `src/byteloader.i` | The 4489_byteloader, as published (used by both) |
| `tools/build_disk.py` | Builds the disk; checks that every label of block 2 on is where the original has it |
| `tools/test_boot.py` | Boots the disk in an emulator (Unicorn) from Kickstart's call to the game's start, on four memory configurations, then calls the game's `TrackRead` as the game does, twice (the second time from the cache when it fits) |
| `tools/test_scroller.py` | Runs the original and the enhanced game side by side in `original/tools/nzsemu` and compares their displays pixel for pixel (`original/tools/display.py`); `--chip` for the machine's chip RAM |
| `tools/test_fly.py` | The cheat's fly mode on F1, with and without the cheat |
| `tools/test_smooth.py` | Plays every level at 50 Hz and at 25 Hz: how many in-between frames are drawn, and that the game keeps its speed; `--blittime` makes the emulator's CPU wait for the blitter as an A500's does |
| `tools/test_mirror.py` | Plays every level with the mirror cache, with it cold, and with all frames mirrored at start-up, and compares the frames built in play and where each pass's drawing ends |
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
| `$04800` | 540,672 | file 2: the 96 tracks of the original disk the game reads while it runs (level data), one after another |
| `$88800` | 432 | file 3: the extension module (`src/ext.s`), loaded to `$65400` |
| after it | about 275 KB | file 0: the game, packed in the original's format |
| | about 64 KB | free |

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

5. keeps the machine description in its header;
6. shows the loading screen as the track 90 loader did: black, 4 planes at `$78000` (`$2000`
   apart), `BPLCON0 $4200`, `DDFSTRT $38`, `DDFSTOP $D0`, `DIWSTRT $3C81`, `DIWSTOP $04C1`, the
   same copper list; the file loaded to `$70000` and decoded there, its colours doubled;
7. loads the game to `$400` and unpacks it in place, as the track 90 loader's `Unpack`; writes
   the machine description and the boot drive into the game's header (`EnhHeader`, `$426`);
8. enters the game at `$400` with `d0 = a0 = $400`, as the track 90 loader did. The game's
   start-up (`Init`) sets up the track cache and the title's memory lines (`EnhInit`).

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

for the **track cache** (`CacheGet` / `CachePut` in `enhanced.s`, called by `TrackRead`): every track the
game reads from the disk is kept there while there is room, first come, first served, and read
from memory the next time. A level played again (after a game over, the next game) reads nothing
from the disk; the levels that share their graphics tracks (4-7, 12-14) read only their map. 512K
holds 93 of the 96 tracks; with more, all of them. With no memory beyond 512K of chip RAM, the
game reads every level from the disk as the original did.

The **title screen** shows the machine and what the game makes of it, under the kiwi:

```
CHIP 512K  SLOW 512K  FAST 0K
TRACK CACHE 93 OF 96 IN SLOW RAM
```

(`NO TRACK CACHE` on a plain 512K machine). The game's title text call (`$404C`) calls
`EnhTitleText`, which prints the original's text and then these two lines with the game's own
printer (`sub_0C6A8`).

**Where the module lives.** `$65400`, in 11 KB between the game's object slots (which end at
`$65396`) and its disk / deinterleave buffer at `$68000`, which the original never uses:
`original/nzs_main.s` has no absolute reference into it, and in `original/tools/nzsemu` nothing
writes to it over 12 games and all 20 levels started in turn. It is needed only while booting;
the scroller's buffers start there.

**One program for every machine**, as decided for Ghosts'n Goblins: the same disk on every
Amiga, scaling up at run time. Next uses of the memory (`TODO.md`): pre-masked interleaved BOBs
in chip RAM above 512K, and moving the program itself into slow / fast RAM to free chip RAM on
an expanded A500.

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

**Performance** (`tools/test_smooth.py`, every level for 240 passes):

| The emulator | In-between frames drawn | Frames for 240 passes (50 Hz / 25 Hz, all levels) |
|---|---|---|
| the CPU timed | 99.0 % | 10,501 / 10,474 |
| the CPU and the blitter timed (`--blittime`) | 96.4 % (83 % on the busiest level, 2-1; all of them on 8 levels) | 10,527 / 10,501 |

The emulator does not count the bitplanes' share of chip memory, which slows an A500's blitter
during the display a little more: WinUAE will tell.

**Tested** (`tools/test_scroller.py`): every S frame pixel for pixel the same as the original's
frame for that pass, on all 20 levels (709 compared). M frames (`tools/test_smooth.py`, levels 1
and 4, every frame for 120 passes): 16,522 object positions half-way between the S frames
either side, 44 not - an object turning, whose new frame has its own offset.

## The mirrored frames (`src/mirror.s`)

An object facing left is drawn from a mirrored copy of its frame. The original builds a copy of
all 289 frames of the main BOB bank at the start of each game (`sub_0C52C`): 94 KB of chip RAM
from `$4A3A6`, and about half a second of the CPU. A level draws at most about 40 KB of them
(`../original/docs/LEVELS.md`, *The frames each level can show*), and since nearly every object
can turn round, no frame can be ruled out.

* **More than 512K of chip RAM:** as the original: all built at start-up.
* **512K:** a 48 KB cache from `$4A3A6`; `$563A6-$611B0` (43 KB) is free in play (the ending
  works in this memory, as it did over the original's copies; each new game starts the cache
  afresh).
  * At start-up the mirrored frames' directory entries are made as the original makes them,
    but each points at its unmirrored frame (the same size, so BlitBob clips with it as before).
  * When BlitBob has clipped a BOB and is about to draw it (`EnhBobFrame`, at `$B7CC`), a
    mirrored frame not built yet is built into the cache and its entry pointed at it. A frame
    that never comes on screen is never built.
  * The cache is a ring: a frame goes at the next free place, and the oldest frames there are
    dropped (their entries pointed back at their unmirrored frames). No search, no
    fragmentation; a hit costs one compare in BlitBob.
  * **Built ahead:** as a level starts, after its tracks are loaded (`EnhLevelStart`, at
    `$41FE`), the cache is emptied and the frames that level was seen to draw mirrored built at
    once (`MirWarm`, made by `build_disk.py` from `../original/assets/levels/observed.json`):
    up to about 40 KB, about a tenth of a second while the level appears.
  * Built by `MirCopy`, unrolled for the frame's width: about 26 cycles a byte against the
    original's 36 (on a 68000, 4 ms for a typical 964-byte frame, 10 ms for the largest).

**Performance** (`tools/test_mirror.py`, every level for 240 passes in the emulator, which
counts the CPU's time but not the blitter's):

| | Frames built in play | Most in one pass | Latest end of a pass's drawing (of 624 lines) | Passes over 2 frames |
|---|---|---|---|---|
| All built at start-up | - | - | 616 | 0 |
| The cache, built ahead | **0** | 0 | 618 (at most 2 lines later on any level) | 0 |
| The cache, nothing built ahead (the worst case) | 261 (86 KB) | 1,684 bytes | 618 (at most 57 lines later) | 0 |

So with the frames built ahead the cache costs nothing in play: every frame the plays needed
was already built. With nothing built ahead, a pass that needs a new frame takes up to 57 lines
(3.6 ms) longer. That is what a frame missing from the list would cost, once.

**Tested** (`tools/test_scroller.py`, with and without `--chip 0x100000`): pixel for pixel the
same display as the original's, on all 20 levels, with the cache and without.

## The cheat

The original's cheat - `MOTHERFUCKENKIWIBASTARD` typed on the title screen - starts the game
with 1,000 lives, and in play the HELP key skips to the next level. The original also has a fly
mode for it that nothing calls (`sub_0900A`): the enhanced game calls it at the end of each pass
of the game loop (`EnhCheatKeys`, at `$43C0`, where the original tests HELP). With the cheat on,
**F1** makes the kiwi fly: he moves 4 pixels a step with the joystick, in any direction, through
the scenery (`sub_08FD4` takes his handler's place, kept at `$5C(a6)`); F1 again lands him (his
handler back: in the air he falls). He is not invulnerable while flying: an enemy still kills
him (1,000 lives...).

**Tested** (`tools/test_fly.py`): with the cheat, F1 then up flies him up through the scenery
and F1 again gives his handler back; without it F1 does nothing. (In WinUAE: type the code on
the title, start, press F1.)

## The game's disk reading (`src/diskload.s`)

The original game reads its level data from the disk at the start of each level (5 tracks of
packed data and 1 more, 2 more on some levels) and at the end of the game, by **track number**
through the jump table's `TrackRead` (`../original/disk/DISKMAP.md`). `diskload.s` takes the
place of the original's `TrackWrite` and `TrackRead`:

* `TrackRead`: same arguments and results (d0 = track, d1 = count, a0 = where; d0 = 0 if read,
  -1 if not). Each original track is looked up in `TrackMap` - its place among the tracks
  stored on this disk (`build/trackmap.i`, written by `build_disk.py`) - then taken from the
  track cache if it is there (`CacheGet`), otherwise read with the byteloader from the drive
  booted from, into the MFM buffer at `$68000` where the original read its tracks, and offered
  to the cache (`CachePut`). All registers are kept; the byteloader leaves the interrupts,
  CIA timers, blitter and copper alone, so the music and display go on while a level loads;
* `TrackWrite` returns -1: only the built-in debug monitor's `W` command used it.

## The source

`src/nzs_game.s` was made from `original/nzs_main.s` (`tools/fork_source.py`) and is edited by
hand. The original's block 1 held a debug monitor (commands, a 68000 disassembler, its own
screen output: about 9 KB) that the game never uses - the start-up and every exception go
straight to `GameStart` - so it was removed, and the enhanced code (`enhanced.s`, which includes
`scroller.s` and `mirror.s`) is in its place, block 1 padded to keep its size (about 3 KB is
still free).

Block 2 (`$3214` on) keeps every byte where the original has it: much of it is reached at fixed
addresses (self-modifying code writes into instructions by address, tables are built beyond the
program's end), so the routines the enhanced code takes over get a `jmp` over their first
instructions and nothing moves. `build_disk.py` compares the address of every label of block 2
on with the original's (1,495 of them) and stops if one has moved.

## Next

Improvements go here, each on its own branch, built and tested in WinUAE before merging. The
list is in [`TODO.md`](TODO.md).
