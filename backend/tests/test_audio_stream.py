from urllib.parse import parse_qs, urlsplit
import asyncio
import sys
import time

import pytest

from conftest import request, run
from opus import auth, playback
from opus.api.routers import play
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


@pytest.mark.parametrize("kind", ["track", "release"])
@pytest.mark.parametrize("prefer", ["stereo", "dsd"])
def test_queue_lookup_and_stream_address_keep_the_same_edition(monkeypatch, kind, prefer):
    asked = []

    async def get(path, **params):
        asked.append(params)
        track = {"id": 77, "codec": "flac"}
        return {"tracks": [track]} if kind == "release" else track

    async def config():
        return _Config()

    monkeypatch.setattr(play.library, "get", get)
    monkeypatch.setattr(play, "current_runtime", config)
    result = run(play.queue(kind, 77, prefer))
    assert asked == [{"prefer": prefer}]
    assert parse_qs(urlsplit(result["tracks"][0]["uri"]).query)["prefer"] == [prefer]


def test_car_sessions_behind_one_proxy_get_distinct_stable_viewer_keys(house, monkeypatch):
    monkeypatch.setattr(auth, "_cars", {})
    auth._cars.update({car: (time.monotonic(), "filip") for car in (1, 2)})
    viewers = []

    async def stream(command, **params):
        viewers.append(params["viewer"])
        yield b"audio"

    monkeypatch.setattr(playback, "stream", stream)

    async def scenario():
        for car in (1, 2, 1):
            token = auth.issue_car("filip", 3, car)
            response = await play.rebuilt(request(headers={"Authorization": "Bearer " + token}),
                                          [], "audio", "track:77")
            async for _ in response.body_iterator:
                pass

    run(scenario())
    assert viewers[0] != viewers[1] and viewers[0] == viewers[2]


def test_unidentified_proxy_clients_do_not_replace_each_others_streams(monkeypatch):
    async def stream(command, **params):
        assert params["viewer"] is None
        yield b"audio"

    monkeypatch.setattr(playback, "stream", stream)
    run(play.rebuilt(request(), [], "audio", "track:77"))


def test_two_real_converters_continue_and_a_seek_replaces_only_its_own(monkeypatch):
    monkeypatch.setattr(playback, "_running", {})
    monkeypatch.setattr(playback, "_live", {})
    monkeypatch.setattr(playback, "_admitting", asyncio.Lock())
    command = [sys.executable, "-u", "-c",
               "import sys,time;sys.stdout.buffer.write(b'a');sys.stdout.flush();time.sleep(60)"]

    async def scenario():
        bodies = []
        try:
            for viewer in ("car1:track77", "car2:track77"):
                body = playback.stream(command, kind="audio", viewer=viewer)
                bodies.append(body)
                assert await body.__anext__() == b"a"
            first, second = playback._live.values()
            assert first.returncode is None and second.returncode is None
            body = playback.stream(command, kind="audio", viewer="car1:track77")
            bodies.append(body)
            assert await body.__anext__() == b"a"
            assert await first.wait() == -9
            assert second.returncode is None
        finally:
            for body in bodies:
                await body.aclose()
        assert playback._live == {} and playback._running == {}

    run(scenario())
