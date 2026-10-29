"""nzs_main.s: the main program, as unpacked to $400 by the track 90 loader.

The bra.w at $400 goes to Relocate ($3218), which copies the first block (file $404-$3213)
down 4 bytes to $400 and jumps to $400. So block 1 runs at $400-$320F; everything from
$3214 runs where it loads. All addresses here are run addresses.
"""
NAME = 'main'
BINARY = 'bin/main.bin'
SEGMENTS = [
    (0x0004, 0x2E14, 0x00400),       # block 1: stored at $404, runs at $400
    (0x2E14, 0x52BA7, 0x03214),      # the rest: runs where it loads
]

ENTRIES = [
    0x3218,                                   # Relocate
    0x400, 0x404, 0x408, 0x40C, 0x410, 0x414, # jump table at the start of block 1
    0x4000,                                   # the game (default for the monitor's G command)
]

COVERAGE = "main_coverage.txt"   # addresses seen executing (tools/nzsemu): traced from

SWEEP = True            # look for unreferenced code after each rts/bra/jmp (marked in the source)
SWEEP_LIMIT = 0xF340    # code ends before the sound samples

CODE_FIELDS = [0x18]    # object slot fields that hold code pointers: move.l #handler,$18(aN)

NORETURN_TRAPS = [14]   # trap #14: error trap, followed by its message (handler $1CDA in the monitor)

PTRTABLES = {           # tables of dc.l code pointers: address -> count
    0x6D2: 19,          # monitor commands, one per letter at $6BE
    0x1D3A: 16,         # monitor disassembler: by an opcode's top nibble
    0x26EE: 8,          # monitor disassembler: by effective-address mode
    0x27BC: 8,          # monitor disassembler: by size/mode
    0x7630: 9,
}

SELFREL_TABLES = {      # tables of dc.w target-* (each entry an offset from itself): address -> count
    0xEBAE: 32,         # sound driver: sequence commands $80-$9F
}

PROLOGUE = r'''
; The New Zealand Story (Ocean 1989, Amiga conversion by Choice Software:
; code C. Gordon, graphics S. Connor) - main program
;
; Packed on tracks 94-143; the track 90 loader unpacks it to $400 and jumps to $400.
; Assemble: vasmm68k_mot -Fbin -m68000 -no-opt -o main.bin nzs_main.s
;
; Block 1 is stored 4 bytes above where it runs: the bra.w below goes to Relocate, which
; moves it down to $400. It has its own org so its labels carry the run addresses while vasm
; writes the bytes contiguously.

	include	"nzs_hw.i"
	include	"nzs_equates.i"

	section	main,code
	org	$400
	bra.w	Relocate			; file $0000
Block1_Stored:					; block 1 as loaded (file $0004)
'''

SEGMENT_TEXT = [
    ';' + '=' * 79 + '\n; Block 1: stored at $404, runs at $400-$320F after Relocate\n;' + '=' * 79
    + '\n\torg\t$400\nBlock1:',
    'Block1_End:\n;' + '=' * 79 + '\n; Runs where it is loaded ($3214 onwards)\n;' + '=' * 79 + '\n\torg\t$3214',
]

OPERANDS = {
    0x3220: 'Block1_Stored(pc),a0',
    0x3224: '#(Block1_End-Block1)/4-1,d0',
    0x3228: '#Block1,a1',
    0x3234: '(Block1).w',
}

NAMES = {
    0x3218: 'Relocate',
    0x400: 'JT_Init', 0x404: 'JT_KeyTest', 0x408: 'JT_ReadJoystick', 0x40C: 'JT_TrackRead',
    0x410: 'JT_TrackWrite', 0x414: 'JT_GetKey',
    0x55A: 'Init',
    0x6BE: 'MonitorCommandKeys',
    0x6D2: 'MonitorCommandTable',
    0x1D3A: 'DisasmOpcodeTable',
    0x15B0: 'mon_GoAddress',
    0x4000: 'GameStart',
    0xA04: 'TrackWrite',
    0xC24: 'TrackRead',
    0x2A6C: 'ReadJoystick',
    0x2AAA: 'GetKey',
    0x2B06: 'KeyTest',
    0x30BA: 'trk_Count',
    0x30F6: 'trk_CurrentTrack',
    0x3102: 'trk_Drive',
    0x3104: 'trk_Buffer',
    0xBDD8: 'Level3_VBL',
    0xBE8A: 'Level6_CIAB',
    0x12D8: 'Level2_Ports',
    0x1CB0: 'UnusedInterrupt',
    0x1CDA: 'ErrorTrap',
    0x55BA: 'LoadTracks',
    0x55F0: 'DiskErrorText',
    0x564A: 'LoadedLevel',
    0x564C: 'UnpackLevel',
    0x5DBA: 'LevelTable',
    0x418C: 'ExtraTracks',
    # graphics
    0x4E92: 'DeinterleaveBobs',
    0xB6C4: 'BlitBob',
    0xBEFE: 'SetPalette',
    0xC1AA: 'GamePalette',
    0xC2BA: 'CopperList',
    0x22AA6: 'BobData',
    0x39AA6: 'BobDirectory',
    # sound effects (channel 3) and the music driver
    0x5692: 'StopSample',
    0x56A8: 'PlaySample',
    0x5778: 'Level4_Sample',
    0xBDC0: 'PlaySong',
    0xBDCC: 'StopSong',
    0xE800: 'Music_Init',
    0xE804: 'Music_Stop',
    0xE808: 'Music_Start',
    0xE80C: 'Music_Play',
    0xE810: 'Music_Voices',
    0xE826: 'Music_Trigger',
    0xE828: 'Music_Voice0',
    0xE87E: 'Music_Voice1',
    0xE8D4: 'Music_Voice2',
    0xEA1C: 'Music_StartLow',
    0xEA3E: 'Music_StartSong',
    0xEB02: 'Music_Frame',
    0xEB78: 'Music_Voice',
    0xEFBC: 'Music_Output',
    0xF10E: 'Music_InitInstruments',
    0xF36E: 'Music_Periods',
    0xF39E: 'Music_Instruments',
    0xF406: 'Music_SampleList',
    0x15794: 'Music_Arpeggios',
    0x157A2: 'Music_Envelopes',
    0x157D0: 'Music_Songs',
    0x15830: 'Music_Patterns',
}
LABELS = []
COMMENTS = {
    0x4132: 'already loaded?',
    0x4140: "the level's single track (LevelTable +$E)",
    0x4144: "the level's packed data: 5 tracks from LevelTable +$C",
    0x414C: 'to $3CAA6',
    0x415A: 'unpack it in place',
    0x4166: 'the single track to $44AA6',
    0x4192: 'on some levels: 2 more tracks (152-159) to $6C000',
    0x43FE: 'track 144: 5 tracks (the progress screen)',
    0x55BA: 'd0 = track, d1 = tracks, a0 = where, d2 = drive (always DF0): 5 tries',
    0x55CC: 'the track reader (TrackRead)',
    0x55EC: 'a fatal disk error: hangs (the text asks for DEL)',
}
HEADERS = {
    0x55BA: '''LoadTracks - read tracks of the disk through the jump table's TrackRead, 5 tries; then the
"fatal disk error" screen. Called at the start of each level (5 tracks of packed level data,
1 more track, and on some levels 2 more) and for the progress screen between levels (track 144). On the
AmigaDOS disk, TrackRead is replaced by enhanced/src/diskload.s.''',
    0x56A8: '''PlaySample - play a sound effect: a0 = an IFF 8SVX file (FORM). Finds VHDR and BODY,
period = 3579546 / samples per second, and plays it on channel 3; the level 4 interrupt
(Level4_Sample) sets the repeat. The effects are IFF 8SVX files saved with Audio Master
(tools/assets/sound.py extracts them).''',
    0xBDC0: '''PlaySong - d0 = song 1-12 (Music_Start). 1 the level start, 2 the main tune, 6 game over,
9 a life lost, 12 an extra life (EXTEND), 10 the cheat; the others timed tunes and jingles
(docs/SOUND.md).''',
    0xE800: '''Jonathan Dunn's music driver: a jump table - init, stop, start song d0 (1-12), play one
frame (called from the vertical blank). Three voices on channels 0-2, their records $56
bytes each (Music_Voice0-2). The data format is in tools/assets/sound.py and docs/SOUND.md.''',
    0xEFBC: '''Music_Output - write the three voices to Paula: the voices that start a note this frame
(Music_Trigger) are stopped, given a period of 1 so their DMA ends at once, then waited for
(their audio interrupt bits) and 3 lines more; then each voice's volume, period and sample
(the start for a new note, the repeat otherwise) and the DMA switched on again.''',
    0x4E92: '''DeinterleaveBobs - rearrange each BOB frame in place from the stored form (per line, per
16-pixel column: mask, planes 0-3) into mask + 4 separate planes (docs/GRAPHICS.md).''',
    0x5DBA: '''LevelTable - 20 levels, 16 bytes each (indexed by $8(a6), level x 16): pointers, then +$C the
first of the 5 tracks of the level's packed data, +$E its single track.''',
}
EQUATES_FILE = 'nzs_equates.i'
EQUATES_HEADER = '''
; The New Zealand Story - memory map equates for nzs_main.s
; Generated by tools/disasm/make.py from tools/disasm/main_cfg.py: edit the config, not this file.
'''
MEM_AUTO = (0x52FA7, 0x80000)   # absolute references in this range get mem_XXXXX names
MEM = {
    0x70000: 'LoadScreenData',   # loading screen file as loaded by track 90 (also reused)
    0x78000: 'Screen78000',
}
MEM_NOTES = {}
