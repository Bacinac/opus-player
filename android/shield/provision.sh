#!/usr/bin/env bash
# Install OPUS TV and make its native Home surface the Shield launcher.
# The NVIDIA launcher remains installed as a recovery path.
set -euo pipefail

cd "$(dirname "$0")/.."

SERIAL=${1:?usage: $0 <shield adb address, e.g. 192.0.2.30:5555> [apk]}
APK=${2:-dist/opus-player.apk}
ADB=${ADB:-adb}
PACKAGE=biz.boskovic.opus.player
HOME_COMPONENT="$PACKAGE/.HomeActivity"
DREAM_COMPONENT="$PACKAGE/.OpusDreamService"

command -v "$ADB" >/dev/null 2>&1 || {
    echo "adb is required (Android SDK platform-tools)" >&2
    exit 1
}
[[ -f "$APK" ]] || { echo "APK not found: $APK" >&2; exit 1; }

"$ADB" connect "$SERIAL" >/dev/null
[[ "$("$ADB" -s "$SERIAL" get-state 2>/dev/null)" == device ]] || {
    echo "Shield is not authorized; accept the ADB prompt on the television and run again." >&2
    exit 1
}

"$ADB" -s "$SERIAL" install -r "$APK"
"$ADB" -s "$SERIAL" shell am start -W -n "$PACKAGE/.PlayerActivity" \
    --ez "$PACKAGE.ENABLE_HOME" true >/dev/null
"$ADB" -s "$SERIAL" shell cmd package set-home-activity --user 0 "$HOME_COMPONENT"
"$ADB" -s "$SERIAL" shell settings put secure screensaver_components "$DREAM_COMPONENT"
"$ADB" -s "$SERIAL" shell settings put secure screensaver_default_component "$DREAM_COMPONENT"
"$ADB" -s "$SERIAL" shell settings put secure screensaver_enabled 1

resolved=$("$ADB" -s "$SERIAL" shell cmd package resolve-activity --brief \
    -a android.intent.action.MAIN -c android.intent.category.HOME | tr -d '\r' | tail -n 1)
[[ "$resolved" == "$HOME_COMPONENT" || "$resolved" == "$PACKAGE/$PACKAGE.HomeActivity" ]] || {
    echo "Android resolved Home to $resolved instead of $HOME_COMPONENT" >&2
    exit 1
}

"$ADB" -s "$SERIAL" shell am start -a android.intent.action.MAIN \
    -c android.intent.category.HOME >/dev/null

for required in com.netflix.ninja hr.a1.android.tv.xploretv; do
    if [[ -z "$("$ADB" -s "$SERIAL" shell pm path "$required" 2>/dev/null | tr -d '\r')" ]]; then
        echo "warning: $required is not installed, so OPUS Home will hide it" >&2
    fi
done

echo "OPUS Home is active on $SERIAL."
echo "OPUS Photos is the active screensaver."
