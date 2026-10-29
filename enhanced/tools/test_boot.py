"""Boot the AmigaDOS disk (build_disk.py: enhanced/build/nzs.adf) in an emulator: the bootblock
(src/boot_4489.s) from Kickstart's call to the game's entry at $400, with the 4489_byteloader
reading the disk through tools/floppy.py (from the Ghosts'n Goblins project).

Checks: the game unpacked at $400 (as build_disk.py assembled it, with BootDrive set to the
drive booted from) and the screen file at $70000 as on the disk; the screen decoded at $78000
exactly as the original's decoder (tools/disk/extract_files.py) decodes it; the colours, display
registers, copper list and DMA as the track 90 loader left them; d0 = a0 = $400; the drive used
is the one booted from; the motor left off. Then the game's Relocate is run, and its TrackRead
(src/diskload.s) called as the game calls it: the tracks it returns must be the original disk's,
from the drive booted from, with the registers kept; a track the disk does not have must give -1.
Writes enhanced/build/test_boot.png: the display rendered from the emulated memory
(original/tools/screen.py).

The machine's memory (exec's memory list, which the bootblock's MemDetect reads) is one of
MACHINES: the machine description must reach the extension module (src/ext.s), the track cache
must be set up in the largest memory beyond 512K of chip RAM, a level read twice must be read
from the disk once when it fits the cache, and the title's memory lines must say so.

The bootblock finds the boot drive by opening trackdisk.device's units; exec's OpenDevice is a
stub (a Python hook) that knows the drives connected. Cases: booted from DF0, DF1 and DF3, and
from a unit of another device (DF0 then).

  python3 enhanced/tools/test_boot.py [--random-start]     (the DMA starting at any sector)
"""
import os, struct, sys
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_M68000, UC_CPU_M68K_M68020, UC_M68K_REG_D3, UC_M68K_REG_D4, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A6,
                                UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_D1, UC_M68K_REG_D2,
                                UC_M68K_REG_SR, UC_M68K_REG_PC)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_disk, floppy
sys.path.insert(0, os.path.join(build_disk.ORIG, 'tools', 'disk'))
import pack                                             # noqa: E402
ORIG = build_disk.ORIG
sys.path.insert(0, os.path.join(ORIG, 'tools'))
sys.path.insert(0, os.path.join(ORIG, 'tools', 'disk'))
import extract_files                                    # noqa: E402  (decode_screen)

EXEC, BOOTBUF = 0x676, 0x20000
OPENDEVICE = 0x1000                     # exec's OpenDevice (EXEC - $1BC jumps here): a hook, then rts
DEVICE, NAME, BOOTREQ = 0x1100, 0x1200, 0x1300
UNITS = [0x1400 + 0x40 * n for n in range(4)]     # trackdisk's unit structures, DF0-DF3
FOREIGN = 0x1600                        # a unit of some other device
LOADER = (0x63100, 0x63500)             # where the loader runs (VHPOSR moves while it is here)
SYMS = build_disk.symbols(os.path.join(build_disk.OUT, 'nzs_game.lst'))   # the game's labels
GAME_LOADER = (SYMS['TrackWrite'], SYMS['LoadTable'])  # the game's TrackRead / byteloader (diskload.s)
GAME_HEADER = 0x426                     # the game's header (ext.i): 'NZSE', boot drive, machine
GAME_ENTRY = 0x4000                     # GameStart: Init has run (EnhInit: the cache, the title's lines)
STOP = 0x1F0                            # a return address that ends a call
READS = [(2, 5), (84, 5), (18, 1), (89, 1), (152, 2), (158, 2), (144, 5), (68, 1)]   # (track, count)
MISSING = [(0, 1), (1, 1), (100, 1), (89, 2)]
FILE_LEN = {}                           # (track, count): the level file's length (loadtable.i)
for _ln in open(os.path.join(build_disk.OUT, 'loadtable.i')):
    if _ln.startswith('\tdc.b\t') and ',' in _ln:
        _tn = tuple(int(x) for x in _ln.split()[1].split(','))
    elif _ln.startswith('\tdc.w\t') and '_tn' in globals():
        FILE_LEN[_tn] = int(_ln.split()[1]); del _tn


EXT_BASE = build_disk.EXT_BASE
MEMLIST = 0x2000                        # the memory headers exec lists (overwritten by the game later)
TRACK = 5632
# the one-blit BOB frames (src/frames.s): with room in the chip RAM above 512K, all of them from
# $80000, and the track cache after them
ONE_ALL = int(next(l.split()[2] for l in open(os.path.join(build_disk.OUT, 'frames.i')) if l.startswith('ONE_ALL')))
ONE_END = (0x80000 + ONE_ALL + 3) & ~3
# the level files (build_disk.py: level_files; diskload.s), all of them: LEVELS_BYTES
LEVELS = int(next(l.split()[2] for l in open(os.path.join(build_disk.OUT, 'loadtable.i')) if l.startswith('LEVELS_BYTES')))
LK = LEVELS // 1024
# name: [(lower, upper, attributes)] as exec lists them (MEMF_CHIP 2, MEMF_FAST 4), and what the
# extension module must make of it: (file cache kind, its base, its size, the title's two lines)
MACHINES = {
    'A500 512K': ([(0x400, 0x80000, 2)], (0, 0, 0, 'CHIP 512K  SLOW 0K  FAST 0K', 'NO FILE CACHE')),
    'A500 512K + 512K slow': ([(0xC00020, 0xC80000, 4), (0x400, 0x80000, 2)],
                              (2, 0xC00020, 0x80000 - 0x20, 'CHIP 512K  SLOW 512K  FAST 0K', f'FILE CACHE {LK}K IN SLOW RAM')),
    'A500+ 1MB chip (Kickstart 1.3 lists $FE800)': ([(0x400, 0xFE800, 2)],
                              (1, ONE_END, 0xFE800 - ONE_END, 'CHIP 1024K  SLOW 0K  FAST 0K',
                               f'FILE CACHE {(0xFE800 - ONE_END) // 1024}K OF {LK}K IN CHIP RAM')),
    'A500 512K + 512K slow + 2MB fast': ([(0x200000, 0x400000, 5), (0xC00020, 0xC80000, 4), (0x400, 0x80000, 2)],
                              (3, 0x200000, 0x200000, 'CHIP 512K  SLOW 512K  FAST 2048K', f'FILE CACHE {LK}K IN FAST RAM')),
    'A1200 (68020) 2MB chip': ([(0x400, 0x200000, 2)],
                              (1, ONE_END, 0x200000 - ONE_END, 'CHIP 2048K  SLOW 0K  FAST 0K', f'FILE CACHE {LK}K IN CHIP RAM')),
}
ATTN = {'A1200 (68020) 2MB chip': 0x0003}   # exec's AttnFlags (bit 0 68010, bit 1 68020); 0 for the rest


class Machine:
    def __init__(self, regions=(), attn=0):
        u = self.u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_M68020 if attn & 2 else UC_CPU_M68K_M68000)
        u.mem_map(0, 0x80000); u.mem_map(0xBFD000, 0x2000); u.mem_map(0xDFF000, 0x1000)
        for lo, hi, attr in regions:                        # memory beyond the first 512K of chip RAM
            lo = max(lo & ~0xFFF, 0x80000) if attr & 2 else lo & ~0xFFF
            if hi > lo:
                u.mem_map(lo, (hi - lo + 0xFFF) & ~0xFFF)
    def r8(self, a): return self.u.mem_read(a, 1)[0]
    def r16(self, a): return struct.unpack('>H', bytes(self.u.mem_read(a, 2)))[0]
    def r32(self, a): return struct.unpack('>L', bytes(self.u.mem_read(a, 4)))[0]
    def w8(self, a, v): self.u.mem_write(a, bytes([v & 0xFF]))
    def w16(self, a, v): self.u.mem_write(a, struct.pack('>H', v & 0xFFFF))
    def w32(self, a, v): self.u.mem_write(a, struct.pack('>L', v & 0xFFFFFFFF))


# 68020 control registers, through code (Unicorn's own access to CACR / VBR does not work): set the
# instruction cache on and the VBR to $7E000; read them into d3, d4. Run at $1C0, regs kept but d1-d4.
MOVEC_SET = '72014e7b1002243c0007e0004e7b2801'        # moveq #1,d1; movec d1,cacr; move.l #$7E000,d2; movec d2,vbr
MOVEC_GET = '4e7a30024e7a4801'                        # movec cacr,d3; movec vbr,d4


def movec(u, which):
    code = bytes.fromhex(globals()[which])
    keep = [u.reg_read(r) for r in (UC_M68K_REG_PC, UC_M68K_REG_SR, UC_M68K_REG_A7)]
    u.reg_write(UC_M68K_REG_SR, 0x2700)
    u.mem_write(0x1C0, code)
    u.emu_start(0x1C0, 0x1C0 + len(code))
    out = u.reg_read(UC_M68K_REG_D3), u.reg_read(UC_M68K_REG_D4)
    u.reg_write(UC_M68K_REG_SR, keep[1]); u.reg_write(UC_M68K_REG_A7, keep[2]); u.reg_write(UC_M68K_REG_PC, keep[0])
    return out


def memlist(w, regions, attn=0):
    """exec's MemList (ExecBase + $142) with a header per region; VBlankFrequency, AttnFlags"""
    w(EXEC + 0x212, '>B', 50); w(EXEC + 0x128, '>H', attn)
    nodes = [MEMLIST + 0x20 * k for k in range(len(regions))]
    w(EXEC + 0x142, '>LLL', nodes[0], 0, nodes[-1])           # lh_Head, lh_Tail, lh_TailPred
    for k, (lo, hi, attr) in enumerate(regions):
        succ = nodes[k + 1] if k + 1 < len(regions) else EXEC + 0x146
        w(nodes[k], '>LLBBLHLLL', succ, 0, 10, 0, 0, attr, 0, lo, hi)


def title_lines(u):
    """the game's title text (EnhTitleText's, in the printer's form) -> [(x, y, colour, text)]"""
    t = bytes(u.mem_read(SYMS['TitleText'], 91))
    out, p = [], 0
    while p < len(t) and t[p] != 0xFF:
        x, y, c2, col = t[p:p + 4]; p += 4
        e = p
        while t[e] not in (0, 0xFF): e += 1
        out.append((x, y, col, t[p:e].decode('latin-1'))); p = e + (1 if t[e] == 0 else 0)
    return out


def boot(adf, unit=0, drives=(0, 1), random_start=False, foreign=False, png=None, machine='A500 512K'):
    regions, (kind, cbase, csize, line1, line2) = MACHINES[machine]
    attn = ATTN.get(machine, 0)
    m = Machine(regions, attn); u = m.u
    w = lambda a, f, *v: u.mem_write(a, struct.pack(f, *v))
    memlist(w, regions, attn)
    u.mem_write(BOOTBUF, adf[:1024])
    w(EXEC - 0x1BC, '>HL', 0x4EF9, OPENDEVICE)                 # jmp OPENDEVICE
    w(OPENDEVICE, '>H', 0x4E75)                                  # rts
    opened = []
    def opendevice(uc, addr, size, ud):
        n, req = u.reg_read(UC_M68K_REG_D0), u.reg_read(UC_M68K_REG_A1)
        name = bytes(u.mem_read(u.reg_read(UC_M68K_REG_A0), 17))
        good = name == b'trackdisk.device\0' and n in drives
        opened.append(n)
        if good: w(req + 0x14, '>LL', DEVICE, UNITS[n])
        w(req + 0x1F, '>B', 0 if good else 32)                  # io_Error (TDERR_BadUnitNum)
        u.reg_write(UC_M68K_REG_D0, 0 if good else 32)
    od_hook = u.hook_add(UC_HOOK_CODE, opendevice, begin=OPENDEVICE, end=OPENDEVICE)
    w(DEVICE + 10, '>L', NAME); u.mem_write(NAME, b'trackdisk.device\0')
    w(BOOTREQ + 0x14, '>LL', DEVICE, FOREIGN if foreign else UNITS[unit])
    u.reg_write(UC_M68K_REG_A1, BOOTREQ)
    m.w8(0xBFE001, 0xFF)
    dma = [0]                                                  # DMACON: set / clear by bit 15
    def dmacon(uc, acc, addr, size, value, ud):
        v = (value >> 16 if size == 4 else value) & 0xFFFF
        dma[0] = dma[0] | (v & 0x7FFF) if v & 0x8000 else dma[0] & ~v
    u.hook_add(UC_HOOK_MEM_WRITE, dmacon, begin=0xDFF096, end=0xDFF097)
    fd = floppy.Floppy(m, adf, timing_ranges=[LOADER, GAME_LOADER], random_start=random_start, unit=unit)
    u.reg_write(UC_M68K_REG_A6, EXEC)
    u.reg_write(UC_M68K_REG_SR, 0x2000)
    u.reg_write(UC_M68K_REG_A7, 0x7F000)
    if attn & 2:                                    # a 68020 as Kickstart could leave it: its instruction
        movec(u, 'MOVEC_SET')                       #   cache on, the vectors elsewhere
    # (in supervisor mode already: the privilege-violation trick is not exercised here)
    u.emu_start(BOOTBUF + 0x0C, 0x400, count=600_000_000)
    pc = u.reg_read(UC_M68K_REG_PC)
    u.hook_del(od_hook)                                   # (the game's own code runs over that address)

    entry = lambda i: struct.unpack_from('>LL', adf, 0x410 + 8 * i)
    mo, ml = entry(0); so, sl = entry(1)
    game = bytearray(pack.unpack(adf[mo:mo + ml]))
    built = open(os.path.join(build_disk.OUT, 'nzs_game.bin'), 'rb').read()
    hd = build_disk.run_addr(GAME_HEADER)                    # the header: as built but for the boot's part
    in_mem = bytes(u.mem_read(0x400, len(game)))
    same_as_built = game == bytearray(built) and in_mem[:hd + 4] == built[:hd + 4] and in_mem[hd + 44:] == built[hd + 44:]
    screen_file = adf[so:so + sl]
    pal, planes, _ = extract_files.decode_screen(screen_file)
    want = b''.join(bytes(p[:8000]) for p in planes)
    got = b''.join(bytes(u.mem_read(0x78000 + 0x2000 * k, 8000)) for k in range(4))
    cop = m.r32(0xDFF080)
    coplist = [m.r16(cop + 2 * k) for k in range(18)]
    want_cop = [0xE0, 7, 0xE2, 0x8000, 0xE4, 7, 0xE6, 0xA000, 0xE8, 7, 0xEA, 0xC000, 0xEC, 7, 0xEE, 0xE000, 0xFFFF, 0xFFFE]
    regs = {r: m.r16(0xDFF000 + r) for r in (0x100, 0x102, 0x108, 0x10A, 0x92, 0x94, 0x8E, 0x90)}
    checks = [('at the game entry ($400), d0 = a0 = $400',
               pc == 0x400 and u.reg_read(UC_M68K_REG_D0) == 0x400 and u.reg_read(UC_M68K_REG_A0) == 0x400),
              ('the file table', adf[0x400:0x404] == b'NZSF'),
              ('the game unpacked at $400 as built', same_as_built),
              ('the screen file at $70000', bytes(u.mem_read(0x70000, sl)) == screen_file),
              ('the screen decoded at $78000 as the original decodes it', got == want),
              ('the 16 colours', [m.r16(0xDFF180 + 2 * k) for k in range(16)] == pal),
              ('the display: BPLCON0 $4200, DDF $38-$D0, DIW $3C81-$04C1, modulos 0',
               regs == {0x100: 0x4200, 0x102: 0, 0x108: 0, 0x10A: 0, 0x92: 0x38, 0x94: 0xD0,
                        0x8E: 0x3C81, 0x90: 0x04C1}),
              (f'DMA: master, bitplanes and copper on, disk off (DMACON ${dma[0]:04X})', dma[0] & 0x390 == 0x380),
              ('the copper list (the 4 plane pointers), in chip RAM', coplist == want_cop and cop < 0x80000),
              (f'units opened: {opened}', opened[0] == 3 and opened[-1] == (0 if foreign else unit)),
              (f'the motor off and DF{unit} deselected', not fd.motor or not fd.sel)]
    ext = open(os.path.join(build_disk.OUT, 'ext.bin'), 'rb').read()
    mi = bytes(u.mem_read(0x400 + hd + 8, 36))
    bootdrive = m.r32(0x400 + hd + 4)
    chip = next((lo, hi) for lo, hi, at in reversed(regions) if at & 2)
    slow = next(((lo, hi) for lo, hi, at in reversed(regions) if not at & 2 and 0xC00000 <= lo < 0xDC0000), (0, 0))
    fast = next(((lo, hi) for lo, hi, at in reversed(regions) if not at & 2 and not 0xC00000 <= lo < 0xDC0000), (0, 0))
    want_mi = b'NZSM' + struct.pack('>BBH', 1, 50, attn) + struct.pack('>6LL', *chip, *slow, *fast, unit if not foreign else 0)
    checks += [('the extension module at $65400', bytes(u.mem_read(EXT_BASE, 16)) == ext[:16]),
               ('the machine description and the boot drive in the game\'s header (chip, slow, fast RAM, PAL)',
                mi == want_mi and bootdrive == (unit if not foreign else 0))]
    if png:
        import screen
        mem = bytes(u.mem_read(0, 0x80000))
        custom = {0x180 + 2 * k: m.r16(0xDFF180 + 2 * k) for k in range(32)}
        custom[0x100] = regs[0x100]
        screen.render(mem, cop, custom=custom, top=0x3C, lines=200).save(png)
    print(f'{machine}, DF{unit} ({"booted from a unit of another device" if foreign else "booted from"}; drives {list(drives)}): '
          f'{fd.reads} track reads (random start: {random_start}), head at cylinder {fd.cyl}')
    # the game's start-up: Relocate, Init (EnhInit) up to GameStart; then its TrackRead, called as
    # the game calls it
    orig_track = build_disk.original_track
    u.emu_start(0x400, GAME_ENTRY, count=20_000_000)
    relocated = u.reg_read(UC_M68K_REG_PC) == GAME_ENTRY
    if attn & 2:
        cacr, vbr = movec(u, 'MOVEC_GET')
        checks.append((f'above a 68000: the caches off and the vectors at 0 for the game (CACR {cacr}, VBR ${vbr:X}; '
                       f'set to 1 and $7E000 before the boot)', cacr == 0 and vbr == 0))
    cache = struct.unpack('>LLLH', bytes(u.mem_read(SYMS['CacheBase'], 14)))     # base, size, used, kind
    lines = title_lines(u)
    checks += [(f'the file cache: {["no", "chip", "slow", "fast"][kind]} RAM, ${cbase:X}, {csize} bytes',
                (cache[3], cache[1]) == (kind, csize) and (not csize or cache[0] == cbase)),
               (f'the title: "{line1}" / "{line2}"', [l[3] for l in lines] == [line1, line2]
                and all(l[0] == (40 - len(l[3])) // 2 for l in lines))]
    def track_read(track, count, buf=0x3CAA6):
        sp = 0x7000
        w(sp, '>L', STOP)
        u.reg_write(UC_M68K_REG_A7, sp)
        u.reg_write(UC_M68K_REG_D0, track); u.reg_write(UC_M68K_REG_D1, count)
        u.reg_write(UC_M68K_REG_D2, 0); u.reg_write(UC_M68K_REG_A0, buf); u.reg_write(UC_M68K_REG_A6, 0x641B8)
        u.mem_write(buf, bytes(count * 5632))
        u.emu_start(0x40C, STOP, count=200_000_000)                # JT_TrackRead
        d0 = u.reg_read(UC_M68K_REG_D0)
        kept = u.reg_read(UC_M68K_REG_A6) == 0x641B8 and u.reg_read(UC_M68K_REG_A0) == buf and u.reg_read(UC_M68K_REG_PC) == STOP
        return d0, bytes(u.mem_read(buf, count * 5632)), kept
    load = lambda t, n: open(os.path.join(build_disk.LOADS, f'load_{t}_{n}.bin'), 'rb').read()
    good_reads = True
    for t, n in READS:
        d0, data, kept = track_read(t, n)
        good_reads &= d0 == 0 and kept and data == load(t, n)
    bad_reads = all(track_read(t, n)[0] == 0xFFFFFFFF for t, n in MISSING)
    disk_reads = fd.reads                                     # the same reads again: from the cache?
    again = True
    for t, n in READS:
        d0, data, kept = track_read(t, n)
        again &= d0 == 0 and kept and data == load(t, n)
    need = sum((FILE_LEN[k] + 3) & ~3 for k in set(READS))      # the cache's room for the files read
    cached = fd.reads == disk_reads if csize >= need else fd.reads > disk_reads
    checks += [('Relocate and Init run: at GameStart ($4000)', relocated),
               (f'TrackRead: {len(READS)} reads (tracks {", ".join(f"{t}+{n}" for t, n in READS)}): each its level file, '
                f'the rest filled, registers kept', good_reads),
               (f'TrackRead: -1 for tracks the disk does not have ({", ".join(f"{t}+{n}" for t, n in MISSING)})', bad_reads),
               (f'TrackRead again: the same files, ' + ('all from the cache (no disk reads)' if csize >= need
                                                         else f'from the disk ({fd.reads - disk_reads} track reads)'), again and cached),
               (f'the motor off again', not fd.motor or not fd.sel)]
    ok = True
    for what, good in checks:
        print(f'  {"ok  " if good else "FAIL"} {what}'); ok &= good
    if png:
        print(f'  rendered the display: {os.path.relpath(png, os.path.join(build_disk.ENH, ".."))}')
    return ok


def main():
    adf = open(build_disk.ADF, 'rb').read()
    rs = '--random-start' in sys.argv
    ok = True
    cases = ((0, (0, 1), False), (1, (0, 1), False), (3, (0, 1, 2, 3), False), (0, (0, 1), True))
    for k, (unit, drives, foreign) in enumerate(cases):
        ok &= boot(adf, unit, drives, rs, foreign, png=os.path.join(build_disk.OUT, 'test_boot.png') if k == 0 else None)
    for machine in list(MACHINES)[1:]:
        ok &= boot(adf, 0, (0, 1), rs, False, machine=machine)
    print('all as expected' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
