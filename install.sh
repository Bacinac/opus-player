#!/usr/bin/env bash
# Install OPUS Player on a playback server. Library URL, the token Library
# issued to Player and the shared session key may come from environment or an
# enrollment env file.
set -euo pipefail
cd "$(dirname "$0")"

source backend/opus_core/ops/install.sh

START=1
ENROLLMENT=
MEDIA_ROOT=
for arg in "$@"; do
	case "$arg" in
		--no-start) START=0 ;;
		--enrollment=*) ENROLLMENT=${arg#*=} ;;
		--media-root=*) MEDIA_ROOT=${arg#*=} ;;
		-h|--help) opus_help; exit 0 ;;
		*) echo "unknown option: $arg" >&2; exit 2 ;;
	esac
done

opus_require docker python3 curl
opus_env_file
if [[ -n "$ENROLLMENT" ]]; then
	[[ -f "$ENROLLMENT" ]] || { echo "enrollment file not found: $ENROLLMENT" >&2; exit 1; }
	while IFS='=' read -r key value; do
		case "$key" in OPUS_LIBRARY_URL|OPUS_LIBRARY_TOKEN|OPUS_SESSION_KEY|VITE_OPUS_LIBRARY_URL|VITE_OPUS_DOWNLOADS_URL) env_set "$key" "$value" ;; esac
	done < "$ENROLLMENT"
fi
opus_required "use --enrollment=FILE" OPUS_LIBRARY_URL OPUS_LIBRARY_TOKEN OPUS_SESSION_KEY
opus_generate POSTGRES_PASSWORD:24

ROOT=$(pwd -P)
HOST=$(opus_host_address)
MEDIA_ROOT=${MEDIA_ROOT:-$ROOT/volumes}
mkdir -p "$ROOT/volumes/postgres" "$ROOT/volumes/art" "$ROOT/volumes/dac"
for name in music movies television video photos; do
	mkdir -p "$MEDIA_ROOT/$name"
	if [[ "$name" == television ]]; then key=OPUS_TV_DEVICE
	else key=OPUS_$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')_DEVICE
	fi
	env_set "$key" "$MEDIA_ROOT/$name"
done
opus_production
[[ -n "$(env_read OPUS_DAC_CARD)" ]] || env_set OPUS_DAC_CARD none
opus_pass_through VITE_OPUS_LIBRARY_URL VITE_OPUS_DOWNLOADS_URL OPUS_COOKIE_DOMAIN OPUS_RENDER_DEVICE

render_device=$(env_read OPUS_RENDER_DEVICE)
if [[ -n "$render_device" ]]; then
	[[ -c "$render_device" ]] || { echo "OPUS_RENDER_DEVICE $render_device is not a device node" >&2; exit 1; }
	env_set OPUS_RENDER_GID "$(stat -c %g "$render_device")"
fi

opus_validate "OPUS Player"
[[ $START == 1 ]] || exit 0

opus_build backend frontend
# DAC is deliberately opt-in: a playback server without USB audio still serves
# browsers, televisions and HDMI. Start it later after naming the ALSA card.
compose up -d postgres backend frontend
opus_wait http://127.0.0.1:8098/api/ready 120 "Player API"
opus_wait http://127.0.0.1:5283/ 60 "Player UI"
echo "OPUS Player is ready: http://$HOST:5283"
echo "OPUS TV APK: http://$HOST:8098/api/app/opus-tv.apk"
echo "OPUS Music APK: http://$HOST:8098/api/app/opus-music.apk"
