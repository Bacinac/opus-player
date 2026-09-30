# OPUS Home on NVIDIA Shield

`provision.sh` installs the signed OPUS TV APK, selects its native,
network-independent Home activity, and selects OPUS Photos as the Shield
screensaver. Existing launchers and screensavers are not removed or disabled;
they remain recovery paths if OPUS Home ever needs to be replaced.

```sh
./provision.sh 192.0.2.30:5555
```

The Shield asks once for ADB authorization on the television. Netflix and A1
Xplore TV stay as their official Play Store packages; changing Home does not
alter their DRM or device certification.

Optional applications can be inspected and disabled for the current user with
`apps.sh`. Disabling is reversible and is used instead of deleting system APKs:

```sh
./apps.sh list
./apps.sh disable com.example.unused
./apps.sh enable com.example.unused
```

The script refuses Android, Google Play, WebView, NVIDIA, Netflix, Xplore and
OPUS packages. A Shield system update can restore a disabled optional package;
run the command again after the update if necessary.

To return to the previously installed Home, open Android settings from OPUS
Home and choose the default Home app, or run:

```sh
./restore.sh 192.0.2.30:5555
```
