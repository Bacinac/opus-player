"""The DAC on this host, and the MPD beside the backend that plays into it.

MPD holds the queue and nothing here keeps a copy of it: what is on is read
back from MPD whenever it is asked, and a song is named by the Library the way
every screen of this player names one. A station is named by this player's own
list, and the song on it by what the station says it is playing.

MPD's protocol is a line out and lines back until OK, so it is spoken here
directly rather than through a client library."""

import asyncio
import logging
import re
import time
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import select

from opus import library
from opus.db import SessionLocal
from opus.models import RadioStation

log = logging.getLogger(__name__)

ADDRESS = ("dac", 6600)
TIMEOUT = 5

# a song of ours is an address this player handed out with a ticket
_TRACK = re.compile(r"/api/play/track/(\d+)/stream")

_TRANSPORT = {"play": "playing", "pause": "paused"}


class DacError(Exception):
    """MPD did not answer, or refused what it was told."""


# one conversation at a time: a queue is replaced in three commands, and a
# second screen's queue arriving between them would be spliced into the first
_turn = asyncio.Lock()


def _quoted(arg) -> str:
    text = str(arg).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


async def _talk(*commands: list) -> list[dict[str, str]]:
    async with _turn:
        return await _exchange(*commands)


async def _exchange(*commands: list) -> list[dict[str, str]]:
    """Caller holds _turn, including any read/decide/write transaction."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(*ADDRESS), TIMEOUT)
    except (OSError, TimeoutError) as exc:
        raise DacError(f"MPD at {ADDRESS[0]}:{ADDRESS[1]} does not answer: {exc}") from exc
    try:
        greeting = await asyncio.wait_for(reader.readline(), TIMEOUT)
        if not greeting.startswith(b"OK MPD"):
            raise DacError(f"not MPD at {ADDRESS[0]}:{ADDRESS[1]}: {greeting!r}")
        answers = []
        for name, *args in commands:
            writer.write(" ".join([name, *map(_quoted, args)]).encode() + b"\n")
            await writer.drain()
            pairs: dict[str, str] = {}
            while True:
                line = (await asyncio.wait_for(reader.readline(), TIMEOUT)).decode()
                if not line:
                    raise DacError(f"MPD hung up during {name}")
                line = line.rstrip("\n")
                if line == "OK":
                    break
                if line.startswith("ACK"):
                    raise DacError(f"MPD refused {name}: {line}")
                key, _, value = line.partition(": ")
                pairs[key] = value
            answers.append(pairs)
        return answers
    except TimeoutError as exc:
        raise DacError(f"MPD stopped answering: {exc}") from exc
    finally:
        writer.close()


async def play(addresses: list[str], start: int) -> None:
    from opus.dac_watchdog import monitor
    async with _turn:
        monitor.reset()
        await _exchange(["clear"], *(["add", address] for address in addresses), ["play", start])


async def control(command: str) -> None:
    from opus.dac_watchdog import monitor
    async with _turn:
        if command == "play_pause":
            status, = await _exchange(["status"])
            command = "pause" if status.get("state") == "play" else "play"
        # Disarm before sending: even a failed stop must cancel recovery intent.
        monitor.reset(blocked=command in ("stop", "pause"))
        await _exchange(["pause", 1] if command == "pause" else [command])


# a song's name does not change while it plays, and the house asks what is on
# every two seconds. Keyed on the edition too: the same track id can be on the
# shelf as both a FLAC and a DSD file, and asking for one must never answer
# with the other's format from a moment ago.
_songs: dict[tuple[int, str], tuple[float, dict]] = {}
_SONG_TTL = 600


async def _song(track_id: int, prefer: str) -> dict:
    key = (track_id, prefer)
    kept = _songs.get(key)
    if kept and time.monotonic() - kept[0] < _SONG_TTL:
        return kept[1]
    try:
        song = await library.get(f"/music/tracks/{track_id}/playback", prefer=prefer)
    except library.LibraryError as exc:
        # what plays keeps playing; only its name is missing
        log.warning("song %s is not named: %s", track_id, exc)
        return {}
    _songs[key] = (time.monotonic(), song)
    return song


async def _station(address: str) -> RadioStation | None:
    async with SessionLocal() as session:
        return (await session.execute(
            select(RadioStation).where(RadioStation.url == address))).scalars().first()


def _number(value: str | None, kind=float):
    try:
        return kind(value) if value not in (None, "") else None
    except ValueError:
        return None


async def now() -> dict:
    from opus.dac_watchdog import monitor
    status, current, gain = await _talk(["status"], ["currentsong"], ["replay_gain_status"])
    current = monitor.current_for(status, current)
    transport = _TRANSPORT.get(status.get("state"), "stopped")
    said = _said(status, gain, transport, _health(monitor, transport, current))
    address = current.get("file")
    if not address:
        return said
    found = _TRACK.search(address)
    if found:
        return await _track_said(said, current, address, int(found.group(1)))
    station = await _station(address)
    if station is not None:
        return _station_said(said, current, station, monitor.stream_info(address))
    return {**said, "kind": "external",
            "title": current.get("Title") or address,
            "artist": current.get("Artist") or "", "album": current.get("Album") or ""}


def _health(monitor, transport: str, current: dict) -> dict:
    health = monitor.snapshot(current.get("file") or "")
    # The API can observe an EOF before the next watchdog tick. Do not report
    # a lost station/intentional stop to home automations during recovery.
    if (transport == "stopped" and monitor.address and not monitor.blocked
            and current.get("file") == monitor.address
            and health.get("state") not in ("recovering", "failed", "unavailable")):
        health = {**health, "state": "recovering", "reason": "stream_ended"}
    return health


def _said(status: dict, gain: dict, transport: str, health: dict) -> dict:
    return {
        "transport": transport,
        "kind": None,
        "title": "", "artist": "", "album": "", "cover_url": None,
        "track_id": None, "release_id": None, "station_id": None,
        # the file as the Library measured it, beside what the DAC is fed, so
        # the two can be held against each other
        "codec": None, "sample_rate_hz": None, "bit_depth": None,
        "position": _number(status.get("elapsed")),
        "duration": _number(status.get("duration")),
        "index": _number(status.get("song"), int),
        # what the DAC is being fed, as MPD opened it: rate:bits:channels
        "format": status.get("audio") if transport != "stopped" else None,
        "bitrate": _number(status.get("bitrate"), int) if transport != "stopped" else None,
        # everything in MPD that could change a sample without changing the
        # format: a software volume (left out when there is no mixer), replay
        # gain, and a crossfade (left out when it is off)
        "volume": _number(status.get("volume"), int),
        "replay_gain": gain.get("replay_gain_mode"),
        "crossfade": _number(status.get("xfade"), int) or 0,
        # MPD keeps playing nothing and says so only here — the DAC unplugged,
        # a station gone — so it is passed on rather than read past
        "error": status.get("error"),
        "health": health,
    }


async def _track_said(said: dict, current: dict, address: str, track_id: int) -> dict:
    # the edition actually asked for travels in the address itself — the
    # source side of the signal path has to name the SAME file MPD opened,
    # not whichever edition a plain stereo lookup would have preferred
    prefer = (parse_qs(urlsplit(address).query).get("prefer") or ["stereo"])[0]
    song = await _song(track_id, prefer)
    return {**said, "kind": "track", "track_id": track_id,
            "release_id": song.get("release_id"),
            "title": song.get("title") or current.get("Title") or "",
            "artist": song.get("artist") or current.get("Artist") or "",
            "album": song.get("album") or current.get("Album") or "",
            "cover_url": song.get("cover_url"), "codec": song.get("codec"),
            "sample_rate_hz": song.get("sample_rate_hz"), "bit_depth": song.get("bit_depth")}


def _station_said(said: dict, current: dict, station: RadioStation, stream) -> dict:
    playing = current.get("Title") or ""
    return {**said, "kind": "station", "station_id": station.id,
            "stream": stream,
            "title": playing or station.name,
            "artist": station.name if playing else station.genre or "",
            "cover_url": station.logo}
