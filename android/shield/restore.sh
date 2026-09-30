#!/usr/bin/env bash
# Return Home handling to the previously installed launcher.
set -euo pipefail

SERIAL=${1:?usage: $0 <shield adb address, e.g. 192.0.2.30:5555>}
ADB=${ADB:-adb}

command -v "$ADB" >/dev/null 2>&1 || { echo "adb is required" >&2; exit 1; }
"$ADB" connect "$SERIAL" >/dev/null
[[ "$("$ADB" -s "$SERIAL" get-state 2>/dev/null)" == device ]] || {
    echo "Shield is not authorized" >&2
    exit 1
}

"$ADB" -s "$SERIAL" shell am start -W \
    -n biz.boskovic.opus.player/.PlayerActivity \
    --ez biz.boskovic.opus.player.DISABLE_HOME true >/dev/null
"$ADB" -s "$SERIAL" shell am start -a android.intent.action.MAIN \
    -c android.intent.category.HOME >/dev/null
echo "The previous Home is active on $SERIAL."
