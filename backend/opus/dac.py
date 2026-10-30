"""The DAC on this host, and the MPD beside the backend that plays into it.

MPD holds the queue and nothing here keeps a copy of it: what is on is read
back from MPD whenever it is asked, and a song is named by the Library the way
every screen of this player names one. A station is named by the Library's
list, and the song on it by what the station says it is playing.

MPD's protocol is a line out and lines back until OK, so it is spoken here
directly rather than through a client library."""

import asyncio
import itertools
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from opus import library, playback, stations

log = logging.getLogger(__name__)

ADDRESS = ("dac", 6600)
TIMEOUT = 5

# a song of ours is an address this player handed out with a ticket
_TRACK = re.compile(r"/api/play/track/(\d+)/stream")
_ANNOUNCEMENT = re.compile(r"/api/play/announcement/(\d+)/stream")

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
        _taken()
        monitor.reset()
        await _exchange(["clear"], *(["add", address] for address in addresses), ["play", start])


async def control(command: str) -> None:
    from opus.dac_watchdog import monitor
    async with _turn:
        _taken()
        if command == "play_pause":
            status, = await _exchange(["status"])
            command = "pause" if status.get("state") == "play" else "play"
        # Disarm before sending: even a failed stop must cancel recovery intent.
        monitor.reset(blocked=command in ("stop", "pause"))
        await _exchange(["pause", 1] if command == "pause" else [command])


# --- the house speaking over the music -------------------------------------

# MPD plays one thing at a time, so the house's sentence goes into the queue
# beside the music and out again, and the music is given back where it was: a
# song at its second, a station from now, a pause as a pause. `single` keeps
# MPD from walking on into the next song when the sentence ends; a sentence that
# follows within GRACE joins the same interruption rather than letting the
# music through between the two.
GRACE = 1.0
_TICK = 0.25
_LONGEST = 60
_KEPT = 8
_numbers = itertools.count(1)
_recorded: dict[int, bytes] = {}


@dataclass
class _Interruption:
    status: dict[str, str]
    waiting: list[str] = field(default_factory=list)
    started: float = 0.0
    quiet_since: float | None = None
    taken: bool = False


_interruption: _Interruption | None = None
_carrying: asyncio.Task | None = None


def _taken() -> None:
    """Somebody chose what the DAC does while the house was speaking: theirs
    wins, and nothing is given back over it. Caller holds _turn."""
    if _interruption is not None:
        _interruption.taken = True


def _encoding(audio_format: str | None) -> list[str]:
    # The DAC is opened bit-perfect, without resampling or remixing, and refuses
    # what speech arrives as (24 kHz mono). The sentence is made in the format
    # the DAC is already open in, so it is not re-clocked for a sentence; CD
    # quality when nothing is on or what is on is DSD.
    rate, _, rest = (audio_format or "").partition(":")
    bits = rest.partition(":")[0]
    deep = bits in ("24", "32", "f")
    return ["-ar", rate if rate.isdigit() else "44100", "-ac", "2",
            *(["-sample_fmt", "s32", "-bits_per_raw_sample", "24"] if deep else ["-sample_fmt", "s16"])]


async def record(audio: bytes) -> int:
    """The house's sound made playable on the DAC, under a number its address
    is built from."""
    if _interruption is not None:
        audio_format = _interruption.status.get("audio")
    else:
        status, = await _talk(["status"])
        audio_format = status.get("audio") if status.get("state") in ("play", "pause") else None
    with tempfile.TemporaryDirectory() as room:
        made = os.path.join(room, "announcement.flac")
        proc = await asyncio.create_subprocess_exec(
            playback._ffmpeg(), "-nostdin", "-v", "error", "-i", "pipe:0",
            "-af", "adelay=300:all=1,apad=pad_dur=0.3", *_encoding(audio_format), "-c:a", "flac", made,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
        try:
            _, said = await asyncio.wait_for(proc.communicate(audio), 20)
        except TimeoutError as exc:
            proc.kill()
            await proc.wait()
            raise DacError("the announcement took too long to prepare") from exc
        if proc.returncode:
            raise DacError(f"the announcement is not sound: {said.decode(errors='replace')[:200]}")
        with open(made, "rb") as file:
            number = next(_numbers)
            _recorded[number] = file.read()
    for old in sorted(_recorded)[:-_KEPT]:
        del _recorded[old]
    return number


def recorded(number: int) -> bytes | None:
    return _recorded.get(number)


async def announce(address: str) -> None:
    """Speaks the recording at `address` over whatever the DAC is doing."""
    global _interruption, _carrying
    async with _turn:
        if _interruption is not None:
            clip, = await _exchange(["addid", address])
            _interruption.waiting.append(clip["Id"])
            return
        status, = await _exchange(["status"])
        clip, = await _exchange(["addid", address])
        _interruption = _Interruption(status, [clip["Id"]], time.monotonic())
        try:
            await _exchange(["consume", 0], ["single", 1], ["playid", clip["Id"]])
        except DacError:
            _interruption.taken = True
            await _give_back(_interruption)
            _interruption = None
            raise
    _carrying = asyncio.create_task(_carry(_interruption))


async def _carry(it: _Interruption) -> None:
    global _interruption
    try:
        while True:
            await asyncio.sleep(_TICK)
            async with _turn:
                if await _step(it, time.monotonic()):
                    await _give_back(it)
                    return
    except DacError as exc:
        log.error("the music was not given back after an announcement: %s", exc)
    finally:
        _interruption = None


async def _step(it: _Interruption, at: float) -> bool:
    """One look at MPD while the house speaks; True when it is time to give
    the music back. Caller holds _turn."""
    if it.taken:
        return True
    status, = await _exchange(["status"])
    if it.waiting and it.quiet_since is None:
        speaking = status.get("state") == "play" and status.get("songid") == it.waiting[0]
        if speaking and at - it.started < _LONGEST:
            return False
        if status.get("error"):
            log.error("an announcement did not play: %s", status["error"])
        await _forget(it.waiting.pop(0))
    if it.waiting:
        await _exchange(["playid", it.waiting[0]])
        it.started, it.quiet_since = at, None
        return False
    if it.quiet_since is None:
        it.quiet_since = at
    return at - it.quiet_since >= GRACE


async def _forget(clip: str) -> None:
    try:
        await _exchange(["deleteid", clip])
    except DacError:
        pass  # a queue somebody replaced took the clip with it


async def _give_back(it: _Interruption) -> None:
    for clip in it.waiting:
        await _forget(clip)
    was = it.status
    await _exchange(["single", was.get("single", "0")], ["consume", was.get("consume", "0")])
    if it.taken:
        return
    song, state = was.get("songid"), was.get("state")
    if state == "play" and song:
        # a station has no duration and no second to go back to, only its now
        await _exchange(["seekid", song, was.get("elapsed", "0")] if was.get("duration") else ["playid", song])
    elif state == "pause" and song:
        await _exchange(["seekid", song, was.get("elapsed", "0")], ["pause", 1])
    else:
        await _exchange(["stop"])


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


async def _station(address: str) -> dict | None:
    try:
        return await stations.by_address(address)
    except library.LibraryError as exc:
        # what plays keeps playing; only its name is missing
        log.warning("station %s is not named: %s", address, exc)
        return None


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
    if _ANNOUNCEMENT.search(address):
        return {**said, "kind": "announcement"}
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


def _station_said(said: dict, current: dict, station: dict, stream) -> dict:
    playing = current.get("Title") or ""
    return {**said, "kind": "station", "station_id": station["id"],
            "stream": stream,
            "title": playing or station["name"],
            "artist": station["name"] if playing else station["genre"] or "",
            "cover_url": station["logo"]}
