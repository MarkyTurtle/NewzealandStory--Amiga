#!/bin/sh
# Build dump (dump.cpp): writes each track of an IPF disk image as raw MFM (tNNN.bin), using the
# SPS / CAPS decoder library (capsimg, github.com/FrodeSolheim/capsimg), cloned and built here.
#   sh tools/disk/build_dump.sh && tools/disk/dump GAME.ipf OUTDIR
set -e
cd "$(dirname "$0")"
[ -d capsimg ] || git clone --depth 1 https://github.com/FrodeSolheim/capsimg
if [ ! -f capsimg/CAPSImg/libcapsimage.so.5.1 ]; then
    (cd capsimg && ./bootstrap && ./configure && make -j4) > capsimg_build.log 2>&1
fi
ln -sf libcapsimage.so.5.1 capsimg/CAPSImg/libcapsimage.so.5
C=capsimg
g++ -O2 -I$C/CAPSImg -I$C/LibIPF -I$C/Core -I$C/Codec -I$C/Device dump.cpp \
    $C/CAPSImg/libcapsimage.so.5.1 -Wl,-rpath,"$(pwd)/$C/CAPSImg" -o dump
echo "built $(pwd)/dump"
