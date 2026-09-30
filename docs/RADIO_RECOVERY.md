# Radio recovery

The Player lifespan runs a radio watchdog every three seconds, independently
of clients asking for now-playing. It arms only for a known radio station that
MPD is already playing. It never starts a stopped/paused queue at boot.

It reads MPD elapsed audio and, when available, the configured ALSA card's
hardware playback pointer via the read-only `/run/opus-asound` mount. Twenty
seconds without progress, or an MPD error, reopens the current song ID without
replacing the queue. A stream EOF/reset also reopens the station on the next
check, even if MPD has discarded `currentsong` and no longer reports an error.
The monitor retains the previously playing song ID only while the queue version
is unchanged, and verifies that ID still names the same URL before each retry.
There are repeated attempts with 20/40/60-second capped backoff while playback
is still wanted; two minutes of sustained progress reset the retry counter. Manual
stop/pause and source changes cancel pending recovery under the same lock as
MPD commands. Playback failures remain visible in `/api/dac/now.health` and
produce logs with the reason and attempt number. After three unsuccessful
attempts health says `failed`, but retries continue once a minute. A lost
`currentsong` during recovery retains station metadata, so home automations see
buffering rather than an intentional stop. Stop/pause must go through the OPUS
control API (as DIDA does), so their intent can be distinguished from a stream EOF.

MPD's curl input has a 20-second low-speed timeout (less than one byte/second)
and TCP keepalive. Thus a connected but silent network cannot wait indefinitely.
This measures transferred bytes, not programme loudness. It does not treat
intentional quiet passages as faults.

`/api/dac/now.stream` reports the codec, rate and channels probed from compressed
stream headers. MPD supplies the current bitrate separately. Decoded PCM depth
is not presented as the original quality of a lossy radio station.

Neither elapsed audio nor a moving USB pointer proves that an amplifier and
speakers are audible. `health.speaker_verified` stays false. Acoustic
verification needs an explicitly configured microphone/feedback input.

Unit tests cover stalls, error stops, bounded recovery, source changes and
manual cancellation. `tests/test_dac_watchdog_live.py` is opt-in via
`OPUS_TEST_MPD`: point it ONLY at a disposable MPD with null output. It serves
a local streaming WAV, stalls, closes, or resets the first connection after
playback is healthy, and verifies reopening and recovery without operator
input. Never run it against the household DAC.
