"""Render a nzsemu audio log ("cycle reg value": writes to the audio registers and DMACON) to a
stereo WAV, as Paula plays it: per channel, when its DMA is switched on the location and length
are latched and the sample words are played, one byte per period (in colour clocks); at the end
of the block the location and length are latched again from the registers (the loop). Channels
0 and 3 left, 1 and 2 right. PAL clocks; no filtering.

  python3 tools/assets/paula.py AUDIO_LOG MEMORY OUT.wav
  (MEMORY: the program image or a snapshot, where the samples are)
"""
import struct, sys, wave

CPU = 7093790
COLOR = 3546895
RATE = 44100


def render(events, mem, seconds=None, rate=RATE):
    end = events[-1][0] if events else 0
    total = int((end / CPU + 0.5) * rate) if seconds is None else int(seconds * rate)
    out = [[0.0] * total, [0.0] * total]
    regs = [dict(lc=0, len=1, per=200, vol=0) for _ in range(4)]
    dma = 0x200                               # DMAEN: the game keeps it on; the log has only the driver's writes
    play = [None] * 4                         # per channel: [pointer, words left, phase]
    ei = 0
    for i in range(total):
        cyc = i * CPU / rate
        while ei < len(events) and events[ei][0] <= cyc:
            _, r, v = events[ei]; ei += 1
            if r == 0x096:
                old = dma
                dma = dma | (v & 0x7FFF) if v & 0x8000 else dma & ~v
                for ch in range(4):
                    on = dma & 0x200 and dma & (1 << ch)
                    was = old & 0x200 and old & (1 << ch)
                    if on and not was:
                        play[ch] = [regs[ch]['lc'], regs[ch]['len'] or 0x10000, 0.0]
                    elif not on:
                        play[ch] = None
            else:
                ch, k = (r - 0xA0) // 16, (r - 0xA0) % 16
                if ch > 3:
                    continue
                g = regs[ch]
                if k == 0: g['lc'] = (g['lc'] & 0xFFFF) | (v << 16)
                elif k == 2: g['lc'] = (g['lc'] & 0xFFFF0000) | v
                elif k == 4: g['len'] = v
                elif k == 6: g['per'] = max(v, 124)
                elif k == 8: g['vol'] = min(v & 0x7F, 64)
        for ch in range(4):
            p = play[ch]
            if not p:
                continue
            g = regs[ch]
            pos = int(p[2])                        # byte within the block
            a = (p[0] + pos) & 0x7FFFF
            s = mem[a] - 256 if mem[a] > 127 else mem[a]
            out[0 if ch in (0, 3) else 1][i] += s * g['vol'] / 64 / 128 / 2
            p[2] += COLOR / g['per'] / rate
            if p[2] >= p[1] * 2:                    # the block played: latch again (the loop)
                p[2] -= p[1] * 2
                p[0], p[1] = g['lc'], g['len'] or 0x10000
    return out


def write(path, out, rate=RATE):
    with wave.open(path, 'wb') as f:
        f.setnchannels(2); f.setsampwidth(2); f.setframerate(rate)
        f.writeframes(b''.join(struct.pack('<hh', max(-32767, min(32767, int(l * 32767))),
                                           max(-32767, min(32767, int(r * 32767)))) for l, r in zip(*out)))


def load(log):
    ev = []
    for ln in open(log):
        c, r, v = ln.split()
        ev.append((int(c), int(r, 16), int(v, 16)))
    return ev


if __name__ == '__main__':
    log, memf, outf = sys.argv[1:4]
    mem = open(memf, 'rb').read()
    if len(mem) < 0x80000:                         # the program file (loaded at $400, block 1 4 lower)
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from amiga_gfx import program
        mem = program()
    write(outf, render(load(log), mem))
