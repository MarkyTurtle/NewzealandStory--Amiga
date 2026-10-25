"""Extract what the game-tracks ADF lacks from the original disk (IPF), via dump's raw tracks.

  sh tools/disk/build_dump.sh
  tools/disk/dump NewZealandStory.ipf TRACKDIR
  python3 tools/disk/ipf_extract.py TRACKDIR [--adf GAME_TRACKS.adf] [--out IPF_DECODED.adf]

Every track except track 1 is AmigaDOS MFM (11 sectors, $4489 sync, checksums valid). Writes:
  disk/files/t000_protection_loader.bin  track 0 bytes $400-$15FF: Rob Northen's protection
                                         loader, read by the bootblock to $60000 (blank in the
                                         game-tracks ADF)
  disk/files/t001_copylock_track.mfm     track 1 as raw MFM: the Copylock track (not AmigaDOS;
                                         its sync words $8914, $A245, $8912, $448A ...)
and with --out an ADF of every AmigaDOS track (track 1 left blank). With --adf, compares each
track with the game-tracks ADF (they agree on tracks 2-159; track 0 differs only by the loader).
"""
import argparse, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from ados import ados_track
from mfm import syncstats

T = 5632


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('tracks')
    ap.add_argument('--adf')
    ap.add_argument('--out')
    a = ap.parse_args()
    img = bytearray(160 * T)
    bad = []
    for t in range(160):
        fn = os.path.join(a.tracks, f't{t:03d}.bin')
        if not os.path.getsize(fn):
            bad.append((t, 'empty')); continue
        o = ados_track(fn)
        good = [s for s in range(11) if s in o and o[s][1] and o[s][2] == t]
        for s in good:
            img[t * T + s * 512:t * T + s * 512 + 512] = o[s][0]
        if len(good) != 11:
            bad.append((t, f'{len(good)} AmigaDOS sectors, syncs {dict(syncstats(fn))}'))
    for t, why in bad:
        print(f'  track {t}: {why}')
    print(f'{160 - len(bad)} AmigaDOS tracks decoded')
    files = os.path.join(ROOT, 'disk', 'files')
    open(os.path.join(files, 't000_protection_loader.bin'), 'wb').write(img[0x400:0x1600])
    open(os.path.join(files, 't001_copylock_track.mfm'), 'wb').write(open(os.path.join(a.tracks, 't001.bin'), 'rb').read())
    print('wrote disk/files/t000_protection_loader.bin, disk/files/t001_copylock_track.mfm')
    if a.adf:
        adf = open(a.adf, 'rb').read()
        diff = [t for t in range(160) if img[t * T:(t + 1) * T] != adf[t * T:(t + 1) * T]]
        print('differs from the game-tracks ADF on tracks:', diff)
    if a.out:
        open(a.out, 'wb').write(img)
        print('wrote', a.out)


if __name__ == '__main__':
    main()
