;==============================================================================
; menu.s - the title menu and the joystick's second button (included by enhanced.s)
;
; The title screen keeps its text, the kiwi, the memory lines and the credits; above the kiwi
; (where the original has nothing) a menu of two pages, three lines:
;
;   title     START GAME / OPTIONS
;   options   INPUT: JUMP ON UP / JUMP ON BUTTON 2 / JUMP 1 FIRE 2,  CHEAT: OFF / ON,  EXIT
;
; Up and down move (round), fire (button 1) chooses; on INPUT and CHEAT left, right and fire
; change the setting. The item chosen shows as > ... < in white. EnhTitleWait takes the place of
; the title's wait (sub_0B9F0, from $406C): it keeps the original's time-out to the attract
; sequence ((a6), not on the options page) and its typed cheat code; START GAME starts the game
; as the original's fire did.
;
; The input setting (JoyMode) changes what ReadJoystick gives the game ($63DB0, read by the
; vertical blank): the second button is POTINP's bit 14 (DATRY: port 2's pin 9, low when
; pressed; POTGO $FF00, as the game sets it, drives it high).
;   0  JUMP ON UP       the original: up jumps, button 1 fires
;   1  JUMP ON BUTTON 2 button 2 is up (jumps, and swims up); the stick's up does nothing
;   2  JUMP 1 FIRE 2    button 1 is up, button 2 fires
; The cheat is the original's: the game's starting lives (l_04F46+2) 1,000 (on) or 3.
; The settings last until the machine is reset.
;==============================================================================

MENU_X          equ     5                       ; the lines: 30 characters from column 5
MENU_W          equ     30
MENU_Y          equ     $44                     ; the first line (12 lines apart)
MENU_COL        equ     $07                     ; an item
MENU_COL_SEL    equ     $0f                     ; the chosen item
LIVES           equ     l_04F46+2               ; the game's starting lives (an immediate)

JoyMode:        dc.w    0
MenuPage:       dc.w    0                       ; 0 title, 1 options
MenuSel:        dc.w    0
MenuPrev:       dc.w    0                       ; the last input (MenuInput's bits)
MenuText:       dcb.b   3*(4+MENU_W+1)+1,$ff    ; the printer's form of the 3 lines
	even

;------------------------------------------------------------------------------
; EnhJoy - ReadJoystick's result d0 (bits 0 down, 1 right, 2 up, 3 left, 7 fire) for the input
; setting. Keeps the other registers.
EnhJoy:         move.w  #$ff00,(CUSTOM+POTGO).l
        tst.w   JoyMode
        beq.b   .out
        move.w  d1,-(a7)
        moveq   #0,d1                           ; d1 = button 2
        btst    #6,(CUSTOM+POTGOR).l            ; (POTINP bit 14: its high byte's bit 6)
        seq.b   d1
        cmp.w   #1,JoyMode
        bne.b   .m2
        bclr    #2,d0                           ; 1: button 2 is up
        tst.b   d1
        beq.b   .done
        bset    #2,d0
        bra.b   .done
.m2:            bclr    #2,d0                   ; 2: button 1 is up, button 2 fires
        bclr    #7,d0
        beq.b   .f
        bset    #2,d0
.f:             tst.b   d1
        beq.b   .done
        bset    #7,d0
.done:          move.w  (a7)+,d1
.out:           rts

; MenuInput - d0 = the joystick as the menu reads it, from the hardware: bit 0 up, 1 down, 2 left,
; 3 right, 4 button 1, 5 button 2. Uses d1-d2.
MenuInput:      moveq   #0,d0
        move.w  (CUSTOM+JOY1DAT).l,d1
        btst    #1,d1                           ; right
        beq.b   .nr
        bset    #3,d0
.nr:            btst    #9,d1                   ; left
        beq.b   .nl
        bset    #2,d0
.nl:            move.w  d1,d2
        lsr.w   #1,d2
        eor.w   d1,d2                           ; bit 0: down, bit 8: up
        btst    #0,d2
        beq.b   .nd
        bset    #1,d0
.nd:            btst    #8,d2
        beq.b   .nu
        bset    #0,d0
.nu:            btst    #7,(CIAA_PRA).l
        bne.b   .n1
        bset    #4,d0
.n1:            btst    #6,(CUSTOM+POTGOR).l
        bne.b   .n2
        bset    #5,d0
.n2:            rts

;------------------------------------------------------------------------------
; MenuDraw - the menu's 3 lines for MenuPage, MenuSel, printed (over the last ones: the
; printer's characters are opaque, and each line is the same width). Keeps the registers.
MenuDraw:       movem.l d0-d7/a0-a3,-(a7)
        lea     MenuText(pc),a2
        moveq   #MENU_Y,d2
        moveq   #0,d4                           ; the line
.line:          bsr.w   MenuItem                ; a1 = its text (0: none)
        bsr.w   MenuLine
        add.w   #12,d2
        addq.w  #1,d4
        cmp.w   #3,d4
        blo.b   .line
        st.b    (a2)
        lea     MenuText(pc),a0
        jsr     sub_0C6A8
        movem.l (a7)+,d0-d7/a0-a3
        rts

; MenuItem - d4 = the line -> a1 = its text in LineBuf (0 terminated), or 0 for none. Uses
; d0-d1, a0, a3.
MenuItem:       lea     LineBuf(pc),a0
        tst.w   MenuPage
        bne.b   .opt
        cmp.w   #2,d4
        beq.b   .none
        lea     .start(pc),a3
        tst.w   d4
        beq.b   .put
        lea     .options(pc),a3
        bra.b   .put
.opt:           lea     .exit(pc),a3
        cmp.w   #2,d4
        beq.b   .put
        tst.w   d4
        bne.b   .cheat
        lea     .input(pc),a1                   ; INPUT: the setting
        bsr.w   PutStrA
        move.w  JoyMode(pc),d0
        add.w   d0,d0
        move.w  .modes(pc,d0.w),d0
        lea     .modes(pc,d0.w),a3
        bra.b   .put
.cheat:         lea     .cheatt(pc),a1
        bsr.w   PutStrA
        lea     .off(pc),a3
        cmpi.w  #1000,LIVES
        bne.b   .put
        lea     .on(pc),a3
.put:           movea.l a3,a1
        bsr.w   PutStrA
        clr.b   (a0)
        lea     LineBuf(pc),a1
        rts
.none:          suba.l  a1,a1
        rts
.modes:         dc.w    .m0-.modes,.m1-.modes,.m2-.modes
.m0:            dc.b    'JUMP ON UP',0
.m1:            dc.b    'JUMP ON BUTTON 2',0
.m2:            dc.b    'JUMP 1 FIRE 2',0
.start:         dc.b    'START GAME',0
.options:       dc.b    'OPTIONS',0
.input:         dc.b    'INPUT: ',0
.cheatt:        dc.b    'CHEAT: ',0
.off:           dc.b    'OFF',0
.on:            dc.b    'ON',0
.exit:          dc.b    'EXIT',0
	even

; PutStrA - the string at a1 to a0 (a0 left after it)
PutStrA:        move.b  (a1)+,(a0)+
        bne.b   PutStrA
        subq.l  #1,a0
        rts

; MenuLine - line d4 at y d2 to a2 in the printer's form: MENU_W characters from MENU_X, the
; text a1 (0: blank) centred, as > text < in MENU_COL_SEL if it is MenuSel's. Uses d0-d1, d3,
; a1, a3.
MenuLine:       move.b  #MENU_X,(a2)+
        move.b  d2,(a2)+
        move.b  #2,(a2)+
        moveq   #MENU_COL,d3
        cmp.w   MenuSel(pc),d4
        bne.b   .c
        moveq   #MENU_COL_SEL,d3
.c:             move.b  d3,(a2)+
        lea     MenuTmp(pc),a3                  ; the line's text: [> ]text[ <]
        move.l  a1,d0
        beq.b   .end
        cmp.w   MenuSel(pc),d4
        bne.b   .t
        move.b  #'>',(a3)+
        move.b  #' ',(a3)+
.t:             move.b  (a1)+,(a3)+
        bne.b   .t
        subq.l  #1,a3
        cmp.w   MenuSel(pc),d4
        bne.b   .end
        move.b  #' ',(a3)+
        move.b  #'<',(a3)+
.end:           move.l  a3,d0
        lea     MenuTmp(pc),a3
        sub.l   a3,d0                           ; its length
        moveq   #MENU_W,d1
        sub.w   d0,d1
        move.w  d1,d3
        lsr.w   #1,d1                           ; spaces before
        sub.w   d1,d3                           ; spaces after
        bra.b   .s1
.sp1:           move.b  #' ',(a2)+
.s1:            dbra    d1,.sp1
        bra.b   .c1
.cp:            move.b  (a3)+,(a2)+
.c1:            dbra    d0,.cp
        bra.b   .s2
.sp2:           move.b  #' ',(a2)+
.s2:            dbra    d3,.sp2
        clr.b   (a2)+
        rts

MenuTmp:        dcb.b   MENU_W+2,0
	even

;------------------------------------------------------------------------------
; EnhTitleText's part: the menu at its first page, drawn
MenuStart:      clr.w   MenuPage
        clr.w   MenuSel
        bra.w   MenuDraw

;------------------------------------------------------------------------------
; EnhTitleWait - the title's wait (sub_0B9F0, from $406C), with the menu: returns with (a6)
; (the time-out) 0 for the attract sequence, or not 0 to start a game (START GAME), as the
; original's. The typed cheat code works as in the original.
EnhTitleWait:   movem.l d0-d7/a0-a5,-(a7)
        lea     dat_045B4(pc),a5                ; the cheat code's next key
        bsr.w   MenuInput
        move.w  d0,MenuPrev                     ; (what is held already does not count)
.loop:          move.w  ScrFrames(pc),d1        ; once a frame
.vb:            cmp.w   ScrFrames(pc),d1
        beq.b   .vb
        tst.w   MenuPage                        ; the options page: no time-out
        beq.b   .time
        move.w  #$1e,(a6)
.time:          tst.w   (a6)
        beq.w   .out
        jsr     (JT_GetKey).w                   ; the cheat code, as sub_0B9F0
        beq.b   .joy
        eori.b  #$41,d0
        cmp.b   (a5),d0
        bne.b   .wrong
        lea     (dat_1E94C).l,a0
        jsr     PlaySample
        move.w  #$1e,(a6)
.held:          moveq   #0,d0
        move.b  (a5),d0
        eori.b  #$41,d0
        jsr     (JT_KeyTest).w
        bne.b   .held
        addq.l  #1,a5
        move.b  (a5),d0
        eori.b  #$41,d0
        addq.b  #1,d0
        bne.b   .joy
        bsr.w   CheatOn
        bsr.w   MenuDraw
.wrong:         lea     dat_045B4(pc),a5
.joy:           bsr.w   MenuInput
        move.w  MenuPrev(pc),d1
        move.w  d0,MenuPrev
        not.w   d1
        and.w   d0,d1                           ; d1 = newly pressed
        beq.b   .loop
        move.w  #$1e,(a6)                       ; (a move: the time-out again)
        moveq   #2,d2                           ; d2 = the items on the page
        tst.w   MenuPage
        beq.b   .n
        moveq   #3,d2
.n:             btst    #0,d1                   ; up
        beq.b   .down
        subq.w  #1,MenuSel
        bpl.w   .draw
        subq.w  #1,d2
        move.w  d2,MenuSel
        bra.w   .draw
.down:          btst    #1,d1
        beq.b   .choose
        addq.w  #1,MenuSel
        cmp.w   MenuSel(pc),d2
        bhi.w   .draw
        clr.w   MenuSel
        bra.w   .draw
.choose:        move.w  MenuSel(pc),d0
        tst.w   MenuPage
        bne.b   .options
        btst    #4,d1                           ; the title: fire
        beq.w   .loop
        tst.w   d0
        bne.b   .toopt
        st.b    (mem_63DB2).l                   ; START GAME: (its fire is not a shot)
        bra.w   .out
.toopt:         move.w  #1,MenuPage
        clr.w   MenuSel
        bra.w   .draw
.options:       cmp.w   #2,d0
        bne.b   .set
        btst    #4,d1                           ; EXIT
        beq.w   .loop
        clr.w   MenuPage
        move.w  #1,MenuSel
        bra.w   .draw
.set:           move.w  d1,d3
        and.w   #%11100,d3                      ; left, right, fire
        beq.w   .loop
        tst.w   d0
        bne.b   .cheat
        move.w  JoyMode(pc),d0                  ; INPUT: on, or back with left
        addq.w  #1,d0
        btst    #2,d1
        beq.b   .m
        subq.w  #2,d0
        bpl.b   .m
        moveq   #2,d0
.m:             cmp.w   #3,d0
        blo.b   .ms
        moveq   #0,d0
.ms:            move.w  d0,JoyMode
        bra.w   .draw
.cheat:         cmpi.w  #1000,LIVES
        beq.b   .off
        bsr.b   CheatOn
        bra.w   .draw
.off:           move.w  #3,LIVES
.draw:          bsr.w   MenuDraw
        bra.w   .loop
.out:           movem.l (a7)+,d0-d7/a0-a5
        rts

; CheatOn - the cheat on, as the original's typed code: 1,000 lives, tune 10
CheatOn:        move.w  #1000,LIVES
        moveq   #$a,d0
        jmp     PlaySong
