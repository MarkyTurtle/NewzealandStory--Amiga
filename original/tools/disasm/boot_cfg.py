"""nzs_boot.s: the bootblock (track 0, $000-$3FF).

Kickstart reads the two boot sectors into a buffer and calls offset 12 with a1 = the trackdisk
IORequest and a6 = ExecBase. The code is position independent, so it is assembled at org 0.
"""
NAME = 'boot'
BINARY = 'disk/files/t000_bootblock.bin'
SEGMENTS = [(0, 0x400, 0)]
ENTRIES = [0xC]

PROLOGUE = r'''
; The New Zealand Story (Ocean 1989, Amiga) - bootblock, track 0 bytes $000-$3FF
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o boot.bin nzs_boot.s
;
; Reads $1200 bytes from disk offset $400 (the rest of track 0: Rob Northen's protection
; loader) to $60000 through trackdisk.device, and "returns" into it: it saves five registers
; but restores four, leaving the $60000 it stored in a2's slot on the stack for the rts.
; In the game-tracks ADF those $1200 bytes are blank (the protection lives on track 0-1 of the
; original disk), so this disk image does not boot by itself.

	include	"nzs_hw.i"

AbsExecBase	equ	4
_LVOForbid	equ	-132
_LVODoIO	equ	-456
IO_COMMAND	equ	$1C
IO_ERROR	equ	$1F
IO_LENGTH	equ	$24
IO_DATA		equ	$28
IO_OFFSET	equ	$2C
CMD_READ	equ	2

	section	boot,code
'''
SEGMENT_TEXT = ['\torg\t0']

NAMES = {0x0: 'BootBlock', 0xC: 'BootEntry', 0x2C: 'ReadRetry'}
MEM = {0x4: 'AbsExecBase'}

OPERANDS = {
    0x14: '_LVOForbid(a6)',
    0x30: 'd0,IO_DATA(a1)',
    0x34: '#$1200,IO_LENGTH(a1)',
    0x3C: '#$400,IO_OFFSET(a1)',
    0x44: '#CMD_READ,IO_COMMAND(a1)',
    0x4E: '_LVODoIO(a6)',
    0x56: 'IO_ERROR(a1),d0',
}

COMMENTS = {
    0xC: 'a0-a2 saved: 5 longs',
    0x10: 'ExecBase',
    0x18: 'a0 slot = this bootblock',
    0x20: "a2 slot = $60000: left on the stack, so the rts goes there",
    0x28: 'a1 slot: the trackdisk IORequest',
    0x34: 'the rest of track 0 after the bootblock',
    0x3C: 'disk offset $400',
    0x5A: 'retry until it reads without error',
    0x5C: 'restores 4 longs only',
    0x60: '-> $60000',
}
HEADERS = {}
