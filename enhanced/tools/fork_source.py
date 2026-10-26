"""Made enhanced/src/nzs_game.s once (October 2026), when the enhanced game's source started to be
edited by hand: from original/nzs_main.s with

  * TrackWrite / TrackRead ($A04-$D87) replaced by `include "diskload.s"` (the AmigaDOS disk's
    disk reading), as enhanced/tools/make_game.py used to do on every build;
  * the debug monitor removed from block 1 - its command loop, commands, screen output, the
    68000 disassembler and the original trackloader's internals (about 9 KB, none of it used by
    the game: the start-up and every exception go straight to GameStart through sub_0158C) -
    keeping the jump table, Init, the motor-off routine, the keyboard interrupt and its key map,
    the joystick and key routines and block 1's variables; the exceptions that showed the
    monitor (ErrorTrap, UnusedInterrupt) restart the game instead (sub_0158C), with COLOR00 red;
  * an "Enhanced code" section at the end of block 1, padded so that block 1 keeps its size
    and nothing after it moves (block 2 is checked label by label by build_disk.py).

Kept for the record; running it again overwrites the hand-edited source.

  python3 enhanced/tools/fork_source.py OUT.s
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ENH = os.path.normpath(os.path.join(HERE, '..'))
ORIG = os.path.normpath(os.path.join(ENH, '..', 'original'))

# block 1 line ranges removed: [from the line starting with A, to the line starting with B)
REMOVE = [
    ('l_00644:', 'sub_009DA:'),            # the monitor's command loop, its commands
    ('dat_00D88:', 'sub_011AE:'),          # the original trackloader's internals, monitor output
    ('sub_01202:', 'sub_01260:'),          # the monitor's display set-up
    ('sub_01268:', 'Level2_Ports:'),       # monitor
    ('sub_01502:', 'sub_0158C:'),          # monitor commands (sub_0157A falls into sub_0158C)
    ('sub_015BC:', 'ReadJoystick:'),       # monitor, disassembler, its exception messages
    ('sub_02B32:', 'dat_02F9E:'),          # monitor text output and font
]


def fork(out):
    src = open(os.path.join(ORIG, 'nzs_main.s')).read().split('\n')
    find = lambda start, frm=0: next(i for i in range(frm, len(src)) if src[i].startswith(start))
    # diskload.s in place of TrackWrite / TrackRead
    s, e = find('TrackWrite:'), find('dat_00D88:')
    src[s:e] = [';' + '-' * 79,
                '; TrackWrite / TrackRead: the AmigaDOS disk\'s (diskload.s)',
                ';' + '-' * 79,
                '\tinclude\t"diskload.s"']
    for a, b in REMOVE:
        i, j = find(a), find(b)
        src[i:j] = ['; (removed: the debug monitor)']
    # the start-up: no monitor banner; DEL (the keyboard's $7F) restarts the game as before
    k = find('        lea.l   (dat_01A1C).l,a0')
    src[k] = '; (the monitor\'s banner was loaded here)'
    # sub_0157A fell into sub_0158C: keep the variables the kept code uses
    k = find('sub_0158C:')
    src[k:k] = ['dat_01578:', '\tdc.b\t$00,$00']
    # the exceptions that showed the monitor: restart the game with COLOR00 red
    k = find('ReadJoystick:')
    src[k:k] = ['UnusedInterrupt:', 'ErrorTrap:',
                '        move.w  #$f00,(CUSTOM+COLOR00).l        ; enhanced: the monitor is gone',
                '        st.b    (dat_01578).l',
                '        bra.w   sub_0158C                       ; restart the game (as every exception)']
    # the enhanced code: at the end of block 1, padded to keep its size
    k = find('Block1_End:')
    src[k:k] = [';' + '=' * 79,
                '; Enhanced code (block 1, in the space the debug monitor left)',
                ';' + '=' * 79,
                '\tinclude\t"enhanced.s"',
                '',
                '\tifgt\t*-$3210',
                '\tfail\tblock 1 is over its original size ($3210)',
                '\tendc',
                '\tdcb.b\t$3210-*,0']
    head = ['; The New Zealand Story - the enhanced game (enhanced/README.md).',
            '; Edited by hand since October 2026; made from original/nzs_main.s by',
            '; enhanced/tools/fork_source.py. Assembled by enhanced/tools/build_disk.py.', ';']
    open(out, 'w').write('\n'.join(head + src))


if __name__ == '__main__':
    fork(sys.argv[1])
