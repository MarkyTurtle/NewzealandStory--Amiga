# The New Zealand Story - Amiga

The Amiga conversion of Taito's *The New Zealand Story* (Ocean 1989; conversion by Choice
Software - code C. Gordon, graphics S. Connor): a disassembly of the original disk, and the
game rebuilt on an ordinary AmigaDOS-format disk.

| | |
|---|---|
| [`enhanced/`](enhanced) | **The game on a standard AmigaDOS disk, improved**: a new bootblock with the [4489_byteloader](https://github.com/MarkyTurtle/4489_byteloader) in place of Rob Northen's Copylock-protected boot chain, the level data as files on the new disk, a scroller that updates only what moves (a corkscrew with a vertical ring, double-buffered, with a pristine buffer), 50 frames a second, the sprites drawn in one blit each, a title menu (options, two-button joysticks, a sound test, the cheat), and the machine's extra memory used for the level files and the sprite frames; it runs on an A500 with 512K and on the A1200. `python3 enhanced/tools/build_disk.py` makes `enhanced/build/nzs.adf` |
| [`original/`](original) | **The original disk**, disassembled: sources that reassemble byte-identical (the main program, the game loader, both bootblocks), the boot chain and the copy protection worked out ([`original/docs/BOOT.md`](original/docs/BOOT.md)), every file on the disk ([`original/disk/`](original/disk)) and the tools that produced them |
| [`original/assets/`](original/assets) | **The game's assets, extracted**: the sound effects and instruments (IFF 8SVX, as `.iff` and `.wav`), the music decoded and rendered through the original driver, every BOB frame as a `.png`, every level's map with the objects it places. Formats in [`original/docs/SOUND.md`](original/docs/SOUND.md), [`GRAPHICS.md`](original/docs/GRAPHICS.md) and [`LEVELS.md`](original/docs/LEVELS.md) |
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

The bootblock and an extension module do it all without the protection: they find the drive
booted from, survey the machine's memory and CPU, show the same loading screen, load and unpack
the program to `$400` and enter it as the original loader did. The disk holds the loading
screen, the level data as 40 files (each load the game makes, cut to the bytes it uses), and the
game. The game's source is edited by hand (`enhanced/src/nzs_game.s`): its own `TrackRead` reads
the level files, and the improvements take over the original's routines through jumps put over
their first instructions, block 2 of the program keeping every label where the original has it.
[`enhanced/README.md`](enhanced/README.md) describes it all; [`enhanced/TODO.md`](enhanced/TODO.md)
what is left.

Status: plays in WinUAE on an A500 (512K, and with a trapdoor expansion) and an A1200; checked in
emulator harnesses (`enhanced/tools/test_*.py`). To try: real hardware.
