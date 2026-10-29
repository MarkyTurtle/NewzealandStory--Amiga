# Building

* **`original/`**: the original game. Its sources (edited by hand) reassemble byte-identical to
  the original disk.
* **`enhanced/`**: the game on an ordinary AmigaDOS disk. Building it makes a playable disk
  image (ADF).

## What you need

| Tool | Needed for | Notes |
|---|---|---|
| [vasm](http://sun.hasenbraten.de/vasm/) (`vasmm68k_mot`), the 68000 assembler with Motorola syntax | every build | Build it from its source (`make CPU=m68k SYNTAX=mot`). Tested with vasm 2.0f |
| [Python](https://www.python.org/) 3 | the disk builder, the tests, the tools | Tested with Python 3.13 |
| Python packages `capstone`, `pillow`, `unicorn` | see below | `pip install capstone pillow unicorn` |
| A C/C++ compiler and Git | only to rebuild the protection tools (`original/tools/protemu`, `original/tools/disk/build_dump.sh`) and the study emulator (`original/tools/nzsemu/build.sh`) | gcc / g++ |
| [FFmpeg](https://ffmpeg.org/) | optional: the rendered songs as `.ogg` (`make_assets.sh`; without it they are `.wav`) | |
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
original/tools/nzsemu/build.sh             # (once) the study emulator, for the tests below
python3 enhanced/tools/test_scroller.py    # the display against the original's (a few minutes)
python3 enhanced/tools/test_menu.py        # the title menu and the cheat
python3 enhanced/tools/test_fly.py         # the cheat's fly mode
python3 enhanced/tools/test_smooth.py --blittime   # 50 frames a second (some minutes)
python3 enhanced/tools/test_frames.py      # the BOB frames' cache on 512K (some minutes)
```

`build_disk.py` assembles the game (`enhanced/src/nzs_game.s`, the enhanced game's own source,
with `diskload.s`, `enhanced.s` - which includes `scroller.s`, `smooth.s` and `menu.s` - and
`frames.s`), the extension module and the bootblock, packs the game and writes the disk with
the loading screen and the level files, cut from the tracks in `original/disk/files/tracks/`.
Open `nzs.adf` in DF0 of an A500 or A1200 (Kickstart 2.0 and later can also boot it from
DF1-DF3) or write it to a floppy.

## The original

```
original/build.sh                          # assembles the four sources and checks their SHA-1
python original/build.py                   # the same, on any system (Windows too)
```

```
original/tools/nzsemu/build.sh             # the study emulator (needed for the music renders)
original/tools/assets/make_assets.sh       # regenerates original/assets/ (samples, music, BOBs)
```

The sources are edited by hand: run `original/build.sh` after any edit (comments too) to check
they still assemble to the original bytes. `python3 original/tools/disasm/make.py` shows how
they were first made from their configs (into `original/tools/disasm/regen/`, for the record).
`original/README.md` describes the sources and tools. The files in `original/disk/files/` were
extracted from the disk images with `original/tools/disk/extract_files.py` (the game-tracks ADF)
and `ipf_extract.py` (the original IPF, via capsimg: `build_dump.sh`); the protection's decrypted
parts with `original/tools/protemu/run_protection.sh` (Musashi: `build.sh`).

## GitHub Actions

`.github/workflows/` builds on every push that changes them:

* **original** (Windows and Linux, Python 3.11 and 3.13): `original/build.py` (and `build.sh` on
  Linux) - the four sources against the original disk's SHA-1.
* **enhanced** (the same systems): `build_disk.py`, the disk's SHA-1 against `ADF_SHA1` in the
  workflow (update it when the game is changed on purpose), `test_boot.py`, and on Linux
  `test_menu.py` and `test_fly.py`; the disk is kept as the run's artifact.
* **release**: when a release is published, the disk built from its tag is attached to it as
  `NewZealandStory_Enhanced_<tag>.adf`.

vasm is built from its source mirror for each run (`.github/actions/vasm`). The packages for the
tests are in `enhanced/requirements.txt` and `original/requirements.txt`.
