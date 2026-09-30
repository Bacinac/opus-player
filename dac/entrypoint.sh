#!/bin/sh
# MPD in front of the DAC. OPUS_DAC_CARD is the ALSA id of the card; "none"
# plays into nothing at the speed of real time, which is what a box without the
# DAC develops against; "proof" writes exactly what would reach the card to
# /proof/mpd.raw, for prove-bitperfect.sh. A card that is named and missing
# stops the container — music that silently goes nowhere is the failure this
# refuses to hide.
set -eu

card="${OPUS_DAC_CARD:?set OPUS_DAC_CARD to the ALSA id of the DAC, or none}"

if [ "$card" = "none" ]; then
    output='
audio_output {
    type        "null"
    name        "DAC"
    mixer_type  "none"
}'
elif [ "$card" = "proof" ]; then
    output='
audio_output {
    type        "pipe"
    name        "DAC"
    command     "cat > /proof/mpd.raw"
    mixer_type  "none"
}'
else
    # Docker masks /proc/asound in a container; sysfs still names the cards
    if ! grep -qx "$card" /sys/class/sound/card*/id 2>/dev/null; then
        echo "the DAC is not plugged in: no ALSA card \"$card\"" >&2
        exit 1
    fi
    node=$(find /dev/snd -maxdepth 1 -type c -name 'controlC*' 2>/dev/null | head -n 1)
    if [ -z "$node" ]; then
        echo "no sound devices under /dev/snd: OPUS_DAC_SOUND does not point at them" >&2
        exit 1
    fi
    # the nodes keep the host's audio group, whose number is not Alpine's
    gid=$(stat -c %g "$node")
    group=$(getent group "$gid" | cut -d: -f1)
    if [ -z "$group" ]; then
        group=snd
        addgroup -g "$gid" "$group"
    fi
    addgroup mpd "$group"
    output="
audio_output {
    type           \"alsa\"
    name           \"DAC\"
    device         \"hw:CARD=$card,DEV=0\"
    mixer_type     \"none\"
    auto_resample  \"no\"
    auto_channels  \"no\"
    dop            \"no\"
}"
fi

# The queue and the place in it survive a restart of this container — a deploy,
# a reboot — but come back paused: music starting by itself when the host comes
# up at three in the morning is worse than a press of play.
state=""
if [ "$card" != "proof" ]; then
    mkdir -p /var/lib/mpd
    chown mpd /var/lib/mpd
    state='state_file        "/var/lib/mpd/state"
restore_paused    "yes"'
fi

# auto_format stays on: it converts only what the card refuses, and the DAC
# takes 16, 24 and 32-bit PCM as they come — what it refuses is the float a
# lossy stream decodes to.
# mad is off because it claims every address that ends in .mp3, and Yammat
# serves AAC under that name: mad decodes it as mono noise at 11025 Hz and
# reports it as playing. ffmpeg decodes real MP3 just as well.
cat > /etc/mpd.conf <<EOF
user              "mpd"
bind_to_address   "0.0.0.0"
port              "6600"
log_level         "notice"
zeroconf_enabled  "no"
$state
$output

# A TCP connection can stay open indefinitely without delivering audio. MPD's
# HTTP timeout turns that into an explicit error the radio watchdog can recover.
# This checks incoming bytes, not loudness (a quiet programme is still data).
input {
    plugin           "curl"
    connect_timeout  "10"
    low_speed_limit  "1"
    low_speed_time   "20"
    tcp_keepalive    "yes"
    tcp_keepidle     "10"
    tcp_keepintvl    "5"
}

decoder {
    plugin   "mad"
    enabled  "no"
}
EOF

exec mpd --no-daemon --stderr /etc/mpd.conf
