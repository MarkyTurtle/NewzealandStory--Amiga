;==============================================================================
; enhanced.s - the enhanced game's own code, in block 1 of nzs_game.s (in the space the debug
; monitor left; included at its end).
;
;   EnhInit       at start-up: the track cache set up for the machine, the title's lines made
;   CacheGet      \ the track cache, for TrackRead (diskload.s): the level tracks read from the
;   CachePut      / disk are kept in memory the game does not otherwise use
;   EnhTitleText  the title's text (the game calls it at $404C in place of the printer,
;                 sub_0C6A8): the original's, then the machine's memory lines
;   mirror.s      the mirrored BOB frames: all built at start-up as the original does, or on a
;                 512K machine built when first drawn into a cache
;
; The machine (the bootblock's description, ext.i, left in EnhMachine by the boot):
;   chip RAM above 512K (A500+, A600, A1200, an A500 with a 1MB Agnus)  \  the largest one
;   slow RAM ($C00000-$DBFFFF: an A500's trapdoor expansion)             >  holds the track
;   fast RAM (any other: a CPU card, an A1200's expansion)               /  cache
; With none of them, the game reads every level from the disk as the original did.
;==============================================================================

CHIP_512K       equ     $80000

	include	"tracks.i"                      ; TRACKS_STORED (build_disk.py)

; EnhInit - at start-up (Init), before the game starts
EnhInit:        bsr.w   CacheInit
        bsr.w   MirInit
        bra.w   MakeTitleText

; the track cache: where, how many tracks it holds, how many it holds now, and for each of the
; original disk's 160 tracks its slot + 1 (0: not in the cache)
CacheBase:      dc.l    0
CacheSlots:     dc.w    0
CacheUsed:      dc.w    0
CacheKind:      dc.w    0                       ; 0 none, 1 chip, 2 slow, 3 fast
CacheMap:       dcb.b   160,0

;------------------------------------------------------------------------------
; CacheInit - choose the track cache's memory: the largest of the chip RAM above 512K, the slow
; RAM region and the fast RAM region; as many whole tracks as fit (at most the tracks on the
; disk). Nothing else in the game uses that memory.
CacheInit:
        lea     EnhMachine(pc),a1
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
; CacheGet - d0.w = the original disk's track, a0 = where it goes -> d7.l = 0 if the track
; was in the cache (copied to a0), -1 if not. Keeps every other register.
CacheGet:
        moveq   #-1,d7
        movem.l d0-d1/a0-a1,-(a7)
        bsr.b   CacheSlot
        beq.b   .out                            ; not in the cache
        exg     a0,a1                           ; from the cache to a0
        bsr.b   CopyTrack
        moveq   #0,d7
.out:           movem.l (a7)+,d0-d1/a0-a1
        rts

; CachePut - d0.w = the original disk's track, just read to a0: kept in the cache if there is
; a free slot and it is not there already. Keeps every register.
CachePut:
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
; EnhTitleText - a0 = the title's text (dat_0C0A2): printed by the game's printer, then the
; menu (menu.s), whose options page shows the machine's lines (MakeTitleText) under the kiwi,
; above the credits. Keeps a0 as the printer.
EnhTitleText:
        jsr     sub_0C6A8
        move.l  a0,-(a7)
        bsr.w   MenuStart                       ; (menu.s: and the memory lines, on its options page)
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
        move.l  EnhMachine+MI_CHIP+4(pc),d0
        bsr.w   PutK
        lea     .slow(pc),a1
        bsr.w   PutStr
        movem.l EnhMachine+MI_SLOW(pc),d1-d2
        move.l  d2,d0
        sub.l   d1,d0
        bsr.w   PutK
        lea     .fast(pc),a1
        bsr.w   PutStr
        movem.l EnhMachine+MI_FAST(pc),d1-d2
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

TITLE_Y1        equ     $46                     ; above the kiwi, under the copyright lines (the menu,
TITLE_Y2        equ     $52                     ;   menu.s, is under him)
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

;==============================================================================
; The scroller (scroller.s) and the game's routines it takes over: each of these is entered
; from a jmp put over the start of the game's routine (nzs_game.s, "enhanced:"), and in the
; game's own display does what the instructions the jmp replaced did, then goes on there.
;==============================================================================
BobMinterm      equ     BobMinterm_+2           ; sub_0B8B4's ori.w #$fca,d7: BlitBob changes it

	include	"scroller.s"
	include	"mirror.s"
	include	"smooth.s"
	include	"menu.s"

; sub_0B8B4: a BOB's 4 blits
EnhBob:         tst.b   ScrActive
        bne.w   ScrBob
        move.l  a1,-(a7)
        adda.w  d5,a1
        adda.l  d4,a1
        jmp     l_0B8BA

; sub_0C744: a character at a character column
EnhPrintCol:    tst.b   ScrActive
        bne.w   ScrPrintCol
        movem.l d0-d3/d7/a0-a3,-(a7)
        move.w  $6(a6),d1
        jmp     l_0C74C

; sub_0C84C: a character at a pixel
EnhPrintPix:    tst.b   ScrActive
        bne.w   ScrPrintPix
        movem.l d0-d4/d7/a0-a3,-(a7)
        andi.w  #$ff,d0
        jmp     l_0C854

; sub_04C78: a rectangle filled in both screens
EnhFill:        tst.b   ScrActive
        bne.w   ScrFill
        movea.l a0,a1
        adda.l  #$70000,a0
        jmp     l_04C80

; sub_0BB76: the screens cleared (black, then cleared at the next frame)
EnhClear:       bsr.w   ScrLeave
        movem.l d0-d1/a0-a2,-(a7)
        lea     dat_0C18A,a0
        jmp     l_0BB7E

;------------------------------------------------------------------------------
; EnhCheatKeys - $43C0, at the end of each pass of the game loop, where the original tests its
; cheat's HELP key: first the original's fly mode, which it never calls. With the cheat on (the
; game's starting lives, l_04F46+2, 1,000: MOTHERFUCKENKIWIBASTARD typed on the title), F1 swaps
; the kiwi's handler for sub_08FD4 (he moves 4 pixels a step with the joystick, through
; anything; his handler kept at $5C(a6)) and F1 again gives it back (sub_08FD4 itself); then as
; the original: a0 = l_04F46, d0 = the starting lives. The cheat's level skip, the original's HELP
; key (tested next, at $43C8, from the 1,000 lives), is moved to F2: with the cheat on, F2 newly
; pressed goes to the next level here (l_054AE) and d0 is given as 3, so the HELP test finds no
; cheat.
EnhCheatKeys:   movem.l d1-d7/a1-a5,-(a7)
        jsr     sub_0900A                       ; (checks the cheat and F1 itself)
        movem.l (a7)+,d1-d7/a1-a5
        lea     l_04F46,a0
        cmpi.w  #1000,$2(a0)
        bne.b   .orig
        moveq   #$51,d0                         ; the cheat's level skip: F2 (newly pressed)
        jsr     (JT_KeyTest).w
        sne.b   d0
        move.b  SkipHeld(pc),d1
        move.b  d0,SkipHeld
        not.b   d1
        and.b   d1,d0
        beq.b   .help
        addq.l  #4,a7                           ; (as the original's bne.w l_054AE: the next level)
        jmp     l_054AE
.help:          moveq   #3,d0                   ; (not 1,000: the original's HELP test after this
        rts                                     ;   finds no cheat)
.orig:          move.w  $2(a0),d0
        rts
SkipHeld:       dc.b    0
	even

; sub_0BCDA: the game's display set up
EnhDisplay:     bsr.w   ScrLeave
        move.l  #$70000,$20(a6)
        jmp     l_0BCE2
