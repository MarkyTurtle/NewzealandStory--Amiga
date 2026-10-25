;==============================================================================
; diskload.s - the game's disk reading on the AmigaDOS disk: replaces TrackWrite ($A04) and
; TrackRead ($C24) of the original (block 1), in exactly their space ($A04-$D87), so that
; nothing else in the program moves. Included in place of those two routines by
; enhanced/tools/make_game.py when it makes the enhanced game's source from original/nzs_main.s.
;
; The game reads the original disk's tracks by number - at the start of each level 5 tracks of
; packed level data and 1 more, on some levels 2 more, and 5 at the end - through the jump table
; entry JT_TrackRead ($40C): d0.w = track, d1.w = count, a0 = where, d2.w = drive (the game
; always asks for DF0). On the new disk those tracks are stored one after another from
; TRACKS_OFFSET (only the ones the game reads), and TrackMap gives each original track's place
; there; TrackRead reads them with the 4489_byteloader from the drive booted from (BootDrive,
; set by the bootblock), into the MFM buffer at $68000 where the original read its tracks.
;
; As the original: d0 = 0 when it worked, negative when not (also stored at $420.w and $3186,
; as the original's error exit did), the motor left off. The byteloader leaves the interrupts,
; CIA timers, blitter and copper alone, so the game's music and display go on while it loads;
; every register is kept (the interrupt handlers load a6 themselves anyway).
;==============================================================================

TRACK_BYTES     equ     11*512
TL_MFM_BUF      equ     $68000                  ; where the original's TrackRead read (to $6B32C)

TrackWrite:                                     ; $A04: writing the disk is not supported (the
        moveq   #-1,d0                          ; monitor's W command)
        rts
BootDrive:      dc.l    0                       ; $A08: the drive booted from (the bootblock)

; the 4489_byteloader (byteloader.i): d0 = offset on the disk, d1 = length, d2 = drive,
; a0 = destination, a1 = MFM buffer -> d0 = 0 if it worked; uses every register
	cnop	0,4
TL_ByteLoader:
	include	"byteloader.i"

	ifgt	*-$C24
	fail	diskload.s: the byteloader runs into TrackRead ($C24)
	endc
	dcb.b	$C24-*,0

;------------------------------------------------------------------------------
; TrackRead ($C24) - d0.w = the original disk's track, d1.w = tracks, a0 = destination,
; (d2 = drive: ignored, the drive booted from is used) -> d0.l = 0 if read, -1 if not
TrackRead:
        movem.l d1-d7/a0-a6,-(a7)
        andi.l  #$ffff,d0
        subq.w  #1,d1
        bmi.b   .done
.track:         lea     TrackMap(pc),a1
        moveq   #0,d3
        move.b  (a1,d0.w),d3                    ; its place among the stored tracks
        cmp.b   #$ff,d3
        beq.b   .error                          ; a track the disk does not have
        mulu    #TRACK_BYTES,d3
        add.l   #TRACKS_OFFSET,d3
        movem.l d0-d1/a0,-(a7)
        move.l  d3,d0
        move.l  #TRACK_BYTES,d1
        move.l  BootDrive(pc),d2
        lea     TL_MFM_BUF,a1
        bsr.w   TL_ByteLoader
        move.l  d0,d7
        movem.l (a7)+,d0-d1/a0
        tst.l   d7
        bne.b   .error
        addq.w  #1,d0
        lea     TRACK_BYTES(a0),a0
        dbra    d1,.track
.done:          moveq   #0,d0
        bra.b   .out
.error:         moveq   #-1,d0
        move.w  d0,($420).w                     ; (as the original's error exit)
        move.l  d0,($3186).w
.out:           movem.l (a7)+,d1-d7/a0-a6
        rts

; TrackMap: for each of the original disk's 160 tracks, its place among the tracks stored from
; TRACKS_OFFSET, or $FF if the disk does not have it (enhanced/build/trackmap.i, written by
; build_disk.py)
TrackMap:
	include	"trackmap.i"

	ifgt	*-$D88
	fail	diskload.s: TrackRead runs past the end of the original's ($D88)
	endc
	dcb.b	$D88-*,0

	ifne	BootDrive-$A08
	fail	diskload.s: BootDrive must be at $A08 (the bootblock writes it there)
	endc
