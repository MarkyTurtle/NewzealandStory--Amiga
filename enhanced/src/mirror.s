;==============================================================================
; mirror.s - the mirrored BOB frames (included by enhanced.s)
;
; An object facing left is drawn from a mirrored copy of its frame: frame + $122 ($88(a6)). The
; original builds a mirrored copy of all 289 frames of the main bank at start-up (sub_0C52C, at
; each new game): 94 KB of chip RAM from $4A3A6, about 0.5 seconds of the CPU.
;
; With more than 512K of chip RAM the enhanced game does the same (MirMode 0). On a 512K
; machine it keeps a cache instead (MirMode 1), MIR_SIZE bytes from $4A3A6, and the memory
; from MIR_END to $613A6 (45 KB) is free:
;   * at start-up the mirrored frames' directory entries are made as the original makes them,
;     but each points at its unmirrored frame (the same size: BlitBob can clip with it) - not
;     built yet;
;   * BlitBob, once it has clipped a BOB and is about to draw it, takes the frame's address from
;     EnhBobFrame: a mirrored frame not built yet is built there and then into the cache, and its
;     directory entry pointed at it;
;   * the cache is a ring: a frame goes at the next free place; the frames there before it, the
;     oldest, are dropped (their entries pointed back at their unmirrored frames) - first out,
;     no search, nothing to fragment;
;   * as a level starts (EnhLevelStart, after its tracks are loaded) the cache is emptied and
;     the frames that level was seen to draw mirrored (MirWarm, made by build_disk.py from
;     ../original/assets/levels/observed.json) built at once, so building during play is rare:
;     in the emulator's plays, at most one new frame in a pass after the first (964 bytes, at
;     most 2,404), against 2-12 frames in the level's first pass.
; The frames are built by MirCopy, unrolled by the frame's width: about 26 cycles a byte against
; the original's 36 (on a 68000: 3.5 ms for a 964-byte frame, 9 ms for the largest).
;
; The ending's and the story's banks have directories of their own: EnhBobFrame only acts on
; the main bank's (BobDirectory).
;==============================================================================

MIR_BASE        equ     dat_4A3A6               ; where the original builds its copies
MIR_SIZE        equ     $c000                   ; the cache: 48K (a level draws at most ~40K)
MIR_END         equ     MIR_BASE+MIR_SIZE
MIR_FIRST       equ     $122                    ; the first mirrored frame ($88(a6))
MIR_FRAMES      equ     289                     ; the main bank's frames
MIR_BUILT       equ     MIR_BASE-BobData        ; a directory offset from here: built (in the cache)
MIR_TABLE       equ     dat_4A2A6               ; a byte's bits reversed (sub_0C048)
MIR_WARM_BYTES  equ     (MIR_FRAMES+7)/8        ; a level's frames to build at its start: a bit each
MirQueue        equ     MIR_END                 ; the queue of frames in the cache (MIR_FRAMES+1 words):
                                                ;   in the memory the cache frees (only used with it)

	include	"mirrors.i"                     ; MirWarm: 20 levels x MIR_WARM_BYTES (build_disk.py)

MirMode:        dc.w    0                       ; 0: all built at start-up (the original); 1: the cache
MirLevel:       dc.w    -1                      ; the level the cache was warmed for ($8(a6))
MirPos:         dc.l    0                       ; where the next frame goes
MirHead:        dc.w    0                       ; the queue of frames in the cache, oldest first:
MirCount:       dc.w    0                       ;   its head (an index) and how many
	even

;------------------------------------------------------------------------------
; MirInit - at start-up (EnhInit): the cache on a machine with no chip RAM above 512K
MirInit:        moveq   #1,d0
        move.l  EnhMachine+MI_CHIP+4(pc),d1
        cmp.l   #CHIP_512K,d1
        bls.b   .set
        moveq   #0,d0
.set:           move.w  d0,MirMode
        rts

;------------------------------------------------------------------------------
; EnhMirrorInit - sub_0C52C, at each new game: the mirrored frames' directory ($84(a6)), and
; all their copies (MirMode 0: the original's code goes on) or none yet (1)
EnhMirrorInit:
        jsr     sub_0C048                       ; MIR_TABLE
        tst.w   MirMode
        bne.b   .cache
        movea.l #MIR_BASE,a1
        jmp     sub_0C52C+10                    ; the original's loop
.cache:         movea.l $84(a6),a3              ; as the original's loop, but no copies made:
        move.w  #MIR_FIRST-2,d7                 ;   each entry's offset is its unmirrored frame's
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
        move.l  #MIR_BASE,MirPos
        clr.w   MirHead
        clr.w   MirCount
        move.w  #-1,MirLevel
        rts

;------------------------------------------------------------------------------
; EnhBobFrame - at $B7CC in BlitBob, once the BOB is clipped: d1.w = the frame, a0 = the bank's
; data, a1 = its directory -> a0 = a1 = the frame's address, d1 = the frame x 16 (as the
; original's lsl.w / adda.l / movea.l). A mirrored frame of the main bank not built yet is
; built. Keeps every other register.
EnhBobFrame:    tst.w   MirMode
        beq.b   .plain
        cmp.w   #MIR_FIRST,d1
        blo.b   .plain
        cmp.w   #MIR_FIRST+MIR_FRAMES,d1
        bhs.b   .plain
        cmpa.l  #BobDirectory,a1
        bne.b   .plain
        move.w  d1,-(a7)
        lsl.w   #4,d1
        cmpi.l  #MIR_BUILT,(a1,d1.w)
        bhs.b   .built
        movem.l d0-d7/a0-a6,-(a7)
        move.w  15*4(a7),d0                     ; (the frame, pushed above)
        bsr.w   MirMiss
        movem.l (a7)+,d0-d7/a0-a6
.built:         addq.l  #2,a7
.plain2:        adda.l  (a1,d1.w),a0
        movea.l a0,a1
        rts
.plain:         lsl.w   #4,d1
        bra.b   .plain2

; MirMiss - a frame built in play (where tools/test_mirror.py counts them)
MirMiss:        bra.w   MirBuild

;------------------------------------------------------------------------------
; EnhLevelStart - $41FE, as a level starts (its tracks loaded, or the same level again):
; sub_0C5C0 as the original, then (MirMode 1) for a level the cache was not warmed for, the
; cache emptied and the frames the level is known to draw mirrored built. Keeps every register.
EnhLevelStart:  jsr     sub_0C5C0
        tst.w   MirMode
        beq.b   .out
        movem.l d0-d7/a0-a6,-(a7)
        move.w  $8(a6),d0
        cmp.w   MirLevel(pc),d0
        beq.b   .done
        move.w  d0,MirLevel
        bsr.w   MirEmpty
        lsr.w   #4,d0                           ; the level
        cmp.w   #20,d0
        bhs.b   .done
        mulu    #MIR_WARM_BYTES,d0
        lea     MirWarm(pc),a2
        adda.w  d0,a2
        moveq   #0,d6                           ; the frame
.byte:          move.b  (a2)+,d5
        moveq   #7,d4
.bit:           add.b   d5,d5
        bcc.b   .next
        move.w  d6,d0
        add.w   #MIR_FIRST,d0
        move.w  d0,d1
        lsl.w   #4,d1
        lea     BobDirectory,a1
        cmpi.l  #MIR_BUILT,(a1,d1.w)
        bhs.b   .next
        movem.l d4-d6/a2,-(a7)
        bsr.w   MirBuild
        movem.l (a7)+,d4-d6/a2
.next:          addq.w  #1,d6
        cmp.w   #MIR_FRAMES,d6
        bhs.b   .done
        dbra    d4,.bit
        bra.b   .byte
.done:          movem.l (a7)+,d0-d7/a0-a6
.out:           rts

;------------------------------------------------------------------------------
; MirEmpty - every frame dropped from the cache. Keeps d0.
MirEmpty:       move.w  d0,-(a7)
.drop:          tst.w   MirCount
        beq.b   .empty
        bsr.w   MirDrop
        bra.b   .drop
.empty:         move.l  #MIR_BASE,MirPos
        clr.w   MirHead
        move.w  (a7)+,d0
        rts

; MirDrop - the oldest frame in the cache dropped: its entry pointed back at its unmirrored
; frame. -> a0 = where it was. Uses d1-d2, a0-a1.
MirDrop:        lea     MirQueue,a1
        move.w  MirHead(pc),d1
        add.w   d1,d1
        move.w  (a1,d1.w),d2                    ; the frame
        lsr.w   #1,d1
        addq.w  #1,d1
        cmp.w   #MIR_FRAMES+1,d1
        blo.b   .h
        moveq   #0,d1
.h:             move.w  d1,MirHead
        subq.w  #1,MirCount
        lea     BobDirectory,a1
        lsl.w   #4,d2
        adda.w  d2,a1
        movea.l (a1),a0
        adda.l  #BobData,a0
        move.l  -MIR_FIRST*16(a1),(a1)
        rts

; MirOldest - -> a0 = where the oldest frame in the cache is (Z set: the cache is empty).
; Uses d1-d2, a1.
MirOldest:      move.w  MirCount(pc),d1
        beq.b   .no
        lea     MirQueue,a1
        move.w  MirHead(pc),d1
        add.w   d1,d1
        move.w  (a1,d1.w),d2
        lsl.w   #4,d2
        lea     BobDirectory,a1
        movea.l (a1,d2.w),a0
        adda.l  #BobData,a0
        moveq   #1,d1                           ; (Z clear)
.no:            rts

;------------------------------------------------------------------------------
; MirBuild - d0.w = a mirrored frame of the main bank (MIR_FIRST on), not in the cache: built
; at the next free place, the oldest frames there dropped. Uses every register.
MirBuild:       lea     CUSTOM,a6
.blit:          btst    #6,2(a6)                ; (DMACONR: the last BOB's blits may still read the cache)
        bne.b   .blit
        lea     BobDirectory,a3
        move.w  d0,d7
        lsl.w   #4,d7
        adda.w  d7,a3                           ; a3 = its entry
        movea.l -MIR_FIRST*16(a3),a5
        adda.l  #BobData,a5                     ; a5 = the unmirrored frame
        move.w  (a5),d6
        mulu    2(a5),d6
        mulu    #10,d6
        addq.l  #4,d6                           ; d6 = its size
        movea.l MirPos(pc),a4                   ; a4 = where it goes
        move.l  a4,d5
        add.l   d6,d5
        cmp.l   #MIR_END,d5
        bls.b   .fits
.tail:          bsr.w   MirOldest               ; at the end: the frames after a4 dropped,
        beq.b   .wrap                           ;   from the start again
        cmpa.l  a4,a0
        blo.b   .wrap
        bsr.w   MirDrop
        bra.b   .tail
.wrap:          movea.l #MIR_BASE,a4
        move.l  a4,d5
        add.l   d6,d5
.fits:          bsr.w   MirOldest               ; the frames in its way dropped (the oldest
        beq.b   .free                           ;   are those after a4, if any)
        cmpa.l  a4,a0
        blo.b   .free
        cmpa.l  d5,a0
        bhs.b   .free
        bsr.w   MirDrop
        bra.b   .fits
.free:          move.l  d5,MirPos
        move.l  a4,d1
        sub.l   #BobData,d1
        move.l  d1,(a3)                         ; its entry: the copy
        lea     MirQueue,a1                 ; the newest in the queue
        move.w  MirHead(pc),d1
        add.w   MirCount(pc),d1
        cmp.w   #MIR_FRAMES+1,d1
        blo.b   .q
        sub.w   #MIR_FRAMES+1,d1
.q:             add.w   d1,d1
        move.w  d0,(a1,d1.w)
        addq.w  #1,MirCount
        movea.l a5,a0
        movea.l a4,a1
;       (falls into MirCopy)

;------------------------------------------------------------------------------
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
