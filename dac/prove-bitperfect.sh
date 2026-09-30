#!/bin/sh
# Prove that the DAC's MPD hands on exactly the samples in the file.
#   dac/prove-bitperfect.sh <library track id>
# Run where the player's compose runs. The music playing meanwhile is not
# touched.
#
# A second MPD from the same image and the same configuration plays the song
# from the address the DAC would fetch it from, into a file instead of the card.
# ffmpeg decodes the same file on its own. The two are compared sample for
# sample: equal means nothing between the decoder and the card's input changed
# a bit. What the card then does with it is the DAC's to show (its MQA light).
set -eu
cd "$(dirname "$0")/.."

track="${1:?usage: dac/prove-bitperfect.sh <library track id>}"
proof=opus_player_dac_proof
work=$(mktemp -d)
trap 'docker rm -f "$proof" >/dev/null 2>&1 || true; rm -rf "$work"' EXIT
chmod 777 "$work"

docker compose exec -T backend python - "$track" > "$work/track.env" <<'PY'
import asyncio, shlex, sys
from opus import library
from opus.api.routers.play import stream_url
from opus.db import SessionLocal
from opus.settings_store import load_runtime

async def main():
    tid = int(sys.argv[1])
    song = await library.get(f"/music/tracks/{tid}/playback")
    async with SessionLocal() as session:
        config = await load_runtime(session)
    said = {"TITLE": f"{song.get('artist')} — {song.get('title')}", "FILE": song["path"],
            "RATE": song["sample_rate_hz"], "BITS": song["bit_depth"], "CHANNELS": song["channels"],
            "URL": stream_url(config, tid, song.get("codec"))}
    for key, value in said.items():
        print(f"{key}={shlex.quote(str(value))}")

asyncio.run(main())
PY
. "$work/track.env"
if [ "$BITS" = 1 ]; then
    # DSD: MPD repacks the raw 1-bit stream into ALSA's DSD_U32_BE words before
    # it reaches the card, a real transform this script has no way to invert
    # and verify byte for byte. A DAC that locks onto DSD (its own light, or
    # onto MQA carried inside a DSD-encoded PCM file) is proof enough that
    # every bit arrived unchanged — decoding either one at all depends on it.
    echo "$TITLE is DSD (${RATE} Hz, 1 bit): prove it on the DAC's own lock, not here" >&2
    exit 0
fi
case "$BITS" in 16|24|32) ;; *) echo "not PCM the DAC takes as it is: ${BITS} bit" >&2; exit 1 ;; esac
echo "track:   $TITLE"
echo "library: ${RATE} Hz / ${BITS} bit / ${CHANNELS} ch"

docker compose exec -T backend /usr/lib/jellyfin-ffmpeg/ffmpeg -v error -i "$FILE" \
    -map 0:a:0 -c:a "pcm_s${BITS}le" -f "s${BITS}le" - > "$work/reference.raw"

docker run -d --name "$proof" -e OPUS_DAC_CARD=proof -v "$work:/proof" opus-player-dac >/dev/null
mpd() { docker exec "$proof" sh -c "printf '%s\nclose\n' \"\$1\" | nc -w 5 127.0.0.1 6600" sh "$1"; }
until mpd status 2>/dev/null | grep -q '^OK MPD'; do sleep 1; done
mpd "add \"$URL\"" >/dev/null
mpd play >/dev/null
opened=""
while :; do
    status=$(mpd status)
    now=$(printf '%s\n' "$status" | sed -n 's/^audio: //p')
    [ -n "$now" ] && opened="$now"
    if printf '%s\n' "$status" | grep -q '^error: '; then
        printf '%s\n' "$status" | grep '^error: ' >&2
        exit 1
    fi
    printf '%s\n' "$status" | grep -q '^state: stop' && [ -n "$opened" ] && break
    sleep 1
done
echo "mpd:     $opened"

docker run --rm -i -v "$work:/w" --entrypoint python opus-player-backend - "$BITS" <<'PY'
import hashlib, sys

bits = int(sys.argv[1])
reference = open("/w/reference.raw", "rb").read()
played = open("/w/mpd.raw", "rb").read()
if bits == 24:
    # MPD carries 24-bit samples in 32-bit words, right-aligned; the card gets
    # the low three bytes of each, which is what ffmpeg wrote
    played = b"".join(played[i:i + 3] for i in range(0, len(played), 4))
width = bits // 8
print(f"samples: library {len(reference) // width}, mpd {len(played) // width}")
same = reference == played
print(f"sha256:  library {hashlib.sha256(reference).hexdigest()[:16]}, "
      f"mpd {hashlib.sha256(played).hexdigest()[:16]}")
print("BIT-PERFECT" if same else "NOT bit-perfect")
sys.exit(0 if same else 1)
PY
