#!/usr/bin/env bash
# Reversibly hide or restore an optional Shield application for user 0.
# Core Android, NVIDIA, DRM and OPUS packages are deliberately protected.
set -euo pipefail

SERIAL=${SHIELD_SERIAL:?set SHIELD_SERIAL to the adb address of the Shield, e.g. 192.0.2.30:5555}
ADB=${ADB:-adb}
ACTION=${1:-}
PACKAGE=${2:-}

usage() {
    echo "usage: $0 list | disable PACKAGE | enable PACKAGE" >&2
    exit 2
}

command -v "$ADB" >/dev/null 2>&1 || { echo "adb is required" >&2; exit 1; }
"$ADB" connect "$SERIAL" >/dev/null
[[ "$("$ADB" -s "$SERIAL" get-state 2>/dev/null)" == device ]] || {
    echo "Shield is not authorized" >&2
    exit 1
}

if [[ "$ACTION" == list && -z "$PACKAGE" ]]; then
    "$ADB" -s "$SERIAL" shell cmd package query-activities \
        -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER \
        | tr -d '\r'
    exit 0
fi

[[ "$ACTION" == disable || "$ACTION" == enable ]] || usage
[[ "$PACKAGE" =~ ^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$ ]] || usage

case "$PACKAGE" in
    android|com.android.*|com.google.android.gms|com.android.vending|com.google.android.webview|\
    com.nvidia.*|com.netflix.ninja|hr.a1.android.tv.xploretv|biz.boskovic.opus.player)
        echo "refusing to change protected package: $PACKAGE" >&2
        exit 1
        ;;
esac

if [[ "$ACTION" == disable ]]; then
    "$ADB" -s "$SERIAL" shell pm disable-user --user 0 "$PACKAGE"
else
    "$ADB" -s "$SERIAL" shell pm enable --user 0 "$PACKAGE"
fi
