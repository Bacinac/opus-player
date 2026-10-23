"""The house speaks over the DAC and the music plays on from where it was."""
import asyncio
import subprocess

import pytest

from conftest import run
from opus import dac, playback

CLIP = "http://192.168.1.102:8098/api/play/announcement/1/stream?ticket=t"
SECOND = "http://192.168.1.102:8098/api/play/announcement/2/stream?ticket=u"


class Mpd:
    """Keeps the little of MPD's state an announcement touches, and what it was told."""

    def __init__(self, **status):
        self.status = {"state": "play", "songid": "7", "elapsed": "83.5", "duration": "245.0",
                       "single": "0", "consume": "1", "audio": "44100:16:2", **status}
        self.heard: list[str] = []
        self.ids = 100

    async def exchange(self, *commands):
        answers = []
        for name, *args in commands:
            self.heard.append(" ".join([name, *map(str, args)]))
            answer = {}
            if name == "status":
                answer = dict(self.status)
            elif name == "addid":
                self.ids += 1
                answer = {"Id": str(self.ids)}
            elif name == "playid":
                self.status.update(state="play", songid=str(args[0]))
            elif name == "clear":
                self.status.update(state="stop", songid="")
            answers.append(answer)
        return answers

    def sentence_ends(self):
        self.status.update(state="stop", songid="")


@pytest.fixture
def mpd(monkeypatch):
    fake = Mpd()
    monkeypatch.setattr(dac, "_exchange", fake.exchange)
    monkeypatch.setattr(dac, "_TICK", 0.01)
    monkeypatch.setattr(dac, "GRACE", 0.05)
    monkeypatch.setattr(dac, "_interruption", None)
    return fake


async def settle():
    await asyncio.sleep(0.03)


def test_a_song_is_given_back_at_its_second(mpd):
    async def scene():
        await dac.announce(CLIP)
        await settle()
        assert "playid 101" in mpd.heard and mpd.heard[-1] == "status"
        mpd.sentence_ends()
        await dac._carrying
    run(scene())
    assert mpd.heard[:5] == ["status", f"addid {CLIP}", "consume 0", "single 1", "playid 101"]
    assert "deleteid 101" in mpd.heard
    assert mpd.heard[-3:] == ["single 0", "consume 1", "seekid 7 83.5"]
    assert dac._interruption is None


def test_a_station_is_given_back_from_now(mpd):
    del mpd.status["duration"]

    async def scene():
        await dac.announce(CLIP)
        await settle()
        mpd.sentence_ends()
        await dac._carrying
    run(scene())
    assert mpd.heard[-1] == "playid 7"


def test_a_pause_stays_a_pause_and_silence_stays_silent(mpd):
    mpd.status["state"] = "pause"

    async def scene():
        await dac.announce(CLIP)
        await settle()
        mpd.sentence_ends()
        await dac._carrying
    run(scene())
    assert mpd.heard[-2:] == ["seekid 7 83.5", "pause 1"]

    mpd.status.update(state="stop", songid="")
    mpd.heard.clear()

    async def again():
        await dac.announce(CLIP)
        await settle()
        mpd.sentence_ends()
        await dac._carrying
    run(again())
    assert mpd.heard[-1] == "stop"


def test_a_sentence_that_follows_joins_the_same_interruption(mpd):
    async def scene():
        await dac.announce(CLIP)
        await settle()
        mpd.sentence_ends()
        await asyncio.sleep(0.02)  # within GRACE: the music must not come back in between
        await dac.announce(SECOND)
        await settle()
        assert "playid 102" in mpd.heard and "seekid 7 83.5" not in mpd.heard
        mpd.sentence_ends()
        await dac._carrying
    run(scene())
    assert mpd.heard.count("seekid 7 83.5") == 1
    assert mpd.heard.index("playid 102") < mpd.heard.index("seekid 7 83.5")


def test_music_chosen_while_the_house_speaks_is_not_overwritten(mpd):
    async def scene():
        await dac.announce(CLIP)
        await settle()
        await dac.play(["http://192.168.1.102:8098/api/play/track/9/stream?ticket=x"], 0)
        await dac._carrying
    run(scene())
    after = mpd.heard[mpd.heard.index("clear"):]
    assert "single 0" in after and "consume 1" in after
    assert not any(h.startswith(("seekid", "playid 7")) for h in after)


def test_a_sentence_mpd_cannot_open_is_a_dac_error_and_changes_nothing(mpd, monkeypatch):
    real = mpd.exchange

    async def refusing(*commands):
        if commands[-1][0] == "playid":
            raise dac.DacError("MPD refused playid: ACK [50@0] {playid} No such song")
        return await real(*commands)
    monkeypatch.setattr(dac, "_exchange", refusing)
    with pytest.raises(dac.DacError):
        run(dac.announce(CLIP))
    assert mpd.heard[-3:] == ["deleteid 101", "single 0", "consume 1"]
    assert dac._interruption is None


def test_the_sentence_is_made_in_the_format_the_dac_is_open_in():
    assert dac._encoding("44100:16:2") == ["-ar", "44100", "-ac", "2", "-sample_fmt", "s16"]
    assert dac._encoding("96000:24:2")[:2] == ["-ar", "96000"]
    assert "s32" in dac._encoding("96000:24:2")
    assert dac._encoding("dsd64:2")[:2] == ["-ar", "44100"]
    assert dac._encoding(None)[:2] == ["-ar", "44100"]


def test_speech_becomes_stereo_flac_the_dac_takes(monkeypatch):
    speech = subprocess.run(
        [playback._ffmpeg(), "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
         "-ar", "24000", "-ac", "1", "-f", "mp3", "pipe:1"], capture_output=True, check=True).stdout

    async def talk(*commands):
        return [{"state": "play", "audio": "48000:16:2"}]
    monkeypatch.setattr(dac, "_talk", talk)
    monkeypatch.setattr(dac, "_interruption", None)
    number = run(dac.record(speech))
    made = dac.recorded(number)
    assert made[:4] == b"fLaC"
    probe = subprocess.run(
        [playback._ffprobe(), "-v", "error", "-show_entries", "stream=sample_rate,channels",
         "-of", "csv=p=0", "pipe:0"], input=made, capture_output=True, check=True).stdout.decode()
    assert probe.strip() == "48000,2"


def test_what_is_not_sound_is_said_not_swallowed(monkeypatch):
    async def talk(*commands):
        return [{"state": "stop"}]
    monkeypatch.setattr(dac, "_talk", talk)
    monkeypatch.setattr(dac, "_interruption", None)
    with pytest.raises(dac.DacError, match="not sound"):
        run(dac.record(b"this is not audio"))


def test_an_announcement_is_named_as_one_not_by_its_address(monkeypatch):
    async def talk(*commands):
        return [{"state": "play", "elapsed": "1.0"}, {"file": CLIP, "Id": "101"}, {}]
    monkeypatch.setattr(dac, "_talk", talk)
    now = run(dac.now())
    assert now["kind"] == "announcement"
    assert now["title"] == ""
