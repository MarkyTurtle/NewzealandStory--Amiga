# The code

Every routine in the sources has a header box above its label saying what it does, what it takes
and gives, and - in capitals - what self-modifying code it does or suffers (`SELFMOD.md`). Code
that the disassembly did not trace (kept as `dc.b`) is described in the header of the routine
before it. This page is the map: where things are, and the two structures most of the code
works on. Field names below are the offsets the code uses.

## Where things are (`nzs_main.s`)

| Addresses | What |
|---|---|
| `$400-$320F` | **Block 1**, the system layer (stored 4 bytes higher; `Relocate` moves it): the jump table (`JT_*`), start-up, the disk's track reader and writer, the keyboard and joystick, the exception handlers, and the debug monitor with its 68000 disassembler (reached only from an exception or the break key) |
| `$3214-$3FFF` | `Relocate`, leftovers (`sub_03268`, `sub_0328C`, `sub_032F0`) and zeros |
| `$4000-$43FF` | `GameStart`: the title, the intro, a new game, each level, the game loop, the progress screen |
| `$4400-$5EF9` | high scores, the warp, the intro, the panel and score, the level complete and the ending, `LoadTracks`, `UnpackLevel`, the sound effects, making an object by its type and placing the level's objects |
| `$5EFA-$91D3` | the objects' handlers: generators, rides, enemies and their shots, fruit and items |
| `$91D4-$9E05` | the kiwi: on the ground, in the air, swimming, his weapons (riding: `sub_08E1E`); the collision map tests |
| `$9E06-$AEEB` | the bosses, the copy protection's check (`sub_0A742`), the caged kiwi and the level's end |
| `$AEEC-$B94F` | the camera, the objects' logic, animation and drawing (`sub_0B0E6`, `sub_0B1C2`, `BlitBob`), the playfield |
| `$B950-$E7FF` | blits, the joystick, the display and copper lists, interrupts, palettes, start-up, the mirrored frames, the map's set-up, the text printers |
| `$E800-$F33D` | the music driver (Jonathan Dunn's: `SOUND.md`) and its IFF 8SVX reader |
| `$F33E` on | data (`Music_Periods` on): instruments, samples, songs, the BOB banks, pictures, level buffers |

## The globals (`a6` = `$641B8`)

| Offset | |
|---|---|
| `(a6)` | the level's time (CIA-B timer B counts it down, about twice a second); also the title's and other waits |
| `$2` | bit 0: `BlitBob` draws on both screens (the panel) |
| `$4`, `$6` | the text cursor: column (or x), y |
| `$8` | the level x 16 (0-`$130`) |
| `$A`, `$10` | the camera's limits, y and x; `$C` the map's bottom row's offset; `$E` the map's width in pixels less 8 |
| `$12` | set by the vertical blank (the frame's flag) |
| `$13` | the EXTEND letters collected (a bit each) |
| `$14` | the panel's split line |
| `$16` | the palette in use |
| `$1A` | lives |
| `$20` | the back screen (`$70000` / `$78000`) |
| `$24` | a frame countdown (the vertical blank) |
| `$26` | level 4-4's second map |
| `$28`, `$2A` | which fruit and which bonus item come next |
| `$2C` | the level a new game can continue from |
| `$2E`, `$30` | the camera's x and y |
| `$36`, `$3A`, `$3C` | the fine horizontal scroll: added to the BOBs' x, the scroll value, for the copper list |
| `$38` | where the kiwi's jump started |
| `$46` | a boss fight (the camera locked: `$42`, `$4E`, `$50`) |
| `$48` | arrows ended on something solid |
| `$4A` | the kiwi rides type 41 |
| `$52` | the kiwi is dying |
| `$54`, `$56` | the grace time after a restart, and its flashing |
| `$58`, `$5A` | the camera's direction |
| `$5C` | the kiwi's handler, kept while he flies (the cheat) |
| `$60` | the kiwi's shots on screen |
| `$62` | the kiwi stands on a platform |
| `$64` | the screen shake (the bomb); `$6C` its copy: every enemy counts as shot |
| `$66`, `$68`, `$6A` | items: the fast ride, the clock (enemies frozen), invincibility |
| `$6E` | oxygen (0-`$136`) |
| `$70` | the time-up enemy's state |
| `$72` | a boss was hit (its parts flash) |
| `$74` | the last world: ice |
| `$76` | the kiwi's speed across, kept in the air |
| `$78` | the time bonus |
| `$7A` | the EXTEND letters flash |
| `$7C`, `$80` | where the kiwi restarts, and whether he does (`-1` after a warp) |
| `$84`, `$88` | the end of the BOB bank's directory, the first mirrored frame (`$122`) |
| `$8E` | the playfield's height (BOBs are clipped to it) |
| `$90`, `$94` | the score, the next extra life |
| `$B0` | free object slots |
| `$C6` | the kiwi's shots: 32 pointers to their objects |
| `$146` | the free rides on screen, listed each pass |

## The objects (`$64380`, 71 slots of `$3A` bytes)

Slot 0 is the kiwi's weapon, slot 1 the kiwi (`$643BA`), slot 2 the caged kiwi; free slots are
taken from slot 7 up (`sub_0B4A2`) or from slot 70 down (`sub_0B4E4`).

| Offset | |
|---|---|
| `(a5)`, `$2` | x, y (in the map) |
| `$4`, `$6` | dx, dy |
| `$8`-`$E` | the box (x, y, width, height), set by `BlitBob` when drawn; 0: no box |
| `$10` | facing left (mirrored) |
| `$12` | the frame (+1; 0 none), set by the animation from the script |
| `$14` | the animation script (`LEVELS.md`, *Animation scripts*), `$22` the position in it |
| `$18` | the handler, called each pass (0: the slot is free) |
| `$1C` | the type (`LEVELS.md`, *Object types*); -1 an enemy knocked down, -2 fruit, items, a boss's parts |
| `$1E`, `$20` | the frame delay count and the delay (`$20` 0: not animating) |
| `$24`, `$25` | a script loop's position and count |
| `$26` | what it carries, or for the kiwi the ride he is on |
| `$2A` | a rider's height above its ride |
| `$2C` | drawn this pass |
| `$2E` | its life: one less each pass, 0 removes it (handlers and drawing set it again) |
| `$30`-`$38` | the handler's own |

## The collision map (`$462A6`)

A byte per 8 x 8 cell, 128 cells a row, built for each level by `sub_0C5C0` from the map and the
tiles' attribute words (a nibble a cell). The values, as the tests use them (`sub_09066`,
`sub_09BDA`, `sub_09CDA`, `sub_09D60`, `sub_09DB8`): 0 air; 1 solid; 2 solid (a floor for
everything, bouncy for the kiwi's head); 3 water; 5 deep water (he sinks); 6 a current; `$F`
spikes.
