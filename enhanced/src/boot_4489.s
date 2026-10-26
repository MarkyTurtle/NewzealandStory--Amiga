;==============================================================================
; boot_4489.s - The New Zealand Story: the bootblock of the AmigaDOS-format disk
; (enhanced/tools/build_disk.py). An ordinary 880K disk - 11 sectors a track, $4489 sync, no
; copy protection - with no filesystem ("NDOS"):
;
;   $000-$3FF   this bootblock
;   $400-$5FF   the file table (FT_OFFSET): 'NZSF', version.w, count.w, 8 bytes free, then
;               per file (file id = index) its offset on the disk and its length, longs
;   $600-       the files, one after another (build_disk.py): the loading screen, the original
;               disk's tracks that the game reads at each level, the extension module and the
;               program (packed)
;
; Every load goes through the 4489_byteloader (byteloader.i): any number of bytes from any
; offset, a track at a time into an MFM buffer of $1760 words, checksums checked.
;
; With the extension module (src/ext.s) it replaces the original's whole boot chain - the
; bootblock, Rob Northen's protection loader and Copylock check on tracks 0-1, the second-stage
; bootblock, and the track 90 game loader with its own Copylock check (original/docs/BOOT.md) -
; and leaves the machine as the track 90 loader did when it entered the game:
;   1. while Kickstart is intact (a6 = ExecBase, a1 = the boot IORequest):
;      MemDetect: the machine description (ext.i: chip, slow and fast RAM from exec's memory
;      list, PAL / NTSC, the CPU), in MachineInfo, part of the loader;
;      the drive booted from: trackdisk.device's units 3..0 opened until one is the boot
;      IORequest's unit (DF0 if none is). Kickstart 1.3 boots only from DF0; 2.0 and later
;      from any drive
;   2. take over: interrupts and DMA off, supervisor mode, stack in free memory
;   3. copy the loader to LOADER and run it there
;   4. read the file table and load the extension module (FID_EXT) to EXT_BASE, then go on in
;      it (ExtBoot) with a5 = LoadIt, a1 = MachineInfo, a2 = the file table: the loading
;      screen, the program and the game's entry are done there (the bootblock has no room)
; A load that fails is tried again; after 8 failures COLOR00 turns red while it goes on
; trying (a disk error: the drive or the disk).
;
; Memory while loading: the program $400-$52FA6, the extension module $65400-, the loader's
; buffers $60000-$63FFF, the screen file $70000-$7420F, the screen $78000-$7FF3F.
;==============================================================================

	include	"ext.i"

MFM_BUF         equ     $60000                  ; $1760 words, to $62EC0
FILE_TABLE      equ     $63000                  ; the file table read from the disk
LOADER          equ     $63100                  ; the loader runs here
STACK           equ     $64000                  ; (falls towards the loader: plenty of room)
FID_EXT         equ     3                       ; (build_disk.py's file ids)
FT_OFFSET       equ     $400                    ; the file table on the disk
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
        bsr.w   MemDetect
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
.found:         lea     MachineInfo(pc),a0          ; (copied with the loader below)
        move.l  d7,MI_DRIVE(a0)
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
; MemDetect - the machine description (ext.i) into MachineInfo (in the loader, so it is copied
; with it): exec's VBlankFrequency and AttnFlags, and from exec's memory list the chip RAM, the
; slow RAM ($C00000-$DBFFFF) and the fast RAM (any other) regions, the last of each kind.
; a6 = ExecBase. (As the Ghosts'n Goblins enhanced bootblock's.)
MemDetect:      lea     MachineInfo(pc),a2
        move.l  #'NZSM',(a2)+                   ; (the rest is zero in the bootblock)
        move.b  #1,(a2)+                        ; version 1
        move.b  $212(a6),(a2)+                  ; VBlankFrequency
        move.w  $128(a6),(a2)+                  ; AttnFlags
        lea     $142(a6),a3                     ; MemList (lh_Head first)
.next:          movea.l (a3),a3
        tst.l   (a3)                            ; ln_Succ = 0: the list's tail
        beq.b   .done
        movem.l 20(a3),d0-d1                    ; mh_Lower, mh_Upper
        movea.l a2,a1                           ; the chip slot
        btst    #1,15(a3)                       ; mh_Attributes: MEMF_CHIP
        bne.b   .store
        addq.l  #8,a1                           ; the slow slot, if in $C00000-$DBFFFF
        cmp.l   #$C00000,d0
        blo.b   .fast
        cmp.l   #$DC0000,d0
        blo.b   .store
.fast:          addq.l  #8,a1                   ; the fast slot
.store:         movem.l d0-d1,(a1)              ; (the last region of each kind is kept)
        bra.b   .next
.done:          rts

;------------------------------------------------------------------------------
; The loader, run at LOADER. a0 = CUSTOM.
	cnop	0,4
Loader:
        move.l  #FT_OFFSET,d0                   ; the file table
        move.l  #FT_ENTRIES*8+16,d1
        lea     FILE_TABLE,a0
        bsr.b   LoadIt
        lea     FILE_TABLE+16+FID_EXT*8,a2      ; the extension module
        movem.l (a2),d0-d1
        lea     EXT_BASE,a0
        bsr.b   LoadIt
        lea     LoadIt(pc),a5                   ; the rest is the module's (ExtBoot)
        lea     MachineInfo(pc),a1
        lea     FILE_TABLE,a2
        lea     CUSTOM,a0
        jmp     EXT_BASE+EXT_BOOT

; LoadIt - d0 = offset, d1 = length, a0 = destination: the byteloader, tried until it works.
; (Also called by the extension module's ExtBoot.) Keeps a0-a5.
LoadIt:         moveq   #0,d6                   ; failures
.try:           movem.l d0-d1/d6/a0-a5,-(a7)
        move.l  MachineInfo+MI_DRIVE(pc),d2     ; the drive booted from
        lea     MFM_BUF,a1
        bsr.w   ByteLoader
        move.l  d0,d7
        movem.l (a7)+,d0-d1/d6/a0-a5
        tst.l   d7
        beq.b   .ok
        addq.w  #1,d6                           ; after 8 failures: red while trying
        cmp.w   #8,d6
        bcs.b   .try
        move.w  #$f00,CUSTOM+$180
        bra.b   .try
.ok:            rts

; the machine description (ext.i), written by MemDetect, copied with the loader
	cnop	0,4
MachineInfo:    dcb.b   MI_SIZE,0

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
	dcb.b	1024-*,0
