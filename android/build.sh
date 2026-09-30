#!/usr/bin/env bash
# Build the signed OPUS apps inside the opus/android-builder container.
#
#   ./build.sh                  lint, test, build, and put both APKs on the shelf (dist/)
#   ./build.sh --check          signed release lint, test and build; the shelf is left alone
#   ./build.sh --debug          debug lint, test and build; no signing material needed
#   ./build.sh --init-keystore <host>
#                               one-time: generate the release signing keystore;
#                               <host> is where the phones reach OPUS (opus.example.com)
#
# Runs only here; the keystore never leaves this box.
set -euo pipefail
cd "$(dirname "$0")"

catalog() { sed -n "s/^$1 = \"\(.*\)\"$/\1/p" gradle/libs.versions.toml; }
PLATFORM="android-$(catalog compileSdk).$(catalog compileSdkMinor)"
BUILD_TOOLS="$(catalog buildTools)"
IMG="opus/android-builder:$( { cat builder.Dockerfile; echo "$PLATFORM $BUILD_TOOLS"; } | sha256sum | cut -c1-12)"
RUN=(docker run --rm -v "$PWD:/project" -w /project
     -v opus-gradle-cache:/gradle-cache -e GRADLE_USER_HOME=/gradle-cache "$IMG")

docker image inspect "$IMG" >/dev/null 2>&1 || docker build -t "$IMG" \
  --build-arg PLATFORM="$PLATFORM" --build-arg BUILD_TOOLS="$BUILD_TOOLS" - < builder.Dockerfile

if [[ "${1:-}" == "--init-keystore" ]]; then
  [[ -n "${2:-}" ]] || { echo "usage: $0 --init-keystore <host the phones reach OPUS at>" >&2; exit 2; }
  umask 077
  mkdir -p keystore
  [[ -f keystore/opus.keystore ]] && { echo "keystore already exists — refusing to overwrite (losing it bricks updates)"; exit 1; }
  # PKCS12 keeps one password for the store and the key.
  PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -d '/+=')
  docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/keystore:/keystore" "$IMG" \
    keytool -genkeypair -v -keystore /keystore/opus.keystore \
    -alias opus -keyalg RSA -keysize 4096 -validity 10950 \
    -storepass "$PASSWORD" -keypass "$PASSWORD" \
    -dname "CN=OPUS Player"
  chmod 600 keystore/opus.keystore
  cat > keystore/keystore.properties <<PROPS
storeFile=keystore/opus.keystore
storePassword=$PASSWORD
keyAlias=opus
keyPassword=$PASSWORD
opusHost=$2
PROPS
  echo "keystore generated."
  exit 0
fi

PUBLISH=true
DEBUG=false
case "${1:-}" in
  --check) PUBLISH=false ;;
  --debug) PUBLISH=false; DEBUG=true ;;
  "") ;;
  *) echo "usage: $0 [--check|--debug|--init-keystore <host>]" >&2; exit 2 ;;
esac

# A release APK must retain its signing identity to be installable as an update.
# The check builds debug APKs instead, so it exercises Android lint, tests and
# compilation without touching that identity.
if ! $DEBUG; then
  [[ -f keystore/keystore.properties ]] || { echo "no keystore — run ./build.sh --init-keystore first"; exit 1; }
fi
# The apps are built for one OPUS: where the phones reach it is part of them.
# A debug build without signing material names it in OPUS_HOST instead.
OPUS_HOST="${OPUS_HOST:-$(sed -n 's/^opusHost=//p' keystore/keystore.properties 2>/dev/null)}"
[[ -n "$OPUS_HOST" ]] || { echo "no opusHost in keystore/keystore.properties — add opusHost=<host the phones reach OPUS at>" >&2; exit 1; }

# An app's version is the position in history of the last commit that changed
# it or what it is built from, so an app nobody touched keeps its version and
# a phone is not offered the same app again.
SHARED=(core build-logic gradle settings.gradle.kts gradle.properties builder.Dockerfile)
version() { git rev-list --count "$(git log -1 --format=%H -- "$1" "${SHARED[@]}")"; }
BASE=$(tr -d ' \t\r\n' < ../VERSION)
[[ "$BASE" =~ ^([0-9]+)\.([0-9]+)$ ]] || { echo "VERSION must be MAJOR.MINOR, got '$BASE'" >&2; exit 1; }
MAJOR=${BASH_REMATCH[1]} MINOR=${BASH_REMATCH[2]}
# Android orders updates by versionCode alone, so it carries the whole version
# rather than the commit count, which restarts whenever the history does.
code() {
  (( MINOR < 100 && $1 < 100000 )) || { echo "v${BASE}.$1 does not fit the versionCode layout" >&2; exit 1; }
  echo $(( MAJOR * 10000000 + MINOR * 100000 + $1 ))
}

APP=$(version app)
MUSIC=$(version music)
APP_CODE=$(code "$APP")
MUSIC_CODE=$(code "$MUSIC")

if $PUBLISH; then
  [[ "$(git rev-parse --is-shallow-repository)" == "false" ]] \
    || { echo "shallow clone: commit counts are not versions here"; exit 1; }
  [[ -z "$(git status --porcelain -- app music "${SHARED[@]}")" ]] \
    || { echo "uncommitted changes: a version names a commit, so commit first (or --check)"; exit 1; }
  shelved() { [[ -f "dist/$1" ]] && sed -n 's/.*"versionCode": *\([0-9]*\).*/\1/p' "dist/$1" || echo 0; }
  (( APP_CODE >= $(shelved apk.json) )) || { echo "the player would go down from $(shelved apk.json) to $APP_CODE, which Android refuses"; exit 1; }
  (( MUSIC_CODE >= $(shelved music.json) )) || { echo "music would go down from $(shelved music.json) to $MUSIC_CODE, which Android refuses"; exit 1; }
fi

if $DEBUG; then
  TASKS=(
    :core:lintDebug :app:lintDebug :music:lintDebug
    :core:testDebugUnitTest :app:testDebugUnitTest :music:testDebugUnitTest
    :app:assembleDebug :music:assembleDebug
  )
else
  TASKS=(
    :core:lintRelease :app:lintRelease :music:lintRelease
    :core:testDebugUnitTest :app:testDebugUnitTest :music:testDebugUnitTest
    :app:assembleRelease :music:assembleRelease
  )
fi

"${RUN[@]}" gradle --no-daemon -q --warning-mode=fail \
  -Papp.versionCode="$APP_CODE" -Papp.versionName="v${BASE}.${APP}" \
  -Pmusic.versionCode="$MUSIC_CODE" -Pmusic.versionName="v${BASE}.${MUSIC}" \
  -PopusHost="$OPUS_HOST" "${TASKS[@]}"

TESTS=$(sed -n 's/^<testsuite [^>]* tests="\([0-9]*\)".*/\1/p' {core,app,music}/build/test-results/testDebugUnitTest/TEST-*.xml | awk '{ n += $1 } END { print n }')
echo "OK tested: ${TESTS} unit tests passed"

SIGNER=""
verify_release() {
  local apk=$1 report digest
  # conscrypt loads its native library; the JDK now asks that to be allowed
  report=$("${RUN[@]}" "/opt/android-sdk/build-tools/${BUILD_TOOLS}/apksigner" \
    -J-enable-native-access=ALL-UNNAMED verify --verbose --print-certs "$apk")
  grep -F 'Verified using v2 scheme (APK Signature Scheme v2): true' <<<"$report" >/dev/null \
    || { echo "release signature v2 verification failed: $apk" >&2; exit 1; }
  digest=$(sed -n 's/^V2 Signer: certificate SHA-256 digest: //p' <<<"$report")
  [[ -n "$digest" && "$digest" != *$'\n'* ]] \
    || { echo "release has no unique signing certificate: $apk" >&2; exit 1; }
  if [[ -n "$SIGNER" && "$SIGNER" != "$digest" ]]; then
    echo "player and music APKs have different signing certificates" >&2
    exit 1
  fi
  SIGNER=$digest
  echo "OK signed: $apk (${digest})"
}

if ! $DEBUG; then
  # Check the files Gradle just signed, not merely the keystore configuration.
  # Both packages must retain the same updater identity before either is placed
  # on the public shelf.
  verify_release app/build/outputs/apk/release/app-release.apk
  verify_release music/build/outputs/apk/release/music-release.apk
fi

if ! $PUBLISH; then
  echo "OK checked: player v${BASE}.${APP}, music v${BASE}.${MUSIC}"
  exit 0
fi

shelve() {
  local built=$1 apk=$2 meta=$3 code=$4 name=$5 revision
  revision=$(git rev-parse HEAD)
  cp "$built" "dist/$apk"
  cat > "dist/$meta" <<META
{
  "versionCode": ${code},
  "versionName": "${name}",
  "bytes": $(stat -c%s "dist/$apk"),
  "sha256": "$(sha256sum "dist/$apk" | cut -d' ' -f1)",
  "sourceRevision": "${revision}",
  "signerSha256": "${SIGNER}"
}
META
  echo "OK dist/$apk ${name} ($(stat -c%s "dist/$apk") bytes)"
}

mkdir -p dist
shelve app/build/outputs/apk/release/app-release.apk opus-player.apk apk.json "$APP_CODE" "v${BASE}.${APP}"
shelve music/build/outputs/apk/release/music-release.apk opus-music.apk music.json "$MUSIC_CODE" "v${BASE}.${MUSIC}"
