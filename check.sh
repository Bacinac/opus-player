#!/bin/sh
# Everything this repository checks about itself, in one command. The check is
# the same for every OPUS module and lives in opus-core; what follows is only
# what the player adds to it.
#
# How the remote walks the screens is tested on a DOM whose boxes are stated
# rather than laid out (happy-dom, lib/tvui/testing.ts). The Android apps are
# built elsewhere and shipped separately, so every address they call is looked
# up in the backend's own route table: a route deleted from under an installed
# app fails here, not in a car. The apps themselves are linted, tested and built
# here, as debug builds that need no signing identity.
set -eu
cd "$(dirname "$0")"
. backend/opus_core/ops/check.sh

opus_check_module() {
	android_get=$(grep -rhoE '"/api/[^"]*' android/app/src/main android/core/src/main android/music/src/main \
	  --include='*.kt' | cut -c2- | grep -v -E '^/api/(app/crash-report|app/playback-report|auth/login|auth/car-token|photos/offer|tv/video)' || true)
	android_calls=$(
	  {
	    printf '%s\n' "$android_get" | sed '/^$/d; s#^#GET #'
	    printf '%s\n' \
	      'POST /api/app/crash-report' \
	      'POST /api/app/playback-report' \
	      'POST /api/auth/car-token' \
	      'POST /api/auth/login' \
	      'POST /api/photos/offer' \
	      'POST /api/tv/video'
	  } | sort -u
	)
	docker compose exec -T -e ANDROID_CALLS="$android_calls" backend python - <<'PY'
import os
import re
import sys

from opus.main import app


def pattern(template):
    return re.compile("^" + "[^/]+".join(re.escape(part) for part in re.split(r"\{[^}]+\}", template)) + "$")


routes = app.openapi()["paths"]
matchers = [(pattern(route), methods) for route, methods in routes.items()]
missing = []
said = [line for line in os.environ["ANDROID_CALLS"].splitlines() if line]
for call in said:
    method, literal = call.split(" ", 1)
    path = re.sub(r"\$\{[^}]*\}?|\$[A-Za-z_]\w*", "1", re.split(r"[?\s]", literal, maxsplit=1)[0])
    if path.endswith("/"):
        found = any(route.startswith(path) and method.lower() in methods
                    for route, methods in routes.items())
    else:
        found = any(matcher.match(path) and method.lower() in methods
                    for matcher, methods in matchers)
    if not found:
        missing.append(call)
if missing:
    print("android calls a method the backend does not answer:", *missing, sep="\n  ")
    sys.exit(1)
print(f"android routes: {len(said)} method/path calls, every one answered")
PY
	./android/build.sh --debug
}

opus_check
