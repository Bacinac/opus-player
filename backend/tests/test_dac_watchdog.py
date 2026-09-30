"""A radio may claim play while elapsed/audio output stop moving."""
from types import SimpleNamespace

import pytest

from conftest import run
from opus import dac, dac_watchdog as watchdog

STATION = "https://radio.invalid/live.mp3"
CURRENT = {"file": STATION, "Id": "19"}


@pytest.fixture
def rig(monkeypatch):
    m = watchdog.RadioMonitor()
    m.probed[STATION] = {"codec": "aac", "sample_rate_hz": 44100}
    commands = []

    async def station(url):
        return SimpleNamespace(id=1, name="Test radio", genre="", logo=None) if url == STATION else None

    async def exchange(*args):
        if args[0][0] == "playlistid":
            return [dict(CURRENT)]
        commands.extend(args)
        return []

    monkeypatch.setattr(dac, "_station", station)
    monkeypatch.setattr(dac, "_exchange", exchange)
    monkeypatch.setattr(watchdog, "monitor", m)
    return m, commands


def observe(m, at, elapsed=10, pointer=100, state="play", error=None, current=CURRENT):
    return m.observe({"state": state, "elapsed": str(elapsed), "songid": "19", "error": error, "playlist": "8"},
                     current, {"state": "RUNNING", "hw_ptr": pointer, "card": "Audio"}, at)


def test_a_stuck_stream_is_reopened_without_replacing_the_queue(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 19, pointer=200)  # DAC can still run out silence
        assert commands == []
        await observe(m, 21, pointer=300)
        assert commands == [["stop"], ["clearerror"], ["playid", "19"]]
        assert m.state == "recovering" and m.reason == "playback_stalled"
        await observe(m, 24, elapsed=1, pointer=400)
        await observe(m, 27, elapsed=4, pointer=500)
        assert m.state == "healthy"
        assert m.snapshot(STATION)["speaker_verified"] is False
    run(scenario())


def test_a_stuck_dac_is_detected_even_when_elapsed_advances(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 21, elapsed=31)  # unchanged hardware pointer
        assert m.reason == "output_stalled"
        assert commands[-1] == ["playid", "19"]
    run(scenario())


def test_normal_playback_never_restarts_including_silent_programme_content(rig):
    m, commands = rig

    async def scenario():
        for at in range(0, 200, 3):
            await observe(m, at, elapsed=at, pointer=at * 44100)
        assert m.state == "healthy" and not commands
    run(scenario())


def test_recovery_keeps_retrying_with_bounded_backoff(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        for at in (21, 42, 63, 82, 103):
            await observe(m, at)
        assert m.attempts == 3 and m.state == "failed"
        assert len(commands) == 9
        await observe(m, 142)
        assert m.attempts == 4 and len(commands) == 12
        await observe(m, 145, elapsed=1, pointer=200)
        await observe(m, 148, elapsed=4, pointer=300)
        assert m.state == "healthy"
    run(scenario())


@pytest.mark.parametrize("command", ["stop", "pause"])
def test_manual_stop_or_pause_cancels_pending_recovery(rig, command):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 21)
        await dac.control(command)
        commands.clear()
        # Even a stale 'play' response or error cannot override manual intent.
        await observe(m, 100, error="old connection error")
        assert commands == [] and m.state == "idle"
    run(scenario())


@pytest.mark.parametrize("state", ["pause", "stop"])
def test_startup_does_not_start_a_paused_or_stopped_queue(rig, state):
    m, commands = rig
    run(observe(m, 100, state=state, error="stale error"))
    assert commands == []


def test_source_change_and_library_playback_cancel_radio_recovery(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 30, current={"file": "http://library/api/play/track/2/stream", "Id": "20"})
        assert commands == [] and m.address == ""
    run(scenario())


def test_mpd_error_recovers_an_already_armed_radio(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 3, state="stop", error="connection reset")
        assert m.reason == "mpd_error" and commands[-1] == ["playid", "19"]
    run(scenario())


def test_http_eof_without_current_song_or_status_error_reopens_same_id(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        # Exact shape after the production HTTP/2 reset: no error/songid/elapsed.
        status = {"state": "stop", "playlist": "8", "playlistlength": "1"}
        await m.observe(status, {}, {"state": "closed"}, 3)
        assert commands == [["stop"], ["clearerror"], ["playid", "19"]]
        assert m.reason == "stream_ended" and m.state == "recovering"
        await m.observe(status, {}, {"state": "closed"}, 6)
        assert len(commands) == 3  # failed reopen doesn't erase retry intent
        await m.observe(status, {}, {"state": "closed"}, 24)
        assert len(commands) == 6
    run(scenario())


@pytest.mark.parametrize("command", ["stop", "pause"])
def test_manual_command_prevents_eof_recovery_even_with_same_queue(rig, command):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await dac.control(command)
        commands.clear()
        await m.observe({"state": "stop", "playlist": "8"}, {}, None, 30)
        assert not commands and not m.address
    run(scenario())


def test_queue_replacement_after_eof_cancels_recovery(rig):
    m, commands = rig

    async def scenario():
        await observe(m, 0)
        await m.observe({"state": "stop", "playlist": "9"}, {}, None, 3)
        assert not commands and not m.address
    run(scenario())


def test_metadata_version_change_keeps_retry_budget_for_same_selected_item(rig):
    m, _ = rig

    async def scenario():
        await observe(m, 0)
        await observe(m, 21)
        await m.observe({"state": "play", "playlist": "9", "elapsed": "1"}, CURRENT, None, 24)
        assert m.attempts == 1 and m.playlist == "9"
    run(scenario())


def test_missing_queued_item_never_rebuilds_or_starts_a_queue(rig, monkeypatch):
    m, commands = rig

    async def exchange(*args):
        assert args == (["playlistid", "19"],)
        return [{}]

    async def scenario():
        await observe(m, 0)
        monkeypatch.setattr(dac, "_exchange", exchange)
        await m.observe({"state": "stop", "playlist": "8"}, {}, None, 3)
        assert not commands and m.blocked
    run(scenario())


def test_now_preserves_station_and_reports_recovery_before_watchdog_tick(rig, monkeypatch):
    m, _ = rig

    async def talk(*args):
        return [{"state": "stop", "playlist": "8"}, {}, {}]

    async def scenario():
        await observe(m, 0)
        monkeypatch.setattr(dac, "_talk", talk)
        said = await dac.now()
        assert said["kind"] == "station" and said["station_id"] == 1
        assert said["transport"] == "stopped"
        assert said["health"]["state"] == "recovering"
        await dac.control("stop")
        said = await dac.now()
        assert said["kind"] is None and said["health"]["state"] == "idle"
    run(scenario())


def test_output_reader_resolves_card_id_and_distinguishes_closed_from_unknown(tmp_path, monkeypatch):
    card = tmp_path / "card2"
    sub = card / "pcm0p/sub0"
    sub.mkdir(parents=True)
    (card / "id").write_text("Audio\n")
    (sub / "status").write_text("state: RUNNING\nhw_ptr      : 12345\n")
    monkeypatch.setenv("OPUS_DAC_CARD", "Audio")
    monkeypatch.setattr(watchdog, "Path", lambda p: tmp_path)
    assert watchdog.output_status() == {"state": "RUNNING", "hw_ptr": 12345, "card": "Audio"}
    (sub / "status").write_text("closed\n")
    assert watchdog.output_status()["state"] == "closed"
    (sub / "status").write_text("state: RUNNING\n")
    assert watchdog.output_status() is None


def test_health_for_a_replaced_station_does_not_inherit_the_previous_reading(rig):
    m, _ = rig
    run(observe(m, 0))
    assert m.snapshot("https://another.invalid/radio")["state"] == "unknown"
