# The New Zealand Story on an ordinary AmigaDOS disk

> The original game, rebuilt from the disassembly in [`../original`](../original) onto a
> standard AmigaDOS-format disk that boots with the
> [4489_byteloader](https://github.com/MarkyTurtle/4489_byteloader) instead of Rob Northen's
> Copylock-protected boot chain. Nothing on it is copy-protected: any emulator or real drive
> reads it, and it can be written to a real floppy with any ADF tool.

```
python3 enhanced/tools/build_disk.py      # -> enhanced/build/nzs.adf
python3 enhanced/tools/test_boot.py       # boots it in an emulator and checks it
```

(`../BUILDING.md` has what to install.) Tested in FS-UAE as an A500 with FS-UAE's built-in AROS
Kickstart replacement: it boots to the loading screen, then the attract sequence, and the game
plays, loading its level data from the disk. Still to be tried: WinUAE and real hardware with a
real Kickstart 1.3 and later.

| File | What it is |
|---|---|
| `src/boot_4489.s` | The bootblock: replaces the whole original boot chain |
| `src/diskload.s` | The game's disk reading on this disk: replaces the original's `TrackWrite` / `TrackRead` in their own space |
| `src/byteloader.i` | The 4489_byteloader, as published (used by both) |
| `tools/build_disk.py` | Builds the disk |
| `tools/make_game.py` | Makes the game's source (`build/nzs_game.s`) from `original/nzs_main.s` with `diskload.s` in place of the track routines |
| `tools/test_boot.py` | Boots the disk in an emulator (Unicorn) from Kickstart's call to the game's entry, then calls the game's new `TrackRead` as the game does |
| `tools/floppy.py` | The floppy drive the test uses (from the Ghosts'n Goblins project) |

## The disk

80 cylinders x 2 heads x 11 sectors of 512 bytes (901,120 bytes), standard AmigaDOS MFM with
the `$4489` sync, no filesystem (Workbench shows it as NDOS):

| Disk offset | Bytes | |
|---|---:|---|
| `$00000` | 1,024 | the bootblock: `'DOS',0`, checksum, root block 880, then the code |
| `$00400` | 144 | the file table: `'NZSF'`, version.w (1), count.w, 8 bytes zero, then for each file id its disk offset and length (longs) |
| `$00600` | 16,896 | file 1: the loading screen (the original file) |
| `$04800` | 540,672 | file 2: the 96 tracks of the original disk the game reads while it runs (level data), one after another |
| `$88800` | 275,473 | file 0: the game, packed in the original's format |
| `$CBC12` | 66,542 | free |

The game is stored packed: unpacked (338,855 bytes) it would leave only about 3 KB free. It is
packed by `original/tools/disk/pack.py`, which reproduces the original's tracks 94-143 byte for
byte from the original program.

## Booting (`src/boot_4489.s`)

It does what the original's five stages (`../original/docs/BOOT.md`) together did, minus the
protection:

1. finds the drive booted from (while Kickstart is intact): opens `trackdisk.device`'s units 3
   to 0 until one is the boot IORequest's unit (DF0 if none is). Kickstart 1.3 boots only from
   DF0; 2.0 and later from any drive. Every load reads that drive, here and in the game;
2. takes the machine over (interrupts and DMA off, supervisor mode) and copies its loader to
   `$63100`, out of the way of everything it loads;
3. shows the loading screen as the track 90 loader did: black, 4 planes at `$78000` (`$2000`
   apart), `BPLCON0 $4200`, `DDFSTRT $38`, `DDFSTOP $D0`, `DIWSTRT $3C81`, `DIWSTOP $04C1`, the
   same copper list; the file loaded to `$70000` and decoded there, its colours doubled;
4. loads the game to `$400` and unpacks it in place, as the track 90 loader's `Unpack`; writes
   the boot drive into the game's `BootDrive` (`$A08`);
5. enters the game at `$400` with `d0 = a0 = $400`, as the track 90 loader did.

A load that fails is tried again; after 8 failures COLOR00 turns red while it goes on trying.
Memory while loading: the game `$400-$52FA6`, the loader and its buffers `$60000-$63FFF`
(MFM buffer `$60000`, file table `$63000`, the loader `$63100`, stack below `$64000`), the
screen file `$70000`, the screen `$78000-$7FF3F`.

## The game's disk reading (`src/diskload.s`)

The original game reads its level data from the disk at the start of each level (5 tracks of
packed data and 1 more, 2 more on some levels) and at the end of the game, by **track number**
through the jump table's `TrackRead` (`../original/disk/DISKMAP.md`). `diskload.s` replaces
`TrackWrite` (`$A04`) and `TrackRead` (`$C24`) in exactly their space (`$A04-$D87`), so every
other byte of the program is the original's (`build_disk.py` checks it):

* `TrackRead`: same arguments and results (d0 = track, d1 = count, a0 = where; d0 = 0 if read,
  -1 if not). Each original track is looked up in `TrackMap` - its place among the tracks
  stored on this disk (`build/trackmap.i`, written by `build_disk.py`) - and read with the
  byteloader from the drive booted from, into the MFM buffer at `$68000` where the original
  read its tracks. All registers are kept; the byteloader leaves the interrupts, CIA timers,
  blitter and copper alone, so the music and display go on while a level loads;
* `TrackWrite` returns -1: only the built-in debug monitor's `W` command used it.

The game itself is unchanged otherwise: `make_game.py` takes `original/nzs_main.s` as it is,
so every annotation made to the original carries over.

## Next

This is the first step: the original game, unprotected. Improvements go here, each on its own
branch, built and tested in WinUAE before merging. The list is in [`TODO.md`](TODO.md).
