# Assets

These files are extracted from the game program (`../bin/main.bin`) by
`../tools/assets/make_assets.sh`. Do not edit them by hand: change the tools and run the script
again.

| Folder | What | Format notes |
|---|---|---|
| `sound/samples/` | the 18 sound effects and instruments: `.iff` (the original IFF 8SVX files, byte for byte) and `.wav` | [`../docs/SOUND.md`](../docs/SOUND.md) |
| `sound/songs.txt`, `sound/sound.json` | the music driver's songs, patterns, instruments, arpeggios and envelopes, decoded | Jonathan Dunn's own format |
| `sound/music/` | the 12 songs rendered by running the original driver (`.ogg`) | |
| `gfx/` | the main BOB bank: a numbered sheet, each frame as a transparent `.png` and as stored (`.bin`), `bobs.json` | [`../docs/GRAPHICS.md`](../docs/GRAPHICS.md) |
| `levels/` | every level's map, with and without the objects it places; the bosses' frames; the object types' sheet; `levels.json`; the frames each type and level can show (`scripts.json`, `frames.json`) and those drawn in play (`observed.json`) | [`../docs/LEVELS.md`](../docs/LEVELS.md) |
