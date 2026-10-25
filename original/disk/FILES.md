# The files on the original disk

The disk has no filesystem: the loaders read whole tracks (a track = one side of a cylinder,
5,632 bytes in an ADF at offset track x 5,632). `files/` holds every file the boot chain reads,
named by track; `SHA1SUMS` their checksums. They come from two images:

* the game-tracks ADF (every AmigaDOS track: all but track 1, with track 0's protection loader
  blank) - `python3 tools/disk/extract_files.py GAME.adf` writes the bootblock, the game loader,
  the loading screen, the packed program, `../bin/main.bin` and the level tracks (`tracks/`,
  found from the program's tables by `tools/disk/game_tracks.py`), with every check on the way;
* the original IPF - `tools/disk/ipf_extract.py` writes the protection loader and the Copylock
  track (see `../docs/BOOT.md`); `tools/protemu/run_protection.sh` then decrypts the second-stage
  bootblock out of the protection loader.

| File | Bytes | Loaded to | Contents | Source |
|---|---:|---|---|---|
| `t000_bootblock.bin` | 1,024 | boot buffer | the bootblock | `nzs_boot.s` |
| `t000_protection_loader.bin` | 4,608 | `$60000` | Rob Northen's protection loader (track 0 `$400-$15FF`), encrypted | `nzs_protection_run.lst` |
| `t000_boot_stage2.bin` | 1,024 | boot buffer, `$76000` | the second-stage bootblock, decrypted from the protection loader | `nzs_boot2.s` |
| `t001_copylock_track.mfm` | 12,553 | - | track 1, raw MFM from the IPF: the Copylock track | - |
| `t090_game_loader.bin` | 5,632 | `$400`, `$76000` | the game loader | `nzs_loader.s`, `nzs_loader_tvd.lst` |
| `t091-093_loading_screen.bin` | 16,896 | `$70000` | the loading screen | - |
| `t094-143_main_packed.bin` | 275,738 | `$400` | the main program, packed | `nzs_main.s`, `tools/disk/pack.py` |
| `tracks/tNNN.bin` | 5,632 each | by track | the 96 tracks the game itself reads while it runs: level data (`DISKMAP.md`) | - |

And in `../bin/`: `main.bin` (338,855 bytes) - the main program unpacked, as it is in memory at
`$400` (what `nzs_main.s` reassembles); `protection_payload_60000.bin` - the protection loader's
decrypted payload as it starts at `$60000`.

## The loading screen (`t091-093_loading_screen.bin`)

Decoded by the track 90 loader (`DecodeLoadScreen`, `$766AC`) and by the new disk's bootblock:

* `+$02`: 16 colour words, stored at half value (doubled when set);
* `+$22`: byte-run data. A byte `n` below `$80` means copy the next `n + 1` bytes; above `$80`,
  repeat the next byte `257 - n` times; `$80` is skipped;
* the output is interleaved by line: 40 bytes of plane 0, then of planes 1, 2 and 3, for each of
  200 lines - a 320 x 200, 16-colour picture, decoded to `$78000` with the planes `$2000` apart.

The data ends at `+$3578`; the rest of the three tracks is unused. `../render/out/loadscreen.png`.

## The packed main program (`t094-143_main_packed.bin`)

Unpacked in place by the track 90 loader (`Unpack`, `$7671E`); `tools/disk/pack.py` packs and
unpacks it, and reproduces this file byte for byte from `bin/main.bin`:

* `long` unpacked length - 1 (`$52BA6`);
* `long` packed length - 1 (`$43511`), the length counting the 8-byte header: the stream is
  `$4350A` bytes, and the loader's move-up copies 8 bytes past it (zeros);
* the first byte of the stream is the escape byte - the least frequent byte value in the program
  (`$8D`, 59 times). Then: escape, value, count means `count + 1` copies of value; any other byte
  is itself. Runs of 3 or more are encoded (up to 256), a literal escape byte as a run of 1; the
  packer never lets a run take in the program's last byte (it writes it as a literal).

The loader moves the packed bytes up to end at `$400 + $52BA7` and unpacks forwards from `$400`;
the read pointer always stays ahead of the write pointer (`extract_files.py` checks it).

## The main program (`../bin/main.bin`, `$400`)

`$400: bra.w Relocate` (`$3218`), which copies the first block (`$B84` longs, file `$404-$3213`)
down to `$400` and jumps there: block 1 runs 4 bytes below where it is stored, and everything
from `$3214` runs where it loads. Block 1 is the system layer and the built-in debug monitor
(jump table at `$400`: init, key test, joystick, track read, track write, get key); the game
starts at `$4000`. See `../README.md`.
