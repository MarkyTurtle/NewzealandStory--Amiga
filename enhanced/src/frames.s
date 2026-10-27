;==============================================================================
; frames.s - the main bank's BOB frames in one blit (block 3 of nzs_game.s: runs at BLOCK3)
;
; The original draws a BOB with 4 cookie-cut blits, one a plane, from a frame stored as its mask
; and its 4 planes one after another (DeinterleaveBobs). The scroller's buffers are interleaved
; (a line holds the 4 planes' rows), so a BOB can be one blit if its frame is stored the same
; way, with the mask repeated for each plane's row (the A channel's modulo cannot read a row 4
; times). A frame in one-blit form (OneCopy):
;   the mask block:  for each line, the mask's row 4 times
;   the plane block: for each line, the rows of planes 0, 1, 2, 3
; (each row the frame's width in words, as stored), 8 rows a line against the original's 5: 1.6
; times the memory. Both blocks have the original's rows, so a clipped BOB reads them with the
; same modulo (BlitBob's) and offsets x 4 (ScrBob: a part of L lines is one blit of 4L rows).
;
; The mirrored frames (frame + MIR_FIRST, $88(a6): an object facing left) are made in the same
; form, mirrored as they are copied: the original's mirrored copies (sub_0C52C) are never built.
; Their directory entries are made as the original makes them but point at the unmirrored frame
; (the same size: BlitBob clips with it), as mirror.s did.
;
; Where they are, by the machine (OneInit):
;   * chip RAM above 512K, room for them all (ONE_ALL bytes, about 290 KB): all built once, at
;     the first new game (EnhMirrorInit), from ONE_HI ($80000) on; the track cache gets the
;     chip RAM after them (CacheInit) - OneMode 0;
;   * 512K: a cache from ONE_LO ($4A3A6, where the original built its mirrored copies) to block
;     3, OneMode 1. A ring: a frame goes at the next free place and the oldest frames in its way
;     are dropped - no search, nothing to fragment. As a level starts (EnhLevelStart) the cache
;     is filled with the frames that level is known to draw (OneWarm, build_disk.py: the most
;     drawn ones first, as many as fit); a frame drawn and not in the cache is built there and
;     then (OneMiss).
; BlitBob takes each frame's address from EnhBobFrame (at $B7CC), which leaves the frame's
; one-blit form in OneCur (0: the other banks - the boss's, the ending's, the story's - and the
; oxygen meter's frame, which the game redraws each pass: drawn as the original draws them).
;==============================================================================

ONE_LO          equ     dat_4A3A6               ; 512K: the cache, from where the original built
ONE_LO_END      equ     BLOCK3                  ;   its mirrored copies to block 3
ONE_HI          equ     CHIP_512K               ; more chip RAM: all of them, from here
ONE_FRAMES      equ     579                     ; frames 0-288 and their mirrored copies 290-578
MIR_FIRST       equ     $122                    ; the first mirrored frame ($88(a6))
MIR_FRAMES      equ     289                     ; the main bank's frames
MIR_TABLE       equ     dat_4A2A6               ; a byte's bits reversed (sub_0C048)
ONE_LIVE        equ     $24                     ; the oxygen meter: sub_052C4 writes its level into
                                                ;   this frame's mask each pass (never copied)
ONE_WARM_BYTES  equ     (ONE_FRAMES+7)/8        ; a level's frames to build at its start: a bit each
ONE_TEMP        equ     BLOCK3_LIMIT-ONE_TEMP_SIZE  ; a mirrored frame made here, then laid out
ONE_TEMP_SIZE   equ     2408                    ;   (the largest stored frame: 2,404 bytes)

	include	"frames.i"                      ; ONE_ALL, OneWarm: 20 levels x ONE_WARM_BYTES (build_disk.py)

OneCur:         dc.l    0                       ; the frame BlitBob is drawing, in one-blit form (0: none)
OneMode:        dc.w    1                       ; 0: all built once (chip RAM above 512K); 1: the cache
OneBuilt:       dc.w    0                       ; OneMode 0: built
OneLevel:       dc.w    -1                      ; the level the cache was filled for ($8(a6))
OneBase:        dc.l    ONE_LO                  ; the memory: from
OneEnd:         dc.l    ONE_LO_END              ;   to
OnePos:         dc.l    ONE_LO                  ; where the next frame goes
OneHead:        dc.w    0                       ; the queue of frames in the cache, oldest first:
OneCount:       dc.w    0                       ;   its head (an index) and how many
OneMisses:      dc.l    0                       ; frames built in play (tools/test_frames.py)
OneMissBytes:   dc.l    0
	even

;------------------------------------------------------------------------------
; OneInit - at start-up (EnhInit, before CacheInit): all built if the chip RAM above 512K holds
; them; the cache otherwise
OneInit:        move.l  EnhMachine+MI_CHIP+4,d1
        cmp.l   #ONE_HI+ONE_ALL,d1
        blo.b   .cache
        clr.w   OneMode
        move.l  #ONE_HI,OneBase
        move.l  #ONE_HI+ONE_ALL,OneEnd
        rts
.cache:         move.w  #1,OneMode
        move.l  #ONE_LO,OneBase
        move.l  #ONE_LO_END,OneEnd
        rts

;------------------------------------------------------------------------------
; EnhMirrorInit - sub_0C52C, at each new game: the mirrored frames' directory ($84(a6)) made as
; the original's, but each entry's offset its unmirrored frame's (no copies); then the one-blit
; frames: all built the first time (OneMode 0), or the cache emptied (1)
EnhMirrorInit:
        jsr     sub_0C048                       ; MIR_TABLE
        movea.l $84(a6),a3
        move.w  #MIR_FIRST-2,d7
        lea     BobDirectory,a4
.entry:         move.l  (a4),(a3)+
        move.l  $4(a4),(a3)+
        move.l  $4(a4),$c(a4)
        move.l  $8(a4),(a3)+
        move.l  $c(a4),(a3)+
        movea.l (a4),a0
        adda.l  #BobData,a0
        move.w  (a0),d0                         ; its width in words: the hot spot mirrored
        asl.w   #4,d0
        subq.w  #2,d0
        add.w   -$c(a3),d0
        neg.w   d0
        move.w  d0,-$c(a3)
        lea     $10(a4),a4
        dbra    d7,.entry
        tst.w   OneMode
        bne.w   OneEmpty
        tst.w   OneBuilt
        bne.b   .out
        movem.l d0-d7/a0-a6,-(a7)               ; all of them, once
        move.l  OneBase,OnePos
        moveq   #0,d0
.all:           move.w  d0,d1
        cmp.w   #MIR_FIRST,d1
        blo.b   .u
        sub.w   #MIR_FIRST,d1
.u:             cmp.w   #ONE_LIVE,d1            ; (289: none; the oxygen meter: never)
        beq.b   .skip
        cmp.w   #MIR_FRAMES,d1
        beq.b   .skip
        move.w  d0,-(a7)
        bsr.w   OneMake
        move.w  (a7)+,d0
.skip:
        addq.w  #1,d0
        cmp.w   #ONE_FRAMES,d0
        blo.b   .all
        move.w  #1,OneBuilt
        movem.l (a7)+,d0-d7/a0-a6
.out:           rts

;------------------------------------------------------------------------------
; EnhBobFrame - at $B7CC in BlitBob, once the BOB is clipped: d1.w = the frame, a0 = the bank's
; data, a1 = its directory -> a0 = a1 = the frame's address, d1 = the frame x 16 (as the
; original's lsl.w / adda.l / movea.l); OneCur = its one-blit form (built if not yet: OneMode 1)
; for a frame of the main bank, else 0. Keeps every other register.
EnhBobFrame:    clr.l   OneCur
        cmpa.l  #BobDirectory,a1
        bne.b   .plain
        cmp.w   #ONE_FRAMES,d1
        bhs.b   .plain
        cmp.w   #MIR_FRAMES,d1
        beq.b   .plain
        cmp.w   #ONE_LIVE,d1
        beq.b   .plain
        cmp.w   #ONE_LIVE+MIR_FIRST,d1
        beq.b   .plain
        movem.l d1/a2,-(a7)
        lea     OneTab,a2
        add.w   d1,d1
        add.w   d1,d1
        tst.l   (a2,d1.w)
        bne.b   .have
        tst.w   OneMode
        beq.b   .none                           ; (all built: not one of them)
        movem.l d0-d7/a0-a6,-(a7)
        move.w  15*4+2(a7),d0                   ; (the frame, pushed above)
        bsr.w   OneMiss
        movem.l (a7)+,d0-d7/a0-a6
.have:          move.l  (a2,d1.w),OneCur
.none:          movem.l (a7)+,d1/a2
.plain:         lsl.w   #4,d1
        adda.l  (a1,d1.w),a0
        movea.l a0,a1
        rts

; OneMiss - a frame built in play (where tools/test_frames.py counts them)
OneMiss:        addq.l  #1,OneMisses
        bsr.w   OneBuild
        add.l   d6,OneMissBytes
        rts

;------------------------------------------------------------------------------
; EnhLevelStart - $41FE, as a level starts (its tracks loaded, or the same level again):
; sub_0C5C0 as the original, then (OneMode 1) for a level the cache was not filled for, the
; cache emptied and the frames the level is known to draw built (OneWarm: a bit a frame, the
; most drawn of them as many as fit). Keeps every register.
EnhLevelStart:  jsr     sub_0C5C0
        tst.w   OneMode
        beq.b   .out
        movem.l d0-d7/a0-a6,-(a7)
        move.w  $8(a6),d0
        cmp.w   OneLevel,d0
        beq.b   .done
        move.w  d0,OneLevel
        bsr.w   OneEmpty
        lsr.w   #4,d0                           ; the level
        cmp.w   #20,d0
        bhs.b   .done
        mulu    #ONE_WARM_BYTES,d0
        lea     OneWarm,a2
        adda.w  d0,a2
        moveq   #0,d6                           ; the frame
.byte:          move.b  (a2)+,d5
        moveq   #7,d4
.bit:           add.b   d5,d5
        bcc.b   .next
        move.w  d6,d0
        add.w   d0,d0
        add.w   d0,d0
        lea     OneTab,a1
        tst.l   (a1,d0.w)
        bne.b   .next
        move.w  d6,d0
        movem.l d4-d6/a2,-(a7)
        bsr.w   OneBuild
        movem.l (a7)+,d4-d6/a2
.next:          addq.w  #1,d6
        cmp.w   #ONE_FRAMES,d6
        bhs.b   .done
        dbra    d4,.bit
        bra.b   .byte
.done:          movem.l (a7)+,d0-d7/a0-a6
.out:           rts

;------------------------------------------------------------------------------
; OneEmpty - every frame dropped from the cache (OneMode 1). Keeps d0.
OneEmpty:       move.l  a0,-(a7)
        lea     OneTab,a0
        move.w  #ONE_FRAMES-1,d1
.clr:           clr.l   (a0)+
        dbra    d1,.clr
        move.l  OneBase,OnePos
        clr.w   OneHead
        clr.w   OneCount
        movea.l (a7)+,a0
        rts

; OneDrop - the oldest frame in the cache dropped. Uses d1-d2, a1.
OneDrop:        lea     OneQueue,a1
        move.w  OneHead,d1
        add.w   d1,d1
        move.w  (a1,d1.w),d2                    ; the frame
        lsr.w   #1,d1
        addq.w  #1,d1
        cmp.w   #ONE_FRAMES+1,d1
        blo.b   .h
        moveq   #0,d1
.h:             move.w  d1,OneHead
        subq.w  #1,OneCount
        lea     OneTab,a1
        add.w   d2,d2
        add.w   d2,d2
        clr.l   (a1,d2.w)
        rts

; OneOldest - -> a0 = where the oldest frame in the cache is (Z set: the cache is empty).
; Uses d1-d2, a1.
OneOldest:      move.w  OneCount,d1
        beq.b   .no
        lea     OneQueue,a1
        move.w  OneHead,d1
        add.w   d1,d1
        move.w  (a1,d1.w),d2
        add.w   d2,d2
        add.w   d2,d2
        lea     OneTab,a1
        movea.l (a1,d2.w),a0
        moveq   #1,d1                           ; (Z clear)
.no:            rts

;------------------------------------------------------------------------------
; OneBuild - d0.w = a frame (0-578, not 289), not in the cache: built at the next free place,
; the oldest frames in its way dropped. -> d6 = its size. Uses every register.
OneBuild:       lea     CUSTOM,a6
.blit:          btst    #6,DMACONR(a6)          ; (the last BOB's blit may still read the cache)
        bne.b   .blit
        bsr.w   OneSource                       ; a5 = the stored frame, d6 = the size
        movea.l OnePos,a4                       ; a4 = where it goes
        move.l  a4,d5
        add.l   d6,d5
        cmp.l   OneEnd,d5
        bls.b   .fits
.tail:          bsr.w   OneOldest               ; at the end: the frames after a4 dropped,
        beq.b   .wrap                           ;   from the start again
        cmpa.l  a4,a0
        blo.b   .wrap
        bsr.w   OneDrop
        bra.b   .tail
.wrap:          movea.l OneBase,a4
        move.l  a4,d5
        add.l   d6,d5
.fits:          bsr.w   OneOldest               ; the frames in its way dropped (the oldest
        beq.b   .free                           ;   are those after a4, if any)
        cmpa.l  a4,a0
        blo.b   .free
        cmpa.l  d5,a0
        bhs.b   .free
        bsr.w   OneDrop
        bra.b   .fits
.free:          move.l  d5,OnePos
        lea     OneQueue,a1                     ; the newest in the queue
        move.w  OneHead,d1
        add.w   OneCount,d1
        cmp.w   #ONE_FRAMES+1,d1
        blo.b   .q
        sub.w   #ONE_FRAMES+1,d1
.q:             add.w   d1,d1
        move.w  d0,(a1,d1.w)
        addq.w  #1,OneCount
        bra.b   OnePut

; OneMake - d0.w = a frame: built at OnePos (OneMode 0, all of them in turn). Uses every register.
OneMake:        bsr.b   OneSource
        movea.l OnePos,a4
        add.l   d6,OnePos
;       (falls into OnePut)

; OnePut - frame d0 built at a4 from a5 (OneSource) and entered in OneTab. Keeps d6.
OnePut:         lea     OneTab,a1
        move.w  d0,d1
        add.w   d1,d1
        add.w   d1,d1
        move.l  a4,(a1,d1.w)
        moveq   #0,d2
        cmp.w   #MIR_FIRST,d0
        blo.b   .copy
        moveq   #1,d2                           ; mirrored
.copy:          move.l  d6,-(a7)
        movea.l a5,a0
        movea.l a4,a1
        bsr.w   OneCopy
        move.l  (a7)+,d6
        rts

; OneSource - d0.w = a frame -> a5 = its stored (unmirrored) frame, d6.l = its one-blit size.
; Uses d1.
OneSource:      move.w  d0,d1
        cmp.w   #MIR_FIRST,d1
        blo.b   .u
        sub.w   #MIR_FIRST,d1
.u:             lsl.w   #4,d1
        lea     BobDirectory,a5
        movea.l (a5,d1.w),a5
        adda.l  #BobData,a5
        move.w  (a5),d6                         ; width in words x height x 16
        mulu    2(a5),d6
        lsl.l   #4,d6
        rts

;------------------------------------------------------------------------------
; OneCopy - the stored frame at a0 (width in words.w, height.w, then the mask and planes 0-3,
; each a block of rows) to a1 in one-blit form; d2 = 0 as it is, else mirrored: first mirrored
; into ONE_TEMP by the CPU (MirCopy, as the original's sub_0C52C), then laid out from there.
; The layout is the blitter's (OneLayout). Uses d0-d7, a0-a6.
OneCopy:        tst.w   d2
        beq.b   OneLayout
        move.l  a1,-(a7)
        lea     ONE_TEMP,a1
        bsr.w   MirCopy
        movea.l (a7)+,a1
        lea     ONE_TEMP,a0
;       (falls into OneLayout)

; OneLayout - the stored frame at a0 to a1 in one-blit form, by 8 blits (A to D): the mask 4
; times, each to every 4th row from the k-th (the mask block), then plane p to every 4th row
; from the p-th of the plane block; done when it returns. Uses d0-d6, a0-a2, a6.
OneLayout:      lea     CUSTOM,a6
        move.w  (a0)+,d0                        ; the width in words
        move.w  (a0)+,d6                        ; the height
        move.w  d0,d5
        add.w   d5,d5                           ; d5 = a row
        moveq   #0,d4
        move.w  d5,d4
        mulu    d6,d4                           ; d4 = a plane
        move.w  d5,d3
        add.w   d3,d3
        add.w   d5,d3                           ; d3 = 3 rows: D's modulo
        lsl.w   #6,d6
        or.w    d0,d6                           ; d6 = BLTSIZE: h lines of w words
        bsr.b   .wait
        move.l  #$09f00000,BLTCON0(a6)          ; A to D (BLTCON0, BLTCON1)
        move.l  #-1,BLTAFWM(a6)
        clr.w   BLTAMOD(a6)
        move.w  d3,BLTDMOD(a6)
        movea.l a1,a2                           ; the mask block
        moveq   #3,d1
.mask:          bsr.b   .wait
        move.l  a0,BLTAPTH(a6)
        move.l  a2,BLTDPTH(a6)
        move.w  d6,BLTSIZE(a6)
        adda.w  d5,a2
        dbra    d1,.mask
        movea.l a1,a2                           ; the plane block: 4 planes after the mask
        adda.l  d4,a2
        adda.l  d4,a2
        adda.l  d4,a2
        adda.l  d4,a2
        moveq   #3,d1
.plane:         adda.l  d4,a0
        bsr.b   .wait
        move.l  a0,BLTAPTH(a6)
        move.l  a2,BLTDPTH(a6)
        move.w  d6,BLTSIZE(a6)
        adda.w  d5,a2
        dbra    d1,.plane
.wait:          btst    #6,DMACONR(a6)
        bne.b   .wait
        rts

; MirCopy - the frame at a0 mirrored to a1: its header, then each line of the mask and the 4
; planes with its bytes in the reverse order and each byte's bits reversed (MIR_TABLE), as the
; original's sub_0C52C. Unrolled for the frame's width (at most 4 words). Uses d0-d7, a0-a5.
MirCopy:        lea     MIR_TABLE,a5
        move.l  (a0)+,d7
        move.l  d7,(a1)+
        move.w  d7,d6                           ; lines: 5 x the height
        mulu    #5,d6
        subq.w  #1,d6
        swap    d7                              ; the width in words
        move.w  d7,d5
        add.w   d5,d5                           ; a line's bytes
        lea     .end(pc),a4
        move.w  d7,d4
        mulu    #12,d4                          ; (12 bytes of code a word)
        suba.w  d4,a4
        moveq   #0,d0
.line:          adda.w  d5,a1
        jmp     (a4)
        rept    4
        move.b  (a0)+,d0
        move.b  (a5,d0.w),-(a1)
        move.b  (a0)+,d0
        move.b  (a5,d0.w),-(a1)
        endr
.end:           adda.w  d5,a1
        dbra    d6,.line
        rts

;------------------------------------------------------------------------------
; OneBob4 - sub_0B8B4 in the game's own display (planes $2000 apart) for a frame in one-blit
; form (OneCur): the original's 4 cookie-cut blits, reading each plane's rows and the mask's
; first copy of each line from it (modulo: 3 rows more). In as sub_0B8B4: a0 = the screen, a1 =
; the frame, d5 / d4 = the x / y offsets into it, d2 = its plane size, d6 = its modulo, d3 = the
; screen's, d7 = the shift (bits 12-15), d0 = BLTSIZE, a2 = CUSTOM; the first / last word masks
; set. -> d7 = BLTCON0, a0 past the 4 planes, as the original; keeps the other registers but d1.
OneBob4:        movem.l d0/d2-d6/a1/a3-a4,-(a7)
        andi.w  #$f000,d7
        movea.l OneCur,a3
        adda.w  d5,a3
        move.l  d4,d1
        add.l   d1,d1
        add.l   d1,d1
        adda.l  d1,a3                           ; a3 = the mask's first line (4 rows a line)
        move.l  d2,d1
        add.l   d1,d1
        add.l   d1,d1
        lea     (a3,d1.l),a4                    ; a4 = plane 0's
        move.w  d0,d1
        and.w   #63,d1
        add.w   d1,d1
        add.w   d6,d1
        move.w  d1,d4                           ; d4 = a row
        add.w   d1,d1
        add.w   d4,d1
        add.w   d6,d1                           ; d1 = the modulo: 3 rows more
        move.w  BobMinterm,d2
        or.w    d7,d2
        moveq   #3,d5
.plane:         btst    #6,DMACONR(a2)
        bne.b   .plane
        move.w  d2,BLTCON0(a2)
        move.w  d7,BLTCON1(a2)
        move.w  d1,BLTAMOD(a2)
        move.w  d1,BLTBMOD(a2)
        move.w  d3,BLTCMOD(a2)
        move.w  d3,BLTDMOD(a2)
        move.l  a3,BLTAPTH(a2)
        move.l  a4,BLTBPTH(a2)
        move.l  a0,BLTCPTH(a2)
        move.l  a0,BLTDPTH(a2)
        move.w  d0,BLTSIZE(a2)
        adda.w  d4,a4
        lea     $2000(a0),a0
        dbra    d5,.plane
        move.w  d2,d7
        movem.l (a7)+,d0/d2-d6/a1/a3-a4
        rts

; (last in block 3, so the program ends with them: zeros, which the in-place unpacking of the
; program (ext.s: Unpack) needs at its end - build_disk.py checks)
	cnop	0,4
OneTab:         dcb.l   ONE_FRAMES,0            ; each frame's one-blit form (0: not built)
OneQueue:       dcb.w   ONE_FRAMES+1,0          ; the frames in the cache, a ring
