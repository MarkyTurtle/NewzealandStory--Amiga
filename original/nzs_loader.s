; The New Zealand Story (Ocean 1989, Amiga conversion by Choice Software)
; Game loader: track 90, loaded to $400 and entered there.
; Made by original/tools/disasm/make.py from its config; edited by hand since October 2026.
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o loader.bin nzs_loader.s
;
; The bytes are written contiguously (5632 bytes, one track), but the block from file offset 4
; runs at $76000: each part has its own org inside one section, so its labels carry the address
; it runs at while vasm writes the bytes with no gaps.

	include	"nzs_hw.i"

	section	loader,code

	org	$400				; file $0000: loaded here
LoaderEntry:
        bra.w   Start                           ; 00400

;===============================================================================
; Runs at $76000 (file offset $0004-$0B8F, copied by Start)
;===============================================================================
	org	$76000
LoaderCode:
LoaderMain:
        move.l  #Supervisor,(V_PrivilegeViol).w ; 76000  privilege violation -> Supervisor
        ori.w   #$700,sr                        ; 76008  (in user mode: privilege violation)
Supervisor:
        lea.l   $68000.l,a7                     ; 7600C  stack, then the variables (a6)
        lea.l   $76ce4(pc),a6                   ; 76012
        move    a7,usp                          ; 76016
        bsr.w   HardwareInit                    ; 76018  interrupts and DMA off, the display set up, black
        move.w  #$1,$2(a6)                      ; 7601C  motor off, DF1 then DF0
        bsr.w   MotorOff                        ; 76022
        clr.w   $2(a6)                          ; 76026
        bsr.w   MotorOff                        ; 7602A
        lea.l   $70000.l,a0                     ; 7602E  3 tracks from track 91: the loading screen
        move.w  #$5b,d0                         ; 76034
        moveq   #$3,d1                          ; 76038
        bsr.w   ReadTracksOrReset               ; 7603A
        bsr.w   MotorOnWaitReady                ; 7603E
        bsr.w   SeekTrack0                      ; 76042
        bsr.w   DecodeLoadScreen                ; 76046  decode it to $78000
        lea.l   $70002.l,a0                     ; 7604A  its colours, stored at half value
        lea.l   (CUSTOM+COLOR00).l,a1           ; 76050
        move.w  #$f,d0                          ; 76056
l_7605A:
        move.w  (a0)+,d1                        ; 7605A
        add.w   d1,d1                           ; 7605C
        move.w  d1,(a1)+                        ; 7605E
        dbra    d0,l_7605A                      ; 76060
        bra.w   Protection                      ; 76064  the protection (Copylock): ends in LoadAndRunGame
	dcb.b	68,$00
dat_760AC:
	dc.b	$00
	dc.b	$00
SavedRegs:
	dcb.b	96,$00
	dc.b	$FF,$FF,$FF,$FF,$00,$00,$00,$01,$00,$00
tvd_Last:
	dc.b	$00,$00,$00,$00,$00,$00,$00,$00
dat_76120:
	dc.b	$FF,$FF,$FF,$FF

;-------------------------------------------------------------------------------
; Protection - Rob Northen Copylock, as on track 0.
; From $76148 the code is trace-vector encrypted: each instruction is decrypted by the trace
; handler ($76234) just before it runs, and re-encrypted after. tools/disasm/tvd.py decrypts it to
; nzs_loader_tvd.lst: it reads the Copylock track (track 1) with its 11 sync words ($764AC),
; times the long track, checks the "Rob Northen Comp" signature and derives the key from the
; track. It ends with a privilege violation into LoadAndRunGame with the key in d0.
;-------------------------------------------------------------------------------
Protection:
        move.l  a6,-(a7)                        ; 76124  save the registers, ILLEGAL -> Prot_Illegal1 (see nzs_loader_tvd.lst)
        lea.l   SavedRegs(pc),a6                ; 76126
        movem.l d0-d7/a0-a7,(a6)                ; 7612A
        lea.l   $40(a6),a6                      ; 7612E
        move.l  (a7)+,-$8(a6)                   ; 76132
        move.l  $10.l,d1                        ; 76136
        pea.l   Prot_Illegal1(pc)               ; 7613C
        move.l  (a7)+,$10.l                     ; 76140
        illegal #$4afc                          ; 76146
Prot_Illegal1:
        pea.l   Prot_NoCacr(pc)                 ; 76148
        move.l  (a7)+,$10.l                     ; 7614C
        movea.l a7,a1                           ; 76152
	dc.b	$4E,$7A,$00,$02,$41,$FA,$FF,$C6,$20,$80,$08,$80,$00,$00,$4E,$7B
	dc.b	$00,$02
Prot_NoCacr:
        movea.l a1,a7                           ; 76166
        move.l  d1,$10.l                        ; 76168
        movem.l $8.l,d0-d7                      ; 7616E
        movem.l d0-d7,(a6)                      ; 76176
        lea.l   TVD_Enter(pc),a0                ; 7617A
        move.l  a0,$10.l                        ; 7617E
        illegal #$4afc                          ; 76184
	dc.b	$D5,$03,$FF,$E1,$60,$1E,$2A,$C6,$B5,$39,$9F,$83,$00,$7C,$4A,$CC
	dc.b	$D5,$33,$FF,$89,$60,$76,$2A,$D6,$B5,$29,$9F,$AB,$00,$54,$4A,$84
	dc.b	$D5,$7B,$00,$49,$9F,$B6,$2A,$82,$B5,$7D,$60,$47,$FF,$B8,$4A,$98
	dc.b	$D5,$67,$00,$71,$9F,$8E,$2A,$B6,$B5,$49,$60,$63,$FF,$9C,$B5,$54
	dc.b	$2A,$AB,$FF,$81,$60,$7E,$D5,$C0,$4A,$3F,$9F,$87,$00,$78,$4A,$7E
	dc.b	$D5,$81,$FF,$81,$60,$7E,$D5,$CC,$4A,$33,$60,$3B,$FF,$C4,$4A,$06
	dc.b	$D5,$F9,$FF,$E9,$60,$16,$D5,$E8,$4A,$17,$60,$1F,$FF,$E0,$4A,$3E
	dc.b	$D5,$C1,$FF,$F5
TVD_Enter:
        movem.l d0/a0-a1,-(a7)                  ; 761FA
        lea.l   TVD_Trace(pc),a0                ; 761FE
        move.l  a0,$24.l                        ; 76202
        lea.l   LoadAndRunGame(pc),a0           ; 76208
        move.l  a0,$20.l                        ; 7620C
        addi.l  #$2,$e(a7)                      ; 76212
        ori.b   #$7,$c(a7)                      ; 7621A
        bchg    #$7,$c(a7)                      ; 76220
        lea.l   tvd_Last(pc),a1                 ; 76226
        beq.b   l_76246                         ; 7622A
        movea.l (a1),a0                         ; 7622C
        move.l  $4(a1),(a0)                     ; 7622E
        bra.b   l_7625A                         ; 76232
TVD_Trace:
        andi.w  #$f8ff,sr                       ; 76234
        movem.l d0/a0-a1,-(a7)                  ; 76238
        lea.l   tvd_Last(pc),a1                 ; 7623C
        movea.l (a1),a0                         ; 76240
        move.l  $4(a1),(a0)                     ; 76242
l_76246:
        movea.l $e(a7),a0                       ; 76246
        move.l  a0,(a1)                         ; 7624A
        move.l  (a0),$4(a1)                     ; 7624C
        move.l  -$4(a0),d0                      ; 76250
        not.l   d0                              ; 76254
        swap    d0                              ; 76256
        eor.l   d0,(a0)                         ; 76258
l_7625A:
        movem.l (a7)+,d0/a0-a1                  ; 7625A
        rte                                     ; 7625E
	dc.b	$F0,$76,$FC,$E0,$40,$E6,$0F,$89,$00,$08,$BA,$0D,$0E,$CE,$81,$36
	dc.b	$0C,$C9,$C1,$2E,$EC,$5B,$31,$65,$9F,$52,$EC,$52,$73,$AD,$60,$BF
	dc.b	$05,$C4,$05,$44,$00,$D6,$06,$04,$06,$44,$06,$C4,$05,$44,$01,$10
	dc.b	$BD,$15,$04,$E7,$B9,$B1,$42,$F6,$DC,$09,$46,$D6,$DE,$29,$20,$64
	dc.b	$AB,$9D,$07,$E0,$9F,$7F,$21,$7A,$05,$DF,$8A,$25,$14,$DA,$FA,$E8
	dc.b	$23,$17,$AC,$EC,$32,$13,$DC,$28,$01,$D7,$DE,$2B,$40,$88,$D4,$95
	dc.b	$5B,$6C,$C5,$93,$2B,$D8,$F6,$24,$68,$8B,$FC,$A2,$0F,$CD,$C5,$1B
	dc.b	$62,$20,$FB,$11,$08,$46,$D3,$B0,$72,$74,$00,$04,$99,$3F,$6A,$68
	dc.b	$97,$9E,$6E,$20,$00,$08,$99,$4D,$6A,$1A,$BC,$98,$6D,$70,$00,$0C
	dc.b	$99,$43,$14,$B9,$C9,$0E,$E6,$68,$FA,$0F,$54,$39,$E6
	dc.b	'mZhV(x~'
	dc.b	$A5,$8B,$6E,$4E,$79,$8F,$E7,$70,$93,$B3,$0D,$4C,$19,$43,$C6,$86
	dc.b	$0F,$45,$90,$BA,$3A,$61,$55,$1F,$C1,$F0,$FE,$F3,$AA,$84,$D5,$BA
	dc.b	$9A,$79,$55,$78,$C7,$83,$48,$7C,$F9,$F6,$76,$F6,$C7,$7C,$4E,$80
	dc.b	$D0,$7F,$39,$11,$A0,$CA,$2B,$35,$B5,$CA,$5E,$E5,$C7,$06,$79,$03
	dc.b	$5C,$3E,$D7,$C3,$18,$06,$A2,$A3,$3C,$5C,$E7,$51,$7E,$8C,$D0,$B9
	dc.b	$E7,$5A,$2C,$9F,$D2,$F8,$4C,$07,$D2,$D2,$4C,$2D,$B2,$84,$0C,$81
	dc.b	$4E,$7C,$B7,$D3,$F3,$7F,$0E,$D0,$48,$2F,$E6,$1B,$0E,$EB,$81,$14
	dc.b	$30,$9E,$87,$86,$9E,$2B,$00,$84,$DB,$7B,$04,$93,$B8,$96,$25,$AE
	dc.b	$39,$D9,$F6,$17,$D2,$51,$0F,$AE,$D0,$50,$4E,$C9,$D6,$CC,$07,$B3
	dc.b	$C8,$5C,$82,$E3,$7F,$5C,$62,$F6,$FB,$E7,$26,$50,$93,$F7,$1E,$03
	dc.b	$C1,$E4,$5F,$1B,$E1,$F2,$2C,$CD,$82,$FB,$E1,$FB,$52,$DB,$7E,$03
	dc.b	$CF,$89,$78,$91,$E1,$FC,$3C,$03,$B7,$F3,$AD,$9D,$B1,$F2,$1F,$C7
	dc.b	$AD,$98,$1E,$B8,$E0,$3E,$51,$B4,$E6,$AC,$7F,$C1,$C8,$7E,$13,$81
	dc.b	$9E,$71,$84,$06,$98,$6B,$02,$98,$F5,$67,$67,$96,$FE,$63,$09,$5C
	dc.b	$98,$68,$07,$93,$F0,$AC,$67,$97,$C9,$A1,$F0,$BB,$43,$9B,$36,$58
	dc.b	$87,$D2,$30,$CA,$B1,$67,$6C,$D0,$D2,$D6,$4E,$47,$F0,$00,$3E,$BF
	dc.b	$B1,$C6,$2F,$39,$C0,$AC,$0E,$2F,$90,$C6,$00,$24,$DE,$92,$6F,$19
	dc.b	$A1,$9A,$47,$6D,$00,$9E,$CE,$1D,$2D,$92,$00,$9E,$CE,$1D,$52,$7D
	dc.b	$00,$96,$CE,$15,$AD,$80,$00,$9C,$9E,$63,$52,$6F,$9C,$EC,$65,$9C
	dc.b	$00,$9E,$B5,$E1,$06,$C1,$FC,$7F,$4D,$F5,$F8,$F6
Prot_TimeLongTrack:
        tst.b   (CIAB_ICR).l                    ; 76440
l_76446:
        btst    #$4,(CIAB_ICR).l                ; 76446
        beq.b   l_76446                         ; 7644E
        move.w  #$8000,$24(a0)                  ; 76450
        move.w  #$8000,$24(a0)                  ; 76456
        moveq   #$0,d1                          ; 7645C
        move.l  #$61a80,d2                      ; 7645E
l_76464:
        subq.l  #$1,d2                          ; 76464
        beq.b   l_76492                         ; 76466
        move.b  $1a(a0),d0                      ; 76468
        btst    #$4,d0                          ; 7646C
        beq.b   l_76464                         ; 76470
        moveq   #$31,d2                         ; 76472
l_76474:
        addq.l  #$1,d1                          ; 76474
        move.w  $1a(a0),d0                      ; 76476
        bpl.b   l_76474                         ; 7647A
        move.b  d0,(a1)+                        ; 7647C
        dbra    d2,l_76474                      ; 7647E
        move.w  #$3cd,d2                        ; 76482
l_76486:
        addq.l  #$1,d1                          ; 76486
        move.w  $1a(a0),d0                      ; 76488
        bpl.b   l_76486                         ; 7648C
        dbra    d2,l_76486                      ; 7648E
l_76492:
        move.w  $1e(a0),d0                      ; 76492
        move.w  #$2,$9c(a0)                     ; 76496
        move.w  #$4000,$24(a0)                  ; 7649C
        btst    #$1,d0                          ; 764A2
        bne.b   l_764C2                         ; 764A6
        moveq   #$0,d1                          ; 764A8
        bra.b   l_764C2                         ; 764AA
CopylockSyncs:
	dc.b	$8A,$91,$8A,$44,$8A,$45,$8A,$51,$89,$12,$89,$11,$89,$14,$89,$15
	dc.b	$89,$44,$89,$45,$89,$51
l_764C2:
        move.l  d1,d0                           ; 764C2
        illegal #$4afc                          ; 764C4
	dc.b	$FB,$76,$76,$76,$81,$08,$04,$8E,$9A,$7F,$45,$BC,$FB,$78,$27,$C0
	dc.b	$B9,$3F,$05,$D7,$9A,$3E,$17,$3E,$A9,$38,$65,$7E,$D1,$00,$3E,$7E
	dc.b	$F1,$BB,$D2,$D5,$7B,$AA,$85,$D4,$6A,$AA,$DB,$20,$65,$26,$95,$EA
	dc.b	$E0,$01,$3F,$C2,$6A,$15,$06,$1A,$F1,$F5,$95,$EF,$0D,$16,$A1,$69
	dc.b	$34,$60,$85,$EA,$0A,$15,$BB,$9F,$0C,$87,$89,$EA,$4C,$17,$D2,$E8
	dc.b	$76,$CB,$8B,$71,$2D,$68,$B5,$9B,$7A,$5E,$29,$65,$B7,$9A,$85,$9B
	dc.b	$42,$65,$D7,$92,$49,$6D,$BD,$A4,$24,$73,$A3,$8C,$E6,$37,$7E,$C6
	dc.b	$EC,$3F,$72,$B0,$DF,$CB,$40,$C0,$DE,$59,$72,$22,$ED,$33,$73,$CC
	dc.b	$8D,$73,$42,$B6,$77,$FB,$6B,$4C,$D5,$49,$73,$BA,$BD,$C1,$2A,$B6
	dc.b	$A5,$49,$16,$69,$D5,$77,$64,$FD,$78,$4A,$C6,$4F,$60,$AE,$AD,$61
	dc.b	$39,$B0,$88,$3A,$3F,$22,$BE,$4F,$39,$E5,$CE,$23,$41,$B4,$00,$BF
	dc.b	$E0,$01,$78,$F2,$E6,$0D,$1F,$D4,$B1,$E7,$E6,$02,$69,$02,$F6,$E7
	dc.b	$39,$22,$6D,$77,$71,$C0,$CF,$C5,$69,$08,$D4,$87,$30,$3A,$BF,$90
	dc.b	$D0,$EB,$6E,$EE,$BB,$13,$74,$6C,$FB,$93,$48,$B3,$8B,$8D,$3A,$07
	dc.b	$B1,$F9,$2E,$04,$A5,$FB,$6A,$3E,$2A,$9F,$E7,$5A,$6E,$A3,$87,$65
	dc.b	$18,$1A,$D1,$00,$2E,$FC,$E7,$9A,$1E,$65,$D1,$00,$2F,$7C,$D4,$83
	dc.b	$2E,$FC,$9B,$02,$03,$F9,$F4,$85,$64,$FF,$D1,$02,$48,$F9,$BF,$85
	dc.b	$2E,$FC,$D9,$80,$40,$7A,$AC,$46,$26,$C0,$D1,$00,$26,$3C,$D9,$3F
	dc.b	$35,$03,$D9,$7C,$D1,$00,$0E,$C3,$26,$83,$0B,$B8,$94,$73,$5B,$B6
	dc.b	$0F,$5B,$C2,$9E,$5F,$53,$9F,$AE,$74,$68,$A0,$13,$D1,$00,$2E,$FD
	dc.b	$5F,$93,$A6,$6C,$D1,$01,$2F,$7C,$D4,$83,$2E,$FD,$9B,$03,$03,$F8
	dc.b	$F4,$85,$64,$FE,$88,$C3,$0B,$C5,$D1,$00,$0E,$C3,$F4,$3A,$05,$DC
	dc.b	$CE,$3C,$DB,$4B,$77,$34,$EE,$37,$5F,$BD,$E1,$B8,$EB,$B4,$34,$CB
	dc.b	$87,$CE,$14,$B4,$FA,$B4,$25,$72,$EB,$4B,$00,$04,$DD,$FB,$63,$FE
	dc.b	$FF,$D9,$2F,$6E,$9C,$03,$29,$00
Prot_Exit:
        move.l  dat_76120(pc),d0                ; 7664E
        bmi.b   l_76658                         ; 76652
	dc.b	$4E,$7B,$00,$02
l_76658:
        movem.l d0-d7,$8.l                      ; 76658
        dc.w    $4CFA,$7FFF,$FA4A               ; 76660  movem.l $760ac(pc),d0-d7/a0-a6
        rte                                     ; 76666

;-------------------------------------------------------------------------------
; LoadAndRunGame - the key in d0 gives the load address (key - $F974D77D): with the right key,
; $400. Reads the packed main program, unpacks it there and jumps to it.
;-------------------------------------------------------------------------------
LoadAndRunGame:
        move.l  d0,-(a7)                        ; 76668  the Copylock key in d0: key - $F974D77D = $400 (key $F974DB7D)
        subi.l  #$f974d77d,d0                   ; 7666A
        movea.l d0,a0                           ; 76670
        move.w  #$5e,d0                         ; 76672  50 tracks from track 94: the packed main program
        move.w  #$32,d1                         ; 76676
        bsr.w   ReadTracksOrReset               ; 7667A
        move.l  (a7),d0                         ; 7667E
        subi.l  #$f974d77d,d0                   ; 76680
        movea.l d0,a0                           ; 76686
        bsr.w   Unpack                          ; 76688  unpack it in place
        move.l  (a7)+,d0                        ; 7668C
        subi.l  #$f974d77d,d0                   ; 7668E
        movea.l d0,a0                           ; 76694
        jmp     (a0)                            ; 76696  enter the game at $400
ReadTracksOrReset:
        bsr.w   ReadTracks                      ; 76698
        tst.w   d0                              ; 7669C
        bpl.w   l_7671C                         ; 7669E
        move.w  $c(a6),d1                       ; 766A2
        jmp     $f80000.l                       ; 766A6  a read that fails resets the machine (Kickstart)
DecodeLoadScreen:
        lea.l   $78000.l,a1                     ; 766AC
        movea.l a1,a2                           ; 766B2
        clr.l   d5                              ; 766B4
        clr.l   d6                              ; 766B6
        clr.l   d7                              ; 766B8
        lea.l   $70022.l,a0                     ; 766BA
l_766C0:
        move.b  (a0)+,d0                        ; 766C0
        bpl.b   l_766DC                         ; 766C2
        cmp.b   #$80,d0                         ; 766C4
        beq.w   l_766C0                         ; 766C8
        neg.b   d0                              ; 766CC
        andi.w  #$7f,d0                         ; 766CE
        move.b  (a0)+,d1                        ; 766D2
l_766D4:
        bsr.b   PutScreenByte                   ; 766D4
        dbra    d0,l_766D4                      ; 766D6
        bra.b   l_766C0                         ; 766DA
l_766DC:
        andi.w  #$7f,d0                         ; 766DC
l_766E0:
        move.b  (a0)+,d1                        ; 766E0
        bsr.b   PutScreenByte                   ; 766E2
        dbra    d0,l_766E0                      ; 766E4
        bra.b   l_766C0                         ; 766E8
PutScreenByte:
        move.b  d1,(a1)+                        ; 766EA
        bchg    #$f,d5                          ; 766EC
        beq.b   l_7671C                         ; 766F0
        addq.b  #$2,d5                          ; 766F2
        cmp.b   #$28,d5                         ; 766F4
        bne.b   l_7671C                         ; 766F8
        clr.b   d5                              ; 766FA
        lea.l   $2000(a2),a2                    ; 766FC
        movea.l a2,a1                           ; 76700
        addi.b  #$1,d6                          ; 76702
        andi.b  #$3,d6                          ; 76706
        bne.b   l_7671C                         ; 7670A
        lea.l   -$7fd8(a2),a2                   ; 7670C
        movea.l a2,a1                           ; 76710
        addq.b  #$1,d7                          ; 76712
        cmp.b   #$c8,d7                         ; 76714
        bne.b   l_7671C                         ; 76718
        addq.l  #$4,a7                          ; 7671A
l_7671C:
        rts                                     ; 7671C
Unpack:
        movem.l d0-d3/a0-a2,-(a7)               ; 7671E
        move.l  a0,-(a7)                        ; 76722
        movea.l a0,a1                           ; 76724
        move.l  (a1)+,d3                        ; 76726
        move.l  (a1)+,d1                        ; 76728
        adda.l  d1,a1                           ; 7672A
        addq.l  #$1,a1                          ; 7672C
        adda.l  d3,a0                           ; 7672E
        addq.l  #$1,a0                          ; 76730
l_76732:
        move.b  -(a1),-(a0)                     ; 76732
        subq.l  #$1,d1                          ; 76734
        bpl.b   l_76732                         ; 76736
        exg.l   a1,a0                           ; 76738
        movea.l (a7)+,a0                        ; 7673A
        move.b  (a1)+,d2                        ; 7673C
l_7673E:
        move.b  (a1)+,d0                        ; 7673E
        cmp.b   d0,d2                           ; 76740
        beq.b   l_7674C                         ; 76742
        move.b  d0,(a0)+                        ; 76744
        subq.l  #$1,d3                          ; 76746
        bpl.b   l_7673E                         ; 76748
        bra.b   l_7675E                         ; 7674A
l_7674C:
        clr.w   d1                              ; 7674C
        move.b  (a1)+,d0                        ; 7674E
        move.b  (a1)+,d1                        ; 76750
l_76752:
        move.b  d0,(a0)+                        ; 76752
        subq.l  #$1,d3                          ; 76754
        dbra    d1,l_76752                      ; 76756
        tst.l   d3                              ; 7675A
        bpl.b   l_7673E                         ; 7675C
l_7675E:
        movem.l (a7)+,d0-d3/a0-a2               ; 7675E
        rts                                     ; 76762
MotorOnWaitReady:
        move.w  d0,-(a7)                        ; 76764
        ori.b   #$f8,(CIAB_PRB).l               ; 76766
        bclr    #$7,(CIAB_PRB).l                ; 7676E
        bset    #$2,(CIAB_PRB).l                ; 76776
        move.w  $2(a6),d0                       ; 7677E
        addq.w  #$3,d0                          ; 76782
        bclr    d0,(CIAB_PRB).l                 ; 76784
l_7678A:
        btst    #$5,(CIAA_PRA).l                ; 7678A
        bne.b   l_7678A                         ; 76792
        move.w  (a7)+,d0                        ; 76794
        rts                                     ; 76796
MotorOff:
        ori.b   #$78,(CIAB_PRB).l               ; 76798
        bset    #$7,(CIAB_PRB).l                ; 767A0
        move.w  d0,-(a7)                        ; 767A8
        move.w  $2(a6),d0                       ; 767AA
        addq.w  #$3,d0                          ; 767AE
        bclr    d0,(CIAB_PRB).l                 ; 767B0
        bset    d0,(CIAB_PRB).l                 ; 767B6
        move.w  (a7)+,d0                        ; 767BC
        rts                                     ; 767BE
dat_767C0:
	dc.b	$00,$00,$00,$00
ReadTracks:
        move.l  a7,$67c0(a6)                    ; 767C4
        move.w  d0,-(a7)                        ; 767C8
        move.w  d1,$8(a6)                       ; 767CA
        move.l  a0,$4(a6)                       ; 767CE
        bsr.w   MotorOnWaitReady                ; 767D2
        bsr.w   SeekTrack0                      ; 767D6
        move.w  (a7)+,$c(a6)                    ; 767DA
        clr.w   $0(a6)                          ; 767DE
l_767E2:
        bsr.w   SeekTrack                       ; 767E2
        clr.w   d7                              ; 767E6
l_767E8:
        move.l  #$68000,(CUSTOM+DSKPTH).l       ; 767E8
        move.w  #$8010,(CUSTOM+DMACON).l        ; 767F2
        move.w  #$4000,(CUSTOM+DSKLEN).l        ; 767FA
        move.w  #$9996,d0                       ; 76802
        move.w  #$2,(CUSTOM+INTREQ).l           ; 76806
        move.w  #$4489,(CUSTOM+DSKSYNC).l       ; 7680E
        move.w  #$8400,(CUSTOM+ADKCON).l        ; 76816
        move.w  d0,(CUSTOM+DSKLEN).l            ; 7681E
        btst    #$4,(CIAB_ICR).l                ; 76824
l_7682C:
        btst    #$4,(CIAB_ICR).l                ; 7682C
        beq.b   l_7682C                         ; 76834
        move.w  d0,(CUSTOM+DSKLEN).l            ; 76836
        clr.w   d6                              ; 7683C
l_7683E:
        btst    #$4,(CIAB_ICR).l                ; 7683E
        beq.b   l_76876                         ; 76846
        addq.w  #$1,d6                          ; 76848
        cmp.w   #$5,d6                          ; 7684A
        bcs.b   l_76876                         ; 7684E
        move.w  #$4000,(CUSTOM+DSKLEN).l        ; 76850
        moveq   #-3,d0                          ; 76858
        bra.w   l_76912                         ; 7685A
l_7685E:
        move.w  d7,-(a7)                        ; 7685E
        move.w  $c(a6),-(a7)                    ; 76860
        bsr.w   SeekTrack0                      ; 76864
        move.w  (a7)+,$c(a6)                    ; 76868
        bsr.w   SeekTrack                       ; 7686C
        move.w  (a7)+,d7                        ; 76870
        bra.w   l_767E8                         ; 76872
l_76876:
        move.w  (CUSTOM+INTREQR).l,d0           ; 76876
        btst    #$1,d0                          ; 7687C
        beq.b   l_7683E                         ; 76880
        move.w  #$4000,(CUSTOM+DSKLEN).l        ; 76882
        move.w  #$2,(CUSTOM+INTREQ).l           ; 7688A
        move.w  #$10,(CUSTOM+DMACON).l          ; 76892
        movea.l #$68000,a0                      ; 7689A
        cmpi.w  #$4489,(a0)+                    ; 768A0
        beq.w   l_768B8                         ; 768A4
        addq.w  #$1,d7                          ; 768A8
        cmp.w   #$5,d7                          ; 768AA
        bcs.w   l_7685E                         ; 768AE
        moveq   #-1,d0                          ; 768B2
        bra.w   l_76912                         ; 768B4
l_768B8:
        cmpi.b  #$44,(a0)                       ; 768B8
        bne.w   l_768CC                         ; 768BC
        cmpi.b  #$89,$1(a0)                     ; 768C0
        bne.w   l_768CC                         ; 768C6
        addq.l  #$2,a0                          ; 768CA
l_768CC:
        lea.l   $76bb0(pc),a4                   ; 768CC
        moveq   #$a,d7                          ; 768D0
l_768D2:
        bsr.w   sub_76922                       ; 768D2
        tst.l   d0                              ; 768D6
        bpl.w   l_768EE                         ; 768D8
        addq.w  #$1,$0(a6)                      ; 768DC
        cmpi.w  #$a,$0(a6)                      ; 768E0
        beq.w   l_76912                         ; 768E6
        bra.w   l_767E2                         ; 768EA
l_768EE:
        dbra    d7,l_768D2                      ; 768EE
        addi.l  #$1600,$4(a6)                   ; 768F2
        addq.w  #$1,$c(a6)                      ; 768FA
        clr.w   $0(a6)                          ; 768FE
        subq.w  #$1,$8(a6)                      ; 76902
        bne.w   l_767E2                         ; 76906
        bsr.w   MotorOff                        ; 7690A
        clr.l   d0                              ; 7690E
        rts                                     ; 76910
l_76912:
        move.l  d0,-(a7)                        ; 76912
        bsr.w   MotorOff                        ; 76914
        move.l  (a7)+,d0                        ; 76918
        movea.l (dat_767C0).l,a7                ; 7691A
        rts                                     ; 76920
sub_76922:
        movea.l a4,a1                           ; 76922
        move.w  #$4,d1                          ; 76924
        bsr.w   sub_769B2                       ; 76928
        move.w  #$10,d1                         ; 7692C
        bsr.w   sub_769B2                       ; 76930
        move.w  #$4,d1                          ; 76934
        bsr.w   sub_769B2                       ; 76938
        move.w  #$4,d1                          ; 7693C
        bsr.w   sub_769B2                       ; 76940
        cmpi.b  #$ff,(a4)                       ; 76944
        beq.w   l_76950                         ; 76948
        moveq   #-1,d0                          ; 7694C
        rts                                     ; 7694E
l_76950:
        movea.l a4,a1                           ; 76950
        clr.l   d0                              ; 76952
        move.b  $2(a4),d0                       ; 76954
        andi.b  #$f,d0                          ; 76958
        asl.l   #$8,d0                          ; 7695C
        add.l   d0,d0                           ; 7695E
        add.l   $4(a6),d0                       ; 76960
        movea.l d0,a1                           ; 76964
        move.w  #$200,d1                        ; 76966
        move.l  a1,-(a7)                        ; 7696A
        bsr.w   sub_769B2                       ; 7696C
        movea.l (a7)+,a1                        ; 76970
        move.w  #$ff,d1                         ; 76972
        bsr.w   sub_769A4                       ; 76976
        cmp.l   $4(a4),d0                       ; 7697A
        adda.l  #$1c,a4                         ; 7697E
        beq.w   l_7698E                         ; 76984
        move.l  d0,d1                           ; 76988
        moveq   #-2,d0                          ; 7698A
        rts                                     ; 7698C
l_7698E:
        cmpi.w  #$4489,(a0)+                    ; 7698E
        bne.w   l_7698E                         ; 76992
        cmpi.w  #$4489,(a0)                     ; 76996
        bne.w   l_769A0                         ; 7699A
        addq.l  #$2,a0                          ; 7699E
l_769A0:
        clr.l   d0                              ; 769A0
        rts                                     ; 769A2
sub_769A4:
        clr.l   d0                              ; 769A4
        clr.l   d2                              ; 769A6
l_769A8:
        move.w  (a1)+,d2                        ; 769A8
        add.l   d2,d0                           ; 769AA
        dbra    d1,l_769A8                      ; 769AC
        rts                                     ; 769B0
sub_769B2:
        lea.l   (a0,d1.w),a2                    ; 769B2
        subq.w  #$1,d1                          ; 769B6
l_769B8:
        move.b  (a0)+,d0                        ; 769B8
        andi.b  #$55,d0                         ; 769BA
        add.b   d0,d0                           ; 769BE
        move.b  (a2)+,d2                        ; 769C0
        andi.b  #$55,d2                         ; 769C2
        or.b    d2,d0                           ; 769C6
        move.b  d0,(a1)+                        ; 769C8
        dbra    d1,l_769B8                      ; 769CA
        movea.l a2,a0                           ; 769CE
        rts                                     ; 769D0
SeekTrack0:
        clr.w   $c(a6)                          ; 769D2
        move.w  #$52,$e(a6)                     ; 769D6
SeekTrack:
        move.w  $c(a6),d0                       ; 769DC
        bset    #$2,(CIAB_PRB).l                ; 769E0
        lsr.w   #$1,d0                          ; 769E8
        bcc.b   l_769F4                         ; 769EA
        bclr    #$2,(CIAB_PRB).l                ; 769EC
l_769F4:
        move.w  d0,$a(a6)                       ; 769F4
        bclr    #$1,(CIAB_PRB).l                ; 769F8
        move.w  #$1,d2                          ; 76A00
        move.w  $a(a6),d0                       ; 76A04
        cmp.w   $e(a6),d0                       ; 76A08
        beq.b   l_76A5C                         ; 76A0C
        bcc.b   l_76A1A                         ; 76A0E
        bset    #$1,(CIAB_PRB).l                ; 76A10
        neg.w   d2                              ; 76A18
l_76A1A:
        add.w   d2,$e(a6)                       ; 76A1A
        bclr    #$0,(CIAB_PRB).l                ; 76A1E
        move.w  #$32,d2                         ; 76A26
l_76A2A:
        dbra    d2,l_76A2A                      ; 76A2A
        bset    #$0,(CIAB_PRB).l                ; 76A2E
        move.w  #$1770,d2                       ; 76A36
l_76A3A:
        dbra    d2,l_76A3A                      ; 76A3A
        move.w  $a(a6),d0                       ; 76A3E
        btst    #$4,(CIAA_PRA).l                ; 76A42
        bne.b   SeekTrack                       ; 76A4A
        clr.w   $e(a6)                          ; 76A4C
        clr.w   $c(a6)                          ; 76A50
        bset    #$2,(CIAB_PRB).l                ; 76A54
l_76A5C:
        move.w  $c(a6),d0                       ; 76A5C
        move.w  #$9100,d2                       ; 76A60
        cmp.w   #$50,d0                         ; 76A64
        bls.b   l_76A82                         ; 76A68
        move.w  #$b100,d2                       ; 76A6A
        cmp.w   #$a0,d0                         ; 76A6E
        bls.b   l_76A82                         ; 76A72
        move.w  #$d100,d2                       ; 76A74
        cmp.w   #$a0,d0                         ; 76A78
        bls.b   l_76A82                         ; 76A7C
        move.w  #$f100,d2                       ; 76A7E
l_76A82:
        move.w  #$6000,(CUSTOM+ADKCON).l        ; 76A82
        move.w  d2,(CUSTOM+ADKCON).l            ; 76A8A
        rts                                     ; 76A90
HardwareOn:
        lea.l   CUSTOM,a0                       ; 76A92
        move.b  #$7f,(CIAA_ICR).l               ; 76A98
        bclr    #$6,(CIAA_CRA).l                ; 76AA0
        move.w  #$7fff,INTREQ(a0)               ; 76AA8
        move.b  (CIAA_ICR).l,d0                 ; 76AAE
        move.b  (CIAA_SDR).l,d0                 ; 76AB4
        move.w  #$7f00,ADKCON(a0)               ; 76ABA
        move.w  #$9100,ADKCON(a0)               ; 76AC0
        move.w  #$8380,DMACON(a0)               ; 76AC6
        rts                                     ; 76ACC
HardwareInit:
        movem.l d0/a0-a1,-(a7)                  ; 76ACE
        lea.l   CUSTOM,a0                       ; 76AD2
        move.w  #$7fff,INTENA(a0)               ; 76AD8
        move.w  #$7fff,DMACON(a0)               ; 76ADE
        move.w  #$4200,BPLCON0(a0)              ; 76AE4
        clr.w   BPLCON1(a0)                     ; 76AEA
        clr.w   BPL1MOD(a0)                     ; 76AEE
        clr.w   BPL2MOD(a0)                     ; 76AF2
        move.w  #$38,DDFSTRT(a0)                ; 76AF6
        move.w  #$d0,DDFSTOP(a0)                ; 76AFC
        move.w  #$3c81,DIWSTRT(a0)              ; 76B02
        move.w  #$4c1,DIWSTOP(a0)               ; 76B08
        move.l  #LoadScreenCopper,COP1LCH(a0)   ; 76B0E
        move.w  COPJMP1(a0),d0                  ; 76B16
        movea.l #$78000,a1                      ; 76B1A
        move.w  #$1fff,d0                       ; 76B20
l_76B24:
        clr.l   (a1)+                           ; 76B24
        dbra    d0,l_76B24                      ; 76B26
        clr.w   $142(a0)                        ; 76B2A
        clr.w   $14a(a0)                        ; 76B2E
        clr.w   $152(a0)                        ; 76B32
        clr.w   $15a(a0)                        ; 76B36
        clr.w   $162(a0)                        ; 76B3A
        clr.w   $16a(a0)                        ; 76B3E
        clr.w   $172(a0)                        ; 76B42
        clr.w   $17a(a0)                        ; 76B46
        lea.l   $180(a0),a1                     ; 76B4A
        move.w  #$1f,d0                         ; 76B4E
l_76B52:
        move.w  #$0,(a1)+                       ; 76B52
        dbra    d0,l_76B52                      ; 76B56
        bsr.w   HardwareOn                      ; 76B5A
        move.w  #$2000,sr                       ; 76B5E
        movem.l (a7)+,d0/a0-a1                  ; 76B62
        rts                                     ; 76B66
LoadScreenCopper:
	dc.b	$00,$E0,$00,$07,$00,$E2,$80,$00,$00,$E4,$00,$07,$00,$E6,$A0,$00
	dc.b	$00,$E8,$00,$07,$00,$EA,$C0,$00,$00,$EC,$00,$07,$00,$EE,$E0,$00
	dc.b	$FF,$FF,$FF,$FE

;===============================================================================
; Runs where it is loaded: file offset $0B90 onwards at $F90
;===============================================================================
	org	$F90
	dc.b	$00,$00
Start:
        move.w  #$7fff,(CUSTOM+INTENA).l        ; 00F92
        lea.l   $404(pc),a0                     ; 00F9A
        move.w  #$2e2,d0                        ; 00F9E
        movea.l #LoaderMain,a1                  ; 00FA2
l_00FA8:
        move.l  (a0)+,(a1)+                     ; 00FA8
        dbra    d0,l_00FA8                      ; 00FAA
        jmp     (LoaderMain).l                  ; 00FAE
	dcb.b	2636,$00
