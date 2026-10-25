#!/bin/sh
# Regenerates original/assets/ from the program (bin/main.bin):
#   assets/sound/samples   every IFF 8SVX sample, byte for byte (.iff) and as .wav
#   assets/sound/songs.txt the music driver's data decoded; sound.json the same parsed
#   assets/sound/music     every song rendered by running the driver (needs tools/nzsemu built; .ogg needs ffmpeg)
#   assets/gfx             the BOB frames (.png, transparent; .bin as stored), the sheet, bobs.json
set -e
cd "$(dirname "$0")/../.."
python3 -I tools/assets/sound.py assets/sound
python3 -I tools/assets/bobs.py assets/gfx
if [ -x tools/nzsemu/nzsemu ]; then
  T=$(mktemp -d)
  python3 -I tools/assets/music.py "$T" 75
  mkdir -p assets/sound/music
  for f in "$T"/*.wav; do
    if command -v ffmpeg >/dev/null; then
      ffmpeg -loglevel error -y -i "$f" -c:a libvorbis -q:a 4 "assets/sound/music/$(basename "$f" .wav).ogg"
    else
      cp "$f" assets/sound/music/
    fi
  done
  rm -rf "$T"
else
  echo "tools/nzsemu/nzsemu not built (tools/nzsemu/build.sh): music not rendered"
fi
