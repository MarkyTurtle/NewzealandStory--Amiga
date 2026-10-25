"""Pack / unpack the main program in the format the track 90 loader unpacks (routine at $7671E).

  python3 tools/disk/pack.py pack   main.bin  main_packed.bin
  python3 tools/disk/pack.py unpack main_packed.bin main.bin
  python3 tools/disk/pack.py check  [main.bin] [packed]   (default: bin/main.bin vs disk/files/t094-143_main_packed.bin)

Format:
  long  unpacked length - 1
  long  packed length - 1, where the packed length counts this 8-byte header (so the loader's
        move-up copies 8 bytes past the stream; the packer pads them with zeros)
  byte  escape byte: the least frequent byte value in the data (lowest value on a tie)
  then  escape, value, count-1   a run of count (1-256) copies of value
        any other byte           itself
Runs of 3 or more are encoded, longer runs split at 256; a literal escape byte is a run of 1.
The original packer never extends a run into the last byte of the data (it ends the program's
final run of zeros one byte early and writes that byte as a literal), so this one doesn't either.
Packing bin/main.bin this way reproduces the original tracks 94-143 byte for byte.
"""
import os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))


def pack(data):
    cnt = Counter(data)
    esc = min(range(256), key=lambda b: (cnt[b], b))
    out = bytearray([esc])
    i, n = 0, len(data)
    while i < n:
        v = data[i]
        r = 1
        while i + r < n - 1 and r < 256 and data[i + r] == v:     # (sic) the last byte never joins a run
            r += 1
        if v == esc or r >= 3:
            out += bytes([esc, v, r - 1])
            i += r
        else:
            out.append(v)
            i += 1
    hdr = (n - 1).to_bytes(4, 'big') + (len(out) + 8 - 1).to_bytes(4, 'big')
    return hdr + bytes(out) + bytes(8)


def unpack(packed):
    n = int.from_bytes(packed[:4], 'big') + 1
    src = packed[8:]
    esc, i, out = src[0], 1, bytearray()
    while len(out) < n:
        b = src[i]; i += 1
        if b != esc:
            out.append(b)
        else:
            v, c = src[i], src[i + 1]; i += 2
            out += bytes([v]) * (c + 1)
    return bytes(out)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'pack':
        open(sys.argv[3], 'wb').write(pack(open(sys.argv[2], 'rb').read()))
    elif cmd == 'unpack':
        open(sys.argv[3], 'wb').write(unpack(open(sys.argv[2], 'rb').read()))
    elif cmd == 'check':
        a = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, 'bin/main.bin')
        b = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, 'disk/files/t094-143_main_packed.bin')
        data, want = open(a, 'rb').read(), open(b, 'rb').read()
        got = pack(data)
        ok = got == want and unpack(got) == data
        print(f'{os.path.basename(a)} -> {len(got)} bytes packed: ' +
              ('identical to ' if ok else 'DIFFERENT from ') + os.path.basename(b))
        sys.exit(0 if ok else 1)
    else:
        raise SystemExit(__doc__)


if __name__ == '__main__':
    main()
