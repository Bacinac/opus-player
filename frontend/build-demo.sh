#!/usr/bin/env bash
# Build the backend-less OPUS Player demo and place signed Android apps on its shelf.
set -euo pipefail

UI="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$UI/.." && pwd)"
OUT="${1:-$UI/demo-dist}"
cd "$UI"
OPUS_DEMO=1 VITE_OPUS_DEMO=1 npm run build
rm -rf "$OUT"
mv build "$OUT"
. ../backend/opus_core/ops/revision.sh
opus_revision HEAD false > "$OUT/demo-version.json"

mkdir -p "$OUT/api/app"
cp "$ROOT/android/dist/opus-player.apk" "$OUT/api/app/opus.apk"
cp "$ROOT/android/dist/opus-player.apk" "$OUT/api/app/opus-tv.apk"
cp "$ROOT/android/dist/opus-music.apk" "$OUT/api/app/opus-music.apk"
cp "$UI/static/demo/qr.svg" "$OUT/api/app/qr.svg"

for id in demo-photo-1 demo-photo-2 demo-photo-3 demo-photo-4; do
	mkdir -p "$OUT/api/photos/$id"
	cp "$UI/static/demo/photo.svg" "$OUT/api/photos/$id/tile"
	cp "$UI/static/demo/photo.svg" "$OUT/api/photos/$id/preview"
done
for id in 501 502; do
	mkdir -p "$OUT/api/photos/faces/$id"
	cp "$UI/static/demo/face.svg" "$OUT/api/photos/faces/$id/crop"
	cp "$UI/static/demo/face.svg" "$OUT/api/photos/faces/$id/portrait"
done

printf '/*  /index.html  200\n' > "$OUT/_redirects"
cat > "$OUT/_headers" <<'EOF'
/api/photos/*
  Content-Type: image/svg+xml
/api/app/*.apk
  Content-Type: application/vnd.android.package-archive
  Content-Disposition: attachment
EOF
echo "OPUS Player demo built -> $OUT"
