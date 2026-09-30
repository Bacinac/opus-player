# Release evidence

The Android release build writes one small, public evidence record beside each
APK in `android/dist/`:

- `apk.json` for OPUS Player;
- `music.json` for OPUS Music.

Each record names the Android version, byte count and APK SHA-256.  It now also
records the exact Git commit used for the build and the SHA-256 of the shared
APK v2 signing certificate.  `android/build.sh` obtains the certificate only
after verifying both release APKs with `apksigner`; it refuses to publish if
the apps have different signing identities.

This is release provenance for artifacts served by Player.  It makes a
downloaded APK independently checkable with `sha256sum`, ties it to a source
revision, and makes an accidental signing-key change visible before users are
asked to update.  Container-image digests belong to the deployment record,
because they are created by the production host while an APK is built here.
