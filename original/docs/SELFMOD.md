# Self-modifying code

The game writes into its own instructions in ten places, the loader decrypts itself as it
runs, and the enhanced game adds one place of its own. Every site is marked in the sources: the
writing instruction with `SMC -> ...` after its address comment, the instruction written to with
`SELF-MODIFIED ...`, and the routine's header box says what changes and why.

The listing always shows the bytes as the program was saved, so a self-modified operand looks
like an ordinary label or constant (`jsr (sub_06A86).l`, `move.w (sub_0B098).l,d3`,
`ori.w #$fca,d7`). Read it as "whatever was written there last".

Why it matters:

* **Caches.** A 68020 or later with its instruction cache on can run the old instruction after it
  has been rewritten. The enhanced game turns the caches off above a 68000 (`ext.s`, the A1200
  fix) rather than flushing at each site.
* **Moving the program.** Several sites write to absolute addresses given as numbers
  (`move.w d3,$4ee8.l`, `move.l a0,$6f20.l`), not labels, so the code cannot be moved or
  reassembled at another address without changing them (`enhanced/TODO.md`, *Not doing*).

## The main program (`nzs_main.s`)

| # | Written | By | What | Why |
|---|---|---|---|---|
| 1 | block 1 (`$404-$3213` to `$400`) | `Relocate` (`$3214`) | the whole of block 1 copied 4 bytes down | block 1 is assembled at `$400` but stored after the `bra.w Relocate` at `$400`. `sub_03268` is an unreferenced variant |
| 2 | `BlitBob+2`, `BlitBob+8` (`$B6C6`, `$B6CC`): the immediates of `lea (BobData).l,a0` and `lea (BobDirectory).l,a1` | the title `l_04016` (`$4040`), the intro `sub_04CC6` (`$4CF2`), a new game `sub_04F1A` (`$4F2A`, `$4F30`), the progress screen `l_043F4` (`$442C`, its bank; `$4540`, the main bank back) | the BOB bank `BlitBob` draws from | one drawing routine for the main bank, the intro's and the progress screen's |
| 3 | `sub_04CC6+2`: the target of its own `jmp (l_04CCC).l` | `sub_04CC6` (`$4DAA`) | `l_04088`, a new game | the intro story is shown only the first time after a reset |
| 4 | `$4EE8`, `$4EEC`, `$4EF0`, `$4EF4`: the displacements of the four `move.w (a0)+,$50(a1)` | `DeinterleaveBobs` (`$4EAC`-`$4EC4`) | 1, 2, 3 and 4 times the frame's plane size | the inner loop spreads each word of a frame into its plane without adding offsets |
| 5 | `$6F20`: the operand of `jsr (sub_06A86).l` at `$6F1E` | `l_06ECA` (`$6ECA`) | the riding enemy's flight routine (`l_06718`, `l_067F4`, `sub_068D2`, `sub_069A8`, `sub_06A86`, `sub_06B4A`), chosen by its type's handler | one shared body for types 10-19 |
| 6 | `$7C6A`: the immediate of `move.l #$0,d1` at `$7C68` | `sub_07C22` (`$7C50`) | type 7's position, 8 pixels up | its burst's 5 pieces all start there (`sub_0B4E2` takes d1) |
| 7 | `l_065AE`: `moveq #0,d0` / `moveq #0,d0` at the start of the collision test `sub_065A8` | `sub_0A742` (`$A772`) | `moveq #0,d0` / `rts` | **the copy protection's sabotage** (below) |
| 8 | `$B0AA`: the operand of `move.w (abs).l,d3` at `$B0A8` | `sub_0B098` (`$B09E`) | the picture's address | the ending's picture decoder reads the plane length from the picture's first word |
| 9 | `$B8DE`: the immediate of `ori.w #$fca,d7` in `sub_0B8B4` | `BlitBob` (`$B7BC`), each BOB | the blitter minterm: `$FCA` (cookie cut) or `$BFA` | a boss's parts (type -2) flash white while `$72(a6)` is set after a hit |
| 10 | `l_04F46+2`: the immediate of `move.w #$3,d0`, the starting lives | the cheat `sub_0B9F0` (`$BA34`) | 1,000 | the cheat; the immediate is then read as its flag by `l_043C0` (the HELP level skip: 1,000 EOR `$3B7` = `$5F`, HELP's key code) and `sub_0900A` (the unused fly mode) |

Also not code but written like it: `sub_052C4` draws the oxygen gauge into the image data of the
main bank's frame `$24` each pass (the enhanced game's frame cache rebuilds that frame:
`frames.s`, `ONE_LIVE`).

## The copy protection's hidden check

The loader's Copylock (`nzs_loader.s`, `Protection`) reads the key track, works out the key
`$F974DB7D`, loads the game to key - `$F974D77D` = `$400` (a wrong key loads it elsewhere and the
machine crashes) - and leaves the key in the trace vector, `$24`: the check derives the key into
its variables at `+$1C` (`BOOT.md`), which is where it saved the vector `$24` on entry, and its
exit (`Prot_Exit`, `$76658`: `movem.l d0-d7,$8.l`) puts the vectors `$8-$24` back from there. The
game's start-up keeps `$24` when it points every other exception vector at its own handler
(`sub_00576`).

`sub_0A742` checks it again: (`$24` EOR `$F9448D74`) must end in `$09` - the right key gives
`$00305609`. It runs

* at every boss: `l_0A6FC`, the end of each boss's set-up (from the caged kiwi on the 4th level
  of worlds 1, 2, 3 and 5, `sub_0AC2A`), falls into it;
* at every warp: `sub_04BEA`, called from the warp's animation script (the warp opens after 5
  shots at the level's warp tile: `sub_04A22`, `dat_04ABA`).

If the key is wrong it copies the 4 bytes at `l_0A77C` (`moveq #0,d0` / `rts`) over `l_065AE`.
`sub_065A8` - does this object touch the kiwi? - then always answers no. Nothing crashes and
the game plays on, but no enemy can hurt the kiwi, he can board no ride and pick up no fruit,
item or EXTEND letter, and the caged kiwi can never be freed (`l_0AC6E` uses the same test), so
the level cannot be finished. The callers of `sub_065A8`: `sub_04B5A`, `sub_06162`, `sub_061C8`,
`sub_0635A`, `sub_064EC`, `sub_06530`, `sub_07494`, `sub_07530`, `sub_0AC2A`, `sub_0AC5C`. The
kiwi's shots use `sub_065B2` directly and still work.

## The loader (`nzs_loader.s`)

From `$76148` the protection's code is trace-vector encrypted: `TVD_Trace`, the trace handler,
puts back the long it decrypted last and decrypts the next instruction in place (EOR with the long
before it, inverted and swapped), so only one instruction is ever in the clear. The bootblock
chain is in `BOOT.md`.

## The enhanced game

Everything above is still there in `enhanced/src/nzs_game.s`, at the same addresses (block 2's
labels are checked against the original's by `build_disk.py`), with these differences:

* `menu.s` writes the starting lives too: `move.w #1000,LIVES` (the cheat on, `CheatOn`) and
  `move.w #3,LIVES` (off), `LIVES` = `l_04F46+2`; `l_043C0`, now `EnhCheatKeys`, reads it to
  allow F1 (the fly mode, `sub_0900A`) and F2 (the level skip).
* `sub_0B8B4` is replaced by `EnhBob` (the scroller's `ScrBob`, `OneBob4` for one-blit frames),
  but `BlitBob` still writes the minterm into its old `ori.w` (labelled `BobMinterm_`), and the
  new code reads it from there (`BobMinterm`).
* `Relocate` also copies block 3 (`frames.s`) from after block 2 to `$5E800`.
* The caches are off above a 68000 (`ext.s`), so none of the sites needs a cache flush.
* The AmigaDOS bootblock and the extension module do not run Copylock, so `$24` does not hold the
  key: the check in `sub_0A742` fails at the first boss or warp unless the key is put there.
