"""The title menu and the joystick's input settings (src/menu.s), in the study emulator.

  python3 enhanced/tools/test_menu.py

Each case runs the enhanced game from the start-up in original/tools/nzsemu with joystick moves
(the second button: "joy 2", POTGOR bit 14) and keys, and checks the menu's state (MenuPage,
MenuSel, JoyMode, the sound test's MenuSong / MenuSfx, its tune playing: Music_Voices, its
effect: channel 3's AUD3LC), the cheat (the game's starting lives, l_04F46+2) and what the game reads
from the joystick ($63DB0: bit 2 up, bit 7 fire). Writes the title's three pages as pictures to
enhanced/build/test_menu/.
"""
import os, struct, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))
sys.path.insert(0, HERE)
sys.path.append(os.path.join(ORIG, 'tools'))
import build_disk                                           # noqa: E402

EMU = os.path.join(ORIG, 'tools', 'nzsemu', 'nzsemu')
OUT = os.path.join(ENH, 'build', 'test_menu')
LIVES = 0x4F48
JOY = 0x63DB1                       # the low byte of the game's joystick word
CHEAT = 'MOTHERFUCKENKIWIBASTARD'
RAW = dict(Q=0x10, W=0x11, E=0x12, R=0x13, T=0x14, Y=0x15, U=0x16, I=0x17, O=0x18, P=0x19, A=0x20,
           S=0x21, D=0x22, F=0x23, G=0x24, H=0x25, J=0x26, K=0x27, L=0x28, Z=0x31, X=0x32, C=0x33,
           V=0x34, B=0x35, N=0x36, M=0x37)


def tap(d):
    return f'joy {d}\nframes 3\njoy\nframes 3\n'


class Run:
    def __init__(self, syms, tmp):
        self.syms, self.tmp, self.n = syms, tmp, 0

    def __call__(self, script):
        self.n += 1
        p = os.path.join(self.tmp, f'r{self.n}')
        open(p + '.txt', 'w').write(script + f'snap {p}\n')
        out = subprocess.run([EMU, os.path.join(ENH, 'build', 'nzs_game.bin'), os.path.join(ORIG, 'disk', 'files', 'tracks'),
                              p + '.txt'], check=True, capture_output=True, text=True).stdout
        m = open(p + '.mem', 'rb').read()
        w = lambda a: struct.unpack_from('>H', m, a)[0]
        regs = open(p + '.regs', 'rb').read()
        return dict(page=w(self.syms['MenuPage']), sel=w(self.syms['MenuSel']), mode=w(self.syms['JoyMode']),
                    lives=w(LIVES), joy=m[JOY], frames=int(out.strip().splitlines()[-1].split()[1].rstrip(',')),
                    song=w(self.syms['MenuSong']), sfx=w(self.syms['MenuSfx']),
                    voices=w(self.syms['Music_Voices']),
                    aud3=struct.unpack_from('>L', regs, 0xD0)[0] & 0x7FFFE, prefix=p)


def main():
    syms = build_disk.symbols(os.path.join(ENH, 'build', 'nzs_game.lst'))
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(dir=os.path.join(ENH, 'build'))
    run = Run(syms, tmp)
    ok = True

    def check(cond, what):
        nonlocal ok
        print(('  ok   ' if cond else '  FAIL ') + what)
        ok &= bool(cond)
    title = 'frames 150\n'
    r = run(title)
    check(r['page'] == 0 and r['sel'] == 0 and r['mode'] == 0 and r['lives'] == 3, 'the title: START GAME chosen, jump on up, no cheat')
    import display
    display.render(*display.load(r['prefix'])).save(os.path.join(OUT, 'title.png'))
    r = run(title + tap('f') + 'until 0x40F8 600\n')
    check(r['frames'] < 150 + 12 + 600, 'START GAME: fire starts a game')
    r = run(title + tap('d'))
    check(r['page'] == 0 and r['sel'] == 1, 'down: OPTIONS')
    r = run(title + tap('u'))
    check(r['sel'] == 1, 'up from the first: round to the last')
    opts = title + tap('d') + tap('f')
    r = run(opts)
    check(r['page'] == 1 and r['sel'] == 0, 'fire on OPTIONS: the options page, INPUT chosen')
    display.render(*display.load(r['prefix'])).save(os.path.join(OUT, 'options.png'))
    r = run(opts + tap('r'))
    check(r['mode'] == 1, 'INPUT, right: jump on button 2')
    r = run(opts + tap('r') + tap('r'))
    check(r['mode'] == 2, 'INPUT, right again: jump 1 fire 2')
    r = run(opts + tap('r') + tap('r') + tap('f'))
    check(r['mode'] == 0, 'INPUT, fire: round to jump on up')
    r = run(opts + tap('l'))
    check(r['mode'] == 2, 'INPUT, left: back round to jump 1 fire 2')
    r = run(opts + tap('d') + tap('f'))
    check(r['sel'] == 1 and r['lives'] == 1000, 'CHEAT, fire: on (1,000 lives)')
    r = run(opts + tap('d') + tap('f') + tap('r'))
    check(r['lives'] == 3, 'CHEAT, right: off')
    r = run(opts + tap('d') * 3 + tap('f'))
    check(r['page'] == 0 and r['sel'] == 1, 'EXIT: the title, OPTIONS chosen')
    snd = opts + tap('d') * 2 + tap('f')
    r = run(snd)
    check(r['page'] == 2 and r['sel'] == 0 and r['song'] == 1, 'SOUND TEST: its page, MUSIC 01 chosen')
    display.render(*display.load(r['prefix'])).save(os.path.join(OUT, 'sound.png'))
    r = run(snd + tap('r') + tap('r'))
    check(r['song'] == 3, 'MUSIC, right twice: 03')
    r = run(snd + tap('l'))
    check(r['song'] == 12, 'MUSIC, left from 01: round to 12')
    r = run(snd + tap('r') + tap('f') + 'frames 20\n')
    check(r['voices'] != 0, 'MUSIC, fire: the tune plays (Music_Voices)')
    r = run(snd + tap('r') + tap('f') + 'frames 20\n' + tap('d') * 2 + tap('f') + 'frames 10\n')
    check(r['voices'] == 0, 'MUSIC OFF: it stops')
    r = run(snd + tap('d') + tap('r') * 2 + tap('f') + 'frames 2\n')
    check(r['sfx'] == 2 and 0x17F84 < r['aud3'] < 0x17F84 + 1060, 'EFFECT 03 (KIWI SHOT), fire: channel 3 plays it')
    r = run(snd + tap('d') + tap('l'))
    check(r['sfx'] == 11, 'EFFECT, left from 01: round to 12')
    r = run(snd + tap('r') + tap('f') + 'frames 20\n' + tap('u') + tap('f') + 'frames 10\n')
    check(r['page'] == 1 and r['sel'] == 2 and r['voices'] == 0, 'EXIT: the options page, SOUND TEST chosen, the tune stopped')
    r = run(snd + 'until 0x45FC 3000\n')
    check(r['frames'] >= 150 + 3000 and r['page'] == 2, 'the sound test does not time out')
    r = run(title + 'until 0x45FC 3000\n')
    check(r['frames'] < 150 + 3000, 'the title times out to the attract sequence')
    r = run(opts + 'until 0x45FC 3000\n')
    check(r['frames'] >= 150 + 3000 and r['page'] == 1, 'the options page does not time out')
    r = run(title + ''.join(f'key {RAW[c]:x}\nframes 12\n' for c in CHEAT))
    check(r['lives'] == 1000, 'the typed cheat code still works')
    r = run(opts + ''.join(f'key {RAW[c]:x}\nframes 12\n' for c in CHEAT))
    check(r['lives'] == 1000 and r['page'] == 1, 'typed on the options page too')
    game = tap('f') + 'until 0x40F8 600\nframes 100\n'
    for mode, cases in ((0, (('u', 1, 0), ('2', 0, 0), ('f', 0, 1))),
                        (1, (('u', 0, 0), ('2', 1, 0), ('f', 0, 1))),
                        (2, (('u', 0, 0), ('f', 1, 0), ('2', 0, 1)))):
        set_mode = opts + tap('r') * mode + tap('d') * 3 + tap('f') + tap('u') if mode else title
        for hold, up, fire in cases:
            r = run(set_mode + game + f'joy {hold}\nframes 4\n')
            check(r['mode'] == mode and bool(r['joy'] & 4) == bool(up) and bool(r['joy'] & 0x80) == bool(fire),
                  f'in play, input {mode}: {dict(u="up", f="button 1")[hold] if hold != "2" else "button 2"} -> '
                  + ('up (jump)' if up else 'fire' if fire else 'nothing'))
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    os.rmdir(tmp)
    print('all as expected' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
