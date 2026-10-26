;==============================================================================
; diskload.s - the game's disk reading on the AmigaDOS disk: replaces the original's TrackWrite
; ($A04) and TrackRead ($C24) in block 1 of nzs_game.s (included there).
;
; The game reads the original disk's tracks by number - at the start of each level 5 tracks of
; packed level data and 1 more, on some levels 2 more, and 5 at the end - through the jump table
; entry JT_TrackRead ($40C): d0.w = track, d1.w = count, a0 = where, d2.w = drive (the game
; always asks for DF0). On the new disk those tracks are stored one after another from
; TRACKS_OFFSET (only the ones the game reads), and TrackMap gives each original track's place
; there; TrackRead reads them with the 4489_byteloader from the drive booted from (BootDrive,
; in the game's header, set while booting), into the MFM buffer at $68000 where the original
; read its tracks.
;
; Each track is first looked for in the track cache (CacheGet, enhanced.s), and a track read
; from the disk is offered to it (CachePut): on a machine with memory beyond the original's 512K
; of chip RAM a level read once is not read again.
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
; (d2 = drive: ignored, the drive booted from is used) -> d0.l = 0 if read, -1 if not
TrackRead:
        bsr.w   ScrLeave                        ; (the disk buffer is in the scroller's buffers)
        movem.l d1-d7/a0-a6,-(a7)
        andi.l  #$ffff,d0
        subq.w  #1,d1
        bmi.b   .done
.track:         lea     TrackMap(pc),a1
        moveq   #0,d3
        move.b  (a1,d0.w),d3                    ; its place among the stored tracks
        cmp.b   #$ff,d3
        beq.b   .error                          ; a track the disk does not have
        movem.l d0-d1/a0,-(a7)
        bsr.w   CacheGet                        ; d7 = 0: it was in the cache (now at a0)
        tst.l   d7
        beq.b   .got
        mulu    #TRACK_BYTES,d3
        add.l   #TRACKS_OFFSET,d3
        move.l  d3,d0
        move.l  #TRACK_BYTES,d1
        move.l  BootDrive(pc),d2
        lea     TL_MFM_BUF,a1
        bsr.w   TL_ByteLoader
        move.l  d0,d7
        bne.b   .got                            ; (not read)
        movem.l (a7),d0-d1/a0
        bsr.w   CachePut                        ; kept, if the cache has room
        moveq   #0,d7
.got:           movem.l (a7)+,d0-d1/a0
        tst.l   d7
        bne.b   .error
        addq.w  #1,d0
        lea     TRACK_BYTES(a0),a0
        dbra    d1,.track
.done:          moveq   #0,d0
        bra.b   .out
.error:         moveq   #-1,d0
        move.w  d0,(dat_00420).l                ; (as the original's error exit)
        move.l  d0,(dat_03186).l
.out:           movem.l (a7)+,d1-d7/a0-a6
        rts

; TrackMap: for each of the original disk's 160 tracks, its place among the tracks stored from
; TRACKS_OFFSET, or $FF if the disk does not have it (enhanced/build/trackmap.i, written by
; build_disk.py)
TrackMap:
	include	"trackmap.i"
	even

