"""nzs_loader.s: the game loader on track 90.

Loaded to $400 by the second-stage bootblock's trackloader. The bra.w at $400 goes to the
copier at $F92, which moves file $404-$F8F to $76000 and jumps there; so most of the loader
runs at $76000 + (file offset - 4).
"""
NAME = 'loader'
BINARY = 'disk/files/t090_game_loader.bin'
SEGMENTS = [
    (0x000, 0x004, 0x00400),        # bra.w to the copier
    (0x004, 0xB90, 0x76000),        # $2E3 longs copied to $76000 and run there
    (0xB90, 0x1600, 0x00F90),       # copier, then unused to the end of the track
]
ENTRIES = [0x400,
           0x76148, 0x76166,      # the protection's clear-text start (illegal / MOVEC CACR handlers)
           0x761FA, 0x76234,      # its enter (ILLEGAL) and trace handlers
           0x76440, 0x7664E,      # the parts that run untraced: the long-track timing, the exit
           0x76668]               # LoadAndRunGame (the privilege-violation vector)

PROLOGUE = r'''
; The New Zealand Story (Ocean 1989, Amiga conversion by Choice Software)
; Game loader: track 90, loaded to $400 and entered there.
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o loader.bin nzs_loader.s
;
; The bytes are written contiguously (5632 bytes, one track), but the block from file offset 4
; runs at $76000: each part has its own org inside one section, so its labels carry the address
; it runs at while vasm writes the bytes with no gaps.

	include	"nzs_hw.i"

	section	loader,code
'''

SEGMENT_TEXT = [
    '\torg\t$400\t\t\t\t; file $0000: loaded here',
    ';' + '=' * 79 + '\n; Runs at $76000 (file offset $0004-$0B8F, copied by Start)\n;' + '=' * 79 + '\n\torg\t$76000\nLoaderCode:',
    ';' + '=' * 79 + '\n; Runs where it is loaded: file offset $0B90 onwards at $F90\n;' + '=' * 79 + '\n\torg\t$F90',
]

NAMES = {
    0x400: 'LoaderEntry',
    0xF92: 'Start',
    0x76000: 'LoaderMain',
    0x7600C: 'Supervisor',
    0x760AE: 'SavedRegs',
    0x76124: 'Protection',
    0x76148: 'Prot_Illegal1',
    0x76668: 'LoadAndRunGame',
    0x76166: 'Prot_NoCacr',
    0x761FA: 'TVD_Enter',
    0x76234: 'TVD_Trace',
    0x76440: 'Prot_TimeLongTrack',
    0x7664E: 'Prot_Exit',
    0x764AC: 'CopylockSyncs',
    0x76118: 'tvd_Last',
    0x76698: 'ReadTracksOrReset',
    0x766AC: 'DecodeLoadScreen',
    0x766EA: 'PutScreenByte',
    0x7671E: 'Unpack',
    0x76764: 'MotorOnWaitReady',
    0x76798: 'MotorOff',
    0x767C4: 'ReadTracks',
    0x769D2: 'SeekTrack0',
    0x769DC: 'SeekTrack',
    0x76A92: 'HardwareOn',
    0x76ACE: 'HardwareInit',
    0x76B68: 'LoadScreenCopper',
}
LABELS = []
COMMENTS = {
    0x76000: 'privilege violation -> Supervisor',
    0x76008: '(in user mode: privilege violation)',
    0x7600C: 'stack, then the variables (a6)',
    0x76018: 'interrupts and DMA off, the display set up, black',
    0x7601C: 'motor off, DF1 then DF0',
    0x7602E: '3 tracks from track 91: the loading screen',
    0x76046: 'decode it to $78000',
    0x7604A: 'its colours, stored at half value',
    0x76064: 'the protection (Copylock): ends in LoadAndRunGame',
    0x76124: 'save the registers, ILLEGAL -> Prot_Illegal1 (see nzs_loader_tvd.lst)',
    0x76668: 'the Copylock key in d0: key - $F974D77D = $400 (key $F974DB7D)',
    0x76672: '50 tracks from track 94: the packed main program',
    0x76688: 'unpack it in place',
    0x76696: 'enter the game at $400',
    0x766A6: 'a read that fails resets the machine (Kickstart)',
}
HEADERS = {
    0x76124: '''Protection - Rob Northen Copylock, as on track 0.
From $76148 the code is trace-vector encrypted: each instruction is decrypted by the trace
handler ($76234) just before it runs, and re-encrypted after. tools/disasm/tvd.py decrypts it to
nzs_loader_tvd.lst: it reads the Copylock track (track 1) with its 11 sync words ($764AC),
times the long track, checks the "Rob Northen Comp" signature and derives the key from the
track. It ends with a privilege violation into LoadAndRunGame with the key in d0.''',
    0x76668: '''LoadAndRunGame - the key in d0 gives the load address (key - $F974D77D): with the right key,
$400. Reads the packed main program, unpacks it there and jumps to it.''',
}
