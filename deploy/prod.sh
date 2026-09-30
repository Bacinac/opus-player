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
	# from the tree the extract replaced
	ssh "${SSH_HOST}" "sudo pct exec ${LXC_ID} -- sh -c 'cd ${LXC_PATH} && docker compose up -d --build dac'"
	ssh "${SSH_HOST}" "sudo pct exec ${LXC_ID} -- sh -c 'for i in \$(seq 1 30); do s=\$(docker inspect -f {{.State.Health.Status}} opus_player_dac); [ \"\$s\" = healthy ] && echo dac: healthy && exit 0; sleep 2; done; echo \"dac: \$s\" >&2; docker logs --tail 5 opus_player_dac >&2; exit 1'"
}

source backend/opus_core/ops/deploy.sh
opus_deploy "$@"
