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

The bootblock finds the boot drive by opening trackdisk.device's units; exec's OpenDevice is a
stub (a Python hook) that knows the drives connected. Cases: booted from DF0, DF1 and DF3, and
from a unit of another device (DF0 then).

  python3 enhanced/tools/test_boot.py [--random-start]     (the DMA starting at any sector)
"""
import os, struct, sys
from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_HOOK_CODE
from unicorn.m68k_const import (UC_CPU_M68K_M68000, UC_M68K_REG_A0, UC_M68K_REG_A1, UC_M68K_REG_A6,
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
GAME_LOADER = (0xA04, 0xD88)            # the game's TrackRead / byteloader (diskload.s), after Relocate
GAME_BOOTDRIVE = 0xA08                  # its BootDrive (run address)
STOP = 0x1F0                            # a return address that ends a call
READS = [(2, 5), (84, 5), (18, 1), (89, 1), (152, 2), (158, 2), (144, 5), (68, 1)]   # (track, count)
MISSING = [(0, 1), (1, 1), (100, 1), (89, 2)]


class Machine:
    def __init__(self):
        u = self.u = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        u.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        u.mem_map(0, 0x80000); u.mem_map(0xBFD000, 0x2000); u.mem_map(0xDFF000, 0x1000)
    def r8(self, a): return self.u.mem_read(a, 1)[0]
    def r16(self, a): return struct.unpack('>H', bytes(self.u.mem_read(a, 2)))[0]
    def r32(self, a): return struct.unpack('>L', bytes(self.u.mem_read(a, 4)))[0]
    def w8(self, a, v): self.u.mem_write(a, bytes([v & 0xFF]))
    def w16(self, a, v): self.u.mem_write(a, struct.pack('>H', v & 0xFFFF))
    def w32(self, a, v): self.u.mem_write(a, struct.pack('>L', v & 0xFFFFFFFF))


def boot(adf, unit=0, drives=(0, 1), random_start=False, foreign=False, png=None):
    m = Machine(); u = m.u
    w = lambda a, f, *v: u.mem_write(a, struct.pack(f, *v))
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
    u.hook_add(UC_HOOK_CODE, opendevice, begin=OPENDEVICE, end=OPENDEVICE)
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
    # (in supervisor mode already: the privilege-violation trick is not exercised here)
    u.emu_start(BOOTBUF + 0x0C, 0x400, count=600_000_000)
    pc = u.reg_read(UC_M68K_REG_PC)

    entry = lambda i: struct.unpack_from('>LL', adf, 0x410 + 8 * i)
    mo, ml = entry(0); so, sl = entry(1)
    game = bytearray(pack.unpack(adf[mo:mo + ml]))
    game[build_disk.run_addr(GAME_BOOTDRIVE):build_disk.run_addr(GAME_BOOTDRIVE) + 4] = struct.pack('>L', unit if not foreign else 0)
    built = open(os.path.join(build_disk.OUT, 'nzs_game.bin'), 'rb').read()
    same_as_built = bytes(game[:build_disk.run_addr(GAME_BOOTDRIVE)]) == built[:build_disk.run_addr(GAME_BOOTDRIVE)] and \
        bytes(game[build_disk.run_addr(GAME_BOOTDRIVE) + 4:]) == built[build_disk.run_addr(GAME_BOOTDRIVE) + 4:]
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
              ('the game unpacked at $400, BootDrive set', same_as_built and bytes(u.mem_read(0x400, len(game))) == bytes(game)),
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
    print(f'DF{unit} ({"booted from a unit of another device" if foreign else "booted from"}; drives {list(drives)}): '
          f'{fd.reads} track reads (random start: {random_start}), head at cylinder {fd.cyl}')
    # the game's own disk reading: run Relocate (to Init), then call TrackRead as the game does
    orig_track = build_disk.original_track
    u.emu_start(0x400, 0x55A, count=10_000_000)
    relocated = u.reg_read(UC_M68K_REG_PC) == 0x55A
    def track_read(track, count, buf=0x3CAA6):
        sp = 0x7000
        w(sp, '>L', STOP)
        u.reg_write(UC_M68K_REG_A7, sp)
        u.reg_write(UC_M68K_REG_D0, track); u.reg_write(UC_M68K_REG_D1, count)
        u.reg_write(UC_M68K_REG_D2, 0); u.reg_write(UC_M68K_REG_A0, buf); u.reg_write(UC_M68K_REG_A6, 0x641B8)
        u.mem_write(buf, bytes(count * 5632))
        u.emu_start(0xC24, STOP, count=200_000_000)
        d0 = u.reg_read(UC_M68K_REG_D0)
        kept = u.reg_read(UC_M68K_REG_A6) == 0x641B8 and u.reg_read(UC_M68K_REG_A0) == buf and u.reg_read(UC_M68K_REG_PC) == STOP
        return d0, bytes(u.mem_read(buf, count * 5632)), kept
    good_reads = True
    for t, n in READS:
        d0, data, kept = track_read(t, n)
        good_reads &= d0 == 0 and kept and data == b''.join(orig_track(t + k) for k in range(n))
    bad_reads = all(track_read(t, n)[0] == 0xFFFFFFFF for t, n in MISSING)
    checks += [('Relocate run: at Init ($55A)', relocated),
               (f'TrackRead: {len(READS)} reads (tracks {", ".join(f"{t}+{n}" for t, n in READS)}) as on the original disk, registers kept', good_reads),
               (f'TrackRead: -1 for tracks the disk does not have ({", ".join(f"{t}+{n}" for t, n in MISSING)})', bad_reads),
               (f'the motor off again', not fd.motor or not fd.sel)]
    ok = True
    for what, good in checks:
        print(f'  {"ok  " if good else "FAIL"} {what}'); ok &= good
    if png:
        import screen
        mem = bytes(u.mem_read(0, 0x80000))
        custom = {0x180 + 2 * k: m.r16(0xDFF180 + 2 * k) for k in range(32)}
        custom[0x100] = regs[0x100]
        screen.render(mem, cop, custom=custom, top=0x3C, lines=200).save(png)
        print(f'  rendered the display: {os.path.relpath(png, os.path.join(build_disk.ENH, ".."))}')
    return ok


def main():
    adf = open(build_disk.ADF, 'rb').read()
    rs = '--random-start' in sys.argv
    ok = True
    cases = ((0, (0, 1), False), (1, (0, 1), False), (3, (0, 1, 2, 3), False), (0, (0, 1), True))
    for k, (unit, drives, foreign) in enumerate(cases):
        ok &= boot(adf, unit, drives, rs, foreign, png=os.path.join(build_disk.OUT, 'test_boot.png') if k == 0 else None)
    print('all as expected' if ok else 'FAILED')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
