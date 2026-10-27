"""The original's fly mode on F1 with the cheat on (enhanced.s: EnhCheatKeys calls sub_0900A).

  python3 enhanced/tools/test_fly.py

In the study emulator (original/tools/nzsemu), twice - with the cheat (the starting lives at
l_04F46+2 poked to 1,000, as typing MOTHERFUCKENKIWIBASTARD on the title does) and without:
a game started on level 1-1, F1 pressed, the joystick held up, F1 pressed again. With the cheat
the kiwi's handler must become sub_08FD4 (the fly mode) with his own kept at $5C(a6), he must
move up through the scenery, and F1 again must give his handler back; without it nothing must
change. (Up: the fly mode is not invulnerable - flying into an enemy kills him as usual, as on
1-1 a short way right of the start.)
"""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
KIWI = 0x643BA                      # the kiwi's object: x.w, y.w ... handler.l at $18
FLY = 0x8FD4                        # sub_08FD4
SAVED = 0x641B8 + 0x5C              # $5C(a6): his handler while he flies
F1 = 0x50


def run(cheat, tmp):
    tag = 'c' if cheat else 'n'
    s = 'frames 200\n'
    if cheat:
        s += 'poke 0x4F48 1000 w\n'
    s += ('joy f\nframes 8\njoy\nuntil 0x40F8 60000\nframes 250\n'
          f'snap {tmp}/{tag}a\nkey {F1:x}\nframes 16\nsnap {tmp}/{tag}b\n'
          f'joy u\nframes 24\njoy\nframes 4\nsnap {tmp}/{tag}c\n'
          f'key {F1:x}\nframes 16\nsnap {tmp}/{tag}d\n')
    p = os.path.join(tmp, tag + '.txt')
    open(p, 'w').write(s)
    subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'), p],
                   check=True, stdout=subprocess.DEVNULL)
    out = []
    for k in 'abcd':
        m = open(os.path.join(tmp, f'{tag}{k}.mem'), 'rb').read()
        x, y = struct.unpack_from('>hh', m, KIWI)
        out.append(dict(x=x, y=y, handler=struct.unpack_from('>L', m, KIWI + 0x18)[0],
                        saved=struct.unpack_from('>L', m, SAVED)[0],
                        lives=struct.unpack_from('>H', m, 0x641B8 + 0x1A)[0]))
    return out


def main():
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    ok = True

    def check(cond, what):
        nonlocal ok
        print(('  ok   ' if cond else '  FAIL ') + what)
        ok &= bool(cond)
    c = run(True, tmp)
    print('with the cheat:', [(s['x'], s['y'], hex(s['handler'])) for s in c], 'lives', c[0]['lives'])
    check(c[0]['lives'] == 1000, 'the game started with 1,000 lives')
    check(c[0]['handler'] != FLY, 'not flying before F1')
    check(c[1]['handler'] == FLY and c[1]['saved'] == c[0]['handler'], 'F1: flying, his handler kept')
    check(c[2]['handler'] == FLY and c[2]['x'] == c[1]['x'] and c[2]['y'] < c[1]['y'] - 40,
          'flying: up with the joystick, through the scenery')
    check(c[3]['handler'] != FLY and c[3]['saved'] == 0 and c[3]['y'] > c[2]['y'],
          'F1 again: his own handler back (and, in the air, he falls: sub_0915A)')
    n = run(False, tmp)
    print('without:', [(s['x'], s['y'], hex(s['handler'])) for s in n], 'lives', n[0]['lives'])
    check(n[0]['lives'] == 3, 'the game started with 3 lives')
    check(all(s['handler'] != FLY and s['saved'] == 0 for s in n), 'F1 does nothing')
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print('all as expected' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
