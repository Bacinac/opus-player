from urllib.parse import parse_qs, urlsplit

from opus.api.routers.play import AUDIO_TYPES, stream_url
from opus.playback import compact_audio_command


def test_dsd_gets_the_mime_mpd_actually_picks_a_decoder_by():
    # MPD chooses its dsf/dsdiff decoders by MIME type, not by the address's
    # suffix (confirmed against its own `decoders` protocol reply on this
    # exact MPD build) — the wrong one here falls through to ffmpeg, which
    # decodes the DSD stream to float PCM instead of handing it to the DAC
    # native. mad claims a bare ".mp3", but nothing else in the table is at
    # risk of a similar fallback.
    assert AUDIO_TYPES["dsf"] == "audio/x-dsf"
    assert AUDIO_TYPES["dff"] == "audio/x-dff"


class _Config:
    def get(self, key):
        return {"stream_base": "http://media:8098"}.get(key)


def test_stream_url_carries_the_edition_it_was_asked_for():
    url = stream_url(_Config(), 4211, "flac", prefer="dsd")
    assert parse_qs(urlsplit(url).query)["prefer"] == ["dsd"]


def test_stream_url_defaults_to_stereo():
    url = stream_url(_Config(), 4211, "flac")
    assert parse_qs(urlsplit(url).query)["prefer"] == ["stereo"]


def test_compact_music_is_bounded_opus_not_a_change_to_house_playback():
    command = compact_audio_command("/music/record.flac")
    assert command[-10:] == [
        "-map", "0:a:0", "-vn", "-c:a", "libopus", "-b:a", "96k",
        "-vbr", "constrained", "-application", "audio", "-f", "ogg", "pipe:1",
    ][-10:]
