#!/usr/bin/env bash
# Build the backend-less OPUS Player demo and place signed Android apps on its shelf.
#
# The household it shows is Library's demo catalogue, read from the Library
# checkout beside this one (OPUS_LIBRARY_SOURCE overrides the path).
set -euo pipefail

UI="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$UI/.." && pwd)"
LIBRARY=${OPUS_LIBRARY_SOURCE:-$ROOT/../opus-library}
OUT="${1:-$UI/demo-dist}"
[[ -x "$LIBRARY/frontend/demo-catalogue.sh" ]] || { echo "no Library checkout at $LIBRARY (set OPUS_LIBRARY_SOURCE)" >&2; exit 1; }

cd "$UI"
OPUS_DEMO=1 VITE_OPUS_DEMO=1 npm run build
rm -rf "$OUT"
mv build "$OUT"
. ../backend/opus_core/ops/revision.sh
opus_revision HEAD false > "$OUT/demo-version.json"
cp demo/demo-net.js "$OUT/"

mkdir -p "$OUT/api/app"
cp "$ROOT/android/dist/opus-player.apk" "$OUT/api/app/opus.apk"
cp "$ROOT/android/dist/opus-player.apk" "$OUT/api/app/opus-tv.apk"
cp "$ROOT/android/dist/opus-music.apk" "$OUT/api/app/opus-music.apk"
cp demo/qr.svg "$OUT/api/app/qr.svg"

printf '/*  /index.html  200\n' > "$OUT/_redirects"
cat > "$OUT/_headers" <<'HEADERS'
/api/app/*.apk
  Content-Type: application/vnd.android.package-archive
  Content-Disposition: attachment
HEADERS
"$LIBRARY/frontend/demo-catalogue.sh" "$OUT"
echo "OPUS Player demo built -> $OUT"
