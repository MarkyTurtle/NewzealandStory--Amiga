# How the original disk boots, and its copy protection

The original disk boots through five stages before the game runs, with Rob Northen's Copylock
protection checked twice: once by the protection loader on track 0, and again by the game loader
on track 90. The new AmigaDOS disk (`../../enhanced`) replaces all five with one bootblock. The
game itself does not depend on the protection (see the end of this page).

| Stage | Where it is on the disk | Runs at | Source / listing |
|---|---|---|---|
| 1. Bootblock | track 0, `$000-$3FF` | Kickstart's boot buffer | `nzs_boot.s` |
| 2. Protection loader (Copylock) | track 0, `$400-$15FF` | `$60000` | `nzs_protection_run.lst` (decrypted, as executed) |
| 3. Its payload | inside stage 2, encrypted | `$60000` | `bin/protection_payload_60000.bin` |
| 4. Second-stage bootblock | inside stage 3 | the boot buffer, then `$76000` | `nzs_boot2.s` |
| 5. Game loader (Copylock again) | track 90 | `$400`, then `$76000` | `nzs_loader.s`, `nzs_loader_tvd.lst` (decrypted) |
| The game | tracks 94-143 (packed) | `$400` | `nzs_main.s` |

Track 1 is the Copylock track: not AmigaDOS. It is a "long track" (100,424 bits in the IPF
against 100,416 for the others, written at a slightly different speed) with 11 custom sync words
(`$8A91 $8A44 $8A45 $8A51 $8912 $8911 $8914 $8915 $8944 $8945 $8951`). The raw MFM is in
`disk/files/t001_copylock_track.mfm`.

## 1. The bootblock (`nzs_boot.s`)

Kickstart calls it with `a1` = the trackdisk IORequest. It calls `Forbid`, reads `$1200` bytes
from disk offset `$400` (the rest of track 0) to `$60000` with `DoIO`, retrying until there is
no error, and "returns" into them: it saves five registers but restores four, so the `$60000`
it stored in `a2`'s slot is left on the stack for the `rts`. Its text: *Protection (C)Copyright
1989 Rob Northen Computing. All Rights Reserved.*

## 2. The protection loader (`$60000`)

Almost all of it is encrypted, in several ways at once. `nzs_protection_run.lst` lists every
instruction as the CPU executed it (decrypted), in the order first executed.

**Trace-vector decryption.** It saves the registers, executes `ILLEGAL` (the illegal vector
pointing at its next stage), tries `MOVEC CACR` (on a 68020 or later: the caches off; on a 68000
that is itself illegal and lands on `$60116`), saves the vectors `$8-$27`, and executes `ILLEGAL`
again into its *enter* handler (`$601BC`). That sets the trace vector (`$601F6`) and the
privilege-violation vector (`$603B0`), steps the return address past the `ILLEGAL`, sets the
trace bit in the stacked SR and decrypts the first instruction. From then on, after every
instruction, the trace handler puts back the encrypted long it decrypted last, and decrypts the
first long of the next instruction at `A` (the stacked PC): `long[A] ^= swap(~long[A-4])`. Only
one instruction is ever in the clear. An `ILLEGAL` inside the encrypted code toggles the trace
bit (the enter handler's `bchg #7`), so the code after it runs untraced, in the clear, until the
next `ILLEGAL`: the timing-critical disk reads are done that way.

**An obfuscated start.** The first instructions set `a4 = $600D2` and clear `d4-d7`, then jump
through a maze of 29 `bra.w` before reaching `$6022A`.

**Layers of self-modifying decryption.** 54 short loops, each of the form `lea X(pc),a7;
move.w #n,d0; [move.w #k,d1]; <op> (a7)+; dbra`, decrypt the code after themselves - `sub.w`,
`add.w`, `eor.w`, `neg.w`, `not.w`, `rol.w`/`ror.w`, swapping word pairs (`movem.w`/`exg`),
swapping the bytes of words (`movep.w`) - all still under trace decryption: 50 decrypt, and 4 instead add
the code up into `d5`, `d6` and `d7` (`add.l (a7)+,dN`): checksums, used later. Between layers,
`eori.w #$2000,sr` in user mode raises a privilege violation whose handler (`$603B0`) toggles
the supervisor bit in the stacked SR and skips the instruction: the code switches between user
and supervisor mode this way.

**Checksum-dependent jumps.** It installs its own vectors `$8-$24` (bus error `$60D7C`, address
error `$60356`, illegal `$601BC`, zero divide `$60DBC`, CHK `$60DFC`, TRAPV `$60E7C`, privilege
`$603B0`, trace `$601F6`) and then branches to *odd* addresses (`bra.w $6256D`). On a 68000 a
jump to an odd address raises an address error as part of the jump (IR = the jump's opcode,
stacked PC = the jump + 2, no trace exception). The handler, for a branch, adds up the code words
from `a4` to the stacked PC + 2 (16-bit sum), moves `a4` on by the sum - 2 and continues there,
through the trace handler. So where each "branch" goes depends on the bytes of the code it has
passed over, and on `a4`, a pointer through the code that every such jump advances. (A fault on a
data access takes the handler's other path, which rebuilds the frame.)

**The Copylock check** (`$604C4`): the same routine as in the track 90 loader (below), laid out
identically ($15DC8 lower; variables at `$60098`). It reads the Copylock track, times it, checks
the signature and derives the key into its variables (`+$1C`).

**The payload.** More layers follow; then (`$60976`) the checksums in `d4-d7` are combined and an
untraced loop decrypts the payload (from `$60CFC`) with them (`add.l d7,(a0)` / `add.l (a0)+,d7`
with bit tests): changing any byte of the protection code changes the checksums and so the
payload. The track 0 copy does not use its Copylock key: at the end the registers saved on entry
are reloaded and `d0`, `d1` and `d7` set to ExecBase. Finally (`$60C64`) it copies a short copier
to `$3E6`, which moves the decrypted payload down to `$60000`, clears the rest of the loader,
restores the vectors `$8-$27` and the registers saved on entry, and `RTE`s into `$60000`.

## 3. The payload (`$60000`, `$424` bytes)

It copies the 1024 bytes at `$60024` over Kickstart's boot buffer (`a0`, as the bootblock was
entered), calls `Permit` and jumps to offset 12 of them: a second bootblock, entered as Kickstart
enters one.

## 4. The second-stage bootblock (`nzs_boot2.s`)

It copies its loader (`$D6` longs from offset `$10`) to `$76000` and runs it: stack at `$400`,
then it reads track 90 to `$400` with the hardware - `DSKLEN $9996` (6,550 words) to `$68000`,
sync `$4489`, waiting for the index pulse, then decoding the 11 sectors (its variables at
`$2004-$200A` and `$61A0`) - and jumps to `$400`.

## 5. The game loader, track 90 (`nzs_loader.s`)

The `bra.w` at `$400` goes to `Start` (`$F92`), which copies the rest (`$2E3` longs from `$404`)
to `$76000` and runs it there. It enters supervisor mode with a privilege violation, takes the
hardware (interrupts and DMA off, CIA-A interrupts off, the display set up black: 4 planes,
`DDFSTRT $38`, `DDFSTOP $D0`, `DIWSTRT $3C81`, `DIWSTOP $04C1`), turns both motors off, reads
tracks 91-93 to `$70000` (the loading screen), decodes it to `$78000` (the byte-run format in
`../disk/FILES.md`) and sets its 16 colours (stored at half value, doubled).

Then the second Copylock check (`Protection`, `$76124`), trace-vector encrypted as on track 0
but without the layers. `tools/disasm/tvd.py` decrypts it statically (each instruction's plain
text depends only on the image and its address, since the handler re-encrypts before it
decrypts) to `nzs_loader_tvd.lst`. After a maze of `bra.w` it seeks to track 1, reads the sync
words in turn (`CopylockSyncs`, `$764AC`) with disk DMA, times the long track in an untraced
loop (counting `DSKBYTR` polls between two points of the track, and requiring a difference of at
least 3% - `$7631A`), checks the signature `"Rob Northen Comp"` read from the track, adds and
rotates the track's longs into the key, and ends with a privilege violation into
`LoadAndRunGame` with the key in `d0`:

```
LoadAndRunGame:  move.l  d0,-(a7)
                 subi.l  #$F974D77D,d0      ; the load address = key - $F974D77D
                 movea.l d0,a0
                 move.w  #94,d0             ; 50 tracks from track 94: the packed program
                 move.w  #50,d1
                 bsr.w   ReadTracksOrReset  ; (a failed read resets the machine)
                 ...                        ; key - $F974D77D again: Unpack in place
                 jmp     (a0)               ; key - $F974D77D again: enter the game
```

So the key must be **`$F974DB7D`**: the only value for which the program loads at `$400`. With
a wrong key the game is read to a wrong address and the machine crashes.

## Tools

* `tools/disasm/tvd.py` - static trace-vector decryption (the track 90 loader in full; the first
  part of the track 0 loader, up to where the layers start modifying the code).
* `tools/protemu/` - **protemu**: the protection run in Musashi (the 68000 core from MAME), built
  with the trace exception, 68000 address errors and prefetch (`build.sh` fetches Musashi). One
  correction is made by the harness (`-o 2`): Musashi completes a jump to an odd address and
  takes the trace exception before failing on the next fetch; a 68000 raises the address error in
  the jump itself (the target is prefetched as part of the instruction). The harness turns that
  trace frame into the 68000's address-error frame (IR = the jump's opcode, PC = the jump + 2, as
  UAE does). With any other stacked PC the checksum jumps leave the loader, which confirms it.
  `run_protection.sh` runs the track 0 loader until it enters its payload and writes the
  payload, the second-stage bootblock and `nzs_protection_run.lst`. The Copylock disk check is
  not emulated (it times the long track): the run jumps from the check's call (`$604D0`) to its
  exit (`$60868`), re-encrypting and decrypting as the trace handler would (`-T`), with
  `d0 = $F974DB7D`.
* (Unicorn, used elsewhere for testing, is not suitable here: being QEMU it has neither the trace
  exception nor address errors, and it loses the condition codes between single steps.)
* `tools/disk/ipf_extract.py` - the protection loader and the Copylock track from the IPF (via
  `tools/disk/dump`, built against capsimg by `build_dump.sh`).

## What the game depends on

Nothing from the protection or the loaders - but it does read the disk itself:

* the game has no Copylock key check: neither key constant appears in it, and nothing in it
  refers to the protection's or the loaders' memory (`$60000-$611FF`, `$76000`). It uses
  `$70000` and `$78000` only as its own screen buffers, clearing them first; `$68000` is its own
  track reader's buffer;
* `Init` saves and restores the trace vector while it fills the others, but nothing reads it;
* it sets up the CIAs and interrupts it uses itself (`$11BE`: CIA-A; `$C3FE`: CIA-B timers and
  alarm);
* **it loads level data from the disk while it runs**: `LoadTracks` (`$55BA`) reads tracks by
  number through the jump table's `TrackRead` (block 1, `$C24`: the hardware, AmigaDOS-format
  sectors, the MFM buffer at `$68000`, always DF0) - at the start of each level 5 tracks of
  packed level data (unpacked in place, in the main program's format) and 1 more track, on some
  levels 2 more, and 5 at the end of the game (`../disk/DISKMAP.md`). After 5 failed tries it
  shows *There has been a fatal disk error - please check the disk & press the 'DEL' key* and
  stops. Those are standard AmigaDOS tracks, but at fixed track numbers.

So the new disk must leave the program at `$400` and enter it there, as the track 90 loader did
(with `d0 = a0 = $400`), **and** give the game a `TrackRead` that finds those tracks on the new
disk: `../../enhanced/src/diskload.s` replaces `TrackWrite` and `TrackRead` in their own space.
