;==============================================================================
; ext.s - The New Zealand Story, the enhanced game's extension module: code the enhanced game
; adds to the original, in memory the original never uses (EXT_BASE, ext.i). A file of its own
; on the disk (FID_EXT), loaded by the bootblock (boot_4489.s), assembled at EXT_BASE by
; build_disk.py.
;
;   ExtBoot      the rest of the boot, entered from the bootblock: the loading screen, the
;                program, the track cache set up for the machine, the title's text, the game
;   ExtTitleText the title's text: the original's, then the machine's memory and what the
;                game uses (the game calls it at $404C in place of the text printer, sub_0C6A8)
;   ExtCacheGet  \ the track cache, for the game's TrackRead (diskload.s): the level tracks
;   ExtCachePut  / read from the disk are kept in memory the game does not otherwise use
;
; The machine (the bootblock's description, ext.i, copied to ExtMachine):
;   chip RAM above 512K (A500+, A600, A1200, an A500 with a 1MB Agnus)  \  the largest one
;   slow RAM ($C00000-$DBFFFF: an A500's trapdoor expansion)             >  holds the track
;   fast RAM (any other: a CPU card, an A1200's expansion)               /  cache
; With none of them, the game runs as the original, reading every level from the disk.
;==============================================================================

	include	"ext.i"
	include	"tracks.i"                      ; TRACKS_STORED (build_disk.py)

CUSTOM          equ     $DFF000
PROGRAM         equ     $400
SCREEN_FILE     equ     $70000                  ; where the track 90 loader read it
SCREEN          equ     $78000                  ; 4 planes, $2000 apart
FID_MAIN        equ     0                       ; (build_disk.py's file ids)
FID_SCREEN      equ     1
TRACK_BYTES     equ     11*512
CHIP_512K       equ     $80000

; in the game (these addresses are the original's: build_disk.py checks that the game is the
; original program but for the parts it lists)
GAME_BOOTDRIVE  equ     $A08+4                  ; BootDrive (diskload.s), before Relocate moves
                                                ; block 1 down 4 bytes
GAME_PRINT      equ     $C6A8                   ; sub_0C6A8: print text (x.b, y.b, then text; $FF ends)

	org	EXT_BASE

ExtHeader:      dc.b    'NZSX'                  ; EXT_MAGIC
        dc.w    1                               ; EXT_VERSION
        dc.w    0
        jmp     ExtBoot                         ; EXT_BOOT
        jmp     ExtTitleText                    ; EXT_TITLETEXT
        jmp     ExtCacheGet                     ; EXT_CACHEGET
        jmp     ExtCachePut                     ; EXT_CACHEPUT
ExtMachine:     dcb.b   MI_SIZE,0               ; EXT_MACHINE: the machine description

	ifne	ExtMachine-ExtHeader-EXT_MACHINE
	fail	ext.s: the header does not match ext.i
	endc

; the track cache: where, how many tracks it holds, how many it holds now, and for each of the
; original disk's 160 tracks its slot + 1 (0: not in the cache)
CacheBase:      dc.l    0
CacheSlots:     dc.w    0
CacheUsed:      dc.w    0
CacheKind:      dc.w    0                       ; 0 none, 1 chip, 2 slow, 3 fast
CacheMap:       dcb.b   160,0

;------------------------------------------------------------------------------
; ExtBoot - from the bootblock's loader, with a0 = CUSTOM, a1 = the machine description,
; a2 = the file table, a5 = LoadIt (d0 = offset, d1 = length, a0 = destination; keeps a0-a5).
; What the bootblock used to do itself, as the track 90 loader did: the loading screen, the
; program loaded to $400 and unpacked, entered with d0 = a0 = $400. Before entering it: the
; machine description kept, the drive booted from written into the game, the track cache set
; up and the title's memory lines made.
ExtBoot:
        lea     ExtMachine(pc),a3               ; keep the machine description
        moveq   #MI_SIZE/4-1,d0
.mi:            move.l  (a1)+,(a3)+
        dbra    d0,.mi
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
        move.l  ExtMachine+MI_DRIVE(pc),GAME_BOOTDRIVE
        bsr.w   CacheInit
        bsr.w   MakeTitleText
        move.l  #PROGRAM,d0                     ; as the track 90 loader left them
        movea.l d0,a0
        jmp     (a0)

;------------------------------------------------------------------------------
; CacheInit - choose the track cache's memory: the largest of the chip RAM above 512K, the slow
; RAM region and the fast RAM region; as many whole tracks as fit (at most the tracks on the
; disk). Nothing else in the game uses that memory.
CacheInit:
        lea     ExtMachine(pc),a1
        moveq   #0,d4                           ; the best: size
        moveq   #0,d5                           ;           base
        moveq   #0,d6                           ;           kind
        move.l  MI_CHIP+4(a1),d1                ; chip RAM above 512K
        move.l  #CHIP_512K,d0
        moveq   #1,d2
        bsr.b   .consider
        movem.l MI_SLOW(a1),d0-d1               ; slow RAM
        moveq   #2,d2
        bsr.b   .consider
        movem.l MI_FAST(a1),d0-d1               ; fast RAM
        moveq   #3,d2
        bsr.b   .consider
        move.w  d6,CacheKind
        move.l  d5,CacheBase
        divu    #TRACK_BYTES,d4                 ; (d4 < 64K tracks)
        cmp.w   #TRACKS_STORED,d4
        bls.b   .n
        move.w  #TRACKS_STORED,d4
.n:             move.w  d4,CacheSlots
        clr.w   CacheUsed
        lea     CacheMap(pc),a0
        moveq   #160/4-1,d0
.clr:           clr.l   (a0)+
        dbra    d0,.clr
        rts
; d0 = lower, d1 = upper, d2 = kind: the best so far if larger (from a long boundary)
.consider:      addq.l  #3,d0
        andi.w  #$fffc,d0
        sub.l   d0,d1
        bls.b   .no
        cmp.l   #TRACK_BYTES*$ffff,d1           ; (at most 64K tracks: divu)
        bls.b   .size
        move.l  #TRACK_BYTES*$ffff,d1
.size:          cmp.l   d4,d1
        bls.b   .no
        move.l  d1,d4
        move.l  d0,d5
        move.w  d2,d6
.no:            rts

;------------------------------------------------------------------------------
; ExtCacheGet - d0.w = the original disk's track, a0 = where it goes -> d7.l = 0 if the track
; was in the cache (copied to a0), -1 if not. Keeps every other register.
ExtCacheGet:
        moveq   #-1,d7
        movem.l d0-d1/a0-a1,-(a7)
        bsr.b   CacheSlot
        beq.b   .out                            ; not in the cache
        exg     a0,a1                           ; from the cache to a0
        bsr.b   CopyTrack
        moveq   #0,d7
.out:           movem.l (a7)+,d0-d1/a0-a1
        rts

; ExtCachePut - d0.w = the original disk's track, just read to a0: kept in the cache if there is
; a free slot and it is not there already. Keeps every register.
ExtCachePut:
        movem.l d0-d1/a0-a1,-(a7)
        bsr.b   CacheSlot
        bne.b   .out                            ; there already
        move.w  CacheUsed(pc),d1
        cmp.w   CacheSlots(pc),d1
        bcc.b   .out                            ; full (or no cache)
        addq.w  #1,d1
        move.w  d1,CacheUsed
        lea     CacheMap(pc),a1
        move.b  d1,(a1,d0.w)
        bsr.b   CacheSlot                       ; a1 = the slot
        bsr.b   CopyTrack                       ; a0 -> the slot
.out:           movem.l (a7)+,d0-d1/a0-a1
        rts

; CacheSlot - d0.w = track -> d1 = its slot + 1 (Z set: not in the cache), a1 = the slot's memory
CacheSlot:      andi.l  #$ff,d0
        lea     CacheMap(pc),a1
        moveq   #0,d1
        move.b  (a1,d0.w),d1
        beq.b   .no
        move.w  d1,-(a7)
        subq.w  #1,d1
        mulu    #TRACK_BYTES,d1
        movea.l CacheBase(pc),a1
        adda.l  d1,a1
        move.w  (a7)+,d1                        ; (sets Z: not zero)
.no:            rts

; CopyTrack - a track from a0 to a1 (even addresses; the CPU reaches any memory)
CopyTrack:      move.w  #TRACK_BYTES/16-1,d1
.copy:          move.l  (a0)+,(a1)+
        move.l  (a0)+,(a1)+
        move.l  (a0)+,(a1)+
        move.l  (a0)+,(a1)+
        dbra    d1,.copy
        rts

;------------------------------------------------------------------------------
; ExtTitleText - a0 = the title's text (dat_0C0A2): printed by the game's printer, then the
; machine's lines (MakeTitleText) under the kiwi, above the credits. Keeps a0 as the printer.
ExtTitleText:
        jsr     GAME_PRINT
        move.l  a0,-(a7)
        lea     TitleText(pc),a0
        jsr     GAME_PRINT
        movea.l (a7)+,a0
        rts

; MakeTitleText - the title's two memory lines, in the printer's form: x (character column),
; y (pixel line), then $02,colour and the characters, $00 then the next line's x, y; $FF ends.
;   CHIP 512K  SLOW 512K  FAST 0K
;   TRACK CACHE 93 OF 96 IN SLOW RAM   /   NO TRACK CACHE
MakeTitleText:
        lea     LineBuf(pc),a0                  ; line 1: the memory
        lea     .chip(pc),a1
        bsr.w   PutStr
        move.l  ExtMachine+MI_CHIP+4(pc),d0
        bsr.w   PutK
        lea     .slow(pc),a1
        bsr.w   PutStr
        movem.l ExtMachine+MI_SLOW(pc),d1-d2
        move.l  d2,d0
        sub.l   d1,d0
        bsr.w   PutK
        lea     .fast(pc),a1
        bsr.w   PutStr
        movem.l ExtMachine+MI_FAST(pc),d1-d2
        move.l  d2,d0
        sub.l   d1,d0
        bsr.w   PutK
        lea     TitleText(pc),a2
        move.w  #TITLE_Y1,d2
        moveq   #TITLE_COL1,d3
        bsr.w   PutLine
        lea     LineBuf(pc),a0                  ; line 2: the track cache
        move.w  CacheSlots(pc),d0
        bne.b   .cache
        lea     .none(pc),a1
        bsr.w   PutStr
        bra.b   .line2
.cache:         lea     .tc(pc),a1
        bsr.w   PutStr
        moveq   #0,d0
        move.w  CacheSlots(pc),d0
        bsr.w   PutDec
        lea     .of(pc),a1
        bsr.w   PutStr
        moveq   #TRACKS_STORED,d0
        bsr.w   PutDec
        lea     .in(pc),a1
        bsr.w   PutStr
        move.w  CacheKind(pc),d0
        add.w   d0,d0
        move.w  .kinds-2(pc,d0.w),d0
        lea     .kinds(pc,d0.w),a1
        bsr.w   PutStr
        lea     .ram(pc),a1
        bsr.w   PutStr
.line2:         move.w  #TITLE_Y2,d2
        moveq   #TITLE_COL2,d3
        bsr.w   PutLine
        st.b    -1(a2)                          ; the end: $FF in place of the last $00
        rts
.kinds:         dc.w    .kchip-.kinds,.kslow-.kinds,.kfast-.kinds
.kchip:         dc.b    'CHIP',0
.kslow:         dc.b    'SLOW',0
.kfast:         dc.b    'FAST',0
.chip:          dc.b    'CHIP ',0
.slow:          dc.b    '  SLOW ',0
.fast:          dc.b    '  FAST ',0
.none:          dc.b    'NO TRACK CACHE',0
.tc:            dc.b    'TRACK CACHE ',0
.of:            dc.b    ' OF ',0
.in:            dc.b    ' IN ',0
.ram:           dc.b    ' RAM',0
	even

TITLE_Y1        equ     $7E                     ; under the kiwi, above 'CONVERSION' ($A0)
TITLE_Y2        equ     $8A
TITLE_COL1      equ     $01                     ; the colours (the printer's $02 command)
TITLE_COL2      equ     $07

; PutStr - the string at a1 (0 ends) to a0
PutStr:         move.b  (a1)+,(a0)+
        bne.b   PutStr
        subq.l  #1,a0
        rts

; PutK - d0.l = bytes -> to a0 in K, rounded up to 64K ('512K'; 0 -> '0K'). Exec lists Kickstart
; 1.3's 1MB of chip RAM as ending at $FE800, and a region's lower end is past its header.
PutK:           add.l   #$ffff,d0
        clr.w   d0
        lsr.l   #6,d0                           ; (in K: whole 64K)
        lsr.l   #4,d0
        bsr.w   PutDec
        move.b  #'K',(a0)+
        rts

; PutDec - d0.l (below 655360) to a0 in decimal
PutDec:         movem.l d0-d2,-(a7)
        moveq   #0,d2                           ; digits pushed
.div:           divu    #10,d0                  ; (d0 / 10 < 65536)
        swap    d0
        move.w  d0,-(a7)
        clr.w   d0
        swap    d0
        addq.w  #1,d2
        tst.l   d0
        bne.b   .div
        subq.w  #1,d2
.put:           move.w  (a7)+,d0
        add.b   #'0',d0
        move.b  d0,(a0)+
        dbra    d2,.put
        movem.l (a7)+,d0-d2
        rts

; PutLine - the line in LineBuf (ending at a0) to a2 in the printer's form, centred on the 40
; columns, at y = d2, colour d3; a2 left at its end
PutLine:        move.l  a0,d0
        lea     LineBuf(pc),a1
        sub.l   a1,d0                           ; its length
        moveq   #40,d1
        sub.w   d0,d1
        lsr.w   #1,d1
        move.b  d1,(a2)+                        ; x
        move.b  d2,(a2)+                        ; y
        move.b  #2,(a2)+                        ; the colour
        move.b  d3,(a2)+
        subq.w  #1,d0
.copy:          move.b  (a1)+,(a2)+
        dbra    d0,.copy
        clr.b   (a2)+                           ; (a $00: another line follows, or $FF ends)
        rts

LineBuf:        dcb.b   40,0
TitleText:      dcb.b   2*(4+40+1)+1,$ff
	even

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
