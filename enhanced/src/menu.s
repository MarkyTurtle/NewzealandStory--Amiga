;==============================================================================
; menu.s - the title menu and the joystick's second button (included by enhanced.s)
;
; The title screen keeps its text, the kiwi, the memory lines and the credits; above the kiwi
; (where the original has nothing) a menu of two pages, three lines:
;
;   title     START GAME / OPTIONS
;   options   INPUT: JUMP ON UP / JUMP ON BUTTON 2 / JUMP 1 FIRE 2,  CHEAT: OFF / ON,
;             SOUND TEST, EXIT; and under the kiwi the machine's memory lines (MakeTitleText),
;             which the title no longer shows
;   sound     MUSIC: nn (1-12), EFFECT: nn NAME (the 12 effects), MUSIC OFF, EXIT: left and
;             right choose, fire plays (PlaySong, PlaySample) or stops (StopSong); EXIT (and
;             MUSIC OFF) stop the tune
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
MENU_Y          equ     $7a                     ; the first line (4 lines, 9 apart: between the
MENU_DY         equ     9                       ;   kiwi's feet and the credits, 'CONVERSION' at $A0)
MENU_LINES      equ     4
MENU_COL        equ     $07                     ; an item
MENU_COL_SEL    equ     $0f                     ; the chosen item
LIVES           equ     l_04F46+2               ; the game's starting lives (an immediate)

JoyMode:        dc.w    0
MenuPage:       dc.w    0                       ; 0 title, 1 options, 2 sound test
MenuSel:        dc.w    0
MenuPrev:       dc.w    0                       ; the last input (MenuInput's bits)
MenuSong:       dc.w    1                       ; the sound test's tune (1-12) and effect (0-11)
MenuSfx:        dc.w    0
MenuText:       dcb.b   MENU_LINES*(4+MENU_W+1)+1,$ff ; the printer's form of the lines
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
        add.w   #MENU_DY,d2
        addq.w  #1,d4
        cmp.w   #MENU_LINES,d4
        blo.b   .line
        st.b    -1(a2)                          ; the end: $FF in place of the last line's 0 (a 0
        lea     MenuText(pc),a0                 ;   then $FF would start one more line: its x $FF
                                                ;   and whatever came next printed at the left)
        jsr     sub_0C6A8
        lea     MemBlank(pc),a0                 ; under the kiwi: the machine's memory lines
        cmpi.w  #1,MenuPage                     ;   on the options page, nothing on the others
        bne.b   .mem
        lea     TitleText(pc),a0
.mem:           jsr     sub_0C6A8
        movem.l (a7)+,d0-d7/a0-a3
        rts

; MemBlank - the memory lines' place (MakeTitleText: TITLE_Y1, TITLE_Y2) cleared: 36 spaces each
MemBlank:       dc.b    2,TITLE_Y1,2,MENU_COL
        dcb.b   36,' '
        dc.b    0,2,TITLE_Y2,2,MENU_COL
        dcb.b   36,' '
        dc.b    $ff
	even

; MenuItem - d4 = the line -> a1 = its text in LineBuf (0 terminated), or 0 for none. Uses
; d0-d1, a0, a3.
MenuItem:       lea     LineBuf(pc),a0
        move.w  MenuPage(pc),d0
        add.w   d0,d0
        add.w   d0,d0
        add.w   d4,d0                           ; page x 4 + line
        add.w   d0,d0
        move.w  .items(pc,d0.w),d0
        beq.w   .none
        jmp     .items(pc,d0.w)
.none:          suba.l  a1,a1
        rts
.items:         dc.w    .start-.items,.options-.items,0,0
        dc.w    .input-.items,.cheat-.items,.sound-.items,.exit-.items
        dc.w    .music-.items,.sfx-.items,.off-.items,.exit-.items
.start:         lea     .tstart(pc),a3
        bra.w   .put
.options:       lea     .toptions(pc),a3
        bra.w   .put
.sound:         lea     .tsound(pc),a3
        bra.w   .put
.exit:          lea     .texit(pc),a3
        bra.w   .put
.off:           lea     .tmoff(pc),a3
        bra.w   .put
.input:         lea     .tinput(pc),a1                  ; INPUT: the setting
        bsr.w   PutStrA
        move.w  JoyMode(pc),d0
        add.w   d0,d0
        move.w  .modes(pc,d0.w),d0
        lea     .modes(pc,d0.w),a3
        bra.w   .put
.cheat:         lea     .tcheat(pc),a1
        bsr.w   PutStrA
        lea     .toff(pc),a3
        cmpi.w  #1000,LIVES
        bne.w   .put
        lea     .ton(pc),a3
        bra.w   .put
.music:         lea     .tmusic(pc),a1                  ; MUSIC: nn
        bsr.w   PutStrA
        move.w  MenuSong(pc),d0
        bsr.w   PutNum2
        bra.w   .end
.sfx:           lea     .tsfx(pc),a1                    ; EFFECT: nn NAME
        bsr.w   PutStrA
        move.w  MenuSfx(pc),d0
        addq.w  #1,d0
        bsr.w   PutNum2
        move.b  #' ',(a0)+
        move.w  MenuSfx(pc),d0
        lsl.w   #3,d0                           ; (8 bytes an entry: address, name offset)
        lea     MenuSfxTab(pc),a3
        move.w  6(a3,d0.w),d0
        adda.w  d0,a3
.put:           movea.l a3,a1
        bsr.w   PutStrA
.end:           clr.b   (a0)
        lea     LineBuf(pc),a1
        rts
.modes:         dc.w    .m0-.modes,.m1-.modes,.m2-.modes
.m0:            dc.b    'JUMP ON UP',0
.m1:            dc.b    'JUMP ON BUTTON 2',0
.m2:            dc.b    'JUMP 1 FIRE 2',0
.tstart:        dc.b    'START GAME',0
.toptions:      dc.b    'OPTIONS',0
.tinput:        dc.b    'INPUT: ',0
.tcheat:        dc.b    'CHEAT: ',0
.toff:          dc.b    'OFF',0
.ton:           dc.b    'ON',0
.tsound:        dc.b    'SOUND TEST',0
.texit:         dc.b    'EXIT',0
.tmusic:        dc.b    'MUSIC: ',0
.tsfx:          dc.b    'EFFECT: ',0
.tmoff:         dc.b    'MUSIC OFF',0
	even

; PutNum2 - d0.w (0-99) to a0 as 2 digits
PutNum2:        ext.l   d0
        divu    #10,d0
        add.b   #'0',d0
        move.b  d0,(a0)+
        swap    d0
        add.b   #'0',d0
        move.b  d0,(a0)+
        rts

; the sound test's effects (the IFF 8SVX files PlaySample takes, ../original/docs/SOUND.md):
; the address, then the offset of the name from MenuSfxTab
MENU_SFX        equ     12
MenuSfxTab:     dc.l    $16800
        dc.w    0,.n0-MenuSfxTab
        dc.l    $1731C
        dc.w    0,.n1-MenuSfxTab
        dc.l    $17F84
        dc.w    0,.n2-MenuSfxTab
        dc.l    $183A8
        dc.w    0,.n3-MenuSfxTab
        dc.l    $1A096
        dc.w    0,.n4-MenuSfxTab
        dc.l    $1BD06
        dc.w    0,.n5-MenuSfxTab
        dc.l    $1D398
        dc.w    0,.n6-MenuSfxTab
        dc.l    $1D5D0
        dc.w    0,.n7-MenuSfxTab
        dc.l    $1E1E6
        dc.w    0,.n8-MenuSfxTab
        dc.l    $1E94C
        dc.w    0,.n9-MenuSfxTab
        dc.l    $1EEB6
        dc.w    0,.n10-MenuSfxTab
        dc.l    $20676
        dc.w    0,.n11-MenuSfxTab
.n0:            dc.b    'KIWI JUMP',0
.n1:            dc.b    'BAD DEAD',0
.n2:            dc.b    'KIWI SHOT',0
.n3:            dc.b    'PICK UP',0
.n4:            dc.b    'SPLASH',0
.n5:            dc.b    'BOOM',0
.n6:            dc.b    'WHACK KIWI',0
.n7:            dc.b    'SPIT',0
.n8:            dc.b    'THROW BOMB',0
.n9:            dc.b    'LASER',0
.n10:           dc.b    'WAND',0
.n11:           dc.b    'EXPLOSION',0
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
        beq.w   .vb
        tst.w   MenuPage                        ; the options page: no time-out
        beq.w   .time
        move.w  #$1e,(a6)
.time:          tst.w   (a6)
        beq.w   .out
        jsr     (JT_GetKey).w                   ; the cheat code, as sub_0B9F0
        beq.w   .joy
        eori.b  #$41,d0
        cmp.b   (a5),d0
        bne.w   .wrong
        lea     (dat_1E94C).l,a0
        jsr     PlaySample
        move.w  #$1e,(a6)
.held:          moveq   #0,d0
        move.b  (a5),d0
        eori.b  #$41,d0
        jsr     (JT_KeyTest).w
        bne.w   .held
        addq.l  #1,a5
        move.b  (a5),d0
        eori.b  #$41,d0
        addq.b  #1,d0
        bne.w   .joy
        bsr.w   CheatOn
        bsr.w   MenuDraw
.wrong:         lea     dat_045B4(pc),a5
.joy:           bsr.w   MenuInput
        move.w  MenuPrev(pc),d1
        move.w  d0,MenuPrev
        not.w   d1
        and.w   d0,d1                           ; d1 = newly pressed
        beq.w   .loop
        move.w  #$1e,(a6)                       ; (a move: the time-out again)
        moveq   #2,d2                           ; d2 = the items on the page
        tst.w   MenuPage
        beq.w   .n
        moveq   #4,d2
.n:             btst    #0,d1                   ; up
        beq.w   .down
        subq.w  #1,MenuSel
        bpl.w   .draw
        subq.w  #1,d2
        move.w  d2,MenuSel
        bra.w   .draw
.down:          btst    #1,d1
        beq.w   .choose
        addq.w  #1,MenuSel
        cmp.w   MenuSel(pc),d2
        bhi.w   .draw
        clr.w   MenuSel
        bra.w   .draw
.choose:        move.w  MenuSel(pc),d0
        move.w  MenuPage(pc),d2
        beq.w   .title
        subq.w  #1,d2
        beq.w   .options
; the sound test: MUSIC (left / right the tune, fire plays it), EFFECT (the same), MUSIC OFF, EXIT
        cmp.w   #2,d0
        blo.w   .snd
        btst    #4,d1
        beq.w   .loop
        move.w  d0,-(a7)
        moveq   #0,d0                           ; (Music_Stop: d0 0 stops every voice)
        jsr     StopSong
        move.w  (a7)+,d0
        cmp.w   #3,d0
        bne.w   .loop
        move.w  #1,MenuPage                     ; EXIT: the options page, SOUND TEST chosen
        move.w  #2,MenuSel
        bra.w   .draw
.snd:           lea     MenuSong(pc),a0         ; d2 = the number's range
        moveq   #12,d2
        moveq   #1,d3                           ; d3 = its first
        tst.w   d0
        beq.w   .num
        lea     MenuSfx(pc),a0
        moveq   #MENU_SFX,d2
        moveq   #0,d3
.num:           btst    #4,d1
        bne.w   .play
        move.w  (a0),d4
        btst    #3,d1                           ; right: on
        beq.w   .lft
        addq.w  #1,d4
        move.w  d4,d5
        sub.w   d3,d5
        cmp.w   d2,d5
        blo.w   .nset
        move.w  d3,d4
        bra.w   .nset
.lft:           btst    #2,d1                   ; left: back
        beq.w   .loop
        subq.w  #1,d4
        cmp.w   d3,d4
        bge.w   .nset
        move.w  d3,d4
        add.w   d2,d4
        subq.w  #1,d4
.nset:          move.w  d4,(a0)
        bra.w   .draw
.play:          tst.w   d0
        bne.w   .sfx
        move.w  MenuSong(pc),d0
        jsr     PlaySong
        bra.w   .loop
.sfx:           move.w  MenuSfx(pc),d0
        lsl.w   #3,d0
        lea     MenuSfxTab(pc),a0
        movea.l (a0,d0.w),a0
        jsr     PlaySample
        bra.w   .loop
.title:         btst    #4,d1                   ; the title: fire
        beq.w   .loop
        tst.w   d0
        bne.w   .toopt
        st.b    (mem_63DB2).l                   ; START GAME: (its fire is not a shot)
        bra.w   .out
.toopt:         move.w  #1,MenuPage
        clr.w   MenuSel
        bra.w   .draw
.options:       cmp.w   #2,d0
        blo.w   .set
        btst    #4,d1
        beq.w   .loop
        cmp.w   #3,d0
        beq.w   .exit
        move.w  #2,MenuPage                     ; SOUND TEST
        clr.w   MenuSel
        bra.w   .draw
.exit:          clr.w   MenuPage                ; EXIT
        move.w  #1,MenuSel
        bra.w   .draw
.set:           move.w  d1,d3
        and.w   #%11100,d3                      ; left, right, fire
        beq.w   .loop
        tst.w   d0
        bne.w   .cheat
        move.w  JoyMode(pc),d0                  ; INPUT: on, or back with left
        addq.w  #1,d0
        btst    #2,d1
        beq.w   .m
        subq.w  #2,d0
        bpl.w   .m
        moveq   #2,d0
.m:             cmp.w   #3,d0
        blo.w   .ms
        moveq   #0,d0
.ms:            move.w  d0,JoyMode
        bra.w   .draw
.cheat:         cmpi.w  #1000,LIVES
        beq.w   .off
        bsr.w   CheatOn
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
