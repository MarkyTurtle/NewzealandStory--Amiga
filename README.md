# The New Zealand Story - Amiga

The Amiga conversion of Taito's *The New Zealand Story* (Ocean 1989; conversion by Choice
Software - code C. Gordon, graphics S. Connor): a disassembly of the original disk, and the
game rebuilt on an ordinary AmigaDOS-format disk.

| | |
|---|---|
| [`enhanced/`](enhanced) | **The game on a standard AmigaDOS disk**: a new bootblock with the [4489_byteloader](https://github.com/MarkyTurtle/4489_byteloader) in place of Rob Northen's Copylock-protected boot chain, and the game's own track reader replaced so it loads its levels from the new disk. `python3 enhanced/tools/build_disk.py` makes `enhanced/build/nzs.adf` |
| [`original/`](original) | **The original disk**, disassembled: sources that reassemble byte-identical (the main program, the game loader, both bootblocks), the boot chain and the copy protection worked out ([`original/docs/BOOT.md`](original/docs/BOOT.md)), every file on the disk ([`original/disk/`](original/disk)) and the tools that produced them |
| [`original/assets/`](original/assets) | **The game's assets, extracted**: the sound effects and instruments (IFF 8SVX, as `.iff` and `.wav`), the music decoded and rendered through the original driver, every BOB frame as a `.png`. Formats in [`original/docs/SOUND.md`](original/docs/SOUND.md) and [`GRAPHICS.md`](original/docs/GRAPHICS.md) |
| [`BUILDING.md`](BUILDING.md) | What to install, and how to build and check both |

## The original disk in brief

The disk has no filesystem. Kickstart loads the bootblock, which reads Rob Northen's protection
loader from the rest of track 0; that checks the Copylock track (track 1) under several layers
of encryption - a trace-vector decoder, self-modifying decryption, checksum-dependent jumps
through deliberate address errors - and decrypts a second-stage bootblock, which reads the game
loader from track 90. That shows the loading screen (tracks 91-93), checks Copylock again (the
key gives the address to load to: `$400`), and reads and unpacks the main program (tracks
94-143). The game then reads its level data by track number at the start of each level.

## The AmigaDOS disk in brief

One bootblock does it all without the protection: it finds the drive booted from, shows the
same loading screen, loads and unpacks the same program to `$400` and enters it as the original
loader did. The disk holds the loading screen, the 96 tracks of level data the game reads, and
the game. In the game, `TrackWrite` and `TrackRead` are replaced, in their own space, by a
`TrackRead` that finds each of the original's tracks on the new disk and reads it with the
byteloader; every other byte of the program is the original's.

Status: it boots and plays in FS-UAE; checked in an emulator harness (`enhanced/tools/test_boot.py`).
To try: WinUAE and real hardware.
