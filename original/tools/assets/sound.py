"""The sound: Jonathan Dunn's music driver ($E800-$F36D) and its data, and the samples.

  python3 tools/assets/sound.py OUTDIR

Writes OUTDIR/samples/NAME.iff (each embedded IFF 8SVX file, byte for byte) and NAME.wav,
OUTDIR/songs.txt (every song decoded) and OUTDIR/sound.json (the parsed data).

The driver (jump table at $E800: +0 init, +4 stop, +8 start a song as music, +C play one frame
- called from the vertical blank; $EA1C starts one at the lower priority) plays up to 3 voices
(channels 0-2: channel 3 is the game's sample player, $56A8). Its data:

  $F36E  periods: 24 words, two octaves
  $F39E  instruments, 16 bytes: base note.w, sample start.l, length (words).w, repeat start.l,
         repeat length (words).w, fixed pitch.w (no transposing). Instrument 0 is a short
         silent loop; 1-6 are filled at init ($F10E) from the IFF 8SVX files listed at $F406
         (offset.w from the entry, base note.w, fixed.w; 0 ends)
  $15794 arpeggios (dc.w offsets from each entry): frames a step.b, steps.b, then a note offset
         (signed) per step, added to the note in turn and repeated
  $157A2 volume envelopes (dc.w offsets from each entry): segments of 2 bytes - n > 0, d: for n
         frames add d (signed) to the volume each frame; n < 0, b: for -n frames add +-1 (the
         sign of b) every |b| frames; 0, 0: the end; 0, r: hold until the note has |r| frames
         left (the release)
  (The envelope and arpeggio entries overlap each other in memory, sharing bytes.)
  $157D0 songs, 8 bytes each (12): for each of 3 voices an offset (from the word) to its
         order list, 0 = voice unused; then a word
  $15830 patterns (dc.w offsets from each entry)

An order list: bytes below $80 play that pattern; $80 ends (loops to the $81 point if one was
set, otherwise the voice stops); $81 sets the loop point; $82 nn sets the transpose (added to
notes); $83 nn plays the next pattern nn times.

A pattern: a byte below $80 is a note (minus the instrument's base note it indexes the
periods), followed by its duration in frames unless a fixed duration is set; commands:
"""
import json, os, struct, sys, wave
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from amiga_gfx import program, END

PERIODS, INSTR, INIT_LIST = 0xF36E, 0xF39E, 0xF406
ENVELOPES, ARPS, SONGS, PATTERNS = 0x15794, 0x157A2, 0x157D0, 0x15830
NSONGS = 12

# pattern commands: name, argument bytes
COMMANDS = {
    0x80: ('end', 0), 0x81: ('loop_point', 0), 0x82: ('nop82', 0), 0x83: ('nop83', 0),
    0x84: ('fixed_duration', 1), 0x85: ('note_durations', 0), 0x86: ('wait256', 0), 0x87: ('rest', 0),  # rest: + duration
    0x88: ('slide', 2), 0x89: ('note_offset', 2), 0x8A: ('note_offset_off', 0),
    0x8B: ('vibrato', 3), 0x8C: ('vibrato_off', 0), 0x8D: ('arpeggio', 1), 0x8E: ('arpeggio_off', 0),
    0x8F: ('volume_envelope', 1), 0x90: ('instrument', 1),
}
NOTE_NAMES = ['C-', 'C#', 'D-', 'D#', 'E-', 'F-', 'F#', 'G-', 'G#', 'A-', 'A#', 'B-']
__doc__ += ''.join(f'  ${k:02X} {n}' + (f' ({a} byte{"s" if a > 1 else ""})' if a else '') + '\n'
                   for k, (n, a) in COMMANDS.items())


def w(mem, a): return struct.unpack_from('>H', mem, a)[0]
def sw(mem, a): return struct.unpack_from('>h', mem, a)[0]
def note_name(n): return f'{NOTE_NAMES[n % 12]}{n // 12}'


def iff_files(mem):
    """every embedded IFF 8SVX: (address, name, bytes, vhdr dict)"""
    out = []
    a = 0x400
    data = bytes(mem[:END])
    while True:
        a = data.find(b'FORM', a)
        if a < 0:
            break
        ln = struct.unpack_from('>L', data, a + 4)[0]
        if data[a + 8:a + 12] == b'8SVX' and ln < 0x10000:
            blob = data[a:a + 8 + ln]
            info, name, body = {}, None, None
            p = a + 12
            while p < a + 8 + ln:
                cid, cl = data[p:p + 4], struct.unpack_from('>L', data, p + 4)[0]
                c = data[p + 8:p + 8 + cl]
                if cid == b'VHDR':
                    one, rep, spc, rate, octs, comp, vol = struct.unpack('>LLLHBBL', c[:20])
                    info = dict(oneshot=one, repeat=rep, rate=rate, octaves=octs, volume=vol / 65536)
                elif cid == b'NAME':
                    name = c.split(b'\0')[0].decode('latin-1')
                    name = name[:-4] if name.lower().endswith('.iff') else name   # the file name as saved
                elif cid == b'BODY':
                    body = c
                p += 8 + cl + (cl & 1)
            out.append(dict(addr=a, name=name or f'sample_{a:05X}', iff=blob, body=body, vhdr=info))
            a += 8 + ln
        else:
            a += 4
    return out


def write_wav(path, body, rate):
    with wave.open(path, 'wb') as f:
        f.setnchannels(1); f.setsampwidth(1); f.setframerate(rate)
        f.writeframes(bytes((b + 128) & 0xFF for b in body))       # 8SVX is signed, WAV 8-bit unsigned


def table(mem, base, n):
    return [base + 2 * k + sw(mem, base + 2 * k) for k in range(n)]


def decode_stream(mem, a, limit=4000):
    """a pattern: [(addr, text)] until $80"""
    out, fixed = [], False
    for _ in range(limit):
        b = mem[a]
        if b < 0x80:
            if fixed:
                out.append((a, note_name(b))); a += 1
            else:
                out.append((a, f'{note_name(b)} {mem[a + 1]}')); a += 2
            continue
        name, n = COMMANDS.get(b, (f'cmd{b:02X}', 0))
        if b == 0x87 and not fixed:                    # a rest has a duration, as a note
            n = 1
        args = list(mem[a + 1:a + 1 + n])
        out.append((a, name + ('' if not args else ' ' + ','.join(str(x) for x in args))))
        if b == 0x84: fixed = True
        if b == 0x85: fixed = False
        a += 1 + n
        if b == 0x80:
            break
    return out


def decode_order(mem, a, limit=400):
    out, pats = [], []
    for _ in range(limit):
        b = mem[a]
        if b < 0x80:
            out.append(f'P{b}'); pats.append(b); a += 1
        elif b == 0x80:
            out.append('end'); break
        elif b == 0x81:
            out.append('loop'); a += 1
        elif b in (0x82, 0x83):
            out.append(('transpose ' if b == 0x82 else 'repeat ') + str(struct.unpack('b', bytes([mem[a + 1]]))[0])); a += 2
        else:
            out.append(f'?{b:02X}'); a += 1
    return out, pats


def main():
    out = sys.argv[1]
    mem = program()
    os.makedirs(os.path.join(out, 'samples'), exist_ok=True)
    samples = iff_files(mem)
    for s in samples:
        open(os.path.join(out, 'samples', s['name'] + '.iff'), 'wb').write(s['iff'])
        write_wav(os.path.join(out, 'samples', s['name'] + '.wav'), s['body'], s['vhdr'].get('rate') or 8363)
    # instruments (as the init makes them)
    instr = []
    k = 0
    while w(mem, INIT_LIST + 6 * k):
        off, base, fixed = struct.unpack_from('>hHH', mem, INIT_LIST + 6 * k)
        form = INIT_LIST + 6 * k + off
        nm = next((s['name'] for s in samples if s['addr'] == form), '?')
        instr.append(dict(number=k + 1, sample=nm, base_note=base, base_name=note_name(base), fixed=bool(fixed), form=form))
        k += 1
    periods = [w(mem, PERIODS + 2 * i) for i in range(24)]
    songs, used = [], set()
    for s in range(NSONGS):
        e = SONGS + 8 * s
        voices = []
        for v in range(3):
            o = w(mem, e + 2 * v)
            if not o:
                voices.append(None); continue
            order, pats = decode_order(mem, e + 2 * v + o)
            used |= set(pats)
            voices.append(dict(order_list=e + 2 * v + o, order=order))
        songs.append(dict(number=s + 1, voices=voices, word=w(mem, e + 6)))
    npat = max(used) + 1
    pat_addr = table(mem, PATTERNS, npat)
    pats = {p: decode_stream(mem, pat_addr[p]) for p in sorted(used)}
    # the tables are as long as the highest number the patterns use
    n_arp = 1 + max([int(t.split()[1]) for ev in pats.values() for a, t in ev if t.startswith('arpeggio ')] or [-1])
    n_env = 1 + max([int(t.split()[1]) for ev in pats.values() for a, t in ev if t.startswith('volume_envelope ')] or [-1])
    sb = lambda x: x - 256 if x > 127 else x
    arps = []
    for a in table(mem, ENVELOPES, n_arp):
        speed, steps = mem[a], mem[a + 1]
        arps.append((a, f'{speed} frames a step, offsets {[sb(x) for x in mem[a + 2:a + 2 + steps]]}'))
    envs = []
    for a in table(mem, ARPS, n_env):
        segs, p = [], a
        for _ in range(40):
            n, v = sb(mem[p]), sb(mem[p + 1]); p += 2
            if n > 0: segs.append(f'{n}x{v:+d}')
            elif n < 0: segs.append(f'{-n}:{"+" if v > 0 else "-"}1/{abs(v)}')
            else:
                segs.append('end' if v == 0 else f'release {abs(v)}'); break
        envs.append((a, ' '.join(segs)))

    L = ['The New Zealand Story - the music and effect sequences (tools/assets/sound.py)',
         'Jonathan Dunn\'s driver ($E800); see the tool for the format.', '',
         'Instruments (from the IFF 8SVX files, at init):']
    L += [f'  {i["number"]}: {i["sample"]:<14} base note {i["base_name"]}' + (' (fixed pitch)' if i['fixed'] else '') for i in instr]
    L += ['', 'Periods (note - base note): ' + ' '.join(f'{p}' for p in periods), '']
    L += ['Arpeggios ($15794):'] + [f'  {k}: ${a:05X} {d}' for k, (a, d) in enumerate(arps)]
    L += ['', 'Volume envelopes ($157A2): NxD = N frames adding D; N:+1/B = N frames, +1 every B; release R = hold until R frames are left']
    L += [f'  {k}: ${a:05X} {d}' for k, (a, d) in enumerate(envs)]
    L += ['']
    for s in songs:
        L.append(f'Song {s["number"]} (word ${s["word"]:04X}):')
        for v, vo in enumerate(s['voices']):
            L.append(f'  voice {v}: ' + ('-' if vo is None else f'${vo["order_list"]:05X}: ' + ' '.join(vo['order'])))
    L.append('')
    for p, ev in pats.items():
        L.append(f'Pattern {p} (${pat_addr[p]:05X}):')
        line = []
        for a, t in ev:
            line.append(t)
            if len(line) == 8:
                L.append('    ' + ' | '.join(line)); line = []
        if line:
            L.append('    ' + ' | '.join(line))
    open(os.path.join(out, 'songs.txt'), 'w').write('\n'.join(L) + '\n')
    json.dump(dict(samples=[dict(name=s['name'], addr=s['addr'], bytes=len(s['iff']), **s['vhdr']) for s in samples],
                   instruments=instr, periods=periods, songs=songs,
                   patterns={str(p): [dict(addr=a, event=t) for a, t in ev] for p, ev in pats.items()}),
              open(os.path.join(out, 'sound.json'), 'w'), indent=1)
    print(f'{len(samples)} samples, {len(instr)} instruments, {len(songs)} songs, {len(pats)} patterns -> {out}')


if __name__ == '__main__':
    main()
