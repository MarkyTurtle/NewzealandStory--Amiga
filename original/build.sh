#!/bin/sh
# Assemble the sources and verify they match the original disk files byte for byte; then pack
# the main program and check it matches tracks 94-143.
# Needs vasmm68k_mot (http://sun.hasenbraten.de/vasm/) on the PATH, and python3 for the packer.
set -e
cd "$(dirname "$0")"
vasmm68k_mot -Fbin -m68000 -no-opt -quiet -o main.bin nzs_main.s
vasmm68k_mot -Fbin -m68000 -no-opt -quiet -o loader.bin nzs_loader.s
vasmm68k_mot -Fbin -m68000 -no-opt -quiet -o boot.bin nzs_boot.s
vasmm68k_mot -Fbin -m68000 -no-opt -quiet -o boot2.bin nzs_boot2.s
check() { s=$(sha1sum "$1" | cut -d' ' -f1); [ "$s" = "$2" ] && echo "$1: OK" || { echo "$1: MISMATCH ($s)"; exit 1; }; }
check main.bin   74d3f9924c56270c5fc2a4231be035c9157851a1
check loader.bin 853592064e08f7ee00a63c6a308e3d24777dec29
check boot.bin   2b0cb038ff946d40f6942dc7e970bee83b3fa07f
check boot2.bin  cb653d3d40abff2489a51a13e55d315a316c847f
python3 tools/disk/pack.py pack main.bin main_packed.bin
check main_packed.bin 068da7113d7db1746161301524898e843a58e787
