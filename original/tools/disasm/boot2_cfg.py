"""nzs_boot2.s: the second-stage bootblock, decrypted from the track 0 protection loader.

The protection's payload (at $60000 once decrypted) copies these 1024 bytes over Kickstart's boot
buffer and enters them at offset 12, as Kickstart enters a bootblock. They copy their loader
($D6 longs from offset $10) to $76000 and run it: it reads track 90 to $400 and jumps there.
(disk/files/t000_boot_stage2.bin is produced by tools/protemu/run_protection.sh.)
"""
NAME = 'boot2'
BINARY = 'disk/files/t000_boot_stage2.bin'
SEGMENTS = [
    (0x000, 0x010, 0x00000),        # 'DOS',0, checksum, root block, bra.w to the copier
    (0x010, 0x368, 0x76000),        # the loader, copied to $76000 and run there
    (0x368, 0x400, 0x00368),        # the copier
]
ENTRIES = [0xC, 0x76000]

PROLOGUE = r'''
; The New Zealand Story (Ocean 1989, Amiga) - second-stage bootblock
; Decrypted from the Rob Northen protection loader on track 0 (tools/protemu/run_protection.sh):
; its payload copies these 1024 bytes over Kickstart's boot buffer and jumps to offset 12.
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o boot2.bin nzs_boot2.s
;
; Offset 12 goes to Start, which copies the loader (offset $10 onwards) to $76000 and runs it:
; it reads track 90 (the game loader) to $400 with the hardware - DSKLEN $9996, sync $4489,
; its variables at $2004-$200A and $61A0 - and jumps to $400.

	include	"nzs_hw.i"

	section	boot2,code
'''
SEGMENT_TEXT = [
    '\torg\t0',
    'Loader_Stored:\n;' + '=' * 79 + '\n; The loader: copied to $76000 by Start and run there\n;' + '=' * 79
    + '\n\torg\t$76000\nLoader:',
    'LoaderEnd:\n;' + '=' * 79 + '\n; Runs in the boot buffer\n;' + '=' * 79 + '\n\torg\t$368',
]
NAMES = {0xC: 'BootEntry', 0x36A: 'Start', 0x7613A: 'LoadGameLoader', 0x76172: 'MotorOn',
         0x761A4: 'ReadTracks'}
OPERANDS = {
    0x372: 'Loader_Stored(pc),a0',
    0x376: '#(LoaderEnd-Loader)/4-1,d0',
    0x37A: '#Loader,a1',
    0x386: '(Loader).l',
}
COMMENTS = {
    0x7613A: 'stack below the game loader',
    0x76164: 'track 90 (the game loader)',
    0x76168: '-> to $400',
    0x7616E: 'enter the game loader',
}
HEADERS = {}
