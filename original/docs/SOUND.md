# The sound

**Short answer:** the sound effects and the instruments are standard **IFF 8SVX** files,
saved with **Audio Master** and included in the program unchanged, file names and all. The
music is **not** in a tracker format (not SoundTracker/ProTracker, not SoundMon). It is
Jonathan Dunn's own driver and data format, written as a compact byte stream. Exotica's list of
Amiga music formats calls it "Special FX" (files prefixed `JD.`). It was produced with the
composer's own tools and is played by a ~3 KB driver built into the game.

Everything below is extracted by `tools/assets/make_assets.sh` into [`../assets/sound`](../assets/sound):

| | |
|---|---|
| `samples/NAME.iff` | the 18 IFF 8SVX files, byte for byte as they are in the program |
| `samples/NAME.wav` | the same, as WAV (8-bit, at the rate in their VHDR) |
| `songs.txt` | every song, order list, pattern, arpeggio and volume envelope, decoded |
| `sound.json` | the same, parsed |
| `music/songNN.ogg` | the 12 songs, rendered by running the driver itself (below) |

## The samples

The files keep their IFF headers. Each has a `VHDR`, a `NAME` chunk, an `ANNO` chunk that says
"Audio Master", and a `BODY`. The game reads them that way at run time: `PlaySample` (`$56A8`)
is given the address of the `FORM`, finds `VHDR` and `BODY` itself, and works out the period
as 3579546 / samples per second.

| Address | Name | Bytes | Rate (Hz) | Used as |
|---|---|---:|---:|---|
| `$0F42C` | VOICE-WAVE | 6732 | 10026 | instrument 1 (looped: repeat part 3076 bytes) |
| `$10E78` | PAN-MALLET | 5304 | 10026 | instrument 2 |
| `$12330` | SYNTH-BASS1 | 3904 | 10026 | instrument 3 |
| `$13270` | VIBES | 6884 | 10026 | instrument 4 |
| `$14D54` | tick | 302 | 8363 | instrument 5 (percussion) |
| `$14E82` | bong | 2322 | 8363 | instrument 6 (percussion) |
| `$16800` | kiwi_jmp | 2844 | 8363 | effect |
| `$1731C` | baddead | 3176 | 19886 | effect (7 call sites) |
| `$17F84` | kiwi_shot | 1060 | 8363 | effect |
| `$183A8` | pick_up | 7406 | 19886 | effect |
| `$1A096` | splash | 7280 | 19886 | effect |
| `$1BD06` | boom | 5778 | 8363 | effect (5 call sites) |
| `$1D398` | whackkiwi | 568 | 8363 | effect (7 call sites) |
| `$1D5D0` | spit | 3094 | 8363 | effect |
| `$1E1E6` | throwbomb | 1894 | 8363 | effect |
| `$1E94C` | laser | 1386 | 8363 | effect |
| `$1EEB6` | wand | 6080 | 8363 | effect |
| `$20676` | explosion | 4702 | 8363 | effect |

The effects play on **channel 3**. The level 4 audio interrupt (`Level4_Sample`, `$5778`)
switches the channel to its repeat once the sample has started. `StopSample` (`$5692`) stops it.
The music uses channels 0-2, so an effect never cuts into the music.

## The music driver (`$E800`-`$F36D`)

A jump table at `$E800`: `Music_Init` (+0), `Music_Stop` (+4), `Music_Start` (+8, d0 = song
1-12) and `Music_Play` (+C, one frame, called from the vertical blank at 50 Hz).
`Music_StartLow` (`$EA1C`) starts a song at the lower priority. The game calls the driver
through `PlaySong` (`$BDC0`) and `StopSong` (`$BDCC`).

Every frame, each of the three voices (records of `$56` bytes at `Music_Voice0-2`,
`$E828/$E87E/$E8D4`) advances its pattern. A voice that starts a note sets its channel's bit in
`Music_Trigger`. `Music_Output` (`$EFBC`) then stops those channels, sets their period to 1 so
their DMA finishes at once, and waits for their audio interrupt bits and 3 more lines. Then it
writes each voice's volume and period, and either the new sample (for a new note) or the
repeat part, and switches DMA back on.

### The data

| Address | What |
|---|---|
| `$F36E` | periods: 24 words (two octaves) |
| `$F39E` | instruments, 16 bytes each: base note.w, sample start.l, length in words.w, repeat start.l, repeat length.w, fixed pitch.w. Instrument 0 is a short silent loop. 1-6 are filled in by `Music_InitInstruments` (`$F10E`) from the list at `$F406` (offset.w to an IFF file, base note.w, fixed.w; 0 ends) |
| `$15794` | arpeggios (self-relative word offsets): frames per step.b, number of steps.b, a signed note offset per step |
| `$157A2` | volume envelopes (self-relative offsets): 2-byte segments. `n>0, d`: add d each frame for n frames. `n<0, b`: for -n frames, step by 1 every \|b\| frames. `0,0`: end. `0,r`: hold until the note has \|r\| frames left (the release) |
| `$157D0` | songs, 8 bytes each (12 of them): a self-relative offset to each of the 3 voices' order lists (0 = voice unused), then a word |
| `$15830` | patterns (self-relative word offsets), 35 used |

**An order list** is a byte stream. `<$80` plays that pattern; `$80` ends (and loops back to the
`$81` point if one is set); `$81` sets the loop point; `$82 nn` sets the transpose; `$83 nn`
repeats the next pattern nn times.

**A pattern** is a byte stream. `<$80` is a note: subtracting the instrument's base note gives
the index into the period table. A duration in frames follows the note, unless a fixed duration
is set. The commands are:

| | | | |
|---|---|---|---|
| `$80` end | `$81` loop point | `$84 n` fixed duration n | `$85` durations after each note again |
| `$86` wait 256 frames | `$87 [d]` rest | `$88 a,b` slide | `$89 a,b` note offset / `$8A` off |
| `$8B d,s,r` vibrato / `$8C` off | `$8D n` arpeggio n / `$8E` off | `$8F n` volume envelope n | `$90 n` instrument n |

The layout is typical of a programmer-composer's own driver: notes with durations instead of a
grid of rows, effects as commands in the stream, and tables reached by self-relative offsets so
that the block can be moved anywhere. It was assembled in as data, not loaded as a module file.

### The songs

| Song | Length | Where the game starts it |
|---|---|---|
| 1 | 9.4 s | the start of a life (`$4276`), the intro (`$4D78`) and after the timed tune 8 (`$42AC`); it leads into song 2 |
| 2 | loops | the main tune: restarted whenever no music is playing (`$4378`), and after tune 11 |
| 3 | loops | the screen drawn at `$54F0` (the high score entry) |
| 4 | loops | `$43B4` (conditions on `$46`/`$52`(a6); not yet identified) |
| 5 | loops | `$AC46`, on every level except `$F0` (the last one) |
| 6 | 3.3 s | game over (`$40D6`) |
| 7 | 3.7 s | `$AC90` (an object's routine) |
| 8 | loops | `$757C`, for 300 frames (6 s), then song 1 |
| 9 | 1.5 s | a life lost (`$97C2`, `$ADCC`) |
| 10 | 3.1 s | `$765A`, and the cheat code typed in (`$BA3E`) |
| 11 | loops | `$7666`, for 150 frames (3 s), then song 2 |
| 12 | 1.9 s | an extra life: all six EXTEND letters (`$74DA`) |

The meanings of 4, 5, 7, 8, 10 and 11 still need confirming in the game.

### Rendering the songs

`tools/assets/music.py` runs the driver itself in `tools/nzsemu`, the Musashi-based emulator.
It calls init, then start, then the frame routine once a frame. It logs every audio register
and DMACON write with its cycle time. `tools/assets/paula.py` plays that log through a model of
Paula: each channel latches its location and length when its DMA is switched on and plays one
byte per period, then latches them again at the end of the block (the loop). Channels 0 and 3
are on the left, 1 and 2 on the right. A song that ends is trimmed. A song that loops is cut at
75 seconds and faded out.
