;==============================================================================
; scroller.s - the enhanced game's display during play: a corkscrew scroller with a vertical
; ring, double-buffered, with a pristine buffer (included by enhanced.s, in block 1).
;
; The original redraws the whole playfield - 20 x 11 tiles, 4 blits each - into the back screen
; on every pass of the game loop (sub_0B55C), then draws the BOBs over it. Here the playfield
; is kept in three buffers that are only updated where the view moves:
;
;   the pristine buffer   the background only: new tile columns / rows drawn from the map
;   display buffers A, B  shown alternately: their new columns / rows copied from the pristine
;                         buffer, the BOBs drawn over them, and each BOB's rectangle copied back
;                         from the pristine buffer before that buffer is drawn again
;
; Layout (every buffer the same, so a rectangle copies to the same offset in another one):
;   line-interleaved, 4 planes of 21 words (42 bytes): 168 bytes a line, 192 lines (a ring of
;   12 tile rows); the 20 words fetched start 2 x the camera's tile column into the buffer, so
;   scrolling right by a tile moves the bitplane pointers on a word and the column that left is
;   the memory of the one that comes in (the corkscrew); world line Y is ring line Y mod 192.
;     pixel (world column C, world line Y, plane p):  base + 2C + 168 (Y mod 192) + 42p
;   The copper list reloads the pointers where the ring wraps inside the 176 playfield lines,
;   and at the panel (line 176, the original's split: BPLCON1 $77) points them at the panel
;   buffer: 24 lines, line-interleaved, 4 x 40 bytes a line.
;
; Memory (all in the first 512K of chip RAM: $65400-$7FFFF, which the original uses only for
; its two screens, its disk / deinterleave buffer and pictures while loading or between games):
SCR_PANEL_A     equ     $65400                  ; 24 x 160 = 3,840
SCR_PANEL_B     equ     $66300
SCR_PRIST       equ     $67200                  ; 192 x 168 + 128 (64 columns of corkscrew) = 32,384
SCR_DISP_A      equ     $6F080
SCR_DISP_B      equ     $76F00
SCR_COPPER_A    equ     $7ED80                  ; the copper lists, 384 bytes each
SCR_COPPER_B    equ     $7EF00
SCR_RESTORE_A   equ     $7F080                  ; restore lists, 1,400 bytes each (175 rectangles)
SCR_RESTORE_B   equ     $7F600                  ; (to $7FB78)
;
; The display is in this mode from the first pass of the game loop (ScrEnter, from sub_0B55C)
; until the game clears its screens or sets up another display (ScrLeave: sub_0BB76,
; sub_0BCDA) or reads the disk (TrackRead). Its screens' memory ($70000 / $78000) is the
; buffers', so the game's screen addresses are translated: $20(a6) still names the back screen
; ($70000: A, $78000: B), and the line table (mem_63E94) gives virtual offsets, 64 bytes a
; line from 64, which the BOB blitter (ScrBob, for sub_0B8B4), the text printers and the panel
; fill translate into the buffers.
;
; Timing: the original's loop takes 2 frames a pass (25 fps) and its logic runs once a pass, so
; the loop is held to at least SCR_MIN_FRAMES frames a pass (EnhWaitFlip): the game runs at its
; original speed, without the original's slow-downs.
;==============================================================================

SCR_MIN_FRAMES  equ     2
SCR_ROWB        equ     42                      ; a plane's row: 21 words
SCR_LINE        equ     4*SCR_ROWB              ; 168
SCR_RING        equ     192                     ; lines (12 tile rows)
SCR_BUF         equ     SCR_RING*SCR_LINE+128
SCR_FIELD       equ     176                     ; playfield lines (then the panel)
SCR_PLINE       equ     160                     ; panel: bytes a line
SCR_PANEL_LINES equ     24
SCR_VBASE       equ     64                      ; the virtual line table: 64 + 64 y
SCR_MAXRESTORE  equ     175
MAP_ROWS        equ     dat_44B26               ; the level's map (+ $C(a6), rows of 64 going down)
TILES           equ     dat_3CB26               ; 16 x 16 tiles, 128 bytes (4 planes a line)

	ifne	SCR_PANEL_B-SCR_PANEL_A-SCR_PANEL_LINES*SCR_PLINE
	fail	scroller.s: panel layout
	endc
	ifne	SCR_DISP_A-SCR_PRIST-SCR_BUF
	fail	scroller.s: buffer layout
	endc
	ifne	SCR_DISP_B-SCR_DISP_A-SCR_BUF
	fail	scroller.s: buffer layout
	endc
	ifgt	SCR_DISP_B+SCR_BUF-SCR_COPPER_A
	fail	scroller.s: buffer layout
	endc
	ifgt	SCR_RESTORE_B+8*SCR_MAXRESTORE-$80000
	fail	scroller.s: the restore lists run past 512K
	endc

; the state
ScrActive:      dc.b    0                       ; the scroller's display is on
ScrSkipWait:    dc.b    0
ScrFrames:      dc.w    0                       ; vertical blanks (EnhVBL)
ScrLoopFrame:   dc.w    0                       ; ScrFrames when the last pass began drawing
ScrTakeFrame:   dc.w    0                       ; ScrFrames when the last frame was taken (EnhL6)
ScrCopNext:     dc.l    0                       ; the copper list for the level 6 interrupt
; per buffer (0 pristine, 1 A, 2 B): the window it holds (tile column, tile row), valid
ScrWinC:        dc.w    0,0,0
ScrWinR:        dc.w    0,0,0
ScrValid:       dc.b    0,0,0
	even
; per display buffer (A, B): the camera it was drawn for (its tile column, its top line),
; its restore list's length, its copper list's wrap: the line in the playfield (0: none) and
; the offset of the WAIT in the list
ScrDrawC:       dc.w    0,0
ScrDrawY:       dc.w    0,0
ScrRestN:       dc.w    0,0
ScrWrapLine:    dc.w    0,0
ScrWrapWait:    dc.w    0,0
ScrDiwTop:      dc.w    $3C                     ; the display window's first line (EnhDIW)

; the buffers' addresses by index (A = $70000's, B = $78000's)
ScrDispTab:     dc.l    SCR_DISP_A,SCR_DISP_B
ScrPanelTab:    dc.l    SCR_PANEL_A,SCR_PANEL_B
ScrCopTab:      dc.l    SCR_COPPER_A,SCR_COPPER_B
ScrRestTab:     dc.l    SCR_RESTORE_A,SCR_RESTORE_B

;------------------------------------------------------------------------------
; EnhVBL - the level 3 interrupt's add.l d1,(dat_0DD66).l (Level3_VBL), the frame count, and
; in the scroller's display the game's copper list's values from its BPLCON1 to its colours
; (sprite pointers, colours: SetPalette and the fades change them at any time) copied into the
; scroller's two lists, which hold the same instructions at SCR_COPBLK: so they take effect from
; the next frame, as in the game's own list. (BPLCON1, the fine scroll, is each list's own.)
SCR_COPBLK      equ     44                      ; DMACON, 8 pointers, 2 modulos: 11 x 4 bytes
EnhVBL:         add.l   d1,(dat_0DD66).l
        addq.w  #1,ScrFrames
        tst.b   ScrActive
        beq.b   .o
        movem.l d0-d1/a0-a2,-(a7)
        lea     SCR_COPPER_A+SCR_COPBLK,a1
        bsr.b   .copy
        lea     SCR_COPPER_B+SCR_COPBLK,a1
        bsr.b   .copy
        movem.l (a7)+,d0-d1/a0-a2
.o:             rts
.copy:          lea     CopperList+32,a0
.i:             move.w  (a0)+,d0
        btst    #0,d0
        bne.b   .end                            ; (the split's WAIT)
        cmp.w   (a1)+,d0
        bne.b   .end                            ; (a list not built yet)
        move.w  (a0)+,d1
        cmp.w   #$0102,d0
        beq.b   .skip
        move.w  d1,(a1)
.skip:          addq.l  #2,a1
        bra.b   .i
.end:           rts

; EnhDIW - the level 3 interrupt's write of DIWSTRT (the screen shake, $64(a6)): the copper
; lists' ring wraps follow the window's first line
EnhDIW:         move.w  d1,(CUSTOM+DIWSTRT).l
        movem.l d0/a0-a1,-(a7)
        moveq   #0,d0
        move.w  d1,d0
        lsr.w   #8,d0
        move.w  d0,ScrDiwTop
        tst.b   ScrActive
        beq.b   .out
        lea     ScrCopTab(pc),a0
        bsr.b   .patch
        addq.l  #4,a0
        bsr.b   .patch
.out:           movem.l (a7)+,d0/a0-a1
        rts
.patch:         movea.l (a0),a1                 ; a0 -> its copper list; the offsets: 4 on
        move.l  a0,d1
        sub.l   #ScrCopTab,d1
        lsr.w   #1,d1                           ; (the buffer's word index)
        lea     ScrWrapLine(pc),a1
        move.w  (a1,d1.w),d0
        beq.b   .none
        add.w   ScrDiwTop(pc),d0
        lsl.w   #8,d0
        addq.w  #1,d0
        lea     ScrWrapWait(pc),a1
        move.w  (a1,d1.w),d1
        movea.l (a0),a1
        move.w  d0,(a1,d1.w)
.none:          move.w  ScrDiwTop(pc),d1        ; (d1 restored for the caller)
        lsl.w   #8,d1
        rts

; EnhL6 - the level 6 interrupt's movea.l (mem_63DDC).l,a0 (Level6_CIAB): when a new frame is
; ready, the scroller's copper list for it (taken at the next vertical blank)
EnhL6:          movea.l (mem_63DDC).l,a0
        move.w  ScrFrames(pc),ScrTakeFrame      ; (smooth.s: the frame it was taken in)
        bsr.w   SmoothTaken
        tst.b   ScrActive
        beq.b   .o
        move.l  ScrCopNext(pc),(CUSTOM+COP1LCH).l
.o:             rts

; EnhWaitFlip - sub_0BCD0: wait until the last frame has been taken (as the original), and
; until SCR_MIN_FRAMES frames since the last pass began drawing
EnhWaitFlip:
.wait:          tst.b   (mem_63DDA).l
        bne.b   .wait
        tst.b   SmoothOn                        ; smooth.s: in the game loop (called from $42DA)
        beq.b   .old                            ;   the frames are paced at the flips (EnhFlip),
        tst.b   ScrActive                       ;   then the in-between frame
        beq.b   .old
        cmpi.l  #$42de,(a7)
        bne.b   .old
        move.w  ScrFrames(pc),ScrLoopFrame
        bra.w   SmoothMid
.old:           move.l  d0,-(a7)
.pace:          move.w  ScrFrames(pc),d0
        sub.w   ScrLoopFrame(pc),d0
        cmp.w   #SCR_MIN_FRAMES,d0
        bcs.b   .pace
        move.w  ScrFrames(pc),ScrLoopFrame
        move.l  (a7)+,d0
        rts

;------------------------------------------------------------------------------
; EnhScroll - from sub_0B55C, once it has set the fine scroll ($36, $3A): the playfield for
; this pass in the back buffer, instead of the original's full redraw. a6 = the globals.
EnhScroll:
        movem.l d0-d7/a0-a5,-(a7)
        tst.b   ScrActive
        bne.b   .on
        bsr.w   ScrEnter
.on:            moveq   #0,d0
        move.w  $2e(a6),d0                      ; the camera: its tile column, its top line
        lsr.w   #4,d0
        move.w  $30(a6),d1
        moveq   #0,d2
        move.w  d1,d2
        lsr.w   #4,d2                           ; its top tile row
        moveq   #0,d7                           ; the pristine buffer
        bsr.w   ScrUpdate
        bsr.w   ScrBack                         ; d7 = 1 / 2: the back buffer
        bsr.w   ScrUpdate
        move.w  d7,d3
        subq.w  #1,d3
        add.w   d3,d3
        lea     ScrDrawC(pc),a0
        move.w  d0,(a0,d3.w)
        lea     ScrDrawY(pc),a0
        move.w  d1,(a0,d3.w)
        bsr.w   ScrRestore                      ; the BOBs' rectangles back from the pristine buffer
        movem.l (a7)+,d0-d7/a0-a5
        rts

; ScrBack - d7 = the back buffer's index (1: A, the $70000 screen; 2: B)
ScrBack:        moveq   #1,d7
        tst.w   $20+2(a6)                       ; ($70000 or $78000)
        bpl.b   .a
        moveq   #2,d7
.a:             rts

;------------------------------------------------------------------------------
; ScrUpdate - buffer d7 (0 pristine, 1 A, 2 B) brought to the window: tile column d0, tile row
; d2 (the camera's). The pristine buffer draws what is new from the map; a display buffer
; copies it from the pristine buffer. Keeps d0-d2, d7.
ScrUpdate:      movem.l d0-d2/d7,-(a7)
        move.w  d7,d6
        add.w   d6,d6
        lea     ScrWinC(pc),a0
        lea     ScrWinR(pc),a1
        lea     ScrValid(pc),a2
        tst.b   (a2,d7.w)
        beq.b   .full
        move.w  d0,d3
        sub.w   (a0,d6.w),d3                    ; columns moved
        move.w  d2,d4
        sub.w   (a1,d6.w),d4                    ; rows moved
        move.w  d3,d5
        bpl.b   .c
        neg.w   d5
.c:             cmp.w   #4,d5
        bhi.b   .full
        move.w  d4,d5
        bpl.b   .r
        neg.w   d5
.r:             cmp.w   #4,d5
        bhi.b   .full
; the new columns
        tst.w   d3
        beq.b   .rows
        bmi.b   .left
        move.w  (a0,d6.w),d5                    ; right: columns old+21 .. new+20
        add.w   #21,d5
        subq.w  #1,d3
.rcol:          bsr.w   ScrColumn
        addq.w  #1,d5
        dbra    d3,.rcol
        bra.b   .rows
.left:          move.w  d0,d5                   ; left: columns new .. old-1
        neg.w   d3
        subq.w  #1,d3
.lcol:          bsr.w   ScrColumn
        addq.w  #1,d5
        dbra    d3,.lcol
.rows:          tst.w   d4
        beq.b   .done
        bmi.b   .up
        move.w  (a1,d6.w),d5                    ; down: rows old+12 .. new+11
        add.w   #12,d5
        subq.w  #1,d4
.drow:          bsr.w   ScrRow
        addq.w  #1,d5
        dbra    d4,.drow
        bra.b   .done
.up:            move.w  d2,d5                   ; up: rows new .. old-1
        neg.w   d4
        subq.w  #1,d4
.urow:          bsr.w   ScrRow
        addq.w  #1,d5
        dbra    d4,.urow
        bra.b   .done
.full:          bsr.w   ScrFull
        st.b    (a2,d7.w)
.done:          move.w  d0,(a0,d6.w)
        move.w  d2,(a1,d6.w)
        movem.l (a7)+,d0-d2/d7
        rts

; ScrColumn - column d5 of buffer d7 for rows d2 .. d2+11 (window column d0). Keeps d0-d7, a0-a2.
ScrColumn:      movem.l d0-d7/a0-a2,-(a7)
        tst.w   d7
        bne.b   .copy
        moveq   #11,d4                          ; the pristine buffer: 12 tiles
        move.w  d2,d6
.t:             move.w  d5,d0
        move.w  d6,d1
        bsr.w   ScrTile
        addq.w  #1,d6
        dbra    d4,.t
        bra.b   .out
.copy:          bsr.w   ScrBufBase              ; a1 = the display buffer
        moveq   #0,d1
        move.w  d5,d1
        add.l   d1,d1
        lea     SCR_PRIST,a0
        adda.l  d1,a0
        adda.l  d1,a1
        move.w  #SCR_ROWB-2,d0                  ; the whole ring's column: 768 rows of a word
        move.w  #(SCR_RING*4)<<6|1,d1
        bsr.w   ScrCopy
.out:           movem.l (a7)+,d0-d7/a0-a2
        rts

; ScrRow - row d5 of buffer d7 for columns d0 .. d0+20. Keeps d0-d7, a0-a2.
ScrRow:         movem.l d0-d7/a0-a2,-(a7)
        tst.w   d7
        bne.b   .copy
        moveq   #20,d4                          ; the pristine buffer: 21 tiles
        move.w  d0,d6
.t:             move.w  d6,d0
        move.w  d5,d1
        bsr.w   ScrTile
        addq.w  #1,d6
        dbra    d4,.t
        bra.b   .out
.copy:          bsr.w   ScrBufBase              ; a display buffer: one block of 64 x 42 bytes
        move.w  d5,d1
        bsr.w   ScrRowOffset                    ; d1.l = 2 x column d0 + its ring line x 168
        lea     SCR_PRIST,a0
        adda.l  d1,a0
        adda.l  d1,a1
        moveq   #0,d0
        move.w  #(16*4)<<6|21,d1
        bsr.w   ScrCopy
.out:           movem.l (a7)+,d0-d7/a0-a2
        rts

; ScrFull - buffer d7 entirely for the window (column d0, row d2). Keeps d0-d7, a0-a2.
ScrFull:        movem.l d0-d7/a0-a2,-(a7)
        tst.w   d7
        bne.b   .copy
        moveq   #11,d4                          ; the pristine buffer: 21 x 12 tiles
        move.w  d2,d5
.row:           bsr.w   ScrRow
        addq.w  #1,d5
        dbra    d4,.row
        bra.b   .out
.copy:          bsr.w   ScrBufBase              ; a display buffer: the ring, 384 x 84 bytes
        moveq   #0,d1
        move.w  d0,d1
        add.l   d1,d1
        lea     SCR_PRIST,a0
        adda.l  d1,a0
        adda.l  d1,a1
        moveq   #0,d0
        move.w  #((SCR_RING*SCR_LINE)/84)<<6|42,d1
        bsr.w   ScrCopy
.out:           movem.l (a7)+,d0-d7/a0-a2
        rts

; ScrRowOffset - d0 = tile column, d1 = tile row -> d1.l = 2 x column + 168 x ring line of the
; row's first line
ScrRowOffset:   move.l  d0,-(a7)
        and.l   #$ffff,d1
        divu    #SCR_RING/16,d1
        swap    d1                              ; row mod 12
        mulu    #16*SCR_LINE,d1
        and.l   #$ffff,d0
        add.l   d0,d1
        add.l   d0,d1
        move.l  (a7)+,d0
        rts

; ScrBufBase - a1 = display buffer d7's address (1: A, 2: B)
ScrBufBase:     move.w  d7,d1
        subq.w  #1,d1
        add.w   d1,d1
        add.w   d1,d1
        lea     ScrDispTab(pc),a1
        movea.l (a1,d1.w),a1
        rts

; ScrTile - the tile at map column d0, row d1 into the pristine buffer (one blit: 64 rows of a
; word, the tile's lines already interleaved as the buffer's). Uses d0-d1, a0-a1.
ScrTile:        moveq   #0,d3
        move.w  d1,d3
        lsl.w   #6,d3                           ; row x 64
        lea     MAP_ROWS,a0
        adda.w  $c(a6),a0
        suba.l  d3,a0
        moveq   #0,d3
        move.b  (a0,d0.w),d3                    ; the tile
        lsl.w   #7,d3
        lea     TILES,a0
        adda.l  d3,a0
        bsr.b   ScrRowOffset
        lea     SCR_PRIST,a1
        adda.l  d1,a1
        move.w  #SCR_ROWB-2,d0
        move.w  #(16*4)<<6|1,d1
        moveq   #0,d3                           ; (A modulo 0)
        bra.b   ScrCopy0

; ScrCopy - a blit from a0 to a1: d0 = both modulos, d1 = BLTSIZE. ScrCopy0: A modulo 0.
ScrCopy:        move.w  d0,d3
ScrCopy0:       lea     CUSTOM,a2
        bsr.w   ScrBlitWait
        move.l  #$09f00000,BLTCON0(a2)
        move.l  #$ffffffff,BLTAFWM(a2)
        move.w  d3,BLTAMOD(a2)
        move.w  d0,BLTDMOD(a2)
        move.l  a0,BLTAPTH(a2)
        move.l  a1,BLTDPTH(a2)
        move.w  d1,BLTSIZE(a2)
        rts

ScrBlitWait:    btst    #6,DMACONR(a2)
.w:             btst    #6,DMACONR(a2)
        bne.b   .w
        rts

;------------------------------------------------------------------------------
; ScrRestore - the back buffer (d7)'s BOB rectangles from its last frame, copied back from the
; pristine buffer (each one blit: its 4 planes' rows are 42 bytes apart). Keeps d7.
ScrRestore:     move.w  d7,d6
        subq.w  #1,d6
        add.w   d6,d6
        lea     ScrRestN(pc),a3
        move.w  (a3,d6.w),d5
        clr.w   (a3,d6.w)
        add.w   d6,d6
        lea     ScrRestTab(pc),a3
        movea.l (a3,d6.w),a3
        lsr.w   #1,d6
        lea     ScrDispTab(pc),a4
        add.w   d6,d6
        move.l  (a4,d6.w),d4                    ; this buffer - the pristine buffer
        sub.l   #SCR_PRIST,d4
        bra.b   .next
.one:           movea.l (a3)+,a1
        move.w  (a3)+,d1
        move.w  (a3)+,d0
        movea.l a1,a0
        suba.l  d4,a0
        bsr.w   ScrCopy
.next:          dbra    d5,.one
        rts

; ScrMark - a rectangle of display buffer d7 to restore before it is drawn again: a1 = its
; plane 0 address, d0 = its BLTSIZE (4 rows a line), d1 = the modulo. Keeps the registers.
ScrMark:        movem.l d2/a2,-(a7)
        move.w  d7,d2
        subq.w  #1,d2
        add.w   d2,d2
        lea     ScrRestN(pc),a2
        cmpi.w  #SCR_MAXRESTORE,(a2,d2.w)
        bcc.b   .full
        move.w  (a2,d2.w),-(a7)
        addq.w  #1,(a2,d2.w)
        add.w   d2,d2
        lea     ScrRestTab(pc),a2
        movea.l (a2,d2.w),a2
        move.w  (a7)+,d2
        lsl.w   #3,d2
        adda.w  d2,a2
        move.l  a1,(a2)+
        move.w  d0,(a2)+
        move.w  d1,(a2)
.full:          movem.l (a7)+,d2/a2
        rts

;------------------------------------------------------------------------------
; ScrMap - a screen address of the game's (a0: $70000 / $78000 + the virtual offset 64 + 64y +
; x byte, x from -2) -> d7 = the buffer (1 A, 2 B), d4 = y, d5 = the x byte (signed),
; a1 = the address in the buffer: the playfield (y < 176) or the panel. Uses d1.
ScrMap:         moveq   #1,d7
        move.l  a0,d1
        and.l   #$ffff,d1
        bclr    #15,d1
        beq.b   .a
        moveq   #2,d7
.a:             sub.w   #SCR_VBASE-16,d1        ; (x from -2 to 40: y = (off - 48) / 64)
        move.w  d1,d4
        lsr.w   #6,d4
        and.w   #63,d1
        sub.w   #16,d1
        move.w  d1,d5
; ScrAddr - d7 = buffer, d4 = y, d5 = x byte (signed) -> a1: in the playfield (y < 176) the
; display buffer for the camera it was drawn for, else the panel. Uses d1.
ScrAddr:        move.w  d7,d1
        subq.w  #1,d1
        add.w   d1,d1                           ; (word index)
        cmp.w   #SCR_FIELD,d4
        bcc.b   .panel
        movem.l d0/d2,-(a7)
        lea     ScrDrawY(pc),a1
        move.w  (a1,d1.w),d2
        add.w   d4,d2                           ; the world line
        and.l   #$ffff,d2
        divu    #SCR_RING,d2
        swap    d2
        mulu    #SCR_LINE,d2                    ; its ring line x 168
        lea     ScrDrawC(pc),a1
        moveq   #0,d0
        move.w  (a1,d1.w),d0
        add.l   d0,d0
        add.l   d0,d2                           ; + 2 x the tile column
        move.w  d5,d0
        ext.l   d0
        add.l   d0,d2                           ; + the x byte
        add.w   d1,d1
        lea     ScrDispTab(pc),a1
        movea.l (a1,d1.w),a1
        adda.l  d2,a1
        movem.l (a7)+,d0/d2
        rts
.panel:         add.w   d1,d1
        lea     ScrPanelTab(pc),a1
        movea.l (a1,d1.w),a1
        move.w  d4,d1
        sub.w   #SCR_FIELD,d1
        mulu    #SCR_PLINE,d1
        adda.l  d1,a1
        move.w  d5,d1
        ext.l   d1
        adda.l  d1,a1
        rts

; ScrRingLeft - d7 = buffer, d4 = y (playfield) -> d1 = the lines from y to the ring's end
ScrRingLeft:    move.w  d7,d1
        subq.w  #1,d1
        add.w   d1,d1
        move.l  a1,-(a7)
        lea     ScrDrawY(pc),a1
        move.w  (a1,d1.w),d1
        movea.l (a7)+,a1
        add.w   d4,d1
        and.l   #$ffff,d1
        divu    #SCR_RING,d1
        swap    d1
        neg.w   d1
        add.w   #SCR_RING,d1
        rts

;------------------------------------------------------------------------------
; ScrBob - sub_0B8B4 in the scroller's display: one BOB's 4 cookie-cut blits as the original's
; (A the mask, B the plane, C = D the screen; BLTCON0's low 12 bits from the immediate at
; BobMinterm, which BlitBob changes), translated into the buffers. In: a0 = the screen address,
; a1 = the frame, d5 / d4 = the offsets into it (x clip, y clip), d2 = its plane size, d6 = its
; modulo, d7 = the shift (bits 12-15), d0 = BLTSIZE; BlitBob has set the first / last word masks.
; A part in the playfield is split where the ring wraps and marked for restoring; a part in
; the panel is not (the original never redraws the panel either). Keeps every register but d1
; and d7 (d7 = BLTCON0 as the original leaves it).
ScrBob:         movem.l d0/d2-d6/a0-a6,-(a7)
        lea     ScrBobVars(pc),a5
        and.w   #$f000,d7
        move.w  d7,(a5)                         ; +0 the shift
        move.w  d0,d1
        and.w   #63,d1
        move.w  d1,2(a5)                        ; +2 w
        lsr.w   #6,d0
        move.w  d0,4(a5)                        ; +4 h
        move.w  d6,6(a5)                        ; +6 the frame's modulo
        move.l  d2,8(a5)                        ; +8 the plane size
        adda.w  d5,a1
        adda.l  d4,a1
        move.l  a1,12(a5)                       ; +12 the mask's first line
        add.w   d1,d1
        add.w   d6,d1
        move.w  d1,16(a5)                       ; +16 a source line: 2w + modulo
        bsr.w   ScrMap                          ; d7 buffer, d4 y, d5 x byte
        move.w  4(a5),d6                        ; lines left
.part:          cmp.w   #SCR_FIELD,d4
        bcc.b   .panel
        move.w  #SCR_FIELD,d3                   ; the playfield: up to its end and the ring's
        sub.w   d4,d3
        bsr.w   ScrRingLeft
        cmp.w   d1,d3
        bls.b   .f1
        move.w  d1,d3
.f1:            cmp.w   d6,d3
        bls.b   .f2
        move.w  d6,d3
.f2:            bsr.w   ScrAddr                 ; a1
        move.w  #SCR_LINE,d1
        sub.w   2(a5),d1
        sub.w   2(a5),d1                        ; the screen modulo: 168 - 2w
        moveq   #SCR_ROWB,d2                    ; planes 42 apart
        bsr.w   ScrBobBlit
        move.w  d3,d0                           ; marked: d3 lines x 4 planes
        lsl.w   #8,d0                           ; (x 4 << 6)
        or.w    2(a5),d0
        moveq   #SCR_ROWB,d1
        sub.w   2(a5),d1
        sub.w   2(a5),d1
        bsr.w   ScrMark
        bra.b   .next
.panel:         move.w  d6,d3                   ; the panel: the rest
        bsr.w   ScrAddr
        move.w  #SCR_PLINE,d1
        sub.w   2(a5),d1
        sub.w   2(a5),d1
        moveq   #SCR_PLINE/4,d2                 ; planes 40 apart
        bsr.w   ScrBobBlit
        tst.b   SmoothOn                        ; smooth.s: in both buffers' panels
        beq.b   .next
        move.w  d7,-(a7)
        moveq   #3,d0
        sub.w   d7,d0
        move.w  d0,d7
        bsr.w   ScrAddr
        move.w  #SCR_PLINE,d1
        sub.w   2(a5),d1
        sub.w   2(a5),d1
        bsr.w   ScrBobBlit
        move.w  (a7)+,d7
.next:          add.w   d3,d4                   ; the next part
        move.w  d3,d0
        mulu    16(a5),d0
        add.l   d0,12(a5)
        sub.w   d3,d6
        bne.w   .part
        movem.l (a7)+,d0/d2-d6/a0-a6
        move.w  BobMinterm,d1                   ; d7 as the original leaves it
        or.w    ScrBobVars(pc),d1
        move.w  d1,d7
        rts

; ScrBobBlit - one part: a1 = the screen, d3 = lines, d1 = the screen modulo, d2 = the planes'
; distance; ScrBobVars as set. Uses d0-d1, a0, a2-a4.
ScrBobBlit:     lea     CUSTOM,a2
        movea.l 12(a5),a3                       ; the mask
        movea.l a3,a4
        adda.l  8(a5),a4                        ; plane 0
        movea.l a1,a0
        move.w  d3,d0
        lsl.w   #6,d0
        or.w    2(a5),d0                        ; BLTSIZE
        movem.l d5/d7,-(a7)
        move.w  BobMinterm,d5
        or.w    (a5),d5                         ; BLTCON0: the shift, the channels, the minterm
        moveq   #3,d7
.plane:         bsr.w   ScrBlitWait
        move.w  d5,BLTCON0(a2)
        move.w  (a5),BLTCON1(a2)                ; B shifted as A
        move.w  6(a5),BLTAMOD(a2)
        move.w  6(a5),BLTBMOD(a2)
        move.w  d1,BLTCMOD(a2)
        move.w  d1,BLTDMOD(a2)
        move.l  a3,BLTAPTH(a2)
        move.l  a4,BLTBPTH(a2)
        move.l  a0,BLTCPTH(a2)
        move.l  a0,BLTDPTH(a2)
        move.w  d0,BLTSIZE(a2)
        adda.l  8(a5),a4
        adda.w  d2,a0
        dbra    d7,.plane
        movem.l (a7)+,d5/d7
        rts

ScrBobVars:     dcb.b   18,0
	even

;------------------------------------------------------------------------------
; ScrEnter - into the scroller's display (the first pass of the game loop): the panels taken
; from the game's two screens (lines 176-199: lives, score, oxygen, as the game drew them), the
; line table made virtual, every buffer to be drawn in full. The bitplanes are off until the
; first copper list of the scroller's turns them on (the screens' memory is the buffers').
ScrEnter:       movem.l d0-d7/a0-a2,-(a7)
        move.w  #$0100,(CUSTOM+DMACON).l        ; bitplanes off
        lea     $70000+SCR_FIELD*40,a0          ; the panels: planar -> interleaved
        lea     SCR_PANEL_A,a1
        bsr.b   .panel
        lea     $78000+SCR_FIELD*40,a0
        lea     SCR_PANEL_B,a1
        bsr.b   .panel
        lea     (mem_63E94).l,a0                ; the line table: 64 + 64y
        moveq   #SCR_VBASE,d0
        move.w  #199,d1
.lt:            move.l  d0,(a0)+
        add.l   #64,d0
        dbra    d1,.lt
        lea     ScrValid(pc),a0
        clr.b   (a0)+
        clr.b   (a0)+
        clr.b   (a0)+
        lea     ScrRestN(pc),a0
        clr.l   (a0)
        move.w  $2e(a6),d0                      ; (both drawn for the camera, until drawn)
        lsr.w   #4,d0
        lea     ScrDrawC(pc),a0
        move.w  d0,(a0)+
        move.w  d0,(a0)
        lea     ScrDrawY(pc),a0
        move.w  $30(a6),(a0)+
        move.w  $30(a6),(a0)
        move.w  ScrFrames(pc),ScrLoopFrame
        sf.b    SmoothValid                     ; (smooth.s: no last frame to move from,
        sf.b    SmoothSValid                    ;   nor a frame taken to pace from)
        st.b    ScrActive
        movem.l (a7)+,d0-d7/a0-a2
        rts
.panel:         moveq   #SCR_PANEL_LINES-1,d1   ; a0 = the screen's line 176, a1 = the panel
.pl:            moveq   #3,d2
        movea.l a0,a2
.pp:            moveq   #10-1,d3                ; 40 bytes
.pb:            move.l  (a2)+,(a1)+
        dbra    d3,.pb
        lea     $2000-40(a2),a2
        dbra    d2,.pp
        lea     40(a0),a0
        dbra    d1,.pl
        rts

; ScrLeave - back to the game's own display (its screens at $70000 / $78000, CopperList, the
; line table of 40 bytes a line). The screens' memory holds the buffers: the game clears them
; (sub_0BB76) or draws a new screen next. Keeps every register.
ScrLeave:       tst.b   ScrActive
        beq.b   .out
        movem.l d0-d1/a0,-(a7)
        sf.b    ScrActive
        sf.b    SmoothValid
        lea     (mem_63E94).l,a0
        moveq   #0,d0
        move.w  #199,d1
.lt:            move.l  d0,(a0)+
        add.l   #40,d0
        dbra    d1,.lt
        move.l  #CopperList,(CUSTOM+COP1LCH).l  ; (from the next frame)
        move.w  #$8100,(CUSTOM+DMACON).l
        movem.l (a7)+,d0-d1/a0
.out:           rts

;------------------------------------------------------------------------------
; EnhFlip - the end of sub_0BC8C (the frame is ready: st.b (mem_63DDA).l): in the scroller's
; display, the copper list for the buffer just drawn, for the level 6 interrupt to take
EnhFlip:        tst.b   ScrActive
        beq.b   .o
        movem.l d0-d7/a0-a3,-(a7)
        bsr.w   ScrBack                         ; (the flip has swapped them: the one drawn is
        moveq   #3,d0                           ; the other one)
        sub.w   d7,d0
        move.w  d0,d7
        bsr.w   ScrCopper
        move.l  a0,ScrCopNext
        bsr.w   SmoothPace                      ; (smooth.s: not before its frame)
        movem.l (a7)+,d0-d7/a0-a3
.o:             st.b    (mem_63DDA).l
        rts

; ScrCopper - the copper list of display buffer d7 -> a0 = it:
;   bitplanes on; the pointers for its first line; modulos 128; the game's list from BPLCON1
;   (its fine scroll, $3C(a6)) to its colours; where the ring wraps in the playfield, a WAIT
;   and the pointers of ring line 0; the game's split ($EC: BPLCON1 $77) with the panel's
;   pointers and modulos 120; the end
ScrCopper:      move.w  d7,d6
        subq.w  #1,d6
        add.w   d6,d6                           ; d6 = word index
        lea     ScrWrapLine(pc),a0              ; (no patching by EnhDIW while it is rebuilt)
        clr.w   (a0,d6.w)
        lea     ScrCopTab(pc),a0
        move.w  d6,d0
        add.w   d0,d0
        movea.l (a0,d0.w),a0
        movea.l a0,a3                           ; (the list's start)
        move.l  #$00968100,(a0)+
        lea     ScrDrawY(pc),a1
        moveq   #0,d1
        move.w  (a1,d6.w),d1
        divu    #SCR_RING,d1
        swap    d1                              ; the first line's ring line
        move.w  d1,d5
        mulu    #SCR_LINE,d1
        lea     ScrDrawC(pc),a1
        moveq   #0,d2
        move.w  (a1,d6.w),d2
        add.l   d2,d2                           ; 2 x the tile column
        lea     ScrDispTab(pc),a1
        move.w  d6,d0
        add.w   d0,d0
        move.l  (a1,d0.w),d3
        add.l   d2,d3                           ; d3 = the buffer + 2 x column (ring line 0)
        move.l  d3,d0
        add.l   d1,d0
        moveq   #SCR_ROWB,d4
        bsr.w   .ptrs
        move.l  #$01080000+SCR_LINE-40,(a0)+
        move.l  #$010A0000+SCR_LINE-40,(a0)+
        lea     CopperList+32,a1                ; the game's: BPLCON1 .. the colours
.copy:          move.w  (a1)+,d0
        btst    #0,d0
        bne.b   .copied                         ; (its split WAIT)
        move.w  d0,(a0)+
        cmp.w   #$0102,d0
        bne.b   .val
        move.w  $3c(a6),(a0)+                   ; the fine scroll
        addq.l  #2,a1
        bra.b   .copy
.val:           move.w  (a1)+,(a0)+
        bra.b   .copy
.copied:        move.w  #SCR_RING,d0            ; the ring's wrap
        sub.w   d5,d0
        lea     ScrWrapLine(pc),a1
        cmp.w   #SCR_FIELD,d0
        bcc.b   .nowrap
        move.l  a0,d1
        sub.l   a3,d1
        lea     ScrWrapWait(pc),a1
        move.w  d1,(a1,d6.w)
        move.w  d0,-(a7)                        ; (ScrWrapLine set when the list is complete)
        add.w   ScrDiwTop(pc),d0
        lsl.w   #8,d0
        addq.w  #1,d0
        move.w  d0,(a0)+
        move.w  #$fffe,(a0)+
        move.l  d3,d0
        moveq   #SCR_ROWB,d4
        bsr.b   .ptrs
        move.w  (a7)+,d0
        lea     ScrWrapLine(pc),a1
        move.w  d0,(a1,d6.w)
.nowrap:
.split:         move.l  (dat_0C366).l,(a0)+     ; the game's split and BPLCON1 $77
        move.l  (dat_0C366+4).l,(a0)+
        lea     ScrPanelTab(pc),a1
        move.w  d6,d0
        add.w   d0,d0
        move.l  (a1,d0.w),d0
        moveq   #SCR_PLINE/4,d4
        bsr.b   .ptrs
        move.l  #$01080000+SCR_PLINE-40,(a0)+
        move.l  #$010A0000+SCR_PLINE-40,(a0)+
        move.l  #$fffffffe,(a0)+
        movea.l a3,a0
        rts
; .ptrs - the 4 bitplane pointers: d0 = plane 0, d4 = the planes' distance
.ptrs:          move.w  #$00e0,d1
        moveq   #3,d2
.p:             move.w  d1,(a0)+
        swap    d0
        move.w  d0,(a0)+
        swap    d0
        addq.w  #2,d1
        move.w  d1,(a0)+
        move.w  d0,(a0)+
        addq.w  #2,d1
        add.l   d4,d0
        dbra    d2,.p
        rts

;------------------------------------------------------------------------------
; The text printers and the panel fill in the scroller's display: the same pixels as the
; game's, written into both display buffers (as the game writes both screens).
;
; ScrPrintCol - sub_0C744's character (d0) at character column $4(a6), line $6(a6): 8 lines of
; a byte, each plane background or foreground colour (dat_0C734-dat_0C73B); the cursor moved on
; as the game's. Keeps the registers.
ScrPrintCol:    movem.l d0-d7/a0-a4,-(a7)
        and.w   #$ff,d0
        sub.w   #$20,d0
        lsl.w   #3,d0
        lea     dat_0DA66,a3
        adda.w  d0,a3                           ; the glyph
        move.w  $6(a6),d4                       ; y
        move.w  $4(a6),d5                       ; x byte
        moveq   #7,d6
.line:          move.b  (a3)+,d2
        moveq   #1,d7                           ; both buffers
.buf:           bsr.w   ScrAddr
        bsr.w   ScrPlaneStep                    ; d3 = the planes' distance
        lea     dat_0C737,a4                    ; plane 0's background (3 - p), foreground (+4)
        movea.l a1,a0
        moveq   #3,d1
.plane:         move.b  (a4),d0
        not.b   d2
        and.b   d2,d0
        not.b   d2
        move.b  4(a4),-(a7)
        and.b   d2,(a7)
        or.b    (a7)+,d0
        move.b  d0,(a0)
        adda.w  d3,a0
        subq.l  #1,a4
        dbra    d1,.plane
        bsr.w   ScrMarkByte
        addq.w  #1,d7
        cmp.w   #2,d7
        bls.b   .buf
        addq.w  #1,d4
        dbra    d6,.line
        addq.w  #1,$4(a6)                       ; the cursor, as the game's
        cmpi.w  #$28,$4(a6)
        blt.b   .out
        clr.w   $4(a6)
        addq.w  #8,$6(a6)
        cmpi.w  #$c8,$6(a6)
        blt.b   .out
        clr.w   $6(a6)
.out:           movem.l (a7)+,d0-d7/a0-a4
        rts

; ScrPrintPix - sub_0C84C's character (d0) at pixel $4(a6), line $6(a6): each line's byte shifted
; into two, over what the back screen holds; the cursor moved on as the game's. Keeps the
; registers.
ScrPrintPix:    movem.l d0-d7/a0-a5,-(a7)
        and.w   #$ff,d0
        sub.w   #$20,d0
        lsl.w   #3,d0
        lea     dat_0DA66,a3
        adda.w  d0,a3
        move.w  $6(a6),d4
        moveq   #7,d6
.line:          moveq   #0,d2
        move.b  (a3)+,d2
        move.w  $4(a6),d0
        and.w   #7,d0
        ror.w   d0,d2                           ; the glyph's line, shifted: low byte, then high
        move.w  $4(a6),d5
        asr.w   #3,d5                           ; its first byte
        bsr.b   .byte
        ror.w   #8,d2
        addq.w  #1,d5
        bsr.b   .byte
        addq.w  #1,d4
        dbra    d6,.line
        addq.w  #8,$4(a6)
        cmpi.w  #$140,$4(a6)
        blt.b   .out
        clr.w   $4(a6)
        addq.w  #8,$6(a6)
        cmpi.w  #$c8,$6(a6)
        blt.b   .out
        clr.w   $6(a6)
.out:           movem.l (a7)+,d0-d7/a0-a5
        rts
; .byte - the low byte of d2 (the glyph's bits) at line d4, byte d5: each plane from the back
; buffer, the bits in the foreground colour (dat_0C73B - p), written to both buffers
.byte:          bsr.w   ScrBack
        bsr.w   ScrAddr
        bsr.w   ScrPlaneStep
        lea     dat_0C73B,a4
        lea     ScrPixVals(pc),a5
        movea.l a1,a0
        moveq   #3,d1
.p:             move.b  (a0),d0
        move.b  d2,d7
        not.b   d7
        and.b   d7,d0
        move.b  d2,d7
        and.b   (a4),d7
        or.b    d7,d0
        move.b  d0,(a5)+
        adda.w  d3,a0
        subq.l  #1,a4
        dbra    d1,.p
        bsr.w   ScrBack
        bsr.b   .put
        moveq   #3,d0
        sub.w   d7,d0
        move.w  d0,d7
.put:           bsr.w   ScrAddr                 ; buffer d7: the 4 values
        lea     ScrPixVals(pc),a5
        movea.l a1,a0
        moveq   #3,d1
.w:             move.b  (a5)+,(a0)
        adda.w  d3,a0
        dbra    d1,.w
        bra.w   ScrMarkByte
ScrPixVals:     dc.b    0,0,0,0

; ScrPlaneStep - d4 = y -> d3 = the planes' distance there (42 in the playfield, 40 in the panel)
ScrPlaneStep:   moveq   #SCR_ROWB,d3
        cmp.w   #SCR_FIELD,d4
        bcs.b   .f
        moveq   #SCR_PLINE/4,d3
.f:             rts

; ScrMarkByte - a byte written at a1 (line d4, buffer d7): in the playfield, its word's 4
; planes marked for restoring. Keeps the registers.
ScrMarkByte:    cmp.w   #SCR_FIELD,d4
        bcc.b   .no
        movem.l d0-d1/a1,-(a7)
        move.l  a1,d0
        bclr    #0,d0
        movea.l d0,a1
        move.w  #4<<6|1,d0
        moveq   #SCR_ROWB-2,d1
        bsr.w   ScrMark
        movem.l (a7)+,d0-d1/a1
.no:            rts

; ScrFill - sub_0C78's fill in both screens: a0 = the screen offset (40 bytes a line), d1 =
; words << 16 | lines, d0 = the word, in all 4 planes. Keeps the registers.
ScrFill:        movem.l d0-d7/a0-a2,-(a7)
        move.l  a0,d4
        divu    #40,d4
        move.l  d4,d5
        swap    d5                              ; x byte
        move.w  d1,d6
        subq.w  #1,d6                           ; lines - 1
        swap    d1
        move.w  d1,a2                           ; words
.line:          move.w  a2,d2
        subq.w  #1,d2
        move.w  d5,-(a7)
.word:          moveq   #1,d7
.buf:           bsr.w   ScrAddr
        bsr.w   ScrPlaneStep
        movea.l a1,a0
        move.w  d0,(a0)
        adda.w  d3,a0
        move.w  d0,(a0)
        adda.w  d3,a0
        move.w  d0,(a0)
        adda.w  d3,a0
        move.w  d0,(a0)
        bsr.w   ScrMarkByte
        addq.w  #1,d7
        cmp.w   #2,d7
        bls.b   .buf
        addq.w  #2,d5
        dbra    d2,.word
        move.w  (a7)+,d5
        addq.w  #1,d4
        dbra    d6,.line
        movem.l (a7)+,d0-d7/a0-a2
        rts
