# Building

* **`original/`**: the original game. Its sources reassemble byte-identical to the original disk.
* **`enhanced/`**: the game on an ordinary AmigaDOS disk. Building it makes a playable disk
  image (ADF).

## What you need

| Tool | Needed for | Notes |
|---|---|---|
| [vasm](http://sun.hasenbraten.de/vasm/) (`vasmm68k_mot`), the 68000 assembler with Motorola syntax | every build | Build it from its source (`make CPU=m68k SYNTAX=mot`). Tested with vasm 2.0f |
| [Python](https://www.python.org/) 3 | the disk builder, the tests, the tools | Tested with Python 3.13 |
| Python packages `capstone`, `pillow`, `unicorn` | see below | `pip install capstone pillow unicorn` |
| A C/C++ compiler and Git | only to rebuild the protection tools (`original/tools/protemu`, `original/tools/disk/build_dump.sh`) | gcc / g++ |
| An Amiga emulator and a Kickstart ROM | playing the disk | [WinUAE](https://www.winuae.net/), [FS-UAE](https://fs-uae.net/) or [Amiberry](https://github.com/BlitterStudio/amiberry). FS-UAE also runs it with its built-in AROS Kickstart replacement |

| Package | Used by |
|---|---|
| `capstone` | the disassembly tools (`original/tools/disasm/make.py`, `tools/dis.py`), and `original/tools/disasm/tvd.py` |
| `pillow` | the pictures (`original/tools/screen.py`, `extract_files.py`, the boot test's screenshot) |
| `unicorn` | `enhanced/tools/test_boot.py` (the 68000 emulator that boots the disk) |

On Debian or Ubuntu: `sudo apt install build-essential git python3 python3-venv`, build vasm,
then in the repository `python3 -m venv .venv && . .venv/bin/activate && pip install capstone
pillow unicorn`. On Windows, WSL is the simplest way; WinUAE on Windows opens the built ADF from
`\\wsl$\...`.

## The AmigaDOS disk

```
python3 enhanced/tools/build_disk.py       # -> enhanced/build/nzs.adf
python3 enhanced/tools/test_boot.py        # boots it in the emulator harness: every check "ok"
```

`build_disk.py` assembles the game (`original/nzs_main.s` with `enhanced/src/diskload.s`, made by
`enhanced/tools/make_game.py`) and the bootblock, packs the game and writes the disk with the
loading screen and the level tracks from `original/disk/files/`. Open `nzs.adf` in DF0 of an
A500 (Kickstart 2.0 and later can also boot it from DF1-DF3) or write it to a floppy.

## The original

```
original/build.sh                          # assembles the four sources and checks their SHA-1
python3 original/tools/disasm/make.py      # regenerates the sources from their configs, and checks them
```

`original/README.md` describes the sources and tools. The files in `original/disk/files/` were
extracted from the disk images with `original/tools/disk/extract_files.py` (the game-tracks ADF)
and `ipf_extract.py` (the original IPF, via capsimg: `build_dump.sh`); the protection's decrypted
parts with `original/tools/protemu/run_protection.sh` (Musashi: `build.sh`).
