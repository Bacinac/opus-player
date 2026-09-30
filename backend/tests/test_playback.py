import asyncio

import pytest
from fastapi import HTTPException

from conftest import request, run
from opus import playback
from opus.api.routers import play
from opus.playback import Sound, decide, shift_vtt, sound_for

FILM = {"video_codec": "hevc", "width": 3840, "height": 2160, "container": "mkv"}


@pytest.mark.parametrize(("media", "asked", "mode", "size"), [
    (FILM, {"can_decode": True, "max_height": 1080, "native": True}, "direct", (3840, 2160)),
    (FILM, {"can_decode": False, "max_height": 1080, "native": True}, "transcode", (1920, 1080)),
    (FILM, {"can_decode": True, "max_height": 1080, "max_width": 1920}, "transcode", (1920, 1080)),
    (FILM, {"can_decode": True, "max_height": 2160}, "remux", (3840, 2160)),
    ({**FILM, "container": "mp4"}, {"can_decode": True, "max_height": 2160}, "direct", (3840, 2160)),
    ({**FILM, "container": "mp4"}, {"can_decode": True, "max_height": 2160, "audio": 1}, "remux", (3840, 2160)),
    ({**FILM, "container": "mp4", "width": 1920, "height": 1080}, {"can_decode": False, "max_height": 1080},
     "transcode", (1920, 1080)),
    ({**FILM, "container": "mp4", "width": 1920, "height": 1080},
     {"can_decode": False, "max_height": 1080, "audio": 1}, "transcode", (1920, 1080)),
    ({"video_codec": "h264", "width": 1920, "height": 1080, "container": "mp4"},
     {"can_decode": False, "max_height": 1080, "native": True}, "transcode", (1920, 1080)),
    ({"video_codec": "h264", "width": 1920, "height": 1080, "container": "mp4"},
     {"can_decode": True, "max_height": 1080, "rebuild_audio": True}, "remux", (1920, 1080)),
    ({"video_codec": "h264", "width": 1920, "height": 1080, "container": "mkv"},
     {"can_decode": False, "max_height": 1080}, "remux", (1920, 1080)),
    ({**FILM, "width": 3840, "height": 1600}, {"can_decode": True, "max_height": 1200, "max_width": 1920},
     "transcode", (1920, 800)),
])
def test_decide(media, asked, mode, size):
    plan = decide(media, **asked)
    assert plan.mode == mode
    assert (plan.width, plan.height) == size


@pytest.mark.parametrize(("codec", "channels", "accepts", "takes", "expected"), [
    ("truehd", 8, [], 0, Sound("aac", 2, "192k")),
    ("eac3", 6, ["eac3", "ac3"], 0, Sound("copy", 0, "")),
    ("eac3", 6, ["eac3"], 2, Sound("aac", 2, "192k")),
    ("truehd", 8, ["eac3", "ac3", "aac"], 0, Sound("eac3", 6, "640k")),
    ("dts", 6, ["ac3"], 0, Sound("ac3", 6, "640k")),
    ("dts", 6, ["aac"], 0, Sound("aac", 6, "384k")),
    ("flac", 2, ["aac", "ac3"], 0, Sound("aac", 2, "192k")),
    ("aac", 2, [" AAC ", ""], 0, Sound("copy", 0, "")),
])
def test_sound_for(codec, channels, accepts, takes, expected):
    assert sound_for(codec, channels, accepts, takes) == expected


VTT = """WEBVTT

1
00:00:05.000 --> 00:00:08.000
gone before the stream began

2
00:29:58.500 --> 00:30:02.250
straddles the start

3
01:10:00.000 --> 01:10:01.000
an hour in"""


def test_shift_vtt():
    shifted = shift_vtt(VTT, 1800)
    assert "gone before" not in shifted
    assert "00:00:00.000 --> 00:00:02.250\nstraddles the start" in shifted
    assert "00:40:00.000 --> 00:40:01.000\nan hour in" in shifted
    assert shifted.startswith("WEBVTT")


def test_shift_vtt_short_stamps():
    assert "00:00:01.000 --> 00:00:02.000" in shift_vtt("WEBVTT\n\n00:11.000 --> 00:12.000\nx", 10)


def test_every_process_counts_against_one_ceiling(monkeypatch):
    monkeypatch.setattr(playback, "_running", {object(): "subtitle" for _ in range(playback.MAX_PROCESSES)})
    body = playback.stream(["true"], kind="remux")
    with pytest.raises(playback.PlaybackError, match="as many as this box will run at once"):
        run(body.__anext__())


def test_transcodes_have_their_own_ceiling(monkeypatch):
    monkeypatch.setattr(playback, "_running", {object(): "transcode" for _ in range(playback.MAX_CONCURRENT)})
    body = playback.stream(["true"], kind="transcode")
    with pytest.raises(playback.PlaybackError, match="re-encoded"):
        run(body.__anext__())


class Probe:
    def __init__(self, said: bytes = b"1799.5\n"):
        self.said = said
        self.returncode = None
        self.pid = 4242
        self.killed = False
        self.answer = asyncio.Event()

    async def communicate(self):
        await self.answer.wait()
        self.returncode = 0
        return self.said, None

    def kill(self):
        self.killed = True
        self.returncode = -9

    async def wait(self):
        return self.returncode


@pytest.fixture
def probe(monkeypatch):
    made: list[Probe] = []

    async def spawn(*command, **kwargs):
        made.append(Probe())
        return made[-1]

    monkeypatch.setattr(playback.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(playback, "_ffprobe", lambda: "ffprobe")
    monkeypatch.setattr(playback, "_KEYFRAMES", {})
    monkeypatch.setattr(playback, "_running", {})
    return made


def test_a_probe_counts_against_the_ceiling_while_it_runs(probe):
    async def scenario():
        asked = asyncio.create_task(playback.snap_start("/movies/film.mkv", 1800))
        while not probe:
            await asyncio.sleep(0)
        assert list(playback._running.values()) == ["probe"]
        probe[0].answer.set()
        return await asked

    assert run(scenario()) == 1799.5
    assert playback._running == {}


def test_a_probe_is_refused_past_the_ceiling(probe, monkeypatch):
    monkeypatch.setattr(playback, "_running", {object(): "remux" for _ in range(playback.MAX_PROCESSES)})
    with pytest.raises(playback.PlaybackError, match="as many as this box will run at once"):
        run(playback.snap_start("/movies/film.mkv", 1800))
    assert probe == []


def test_a_cancelled_probe_is_killed_and_released(probe):
    async def scenario():
        asked = asyncio.create_task(playback.snap_start("/movies/film.mkv", 1800))
        while not probe:
            await asyncio.sleep(0)
        asked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asked

    run(scenario())
    assert probe[0].killed
    assert playback._running == {}


def test_a_refused_probe_is_an_answer_on_both_routes(probe, monkeypatch):
    film = {"path": __file__, "video_codec": "h264", "width": 1920, "height": 1080,
            "container": "mkv", "streams": [], "subtitles": [{"id": 3, "path": __file__}]}

    async def media(kind, item_id, lang="en", prefer=None):
        return film

    monkeypatch.setattr(play, "_media", media)
    monkeypatch.setattr(playback, "_running", {object(): "remux" for _ in range(playback.MAX_PROCESSES)})
    with pytest.raises(HTTPException) as refused:
        run(play.stream("movie", 5, request(path="/api/play/movie/5/stream"), t=1800))
    assert refused.value.status_code == 503
    with pytest.raises(HTTPException) as refused:
        run(play.subtitles("movie", 5, 3, t=1800, snap=True))
    assert refused.value.status_code == 503
    assert probe == []


def test_compact_track_is_an_explicit_opus_stream(monkeypatch):
    seen = {}

    async def media(kind, item_id, lang="en", prefer=None):
        assert (kind, item_id, prefer) == ("track", 5, "stereo")
        return {"path": "/music/record.flac", "codec": "flac"}

    async def rebuilt(request, command, mode, what, media_type="video/mp4"):
        seen.update(command=command, mode=mode, what=what, media_type=media_type)
        return object()

    monkeypatch.setattr(play, "_media", media)
    monkeypatch.setattr(play, "rebuilt", rebuilt)
    assert run(play.stream("track", 5, request(path="/api/play/track/5/stream"), compact=True)) is not None
    assert seen["mode"] == "audio"
    assert seen["what"] == "track:5"
    assert seen["media_type"] == "audio/ogg"
    assert "libopus" in seen["command"] and "96k" in seen["command"]


def test_a_compact_audio_head_does_not_start_an_encoder(monkeypatch):
    async def media(kind, item_id, lang="en", prefer=None):
        return {"path": "/music/record.flac", "codec": "flac"}

    async def must_not_run(*args, **kwargs):
        raise AssertionError("HEAD must not start an audio encoder")

    monkeypatch.setattr(play, "_media", media)
    monkeypatch.setattr(play, "rebuilt", must_not_run)
    answer = run(play.stream("track", 5, request(method="HEAD", path="/api/play/track/5/stream"), compact=True))
    assert answer.status_code == 200 and answer.media_type == "audio/ogg"
