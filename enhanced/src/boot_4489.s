;==============================================================================
; boot_4489.s - The New Zealand Story: the bootblock of the AmigaDOS-format disk
; (enhanced/tools/build_disk.py). An ordinary 880K disk - 11 sectors a track, $4489 sync, no
; copy protection - with no filesystem ("NDOS"):
;
;   $000-$3FF   this bootblock
;   $400-$5FF   the file table (FT_OFFSET): 'NZSF', version.w, count.w, 8 bytes free, then
;               per file (file id = index) its offset on the disk and its length, longs
;   $600-       the files, one after another (build_disk.py): the loading screen, the program
;               (packed), and the original disk's tracks that the game reads at each level
;
; Every load goes through the 4489_byteloader (byteloader.i): any number of bytes from any
; offset, a track at a time into an MFM buffer of $1760 words, checksums checked.
;
; It replaces the original's whole boot chain - the bootblock, Rob Northen's protection loader
; and Copylock check on tracks 0-1, the second-stage bootblock, and the track 90 game loader
; with its own Copylock check (see original/docs/BOOT.md) - and leaves the machine as the track
; 90 loader did when it entered the game:
;   1. find the drive booted from (while Kickstart is intact; a6 = ExecBase, a1 = the boot
;      IORequest): open trackdisk.device's units 3..0 until one is the boot IORequest's unit
;      (DF0 if none is). Kickstart 1.3 boots only from DF0; 2.0 and later from any drive
;   2. take over: interrupts and DMA off, supervisor mode, stack in free memory
;   3. copy the loader to LOADER and run it there
;   4. the loading screen as the track 90 loader showed it: 320 x 200, 4 planes at $78000
;      ($2000 apart), decoded from the file loaded to $70000 (byte-run, 16 colours at half
;      value); the same display window, fetch, copper list and DMA
;   5. the program (file 0, packed as the original's tracks 94-143) to $400, unpacked in place
;      as the track 90 loader unpacked it; the drive booted from written into the game's
;      BootDrive (diskload.s: the game reads its level tracks from that drive too); then
;      enter it at $400 with d0 = a0 = $400, as the track 90 loader did
; A load that fails is tried again; after 8 failures COLOR00 turns red while it goes on
; trying (a disk error: the drive or the disk).
;
; Memory while loading: the program $400-$52FA6, the loader's buffers $60000-$63FFF, the screen
; file $70000-$7420F, the screen $78000-$7FF3F.
;==============================================================================

PROGRAM         equ     $400
MFM_BUF         equ     $60000                  ; $1760 words, to $62EC0
FILE_TABLE      equ     $63000                  ; the file table read from the disk
BOOT_DRIVE      equ     $630FC                  ; the drive booted from (long)
LOADER          equ     $63100                  ; the loader runs here
STACK           equ     $64000                  ; (falls towards the loader: plenty of room)
SCREEN_FILE     equ     $70000                  ; where the track 90 loader read it
SCREEN          equ     $78000                  ; 4 planes, $2000 apart
FID_MAIN        equ     0                       ; (build_disk.py's file ids)
FID_SCREEN      equ     1
FT_OFFSET       equ     $400                    ; the file table on the disk
GAME_BOOTDRIVE  equ     $A08+4                  ; the game's BootDrive (diskload.s): $A08 once
                                                ; Relocate has moved block 1 down 4 bytes
FT_ENTRIES      equ     16

CUSTOM          equ     $DFF000

	org	0
	dc.b	'DOS',0
	dc.l	0                               ; checksum (build_disk.py)
	dc.l	880                             ; root block (no filesystem: NDOS)

;------------------------------------------------------------------------------
; Kickstart calls here with a6 = ExecBase and a1 = the boot IORequest (trackdisk.device, the
; unit booted from).
BootEntry:
        movem.l $14(a1),a4-a5                   ; IO_DEVICE, IO_UNIT: the boot drive's unit
; the drive booted from: trackdisk.device's units 3 .. 0 opened in turn (an IORequest on the
; stack) until one is the boot IORequest's unit (DF0 if none is). Never closed: the machine is
; taken over next.
        movea.l $a(a4),a4                       ; the device's name (ln_Name)
        lea     -$30(a7),a7
        movea.l a7,a3
        moveq   #3,d7
.unit:          movea.l a4,a0
        movea.l a3,a1
        move.l  d7,d0
        moveq   #0,d1
        jsr     -$1bc(a6)                       ; OpenDevice
        tst.b   d0
        bne.b   .next
        cmpa.l  $18(a3),a5                      ; IO_UNIT: the one booted from?
        beq.b   .found
.next:          dbra    d7,.unit
        moveq   #0,d7
.found:         move.l  d7,BOOT_DRIVE
        lea     CUSTOM,a0
        move.w  #$7fff,$9a(a0)                  ; INTENA: all off
        move.w  #$7fff,$96(a0)                  ; DMACON: all off
        move.w  #$7fff,$9c(a0)                  ; INTREQ: none pending
        lea     .super(pc),a1                   ; privilege violation -> the next instruction
        move.l  a1,$20.w
.super:         move.w  #$2700,sr               ; supervisor (or a trap that lands here), no interrupts
        lea     STACK,a7
        lea     Loader(pc),a1                   ; the loader, up out of the way
        lea     LOADER,a2
        movea.l a2,a3
        move.w  #(LoaderEnd-Loader)/4,d0
.copy:          move.l  (a1)+,(a2)+
        dbra    d0,.copy
        jmp     (a3)

;------------------------------------------------------------------------------
; The loader, run at LOADER. a0 = CUSTOM.
	cnop	0,4
Loader:
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
; the file table, then the loading screen
        move.l  #FT_OFFSET,d0
        move.l  #FT_ENTRIES*8+16,d1
        lea     FILE_TABLE,a0
        bsr.w   LoadIt
        lea     FILE_TABLE+16+FID_SCREEN*8,a2
        movem.l (a2),d0-d1
        lea     SCREEN_FILE,a0
        bsr.w   LoadIt
        bsr.w   Decode
        lea     SCREEN_FILE+2,a1                ; its 16 colours, at half value
        lea     CUSTOM+$180,a2
        moveq   #15,d0
.pal:           move.w  (a1)+,d1
        add.w   d1,d1
        move.w  d1,(a2)+
        dbra    d0,.pal
; the program
        lea     FILE_TABLE+16+FID_MAIN*8,a2
        movem.l (a2),d0-d1
        lea     PROGRAM,a0
        bsr.w   LoadIt
        lea     PROGRAM,a0
        bsr.w   Unpack
        move.l  BOOT_DRIVE,GAME_BOOTDRIVE
        move.l  #PROGRAM,d0                     ; as the track 90 loader left them
        movea.l d0,a0
        jmp     (a0)

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

; LoadIt - d0 = offset, d1 = length, a0 = destination: the byteloader, tried until it works
LoadIt:         moveq   #0,d6                   ; failures
.try:           movem.l d0-d1/d6/a0,-(a7)
        move.l  BOOT_DRIVE,d2                   ; the drive booted from
        lea     MFM_BUF,a1
        bsr.w   ByteLoader
        move.l  d0,d7
        movem.l (a7)+,d0-d1/d6/a0
        tst.l   d7
        beq.b   .ok
        addq.w  #1,d6                           ; after 8 failures: red while trying
        cmp.w   #8,d6
        bcs.b   .try
        move.w  #$f00,CUSTOM+$180
        bra.b   .try
.ok:            rts

; the loading screen's copper list, as the track 90 loader's ($76B68): the 4 plane pointers
Copper:         dc.w    $00E0,SCREEN>>16,$00E2,SCREEN&$FFFF
        dc.w    $00E4,SCREEN>>16,$00E6,(SCREEN+$2000)&$FFFF
        dc.w    $00E8,SCREEN>>16,$00EA,(SCREEN+$4000)&$FFFF
        dc.w    $00EC,SCREEN>>16,$00EE,(SCREEN+$6000)&$FFFF
        dc.w    $FFFF,$FFFE

; the 4489_byteloader (byteloader.i): d0 = offset on the disk, d1 = length, d2 = drive,
; a0 = destination, a1 = MFM buffer -> d0 = 0 if it worked; uses every register
	cnop	0,4
ByteLoader:
	include "byteloader.i"
	cnop	0,4
LoaderEnd:                                      ; (the loader copied to LOADER ends here)

	ifgt	*-1024
	fail	the bootblock is over 1024 bytes
	endc
	ifgt	LOADER+LoaderEnd-Loader-(STACK-$100)
	fail	the loader runs into its stack
	endc
	ifgt	BOOT_DRIVE+4-LOADER
	fail	BOOT_DRIVE overlaps the loader
	endc
	dcb.b	1024-*,0
