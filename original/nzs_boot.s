; The New Zealand Story (Ocean 1989, Amiga) - bootblock, track 0 bytes $000-$3FF
; Made by original/tools/disasm/make.py from its config; edited by hand since October 2026.
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

	org	0
BootBlock:
	dc.b	$44,$4F,$53,$00
dat_00004:
	dc.b	$4C,$CA,$C7,$2D,$00,$00,$03,$70
BootEntry:
        movem.l d0-d1/a0-a2,-(a7)               ; 0000C  a0-a2 saved: 5 longs
        movea.l (AbsExecBase).w,a6              ; 00010  ExecBase
        jsr     _LVOForbid(a6)                  ; 00014
        lea.l   BootBlock(pc),a0                ; 00018  a0 slot = this bootblock
        move.l  a0,$8(a7)                       ; 0001C
        move.l  #$60000,$10(a7)                 ; 00020  a2 slot = $60000: left on the stack, so the rts goes there
        movea.l $c(a7),a1                       ; 00028  a1 slot: the trackdisk IORequest
ReadRetry:
        move.l  $10(a7),d0                      ; 0002C
        move.l  d0,IO_DATA(a1)                  ; 00030
        move.l  #$1200,IO_LENGTH(a1)            ; 00034  the rest of track 0 after the bootblock
        move.l  #$400,IO_OFFSET(a1)             ; 0003C  disk offset $400
        move.w  #CMD_READ,IO_COMMAND(a1)        ; 00044
        movea.l (AbsExecBase).w,a6              ; 0004A
        jsr     _LVODoIO(a6)                    ; 0004E
        movea.l $c(a7),a1                       ; 00052
        move.b  IO_ERROR(a1),d0                 ; 00056
        bne.b   ReadRetry                       ; 0005A  retry until it reads without error
        movem.l (a7)+,d0-d1/a0-a1               ; 0005C  restores 4 longs only
        rts                                     ; 00060  -> $60000
	dc.b	'Protection (C)Copyright 1989 Rob Northen Computing. All Rights Reserved.'
	dcb.b	854,$00
