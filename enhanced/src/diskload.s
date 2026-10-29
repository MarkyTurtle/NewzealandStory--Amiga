;==============================================================================
; diskload.s - the game's disk reading on the AmigaDOS disk: replaces the original's TrackWrite
; ($A04) and TrackRead ($C24) in block 1 of nzs_game.s (included there).
;
; The game reads the original disk's tracks by number - at the start of each level 5 tracks of
; packed level data and 1 more, on some levels 2 more, and 5 at the end - through the jump table
; entry JT_TrackRead ($40C): d0.w = track, d1.w = count, a0 = where, d2.w = drive (the game
; always asks for DF0). On the new disk each of those loads is a file holding just the bytes the
; game uses (build_disk.py: level_files), found through LoadTable and read with the
; 4489_byteloader from the drive booted from (BootDrive, in the game's header, set while
; booting), through the MFM buffer at $68000 where the original read its tracks.
;
; Each file is first looked for in the file cache (FileGet, enhanced.s), and a file read from
; the disk is offered to it (FilePut): on a machine with memory beyond the original's 512K of
; chip RAM a level read once is not read again.
;
; As the original: d0 = 0 when it worked, negative when not (also stored at $420.w and $3186,
; as the original's error exit did), the motor left off. The byteloader leaves the interrupts,
; CIA timers, blitter and copper alone, so the game's music and display go on while it loads;
; every register is kept (the interrupt handlers load a6 themselves anyway).
;==============================================================================

TRACK_BYTES     equ     11*512
TL_MFM_BUF      equ     $68000                  ; where the original's TrackRead read (to $6B32C)

TrackWrite:                                     ; writing the disk is not supported (only the
        moveq   #-1,d0                          ; debug monitor's W command wrote)
        rts

; the 4489_byteloader (byteloader.i): d0 = offset on the disk, d1 = length, d2 = drive,
; a0 = destination, a1 = MFM buffer -> d0 = 0 if it worked; uses every register
	cnop	0,4
TL_ByteLoader:
	include	"byteloader.i"

;------------------------------------------------------------------------------
; TrackRead - d0.w = the original disk's track, d1.w = tracks, a0 = destination,
; (d2 = drive: ignored, the drive booted from is used) -> d0.l = 0 if read, -1 if not.
; Each load the game makes is a file on this disk (LoadTable: its first track and count, its
; offset and length): from the file cache (FileGet) or the disk (then offered to the cache:
; FilePut), the rest of the d1 x 5,632 bytes the original read filled with zeros. A load
; the disk has no file for gives -1.
TrackRead:
        bsr.w   ScrLeave                        ; (the disk buffer is in the scroller's buffers)
        movem.l d1-d7/a0-a6,-(a7)
        lea     LoadTable(pc),a1
        moveq   #0,d3                           ; the file
.find:          cmp.b   #$ff,(a1)
        beq.b   .error                          ; a load the disk has no file for
        cmp.b   (a1),d0
        bne.b   .next
        cmp.b   1(a1),d1
        beq.b   .found
.next:          addq.l  #8,a1
        addq.w  #1,d3
        bra.b   .find
.found:         move.l  2(a1),d5                ; its offset on the disk
        moveq   #0,d6
        move.w  6(a1),d6                        ; its length
        bsr.w   FileGet                         ; d7 = 0: it was in the cache (now at a0)
        tst.l   d7
        beq.b   .fill
        movem.l d3/d6/a0,-(a7)
        move.l  d5,d0
        move.l  d6,d1
        move.l  BootDrive(pc),d2
        lea     TL_MFM_BUF,a1
        bsr.w   TL_ByteLoader
        movem.l (a7)+,d3/d6/a0
        tst.l   d0
        bne.b   .error                          ; (not read)
        bsr.w   FilePut                         ; kept, if the cache has room
.fill:          move.w  2(a7),d1                ; the rest of the tracks asked for
        mulu    #TRACK_BYTES,d1
        sub.l   d6,d1
        bls.b   .done
        lea     (a0,d6.l),a1
.zero:          clr.b   (a1)+
        subq.l  #1,d1
        bne.b   .zero
.done:          moveq   #0,d0
        bra.b   .out
.error:         moveq   #-1,d0
        move.w  d0,(dat_00420).l                ; (as the original's error exit)
        move.l  d0,(dat_03186).l
.out:           movem.l (a7)+,d1-d7/a0-a6
        rts

; LoadTable (enhanced/build/loadtable.i, written by build_disk.py: level_files)
	include	"loadtable.i"
	even
