;==============================================================================
; ext.s - The New Zealand Story: the boot's extension module, the part of the boot the
; bootblock (boot_4489.s) has no room for. A file of its own on the disk (FID_EXT), loaded by
; the bootblock to EXT_BASE (ext.i) and entered at ExtBoot; assembled at EXT_BASE by
; build_disk.py. Needed only while booting: the game uses that memory afterwards.
;
;   ExtBoot      the loading screen, the program loaded and unpacked, the machine description
;                and the drive booted from left in the game's header (GAME_HEADER), the game
;                entered as the original's track 90 loader entered it
;==============================================================================

	include	"ext.i"

CUSTOM          equ     $DFF000
PROGRAM         equ     $400
SCREEN_FILE     equ     $70000                  ; where the track 90 loader read it
SCREEN          equ     $78000                  ; 4 planes, $2000 apart
FID_MAIN        equ     0                       ; (build_disk.py's file ids)
FID_SCREEN      equ     1


	org	EXT_BASE

ExtHeader:      dc.b    'NZSX'                  ; EXT_MAGIC
        dc.w    1                               ; EXT_VERSION
        dc.w    0
        jmp     ExtBoot                         ; EXT_BOOT

;------------------------------------------------------------------------------
; ExtBoot - from the bootblock's loader, with a0 = CUSTOM, a1 = the machine description,
; a2 = the file table, a5 = LoadIt (d0 = offset, d1 = length, a0 = destination; keeps a0-a5).
; What the bootblock used to do itself, as the track 90 loader did: the loading screen, the
; program loaded to $400 and unpacked, entered with d0 = a0 = $400. Before entering it: the
; machine description kept, the drive booted from written into the game, the track cache set
; up and the title's memory lines made.
ExtBoot:
        movea.l a1,a3                           ; (the machine description)
        movea.l a2,a4                           ; (the file table)
; the display as the track 90 loader set it up ($76ACE): black, the screen cleared, 4 planes
        lea     $180(a0),a1                     ; all 32 colours black
        moveq   #31,d0
.black:         clr.w   (a1)+
        dbra    d0,.black
        lea     $140(a0),a1                     ; sprites off: SPRxPOS/CTL
        moveq   #15,d0
.spr:           clr.l   (a1)+
        addq.l  #4,a1
        dbra    d0,.spr
        lea     SCREEN,a1
        move.w  #$1fff,d0
.clr:           clr.l   (a1)+
        dbra    d0,.clr
        move.w  #$4200,$100(a0)                 ; BPLCON0: 4 planes, colour
        clr.w   $102(a0)                        ; BPLCON1
        clr.w   $108(a0)                        ; BPL1MOD
        clr.w   $10a(a0)                        ; BPL2MOD
        move.w  #$38,$92(a0)                    ; DDFSTRT
        move.w  #$d0,$94(a0)                    ; DDFSTOP
        move.w  #$3c81,$8e(a0)                  ; DIWSTRT
        move.w  #$04c1,$90(a0)                  ; DIWSTOP: 200 lines
        lea     Copper(pc),a1
        move.l  a1,$80(a0)                      ; COP1LC
        move.w  $88(a0),d0                      ; COPJMP1
        move.w  #$8380,$96(a0)                  ; DMA: master, bitplanes, copper
; the loading screen
        movem.l 16+FID_SCREEN*8(a4),d0-d1
        lea     SCREEN_FILE,a0
        jsr     (a5)
        bsr.w   Decode
        lea     SCREEN_FILE+2,a1                ; its 16 colours, at half value
        lea     CUSTOM+$180,a2
        moveq   #15,d0
.pal:           move.w  (a1)+,d1
        add.w   d1,d1
        move.w  d1,(a2)+
        dbra    d0,.pal
; the program
        movem.l 16+FID_MAIN*8(a4),d0-d1
        lea     PROGRAM,a0
        jsr     (a5)
        lea     PROGRAM,a0
        bsr.w   Unpack
; the machine description and the drive booted from, into the game's header (still 4 bytes
; above where it will run: Relocate moves block 1 down when the game starts)
        cmpi.l  #'NZSE',GAME_HEADER+4           ; (the game this module was built with)
        bne.b   .nohdr
        lea     GAME_MACHINE+4,a1
        moveq   #MI_SIZE/4-1,d0
.mi:            move.l  (a3)+,(a1)+
        dbra    d0,.mi
        move.l  GAME_MACHINE+4+MI_DRIVE,GAME_BOOTDRIVE+4
.nohdr:         move.l  #PROGRAM,d0                     ; as the track 90 loader left them
        movea.l d0,a0
        jmp     (a0)

;------------------------------------------------------------------------------
; Unpack - the program at a0 (packed: unpacked length - 1, packed length - 1 counting this
; 8-byte header, then the stream) unpacked in place, as the track 90 loader's $7671E: the
; packed bytes moved up to end where the program will, then unpacked forwards from a0. The
; first byte of the stream is the escape byte; escape, value, count = count+1 copies of value.
Unpack:         movea.l a0,a2
        movea.l a0,a1
        move.l  (a1)+,d3                        ; unpacked length - 1
        move.l  (a1)+,d1                        ; packed length - 1
        adda.l  d1,a1
        addq.l  #1,a1
        adda.l  d3,a0
        addq.l  #1,a0
.up:            move.b  -(a1),-(a0)
        subq.l  #1,d1
        bpl.b   .up
        movea.l a0,a1                           ; the packed bytes, moved up
        movea.l a2,a0
        move.b  (a1)+,d2                        ; the escape byte
.byte:          move.b  (a1)+,d0
        cmp.b   d0,d2
        beq.b   .run
        move.b  d0,(a0)+
        subq.l  #1,d3
        bpl.b   .byte
        rts
.run:           moveq   #0,d1
        move.b  (a1)+,d0
        move.b  (a1)+,d1
.copy:          move.b  d0,(a0)+
        subq.l  #1,d3
        dbra    d1,.copy
        tst.l   d3
        bpl.b   .byte
        rts

;------------------------------------------------------------------------------
; Decode - the loading screen file at SCREEN_FILE to SCREEN, as the track 90 loader's $766AC:
; byte-run data from +$22 (n < $80: copy n+1 bytes; n > $80: repeat the next byte 257-n
; times; $80: nothing), 40 bytes a plane line, planes 0-3 of each line in turn, 200 lines.
Decode:         lea     SCREEN_FILE+$22,a0
        lea     SCREEN,a2                       ; this line, plane 0
        movea.l a2,a1                           ; where the next byte goes
        moveq   #0,d4                           ; plane
        moveq   #0,d5                           ; byte in the plane line
        move.w  #200-1,d6                       ; lines left
.next:          move.b  (a0)+,d0
        bpl.b   .copy
        cmp.b   #$80,d0
        beq.b   .next
        neg.b   d0
        andi.w  #$7f,d0                         ; repeats - 1
        move.b  (a0)+,d1
.rep:           bsr.b   .put
        dbra    d0,.rep
        bra.b   .next
.copy:          andi.w  #$7f,d0                 ; bytes - 1
.lit:           move.b  (a0)+,d1
        bsr.b   .put
        dbra    d0,.lit
        bra.b   .next
.put:           move.b  d1,(a1)+
        addq.w  #1,d5
        cmp.w   #40,d5
        bne.b   .ret
        moveq   #0,d5
        lea     $2000-40(a1),a1                 ; the next plane
        addq.w  #1,d4
        cmp.w   #4,d4
        bne.b   .ret
        moveq   #0,d4
        lea     40(a2),a2                       ; the next line
        movea.l a2,a1
        subq.w  #1,d6
        bpl.b   .ret
        addq.l  #4,a7                           ; the last line: return from Decode
.ret:           rts

; the loading screen's copper list, as the track 90 loader's ($76B68): the 4 plane pointers
	cnop	0,4
Copper:         dc.w    $00E0,SCREEN>>16,$00E2,SCREEN&$FFFF
        dc.w    $00E4,SCREEN>>16,$00E6,(SCREEN+$2000)&$FFFF
        dc.w    $00E8,SCREEN>>16,$00EA,(SCREEN+$4000)&$FFFF
        dc.w    $00EC,SCREEN>>16,$00EE,(SCREEN+$6000)&$FFFF
        dc.w    $FFFF,$FFFE

ExtEnd:
	ifgt	ExtEnd-EXT_LIMIT
	fail	ext.s: the module runs past EXT_LIMIT
	endc
