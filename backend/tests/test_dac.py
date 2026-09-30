import asyncio
from types import SimpleNamespace

import pytest

from conftest import run
from opus import dac, library

TRACK = "http://192.168.1.102:8098/api/play/track/4211/stream?ticket=abc&fmt=.flac"
STATION = "https://stream.yammat.fm/radio/8000/yammat.mp3"


class FakeMpd:
    """Answers each command from a table, and keeps what it was told."""

    def __init__(self, answers: dict[str, list[str]] | None = None):
        self.answers = answers or {}
        self.heard: list[str] = []

    async def serve(self, reader, writer):
        writer.write(b"OK MPD 0.24.0\n")
        await writer.drain()
        while line := await reader.readline():
            command = line.decode().rstrip("\n")
            self.heard.append(command)
            name = command.split(" ", 1)[0]
            for reply in self.answers.get(name, []):
                writer.write(reply.encode() + b"\n")
            if not any(r.startswith("ACK") for r in self.answers.get(name, [])):
                writer.write(b"OK\n")
            await writer.drain()
        writer.close()


def talking_to(fake: FakeMpd, monkeypatch, body):
    async def scene():
        server = await asyncio.start_server(fake.serve, "127.0.0.1", 0)
        monkeypatch.setattr(dac, "ADDRESS", server.sockets[0].getsockname()[:2])
        async with server:
            return await body()
    return run(scene())


def test_a_queue_replaces_what_was_on_and_starts_where_it_was_asked(monkeypatch):
    fake = FakeMpd()
    talking_to(fake, monkeypatch, lambda: dac.play([TRACK, 'http://x/"odd"'], 1))
    assert fake.heard == ["clear", f'add "{TRACK}"', 'add "http://x/\\"odd\\""', 'play "1"']


def test_play_pause_asks_before_it_decides(monkeypatch):
    fake = FakeMpd({"status": ["state: play"]})
    talking_to(fake, monkeypatch, lambda: dac.control("play_pause"))
    assert fake.heard == ["status", 'pause "1"']
    fake = FakeMpd({"status": ["state: pause"]})
    talking_to(fake, monkeypatch, lambda: dac.control("play_pause"))
    assert fake.heard == ["status", "play"]


def test_a_song_of_ours_is_named_by_the_library(monkeypatch):
    fake = FakeMpd({
        "status": ["volume: -1", "state: play", "song: 2", "elapsed: 61.5", "duration: 184.0",
                   "audio: 96000:24:2", "bitrate: 2400"],
        "currentsong": [f"file: {TRACK}", "Title: from the file"],
        "replay_gain_status": ["replay_gain_mode: off"],
    })
    asked = []

    async def get(path, **params):
        asked.append((path, params))
        return {"title": "Wristwatch", "artist": "MJ Lenderman", "album": "Manning Fireworks",
                "cover_url": "https://art/1.jpg", "release_id": 77, "codec": "flac",
                "sample_rate_hz": 96000, "bit_depth": 24}

    monkeypatch.setattr(dac, "_songs", {})
    monkeypatch.setattr(library, "get", get)
    said = talking_to(fake, monkeypatch, dac.now)
    assert said["transport"] == "playing"
    assert (said["kind"], said["track_id"], said["release_id"]) == ("track", 4211, 77)
    assert (said["title"], said["artist"], said["album"]) == ("Wristwatch", "MJ Lenderman", "Manning Fireworks")
    assert (said["index"], said["position"], said["duration"]) == (2, 61.5, 184.0)
    assert (said["format"], said["bitrate"], said["volume"]) == ("96000:24:2", 2400, -1)
    assert (said["codec"], said["sample_rate_hz"], said["bit_depth"]) == ("flac", 96000, 24)
    assert (said["replay_gain"], said["crossfade"]) == ("off", 0)
    talking_to(fake, monkeypatch, dac.now)
    # an address that named no edition asks the library for the stereo one,
    # and the second ask is cached rather than repeated
    assert asked == [("/music/tracks/4211/playback", {"prefer": "stereo"})]


def test_a_dsd_address_is_named_from_its_own_edition_not_the_stereo_one(monkeypatch):
    # the DAC asked for the DSD edition when it queued this track (cast.py's
    # _addresses); now() must name it the same way, or the signal path would
    # compare a stereo reading against what the card is actually playing
    dsd_track = "http://media:8098/api/play/track/4211/stream?ticket=abc&prefer=dsd&fmt=.flac"
    fake = FakeMpd({
        "status": ["state: play", "audio: dsd64:2"],
        "currentsong": [f"file: {dsd_track}"],
    })
    asked = []

    async def get(path, **params):
        asked.append((path, params))
        return {"title": "Closer To The Music", "artist": "Stockfisch", "codec": "dsf",
                "sample_rate_hz": 2822400, "bit_depth": 1}

    monkeypatch.setattr(dac, "_songs", {})
    monkeypatch.setattr(library, "get", get)
    said = talking_to(fake, monkeypatch, dac.now)
    assert asked == [("/music/tracks/4211/playback", {"prefer": "dsd"})]
    assert (said["codec"], said["sample_rate_hz"], said["bit_depth"]) == ("dsf", 2822400, 1)


def test_the_same_track_id_caches_each_edition_on_its_own(monkeypatch):
    stereo = "http://media:8098/api/play/track/4211/stream?ticket=a&prefer=stereo&fmt=.flac"
    wide = "http://media:8098/api/play/track/4211/stream?ticket=b&prefer=dsd&fmt=.flac"
    seen = []

    async def get(path, **params):
        seen.append(params["prefer"])
        return {"codec": "dsf" if params["prefer"] == "dsd" else "flac"}

    monkeypatch.setattr(dac, "_songs", {})
    monkeypatch.setattr(library, "get", get)
    for address in (stereo, wide, stereo, wide):
        fake = FakeMpd({"status": ["state: play"], "currentsong": [f"file: {address}"]})
        said = talking_to(fake, monkeypatch, dac.now)
        assert said["codec"] == ("dsf" if address is wide else "flac")
    # each edition asked the library exactly once; the repeats came from cache
    assert seen == ["stereo", "dsd"]


def test_a_station_is_named_by_the_list_and_its_song_by_the_station(monkeypatch):
    fake = FakeMpd({
        "status": ["state: play", "song: 0", "audio: 44100:16:2", "bitrate: 322", "xfade: 3"],
        "currentsong": [f"file: {STATION}", "Title: Placebo - Shout", "Name: Yammat FM"],
    })

    async def station(address):
        assert address == STATION
        return SimpleNamespace(id=3, name="Yammat FM", genre="Alternative", logo="https://logo")

    monkeypatch.setattr(dac, "_station", station)
    said = talking_to(fake, monkeypatch, dac.now)
    assert (said["kind"], said["station_id"]) == ("station", 3)
    assert (said["title"], said["artist"], said["cover_url"]) == ("Placebo - Shout", "Yammat FM", "https://logo")
    assert said["crossfade"] == 3


def test_stopped_says_no_format_and_passes_the_error_on(monkeypatch):
    fake = FakeMpd({
        "status": ["state: stop", "audio: 44100:16:2",
                   "error: Failed to open \"DAC\" (alsa); No such device"],
        "currentsong": [],
    })
    said = talking_to(fake, monkeypatch, dac.now)
    assert said["transport"] == "stopped"
    assert said["format"] is None and said["kind"] is None
    assert "No such device" in said["error"]


def test_a_refusal_is_said_not_swallowed(monkeypatch):
    fake = FakeMpd({"play": ["ACK [2@0] {play} Bad song index"]})
    with pytest.raises(dac.DacError, match="Bad song index"):
        talking_to(fake, monkeypatch, lambda: dac.play([TRACK], 5))


def test_nobody_answering_is_a_dac_error(monkeypatch):
    monkeypatch.setattr(dac, "ADDRESS", ("127.0.0.1", 9))
    with pytest.raises(dac.DacError, match="does not answer"):
        run(dac.now())
