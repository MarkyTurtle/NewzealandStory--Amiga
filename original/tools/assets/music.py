"""Render every song of the music driver to a WAV, by running the driver itself in the emulator
(tools/nzsemu) and playing its register writes through a Paula model (paula.py).

  python3 tools/assets/music.py OUTDIR [SECONDS]

For each song n (1-12): init ($E800), start song n ($E808, d0 = n), then call the frame routine
($E80C) once a frame - as the vertical blank does - logging the audio registers. A song that
stops (every voice reached an $80 with no loop point) is trimmed at its end; one that loops is
rendered for SECONDS (default 75) and faded out over the last 3.
Needs the emulator built: tools/nzsemu/build.sh.
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paula

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, '..', '..'))
EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
FPS = 50


def render_song(n, seconds, tmp):
    log, mem = os.path.join(tmp, f'a{n}.txt'), os.path.join(tmp, f'm{n}')
    script = os.path.join(tmp, f's{n}.txt')
    with open(script, 'w') as f:
        f.write(f'poke 0xDFF096 0x8200 w\naudio {log}\ncall 0xE800\ncall 0xE808 {n}\nplay 0xE80C {seconds * FPS}\nsnap {mem}\n')
    subprocess.run([EMU, os.path.join(ORIG, 'bin', 'main.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), script],
                   check=True, stdout=subprocess.DEVNULL)
    ev = paula.load(log)
    image = open(mem + '.mem', 'rb').read()
    out = paula.render(ev, image, seconds=seconds)
    # trim the silence after the end; otherwise (still playing at the end) fade the last 3 seconds
    last = max((i for i in range(len(out[0])) if out[0][i] or out[1][i]), default=0)
    if last < len(out[0])- paula.RATE:            # silent for the last second: it ended
        end = min(len(out[0]), last + paula.RATE // 2)
        out = [c[:end] for c in out]
        looped = False
    else:
        fade = 3 * paula.RATE
        for c in out:
            for i in range(fade):
                c[-fade + i] *= 1 - i / fade
        looped = True
    return out, looped


def main():
    outdir = sys.argv[1]
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 75
    os.makedirs(outdir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(1, 13):
            out, looped = render_song(n, seconds, tmp)
            path = os.path.join(outdir, f'song{n:02d}.wav')
            paula.write(path, out)
            print(f'song {n:2}: {len(out[0]) / paula.RATE:5.1f} s{" (loops)" if looped else ""} -> {path}')


if __name__ == '__main__':
    main()
