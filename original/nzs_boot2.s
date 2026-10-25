; The New Zealand Story (Ocean 1989, Amiga) - second-stage bootblock
; Decrypted from the Rob Northen protection loader on track 0 (tools/protemu/run_protection.sh):
; its payload copies these 1024 bytes over Kickstart's boot buffer and jumps to offset 12.
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o boot2.bin nzs_boot2.s
;
; Offset 12 goes to Start, which copies the loader (offset $10 onwards) to $76000 and runs it:
; it reads track 90 (the game loader) to $400 with the hardware - DSKLEN $9996, sync $4489,
; its variables at $2004-$200A and $61A0 - and jumps to $400.

	include	"nzs_hw.i"

	section	boot2,code

	org	0
	dc.b	$44,$4F,$53,$00,$DC,$4C,$1A,$A8,$00,$00,$00,$00
BootEntry:
        bra.w   Start                           ; 0000C

Loader_Stored:
;===============================================================================
; The loader: copied to $76000 by Start and run there
;===============================================================================
	org	$76000
Loader:
sub_76000:
        bra.w   LoadGameLoader                  ; 76000
	dc.b	$00
	dc.b	$00
dat_76006:
	dcb.b	308,$00
LoadGameLoader:
        lea.l   $400.l,a7                       ; 7613A  stack below the game loader
        lea.l   CUSTOM,a5                       ; 76140
        move.w  #$7fff,INTREQ(a5)               ; 76146
        move.w  #$7f00,ADKCON(a5)               ; 7614C
        move.w  #$9100,ADKCON(a5)               ; 76152
        move.w  #$8380,DMACON(a5)               ; 76158
        movea.l #$400,a0                        ; 7615E
        move.l  #$5a,d0                         ; 76164  track 90 (the game loader)
        bsr.w   ReadTracks                      ; 7616A
        jmp     $400.w                          ; 7616E  enter the game loader
MotorOn:
        ori.b   #$f8,(CIAB_PRB).l               ; 76172
        bclr    #$7,(CIAB_PRB).l                ; 7617A
        bset    #$2,(CIAB_PRB).l                ; 76182
        bclr    #$3,(CIAB_PRB).l                ; 7618A
l_76192:
        btst    #$5,(CIAA_PRA).l                ; 76192
        bne.w   l_76192                         ; 7619A
        rts                                     ; 7619E
	dc.b	$00,$00,$00,$00
ReadTracks:
        move.l  a7,$61a0.w                      ; 761A4
        move.w  d0,-(a7)                        ; 761A8
        move.w  d1,$2008.w                      ; 761AA
        move.l  a0,$2004.w                      ; 761AE
        bsr.w   MotorOn                         ; 761B2
        bsr.w   sub_762C4                       ; 761B6
        move.w  (a7)+,$200a.w                   ; 761BA
        bsr.w   sub_762CE                       ; 761BE
l_761C2:
        move.l  #$68000,$20(a5)                 ; 761C2
        move.w  #$8010,$96(a5)                  ; 761CA
        move.w  #$4000,$24(a5)                  ; 761D0
        move.w  #$9996,d0                       ; 761D6
        move.w  #$2,$9c(a5)                     ; 761DA
        move.w  #$4489,$7e(a5)                  ; 761E0
        move.w  #$8400,$9e(a5)                  ; 761E6
        move.w  d0,$24(a5)                      ; 761EC
        btst    #$4,(CIAB_ICR).l                ; 761F0
l_761F8:
        btst    #$4,(CIAB_ICR).l                ; 761F8
        beq.b   l_761F8                         ; 76200
        move.w  d0,$24(a5)                      ; 76202
l_76206:
        move.w  $1e(a5),d0                      ; 76206
        btst    #$1,d0                          ; 7620A
        beq.b   l_76206                         ; 7620E
        move.w  #$4000,$24(a5)                  ; 76210
        move.w  #$2,$9c(a5)                     ; 76216
        move.w  #$10,$96(a5)                    ; 7621C
        movea.l #$68000,a0                      ; 76222
        cmpi.w  #$4489,(a0)+                    ; 76228
        bne.b   l_761C2                         ; 7622C
        cmpi.b  #$44,(a0)                       ; 7622E
        bne.b   l_7623E                         ; 76232
        cmpi.b  #$89,$1(a0)                     ; 76234
        bne.b   l_7623E                         ; 7623A
        addq.l  #$2,a0                          ; 7623C
l_7623E:
        lea.l   dat_76006(pc),a4                ; 7623E
        moveq   #$a,d7                          ; 76242
l_76244:
        bsr.w   sub_7624E                       ; 76244
        dbra    d7,l_76244                      ; 76248
        rts                                     ; 7624C
sub_7624E:
        movea.l a4,a1                           ; 7624E
        moveq   #$4,d1                          ; 76250
        bsr.w   sub_762A4                       ; 76252
        moveq   #$10,d1                         ; 76256
        bsr.w   sub_762A4                       ; 76258
        moveq   #$4,d1                          ; 7625C
        bsr.w   sub_762A4                       ; 7625E
        moveq   #$4,d1                          ; 76262
        bsr.w   sub_762A4                       ; 76264
        movea.l a4,a1                           ; 76268
        clr.l   d0                              ; 7626A
        move.b  $2(a4),d0                       ; 7626C
        andi.b  #$f,d0                          ; 76270
        asl.l   #$8,d0                          ; 76274
        add.l   d0,d0                           ; 76276
        add.l   $2004.w,d0                      ; 76278
        movea.l d0,a1                           ; 7627C
        move.w  #$200,d1                        ; 7627E
        move.l  a1,-(a7)                        ; 76282
        bsr.w   sub_762A4                       ; 76284
        movea.l (a7)+,a1                        ; 76288
        move.w  #$ff,d1                         ; 7628A
l_7628E:
        cmpi.w  #$4489,(a0)+                    ; 7628E
        bne.w   l_7628E                         ; 76292
        cmpi.w  #$4489,(a0)                     ; 76296
        bne.w   l_762A0                         ; 7629A
        addq.l  #$2,a0                          ; 7629E
l_762A0:
        clr.l   d0                              ; 762A0
        rts                                     ; 762A2
sub_762A4:
        lea.l   (a0,d1.w),a2                    ; 762A4
        subq.w  #$1,d1                          ; 762A8
l_762AA:
        move.b  (a0)+,d0                        ; 762AA
        andi.b  #$55,d0                         ; 762AC
        add.b   d0,d0                           ; 762B0
        move.b  (a2)+,d2                        ; 762B2
        andi.b  #$55,d2                         ; 762B4
        or.b    d2,d0                           ; 762B8
        move.b  d0,(a1)+                        ; 762BA
        dbra    d1,l_762AA                      ; 762BC
        movea.l a2,a0                           ; 762C0
        rts                                     ; 762C2
sub_762C4:
        clr.w   $200a.w                         ; 762C4
        move.w  #$52,$200c.w                    ; 762C8
sub_762CE:
        move.w  $200a.w,d0                      ; 762CE
        bset    #$2,(CIAB_PRB).l                ; 762D2
        lsr.w   #$1,d0                          ; 762DA
        bcc.w   l_762E8                         ; 762DC
        bclr    #$2,(CIAB_PRB).l                ; 762E0
l_762E8:
        move.w  d0,$2000.w                      ; 762E8
        bclr    #$1,(CIAB_PRB).l                ; 762EC
        move.w  #$1,d2                          ; 762F4
        move.w  $2000.w,d0                      ; 762F8
        cmp.w   $200c.w,d0                      ; 762FC
        beq.w   l_76356                         ; 76300
        bcc.w   l_76312                         ; 76304
        bset    #$1,(CIAB_PRB).l                ; 76308
        neg.w   d2                              ; 76310
l_76312:
        add.w   d2,$200c.w                      ; 76312
        bclr    #$0,(CIAB_PRB).l                ; 76316
        move.w  #$32,d2                         ; 7631E
l_76322:
        dbra    d2,l_76322                      ; 76322
        bset    #$0,(CIAB_PRB).l                ; 76326
        move.w  #$1770,d2                       ; 7632E
l_76332:
        dbra    d2,l_76332                      ; 76332
        move.w  $2000.w,d0                      ; 76336
        btst    #$4,(CIAA_PRA).l                ; 7633A
        bne.w   sub_762CE                       ; 76342
        clr.w   $200c.w                         ; 76346
        clr.w   $200a.w                         ; 7634A
        bset    #$2,(CIAB_PRB).l                ; 7634E
l_76356:
        rts                                     ; 76356

LoaderEnd:
;===============================================================================
; Runs in the boot buffer
;===============================================================================
	org	$368
	dc.b	$00,$00
Start:
        move.w  #$7fff,(CUSTOM+INTENA).l        ; 0036A
        lea.l   Loader_Stored(pc),a0            ; 00372
        move.w  #(LoaderEnd-Loader)/4-1,d0      ; 00376
        movea.l #Loader,a1                      ; 0037A
l_00380:
        move.l  (a0)+,(a1)+                     ; 00380
        dbra    d0,l_00380                      ; 00382
        jmp     (Loader).l                      ; 00386
	dcb.b	116,$00
