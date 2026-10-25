"""Merge nzsemu coverage bitmaps (the script's "cover FILE": 1 bit per address, set where an
instruction started) into the disassembler's code hints, tools/disasm/main_coverage.txt.

  python3 tools/nzsemu/coverage.py COVER.bin [COVER.bin ...] > tools/disasm/main_coverage.txt
  python3 tools/nzsemu/coverage.py --run OUTDIR > tools/disasm/main_coverage.txt

Only addresses inside the program ($400 up to its end) are kept. --run plays the three sessions
the hints came from (the attract mode; 12 games with a random joystick; each of the 20 levels
started in turn - the level number poked at $641C0 (x 16) and 5 lives at $641D2 as the level
starts at $40F8), leaving their snapshots (f300, f900, play1, lvlNN) and logs in OUTDIR.
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ORIG = os.path.normpath(os.path.join(HERE, '..', '..'))
FIRE = 'joy f\nframes 8\njoy\n'


def scripts(o):
    s1 = f'log {o}/log.txt\nframes 300\nsnap {o}/f300\nframes 600\nsnap {o}/f900\ncover {o}/c1.bin\n'
    s2 = f'log {o}/log.txt\nframes 200\n'
    for g in range(1, 13):
        s2 += FIRE + 'frames 60\n' + FIRE + f'frames 100\nrandom 2500 {g}\n'
        if g == 4:
            s2 += f'snap {o}/play1\n'
    s2 += f'cover {o}/c2.bin\n'
    s3 = f'log {o}/log.txt\nframes 200\n' + FIRE
    for lv in range(20):
        s3 += (f'until 0x40F8 60000\npoke 0x641C0 {lv * 16} w\npoke 0x641D2 5 w\nframes 120\n' + FIRE +
               f'frames 250\nsnap {o}/lvl{lv:02d}\nrandom 1500 {11 + lv}\n')
    s3 += f'until 0x40F8 60000\ncover {o}/c3.bin\n'
    return [s1, s2, s3]


def run(o):
    os.makedirs(o, exist_ok=True)
    out = []
    for k, text in enumerate(scripts(os.path.abspath(o)), 1):
        sp = os.path.join(o, f's{k}.txt')
        open(sp, 'w').write(text)
        subprocess.run([os.path.join(HERE, 'nzsemu'), os.path.join(ORIG, 'bin', 'main.bin'),
                        os.path.join(ORIG, 'disk', 'files', 'tracks'), sp], check=True, stdout=subprocess.DEVNULL)
        out.append(os.path.join(o, f'c{k}.bin'))
    return out

START, END = 0x400, 0x52FA7

HEADER = '''# Instruction addresses seen executing in tools/nzsemu (attract mode, the intro, levels played
# with a random joystick): code hints for the tracer. Written by tools/nzsemu/coverage.py.'''


def main():
    bits = bytearray(0x10000)
    files = run(sys.argv[2]) if sys.argv[1] == '--run' else sys.argv[1:]
    for f in files:
        for i, b in enumerate(open(f, 'rb').read()[:len(bits)]):
            bits[i] |= b
    addrs = [a for a in range(START, END) if bits[a >> 3] >> (a & 7) & 1]
    print(HEADER)
    for k in range(0, len(addrs), 12):
        print(' '.join(f'{a:05X}' for a in addrs[k:k + 12]))


if __name__ == '__main__':
    main()
