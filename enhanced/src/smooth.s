;==============================================================================
; smooth.s - 50 frames a second in play (included by enhanced.s, after scroller.s)
;
; The game's logic runs once a pass of its loop and a pass takes 2 frames: the original shows 25
; frames a second, each twice. The logic stays as it is (every speed and timer in the game is per
; pass); what changes is the drawing. Each pass now draws two frames:
;
;   M  the in-between frame: the camera and every object half-way between where they were in
;      the last pass's frame and where they are in this one (interpolated: the screen shows each
;      pass one frame later than before, 20 ms);
;   S  this pass's frame, as before.
;
; The loop (l_04298): the logic (sub_04A22, sub_0B0E6, the camera sub_0AEEC), then sub_0BCD0 -
; EnhWaitFlip, which waits until the last frame has been taken and the pass's 2 frames are up,
; and then here (SmoothMid, in the main loop only):
;   * the objects' animation run now (sub_0B1C2 without its drawing): the pass's positions;
;   * if there is time and the last pass's positions are known: M drawn - the camera and
;     every object moved half-way, the background (sub_0B55C), the BOBs (l_0B14E), the flip
;     (sub_0BC8C); everything moved back; then wait until it has been taken;
;   * the positions kept for the next pass.
; The loop goes on: S drawn as before (sub_0B1C2 skips the animation it has had: EnhAnim).
;
; Time: each frame is taken at the split (the level 6 interrupt, line $14(a6)) and shown from the
; next frame. The pass goes on (EnhWaitFlip) as soon as the last S has been taken, at split t;
; M must be taken at the next split, t+1, and S at the one after, t+2: S is not flipped before
; frame t+2 begins (SmoothPace, in EnhFlip), which paces the game at 2 frames a pass whether M
; is drawn or not. So M has from the end of the logic to split t+1 (312 lines less the logic):
; if the animation and drawing would not fit (measured on the passes before, SmoothNeed), M is
; left out and the pass shows S twice as before - never slower. Not drawn either: the first pass in the scroller's display, or when
; the camera has jumped (more than SMOOTH_JUMP pixels); an object that has jumped, or is new, is
; drawn where it is.
;
; The panel (lines 176-199) is not redrawn each frame: BOBs drawn there (the oxygen gauge, the
; lives, the EXTEND letters) go into both display buffers' panels (ScrBob), so both show it
; whichever is drawn when.
;==============================================================================

SMOOTH_SLOTS    equ     71                      ; the objects: mem_64380, $3A bytes each
SMOOTH_SIZE     equ     $3a
SMOOTH_JUMP     equ     32                      ; a move larger than this: not interpolated
SMOOTH_MARGIN   equ     12                      ; lines
SMOOTH_LEAST    equ     64                      ; the least SmoothNeed eases off to

SmoothOn:       dc.b    1                       ; 0: as before (25 frames a second)
SmoothAnimOnly: dc.b    0                       ; sub_0B1C2: animate only, do not draw
SmoothAnimDone: dc.b    0                       ; the pass's animation is done: sub_0B1C2 only draws
SmoothValid:    dc.b    0                       ; SmoothCam / SmoothPos hold the last pass's frame
SmoothPendM:    dc.b    0                       ; the frame flipped is M (not S)
SmoothSValid:   dc.b    0                       ; SmoothSTake is known
	even
SmoothSTake:    dc.w    0                       ; the frame (ScrFrames) the last S was taken in
SmoothNeed:     dc.w    240                     ; lines M is expected to take (animation + drawing)
SmoothMids:     dc.l    0                       ; frames M drawn, passes left out (for the tests)
SmoothSkips:    dc.l    0
SmoothStart:    dc.w    0                       ; the frame SmoothMid began in, and its line
SmoothStartL:   dc.w    0
SmoothCam:      dc.l    0                       ; the camera ($2E(a6), $30(a6)) in the last pass's frame
SmoothPos:      dcb.l   SMOOTH_SLOTS,0          ; each object's position (x.w, y.w) then
SmoothAct:      dcb.b   SMOOTH_SLOTS+1,0        ; ... and whether it was there
SmoothSave:     dcb.b   SMOOTH_SLOTS*6,0        ; while M is drawn: each object's position, $2E
	even

;------------------------------------------------------------------------------
; SmoothSince - d1.w = a frame count (ScrFrames) -> d0.l = the lines from the start of that frame
; to now (signed: the frame counts wrap). Uses d1.
SmoothSince:    move.w  d2,-(a7)
.again:         move.w  ScrFrames(pc),d2
        move.l  (CUSTOM+VPOSR).l,d0             ; VPOSR, VHPOSR: the beam's line
        cmp.w   ScrFrames(pc),d2
        bne.b   .again                          ; (a vertical blank between)
        lsr.l   #8,d0
        and.l   #$1ff,d0
        sub.w   d1,d2                           ; the frames since
        muls    #312,d2
        add.l   d2,d0
        move.w  (a7)+,d2
        rts

;------------------------------------------------------------------------------
; SmoothRecord - every object's position and the camera kept: this pass's frame (S)
SmoothRecord:   movem.l d0/d7/a0-a2/a5,-(a7)
        lea     (mem_64380).l,a5
        lea     SmoothPos(pc),a0
        lea     SmoothAct(pc),a1
        moveq   #SMOOTH_SLOTS-1,d7
.o:             move.l  (a5),(a0)+
        tst.l   $18(a5)
        sne.b   (a1)+
        lea     SMOOTH_SIZE(a5),a5
        dbra    d7,.o
        move.l  $2e(a6),SmoothCam
        st.b    SmoothValid
        movem.l (a7)+,d0/d7/a0-a2/a5
        rts

;------------------------------------------------------------------------------
; SmoothMid - from EnhWaitFlip in the game loop: the pass's animation, and M if it fits. Keeps
; every register.
SmoothMid:      movem.l d0-d7/a0-a6,-(a7)
        move.w  ScrFrames(pc),d1                ; the start
        move.w  d1,SmoothStart
        bsr.w   SmoothSince
        move.w  d0,SmoothStartL
        st.b    SmoothAnimOnly                  ; the animation
        jsr     sub_0B1C2
        sf.b    SmoothAnimOnly
        st.b    SmoothAnimDone
        tst.b   SmoothValid                     ; M?
        beq.w   .skip
        move.w  $2e(a6),d0                      ; the camera: not if it has jumped
        sub.w   SmoothCam(pc),d0
        bpl.b   .cx
        neg.w   d0
.cx:            cmp.w   #SMOOTH_JUMP,d0
        bhi.w   .skip
        move.w  $30(a6),d0
        sub.w   SmoothCam+2(pc),d0
        bpl.b   .cy
        neg.w   d0
.cy:            cmp.w   #SMOOTH_JUMP,d0
        bhi.w   .skip
        tst.b   SmoothSValid
        beq.w   .skip
        move.w  SmoothSTake(pc),d1              ; the time left until M must be taken: the split
        addq.w  #1,d1                           ;   of the frame after the one the last S was
        bsr.w   SmoothSince                     ;   taken in
        moveq   #0,d1
        move.w  $14(a6),d1
        sub.l   d0,d1                           ; d1 = lines left
        moveq   #0,d2
        move.w  SmoothNeed(pc),d2
        add.l   #SMOOTH_MARGIN,d2
        cmp.l   d2,d1
        blt.w   .late
; M: the objects and the camera half-way
        lea     (mem_64380).l,a5
        lea     SmoothPos(pc),a0
        lea     SmoothAct(pc),a1
        lea     SmoothSave(pc),a2
        moveq   #SMOOTH_SLOTS-1,d7
.obj:           move.l  (a5),(a2)+              ; kept: the position, $2E (BlitBob sets it)
        move.w  $2e(a5),(a2)+
        move.l  (a0)+,d2                        ; the last frame's position
        tst.b   (a1)+
        beq.b   .next                           ; (not there then)
        tst.l   $18(a5)
        beq.b   .next
        move.w  (a5),d0
        move.w  d2,d1                           ; y
        swap    d2                              ; x
        move.w  d0,d3
        sub.w   d2,d3
        bpl.b   .ox
        neg.w   d3
.ox:            cmp.w   #SMOOTH_JUMP,d3
        bhi.b   .next
        move.w  2(a5),d4
        move.w  d4,d3
        sub.w   d1,d3
        bpl.b   .oy
        neg.w   d3
.oy:            cmp.w   #SMOOTH_JUMP,d3
        bhi.b   .next
        add.w   d2,d0                           ; half-way
        asr.w   #1,d0
        add.w   d1,d4
        asr.w   #1,d4
        move.w  d0,(a5)
        move.w  d4,2(a5)
.next:          lea     SMOOTH_SIZE(a5),a5
        dbra    d7,.obj
        move.l  $2e(a6),-(a7)                   ; the camera
        move.w  $2e(a6),d0
        add.w   SmoothCam(pc),d0
        asr.w   #1,d0
        move.w  d0,$2e(a6)
        move.w  $30(a6),d0
        add.w   SmoothCam+2(pc),d0
        asr.w   #1,d0
        move.w  d0,$30(a6)
        jsr     sub_0B55C                       ; drawn: the background, the BOBs; the flip
        bsr.w   SmoothObjects
        st.b    SmoothPendM
        jsr     sub_0BC8C
        move.l  (a7)+,$2e(a6)                   ; everything back
        lea     (mem_64380).l,a5
        lea     SmoothSave(pc),a2
        moveq   #SMOOTH_SLOTS-1,d7
.back:          move.l  (a2)+,(a5)
        move.w  (a2)+,$2e(a5)
        lea     SMOOTH_SIZE(a5),a5
        dbra    d7,.back
        move.w  SmoothStart(pc),d1              ; what it took, for the next pass's estimate
        bsr.w   SmoothSince
        sub.w   SmoothStartL(pc),d0
        move.w  d0,SmoothNeed
        addq.l  #1,SmoothMids
        bsr.w   SmoothRecord
.taken:         tst.b   (mem_63DDA).l           ; until M has been taken
        bne.b   .taken
        movem.l (a7)+,d0-d7/a0-a6
        rts
.late:          cmpi.w  #SMOOTH_LEAST+8,SmoothNeed ; (the estimate eases off: M is tried again)
        blt.b   .skip
        subq.w  #8,SmoothNeed
.skip:          addq.l  #1,SmoothSkips
        bsr.w   SmoothRecord
        movem.l (a7)+,d0-d7/a0-a6
        rts

;------------------------------------------------------------------------------
; SmoothObjects - M's BOBs: the game's l_0B14E (every object, last slot first, through BlitBob),
; but an object far off the screen is not passed to BlitBob at all. BlitBob would only clip it
; away after setting its fields for the logic ($8-$E, $2C), and S, drawn next, sets them for the
; logic as the game does. (A frame reaches at most 186 pixels from its object: SMOOTH_FAR.)
SMOOTH_FAR      equ     256
SmoothObjects:  lea     (mem_6535C).l,a5
        moveq   #SMOOTH_SLOTS-1,d7
.o:             tst.l   $18(a5)
        beq.b   .next
        move.w  $12(a5),d1
        beq.b   .next
        move.l  (a5),d0
        sub.w   $30(a6),d0                      ; y on the screen
        cmp.w   #-SMOOTH_FAR,d0
        blt.b   .next
        cmp.w   #SCR_FIELD+SMOOTH_FAR,d0
        bgt.b   .next
        swap    d0
        sub.w   $2e(a6),d0                      ; x
        cmp.w   #-SMOOTH_FAR,d0
        blt.b   .next
        cmp.w   #320+SMOOTH_FAR,d0
        bgt.b   .next
        swap    d0
        subq.w  #1,d1                           ; as l_0B14E from here: the frame, mirrored
        tst.b   $10(a5)
        beq.b   .m
        add.w   $88(a6),d1
.m:             movem.l d7/a5,-(a7)
        tst.w   $54(a6)                         ; (the kiwi flashing after a life: l_0B198)
        beq.b   .draw
        tst.w   $56(a6)
        bne.b   .draw
        move.w  $1c(a5),d7
        beq.b   .skip                           ; the kiwi
        cmp.w   #$21,d7
        blt.b   .draw
        cmp.w   #$29,d7
        bgt.b   .draw
        lea     (mem_643BA).l,a4                ; what he rides
        cmpa.l  $26(a4),a5
        beq.b   .skip
.draw:          jsr     BlitBob
.skip:          movem.l (a7)+,d7/a5
.next:          lea     -SMOOTH_SIZE(a5),a5
        dbra    d7,.o
        rts

;------------------------------------------------------------------------------
; SmoothTaken - the level 6 interrupt (EnhL6) has taken a frame: if S, its frame noted
SmoothTaken:    tst.b   SmoothPendM
        beq.b   .s
        sf.b    SmoothPendM
        rts
.s:             move.w  ScrFrames(pc),SmoothSTake
        st.b    SmoothSValid
        rts

; SmoothPace - EnhFlip, as a frame is ready: S is not to be taken before the second frame after
; the last S was taken (so a pass is 2 frames: M then S, or S twice). Keeps the registers.
SmoothPace:     tst.b   SmoothOn
        beq.b   .out
        tst.b   SmoothPendM
        bne.b   .out
        tst.b   SmoothSValid
        beq.b   .out
        move.l  d0,-(a7)
.w:             move.w  ScrFrames(pc),d0
        sub.w   SmoothSTake(pc),d0
        cmp.w   #2,d0
        blt.b   .w
        move.l  (a7)+,d0
.out:           rts

;------------------------------------------------------------------------------
; EnhAnim - sub_0B1C2 (the objects' animation, then their drawing, l_0B14E): only the drawing
; when SmoothMid has done the animation this pass
EnhAnim:        tst.b   SmoothAnimDone
        beq.b   .anim
        sf.b    SmoothAnimDone
        jmp     l_0B14E
.anim:          lea     (mem_64380).l,a5
        jmp     sub_0B1C2+6

; EnhAnimEnd - the end of sub_0B1C2's animation ($B316): the list at $146(a6) ended, then the
; drawing - not for SmoothMid (it draws later); the positions kept when the pass has no M
EnhAnimEnd:     ext.l   d7
        move.l  d7,(a3)+
        tst.b   SmoothAnimOnly
        bne.b   .only
        tst.b   ScrActive
        beq.b   .draw
        bsr.w   SmoothRecord
.draw:          jmp     l_0B14E
.only:          rts
