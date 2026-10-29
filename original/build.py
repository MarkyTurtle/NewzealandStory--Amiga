"""Assemble the original game's four sources and check them against the original disk's files,
byte for byte (SHA-1); then pack the main program and check it against tracks 94-143.
The same as build.sh, for any system with Python 3 and vasmm68k_mot on the PATH (Windows too).

  python original/build.py
"""
import hashlib, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = [                                   # (source, output, SHA-1 of the original)
    ('nzs_main.s', 'main.bin', '74d3f9924c56270c5fc2a4231be035c9157851a1'),
    ('nzs_loader.s', 'loader.bin', '853592064e08f7ee00a63c6a308e3d24777dec29'),
    ('nzs_boot.s', 'boot.bin', '2b0cb038ff946d40f6942dc7e970bee83b3fa07f'),
    ('nzs_boot2.s', 'boot2.bin', 'cb653d3d40abff2489a51a13e55d315a316c847f'),
]
PACKED = ('main_packed.bin', '068da7113d7db1746161301524898e843a58e787')


def check(name, want):
    got = hashlib.sha1(open(os.path.join(HERE, name), 'rb').read()).hexdigest()
    print(f'{name}: {"OK" if got == want else f"MISMATCH ({got})"}')
    return got == want


def main():
    ok = True
    for src, out, sha in SOURCES:
        r = subprocess.run(['vasmm68k_mot', '-Fbin', '-m68000', '-no-opt', '-quiet', '-o', out, src],
                           cwd=HERE, capture_output=True, text=True)
        if r.returncode:
            sys.stdout.write(r.stdout + r.stderr)
            print(f'{src}: vasm failed')
            return False
        ok &= check(out, sha)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'tools', 'disk', 'pack.py'), 'pack', 'main.bin', PACKED[0]],
                       cwd=HERE, capture_output=True, text=True)
    if r.returncode:
        sys.stdout.write(r.stdout + r.stderr)
        return False
    return check(*PACKED) and ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
