# The levels

The 20 levels (5 worlds of 4), their data, and the objects each one places. Extracted by
`tools/levels/levels.py` (part of `tools/assets/make_assets.sh`) into
[`../assets/levels`](../assets/levels):

| | |
|---|---|
| `levelNN.png` | the whole map, each object the level places drawn where it starts (its type's first frame), a yellow box and its type number; the kiwi's start is type 0 |
| `levelNN_map.png` | the map alone |
| `types.png` | each object type's first frame, numbered |
| `levels.json` | every level decoded (below) and the object types table |
| `observed.json` | the frames each level drew when played in the emulator (`tools/levels/observe.py`) |
| `frames.json` | the frames each level needs, and their size (`tools/levels/frames.py`) |

![Level 2-1, the top left quarter](../assets/levels/level04.png)

## The level table

`LevelTable` (`$5DBA`): 20 entries of 16 bytes, indexed by `$8(a6)` (level × 16).

| Offset | |
|---|---|
| +0 long | the tile attributes: a word for each tile number, `$AAAA` ends. `sub_0C5C0` builds the collision map at `$462A6` from this and the map |
| +4 long | the object list (below), read by `sub_05AD4` |
| +8 long | not yet known (a pointer into `$C98A-$CFF2`) |
| +C word | the first of the 5 tracks of the world's data |
| +E word | the track of the map |

### The world data

5 tracks, packed in the same format as the main program (`../tools/disk/pack.py`) and unpacked
in place at `$3CAA6`:

| Offset | |
|---|---|
| +0 | `01` |
| +2 | 16 colours, each stored as half its value (as every palette in the game) |
| +$80 | the 16×16 tiles, 128 bytes each: 16 lines, each line the 4 planes' words in turn |

Levels in the same world share these tracks: levels 4-7 all use tracks 22-26 and levels 12-14
use 52-56. The game reads them again at each level all the same (`LoadedLevel` only skips the
load when the same level restarts).

### The map

1 track, loaded at `$44AA6`:

| Offset | |
|---|---|
| +0 | `01` |
| +2 word | width in tiles |
| +4 word | height in tiles |
| +$E, +$10 | not yet known |
| +$80 | the rows, 64 bytes each (one byte a tile), **the top row last**: row R (from the top) is at +$80 + (height − 1 − R) × 64 |

`sub_0C5C0` sets the camera's limits from it: x up to width × 16 − `$130`, y up to
(height − 11) × 16; `$C(a6)` = (height − 1) × 64. Level 15 (4-4) is forced to 32 columns.

### The object list

| | |
|---|---|
| word | the level's time (at least `$28`; to `(a6)`, counted down by the CIA-B timer) |
| byte | not yet known |
| 2 bytes | the kiwi's start, x and y in tiles (placed at x × 16 + 4, y × 16) |
| byte | not yet known |
| 4 bytes each | the objects: type, x, y (tiles, as the kiwi), parameter. A negative type ends the list |

The parameter: `$FF` none. For type 3, a path number (the table `dat_05C0A`). For the others,
bit 7 moves the object 8 pixels right and bits 0-6 × 2 is where in its animation script it
starts (`$22`).

## The levels

| Level | | Size (tiles) | World tracks | Map track | Time | Objects | Types placed | Frames drawn (+ mirrored) | Their size |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 1-1 | 64×14 | 2-6 | 18 | 80 | 12 | 1, 4, 5, 6 | 57 + 61 | 44.6 KB |
| 1 | 1-2 | 64×32 | 6-10 | 19 | 100 | 22 | 1, 3, 4, 5, 6, 7, 14, 18, 32, 33 | 121 + 100 | 74.6 KB |
| 2 | 1-3 | 64×32 | 11-15 | 20 | 240 | 19 | 1, 3, 4, 14, 25, 32 | 131 + 99 | 76.5 KB |
| 3 | 1-4 | 64×64 | 14-18 | 21 | 280 | 34 | 2, 3, 4, 5, 6, 7, 11, 14, 24, 32 | 154 + 129 | 76.2 KB |
| 4 | 2-1 | 64×64 | 22-26 | 25 | 440 | 41 | 1, 3, 5, 7, 10, 14, 17, 21, 29, 30, 31, 32, 41, 44 | 178 + 115 | 92.7 KB |
| 5 | 2-2 | 64×64 | 22-26 | 26 | 440 | 43 | 1, 3, 4, 5, 6, 24, 31, 32 | 176 + 123 | 96.0 KB |
| 6 | 2-3 | 64×64 | 22-26 | 27 | 440 | 34 | 1, 3, 4, 5, 24, 31, 32, 44 | 98 + 59 | 53.9 KB |
| 7 | 2-4 | 64×64 | 22-26 | 28 | 440 | 35 | 2, 3, 24, 27, 28, 29, 30, 31 | 155 + 93 | 77.0 KB |
| 8 | 3-1 | 64×64 | 29-33 | 48 | 240 | 35 | 1, 3, 9, 10, 11, 14, 17, 31 | 157 + 99 | 82.3 KB |
| 9 | 3-2 | 64×64 | 34-38 | 49 | 240 | 27 | 1, 3, 23, 24, 32 | 102 + 71 | 64.9 KB |
| 10 | 3-3 | 64×64 | 39-43 | 50 | 240 | 31 | 1, 3, 25, 32, 43, 45 | 129 + 102 | 76.4 KB |
| 11 | 3-4 | 64×64 | 44-48 | 51 | 360 | 33 | 2, 3, 10, 11, 14, 17, 18, 24, 26, 32 | 157 + 116 | 82.6 KB |
| 12 | 4-1 | 64×64 | 52-56 | 56 | 360 | 33 | 1, 3, 14, 24, 25, 26, 32 | 125 + 95 | 77.4 KB |
| 13 | 4-2 | 64×64 | 52-56 | 57 | 360 | 16 | 1, 3, 24, 25, 26 | 104 + 83 | 66.7 KB |
| 14 | 4-3 | 64×64 | 52-56 | 58 | 360 | 22 | 1, 3, 21, 24, 26, 32 | 153 + 100 | 80.4 KB |
| 15 | 4-4 | 32×48 | 59-63 | 68 | 480 | 21 | 2, 3, 5, 6, 14, 21 | 72 + 45 | 40.5 KB |
| 16 | 5-1 | 64×64 | 70-74 | 79 | 480 | 25 | 1, 3, 14 | 144 + 91 | 79.2 KB |
| 17 | 5-2 | 64×64 | 74-78 | 80 | 480 | 26 | 1, 3, 14, 21 | 84 + 64 | 58.0 KB |
| 18 | 5-3 | 64×64 | 81-85 | 88 | 480 | 21 | 1, 3 | 111 + 84 | 68.3 KB |
| 19 | 5-4 | 64×64 | 84-88 | 89 | 800 | 19 | 2, 3, 14 | 104 + 64 | 52.9 KB |

Some levels' world tracks overlap the next level's (2 and 3, 16 and 17, 18 and 19): the packed
data is shorter than 5 tracks, and the loader always reads 5.

## Object types

`dat_05854`: 46 types (0-45) of 12 bytes. Objects made from it (`sub_057D8`, `sub_057E8`) keep
their type at `$1C`.

| Offset | |
|---|---|
| +0 long | the handler (the object's `$18`), called each pass |
| +4 long | the animation script (`$14`) |
| +8 word | the frames between script steps |
| +A word | a linked type, created with it (0: none) |

![The object types](../assets/levels/types.png)

What is clear so far (the names of the rest are still to be worked out from their handlers):
* 0: the kiwi. 1, 2: the caged kiwi (2 on the 4th level of each world).
* 3: the object that follows a path (`dat_05C0A`); placed on almost every level.
* 10-20 and 22 each have a linked type from 33-42: the enemy and what it rides (the balloons,
  the duck, ...), created together.

The objects the game draws that are not in the table: 47 and 48 (made by code), and the
panel and effects drawn without an object (`$FFFE`, `$FFFF` in `observed.json`).

### Animation scripts

A script is a list of words. A positive word is a frame number + 1 (0: no frame this step).
A negative word is a command, `$8000 | n`:

| n | | Arguments |
|---|---|---|
| `$00` | start the script again | |
| `$04`, `$08` | set dx, dy | word |
| `$0C`, `$10` | add to x, y | word |
| `$14`, `$18` | set x, y | word |
| `$1C` | go to | long |
| `$20` | loop count (negative: a random count) | word |
| `$24` | loop | |
| `$28` | the frames between steps | word |
| `$2C`, `$30`, `$34`, `$38` | compare x / y, and go to a script if so | word, long |
| `$3C` | end the object | |
| `$40` | mirror (toggle `$10`) | |
| `$44` | set a field | offset word, value word |
| `$48` | clear the speed | |
| `$4C` | call code | long |

## The frames each level needs

The main BOB bank holds 289 frames (93,706 bytes). At start-up `sub_0C52C` builds a mirrored
copy of every one of them (`$4A3A6` on, about the same size again, over the intro's picture):
a mirrored frame is drawn as frame + `$122`. So about 187 KB of chip RAM holds BOB graphics on
every level.

`tools/levels/frames.py` estimates what each level really uses, from two sources:
* **Static:** the animation scripts of the types the level places, and of their linked types,
  walked with every jump and conditional followed. This misses the frames chosen in code: the
  kiwi's (30 frames, his script has 3), weapons, items, effects.
* **Observed:** `tools/levels/observe.py` plays each level in `tools/nzsemu` (99 lives, a random
  joystick, the kiwi moved to each placed object in turn so that all of them come on screen)
  and logs every call of `BlitBob` with the frame, the object's type and its mirror flag.
  Two plays a level so far: a lower bound for what a play-through can reach.

The union (table above, and `frames.json`):

| | Frames | Bytes |
|---|---|---|
| The main bank | 289 | 93,706 |
| Its mirrored copies | 289 | 93,706 |
| Used on any level | 258 | 79,564 |
| Used mirrored on any level | 224 | 64,912 |
| The most any level uses (5, 2-2) | 176 + 123 mirrored | 98,348 |
| The most any world uses (levels 4-7) | 208 + 160 mirrored | 114,438 |

So:
* Mirroring only the frames that are ever drawn mirrored saves about **28 KB** for the whole
  game, with no change to loading.
* Holding only the current world's frames (normal and mirrored) would need at most 112 KB
  against 183 KB: about **71 KB** freed, but the frames have to come from disk with the world
  (a file per world).
* Per level, at most 96 KB: about **87 KB** freed.

The observed sets are a lower bound, so a per-world bank would need a margin, or a fallback: a
frame missing from the bank built (mirrored on the fly) into a small cache, as the enhanced
Ghosts'n Goblins does.

No frame of the per-level extra bank (`$6C000`, frames from 289) was drawn in these plays:
which levels load it and what it holds is still to be worked out.

## Still to do

* The level table's +8, the object list's two unknown bytes, the map header's +$E and +$10.
* The extra BOB tracks: which levels, and which frames.
* The object types' names, from their handlers.
* More plays for `observed.json`, until the sets stop growing.
