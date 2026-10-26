;==============================================================================
; ext.i - the boot's extension module (src/ext.s): where it lives, its entry point, the
; machine description and where the game keeps it. Included by the bootblock (boot_4489.s),
; the module and the game (nzs_game.s).
;
; The module is a file of its own (FID_EXT), loaded by the bootblock to EXT_BASE, which does the
; part of the boot the bootblock has no room for. It is needed only while booting: the game
; uses that memory afterwards (the scroller's buffers).
;==============================================================================

EXT_BASE        equ     $65400
EXT_LIMIT       equ     $68000                  ; the module must end below this

; the module's header (at EXT_BASE)
EXT_MAGIC       equ     0                       ; 'NZSX'
EXT_VERSION     equ     4                       ; .w
EXT_BOOT        equ     8                       ; jmp: the rest of the boot (from the bootblock)

; the game's header (nzs_game.s: EnhHeader), where the module leaves the machine description and
; the boot drive for the game: a run address (block 1 is stored 4 bytes higher until Relocate)
GAME_HEADER     equ     $426                    ; 'NZSE'
GAME_BOOTDRIVE  equ     GAME_HEADER+4           ; .l
GAME_MACHINE    equ     GAME_HEADER+8           ; MI_SIZE bytes

; the machine description: written by the bootblock (MemDetect) while Kickstart is still
; running, from exec's memory list; copied into the game's header (GAME_MACHINE). The layout
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
