;==============================================================================
; ext.i - the enhanced game's extension module (src/ext.s): where it lives, its entry points
; and the machine description. Included by the bootblock (boot_4489.s), the game's disk
; reading (diskload.s, so by the game) and the module itself.
;
; The module is a file of its own (FID_EXT), loaded by the bootblock to EXT_BASE: memory that the
; original game never touches, between its object slots (which end at $65396) and the disk /
; deinterleave buffer at $68000 (no absolute reference into it in original/nzs_main.s, and no
; write to it in tools/nzsemu over 12 games and all 20 levels started in turn).
;==============================================================================

EXT_BASE        equ     $65400
EXT_LIMIT       equ     $68000                  ; the module must end below this

; the module's header (at EXT_BASE)
EXT_MAGIC       equ     0                       ; 'NZSX'
EXT_VERSION     equ     4                       ; .w
EXT_BOOT        equ     8                       ; jmp: the rest of the boot (from the bootblock)
EXT_TITLETEXT   equ     14                      ; jmp: the title's text (the game, $404C)
EXT_CACHEGET    equ     20                      ; jmp: a track from the cache (TrackRead)
EXT_CACHEPUT    equ     26                      ; jmp: a track into the cache (TrackRead)
EXT_MACHINE     equ     32                      ; the machine description (MI_SIZE bytes)

; the machine description: written by the bootblock (MemDetect) while Kickstart is still
; running, from exec's memory list; copied into the module's header (EXT_MACHINE). The layout
; of the Ghosts'n Goblins enhanced game's MACHINE_INFO, with its own magic.
MI_MAGIC        equ     0                       ; 'NZSM'
MI_VERSION      equ     4                       ; .b (1)
MI_VBLANK       equ     5                       ; .b exec's VBlankFrequency (50 PAL, 60 NTSC)
MI_ATTN         equ     6                       ; .w exec's AttnFlags (CPU / FPU)
MI_CHIP         equ     8                       ; .l lower, .l upper: chip RAM (the last region exec lists)
MI_SLOW         equ     16                      ; .l lower, .l upper: slow RAM ($C00000-$DBFFFF), 0 = none
MI_FAST         equ     24                      ; .l lower, .l upper: fast RAM (any other), 0 = none
MI_DRIVE        equ     32                      ; .l the drive booted from (0-3)
MI_SIZE         equ     36
