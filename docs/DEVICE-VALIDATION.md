# Player device-validation matrix

This is release evidence for the paths that unit, integration and build tests
cannot exercise. Run it against a non-private fixture package before releasing
an Android build. Record the APK version, server commit, device model, Android
version, network, fixture hash and result for every row. A failed row is a
supported-path defect; it must not silently turn into software decoding or an
unrelated player.

## Fixture package

Keep the fixture outside Git and record its SHA-256 with each run. It needs:

- H.264 and HEVC in both MP4 and MKV;
- stereo and multichannel audio, alternate audio tracks, text and bitmap
  subtitles, and an HDR sample;
- an unsupported video/audio combination, a long audio track, and a photo/video
  vault pair.

## Phone and Android Auto

| Check | Expected evidence |
|---|---|
| Pair, restart the app, and revoke the device | Pairing survives restart; revoked credentials cannot browse or play. |
| Select albums, cache them, then disconnect | Only selected tracks are available under Offline albums; playback resumes without a network request. |
| Change pairing or sign out | Offline selection, queue, and cached audio belonging to the old pairing are removed. |
| Switch Wi-Fi to mobile data during playback | The app recovers or reports a clear failure; it does not loop or keep an obsolete ticket. |
| Android Auto reconnect and process recreation | Browse tree, transport controls, and Offline albums remain usable after the head unit reconnects. |

## Android TV / Shield

| Check | Expected evidence |
|---|---|
| H.264 and HEVC fixture playback | The native Media3/ExoPlayer engine follows the server plan and starts video with D-pad focus intact. |
| Unsupported codec or audio format | The bridge selects server transcode for unsupported video and remux for unsupported audio; both succeed or report an actionable error, never a black screen. |
| Alternate audio and subtitle switching | The selection changes without invalidating the video decision or losing the stream ticket. |
| HDR, seek, pause/resume, and app recreation | Output remains correct and playback can resume after process recreation. |
| Interrupted and weak network | Recovery or error is bounded; the app does not retry indefinitely. |

## Vault recovery

Use an administrator-approved, non-production copy of a fixture only. Record
the source hash, interrupt an upload at each chunk boundary, restart the client,
restore into an empty target, and compare restored bytes with the source hash.
Keep the result in the private release record, never in Git.

## Release gate

Attach this completed matrix to the release record together with the Android
`apksigner` certificate check, backend readiness result, and deployed commit
hash. Automated checks prove the code contract; this matrix proves the actual
device contract.
