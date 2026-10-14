#!/bin/bash
# Deploy OPUS · Player to an instance from deploy/hosts.conf (default: prod).
# The steps are opus-core's ops/deploy.sh; this file names what only Player has.
set -euo pipefail
cd "$(dirname "$0")/.."

OPUS_MODULE=opus-player
OPUS_SERVICES=(backend frontend)
OPUS_HEALTH_PORTS=(8098)
# every picture, not only the directories: a cache hit refreshes its recency
# with utime so the size sweep knows what was used, and that fails with EACCES
# on a file the app does not own
OPUS_VOLUME_OWNER=(opus_player_backend all /art)
# android/ stays behind apart from the built app: the media host builds no APK,
# and the signing keystore lives in there
OPUS_SHIP_APART=(android)
OPUS_SHIP_BUILT=(android/dist)

opus_deploy_module() {
	# the dac is NOT forced: recreating it stops the music, so it is replaced only
	# when its own image or definition changed — nothing of it is bind-mounted
	# from the tree the extract replaced. "Its image changed" is the dac/ tree the
	# image is labelled with, not `--build`: that leans on BuildKit's cache, and
	# once the prune evicted it an unchanged dac rebuilt into a new image and was
	# recreated under a playing station. MPD restores its queue paused (right for
	# a cold boot), so a replacement made here puts back what was playing.
	ssh "${SSH_HOST}" "sudo pct exec ${LXC_ID} -- sh -s $(git rev-parse HEAD:dac) ${LXC_PATH}" <<'EOF'
set -eu
tree=$1
cd "$2"
mpd() { docker exec opus_player_dac sh -c "printf '$1\nclose\n' | nc -w 3 127.0.0.1 6600"; }
built=$(docker image inspect -f '{{with index .Config.Labels "opus.dac.tree"}}{{.}}{{end}}' opus-player-dac 2>/dev/null || true)
if [ "$built" != "$tree" ]; then docker compose build --build-arg OPUS_DAC_TREE="$tree" dac; fi
before=$(docker inspect -f '{{.Id}}' opus_player_dac 2>/dev/null || true)
state=$(mpd status 2>/dev/null | sed -n 's/^state: //p' || true)
docker compose up -d dac
if [ "$(docker inspect -f '{{.Id}}' opus_player_dac)" != "$before" ] && [ "$state" = play ]; then
	for i in $(seq 1 30); do
		mpd play 2>/dev/null | grep -qx OK && break
		sleep 1
	done
	mpd status | grep -qx 'state: play' || { echo "dac: replaced, but MPD did not resume" >&2; exit 1; }
	echo "dac: replaced, playback resumed"
fi
for i in $(seq 1 30); do
	s=$(docker inspect -f '{{.State.Health.Status}}' opus_player_dac)
	[ "$s" = healthy ] && break
	sleep 2
done
if [ "$s" != healthy ]; then echo "dac: $s" >&2; docker logs --tail 5 opus_player_dac >&2; exit 1; fi
echo dac: healthy
EOF
}

source backend/opus_core/ops/deploy.sh
opus_deploy "$@"
