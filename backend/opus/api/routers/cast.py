"""Sound aimed at the house instead of this screen.

Stereo goes to the DAC on this very host, through the MPD beside the backend.
Anything with more channels goes to OUR OWN app on the television streamer —
the receiver takes multichannel only over HDMI, and the box runs this player's
wrapper with its Media3 engine. What travels here is only the sentence — every
renderer pulls the bytes straight from this module with a ticket.

The television is not a DIDA device for this: it is another face of this very
player, so the command channel is a mailbox here — one per box that was let in.
Its page long-polls it, plays what arrives through its own engine, and reports
back what is on, which is what the other screens mirror. An order is addressed
to one box: the one named, or the one the house means by its television.

The same mailbox carries the other direction: when the sound goes to a device
in the house, the television is told to SHOW that record and follow the device
playing it, so the sleeve and the words are on the big screen while the sound
comes out of the amplifier."""

import asyncio
import json
import logging
import secrets
import time

import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request
from opus_core import dida
from pydantic import BaseModel, Field
from sqlalchemy import select

from opus import auth, dac, house, library
from opus.api.routers.art import asked_for
from opus.api.routers.play import stream_url
from opus.api.routers.radio import play_url
from opus.api.routers.users import picked, profile_key, require_picked
from opus.cards import artist_card, croatian, episode_card, movie_card, series_card
from opus.db import SessionLocal
from opus.models import BoxPreference, RadioStation, User
from opus.settings_store import current_runtime

log = logging.getLogger(__name__)
router = APIRouter()

OUTPUT_KEYS = {"stereo": "audio_output_stereo", "multi": "audio_output_multi"}

# the sentinel an output setting holds when the destination is our own wrapper
# on the television streamer rather than a DIDA entity
TV = "tv"
# …and when it is the DAC on this host
DAC = "dac"


class _TvChannel:
    """The mailbox between the screens that command and one screen that plays.

    Ephemeral on purpose: an order to play is a live sentence, not state — a
    restart with nobody listening has nothing worth keeping."""

    def __init__(self, box: auth.Box):
        self.box = box
        # a restart counts from nought again, and a screen still counting from
        # before would take every new order for one it had already acted on
        self.boot = secrets.token_hex(4)
        self.seq = 0
        self.order: dict | None = None
        self.control: dict | None = None
        self.state: dict = {}
        self.state_at = 0.0
        # when the television last came to the door. It only reports what it is
        # playing while something IS playing, so silence there proves nothing —
        # but a screen that is not even asking is a screen nothing can reach.
        self.seen_at = 0.0
        # what the box's picture goes into, as it last said; empty where it
        # cannot tell
        self.sink = ""
        self.wake = asyncio.Event()

    @property
    def listening(self) -> bool:
        # the wrapper long-polls on a 25-second answer and asks again at once,
        # so a minute of nothing is a screen that has gone
        return self.seen_at > 0 and time.monotonic() - self.seen_at < 60

    def post(self, order: dict | None = None, control: dict | None = None):
        self.seq += 1
        if order is not None:
            self.order = {**order, "seq": self.seq}
        if control is not None:
            self.control = {**control, "seq": self.seq}
        self.wake.set()
        self.wake = asyncio.Event()


# one per box that has come to the door since this process started, by the id
# the list of boxes next door gave it
_boxes: dict[int, _TvChannel] = {}

# the package the house opens on a television it wakes
TV_APP = "biz.boskovic.opus.player"
# waking a box from sleep, opening the player and loading its page; an order
# still undelivered by then is not what anybody is waiting for any more
WAKE_S = 90

# a film sent to a television that was woken for it, by box: posted only once
# the screen is back and counting from this process, because an order posted
# before that is history to the screen by the time it asks
_waiting: dict[int, tuple[dict, float]] = {}


async def _this_box(request: Request) -> _TvChannel:
    box = await auth.device(request.cookies.get(auth.DEVICE_COOKIE))
    if box is None:
        raise HTTPException(403, "only a television that was let in has a mailbox")
    channel = _boxes.get(box.id)
    if channel is None:
        channel = _boxes[box.id] = _TvChannel(box)
    channel.box = box
    return channel


def _house(config, box: int | None = None) -> _TvChannel | None:
    """The television an order is meant for: the box named, or the one set as
    the house's, or — while none is set — the only box listening. Several
    listening with none set is a question nobody has answered, and guessing it
    sends a film to the terrace."""
    if box is not None:
        return _boxes.get(box)
    chosen = config.get("tv_box")
    if chosen:
        return _boxes.get(int(chosen))
    listening = [channel for channel in _boxes.values() if channel.listening]
    if len(listening) > 1:
        raise HTTPException(409, "more than one television is listening and none is set "
                                 "as the house's; name one or set tv_box")
    return listening[0] if listening else None


def _listening(config, box: int | None = None) -> _TvChannel:
    channel = _house(config, box)
    if channel is None or not channel.listening:
        raise HTTPException(503, "the television is not listening")
    return channel


def _mirror(config) -> _TvChannel | None:
    """The house's television, where it can be told to show what the house is
    playing. The sound does not fail with it."""
    try:
        channel = _house(config)
    except HTTPException as refused:
        log.warning("not shown on a television: %s", refused.detail)
        return None
    return channel if channel is not None and channel.listening else None


# what a device is called is DIDA's to answer, and it answers slowly enough
# that asking on every visit to the picker would be felt
_names: dict[str, tuple[float, str]] = {}
_NAME_TTL = 600


async def _entity_name(config, entity: str) -> str:
    cached = _names.get(entity)
    if cached and time.monotonic() - cached[0] < _NAME_TTL:
        return cached[1]
    try:
        name = (await house.state(config, entity))["name"]
    except dida.DidaError:
        name = entity
    _names[entity] = (time.monotonic(), name)
    return name


def _dac_name(config) -> str:
    return config.get("audio_dac_name") or "DAC"


def _entity(config, output: str) -> str:
    key = OUTPUT_KEYS.get(output)
    if key is None:
        raise HTTPException(404, "no such output")
    entity = config.get(key)
    if not entity:
        raise HTTPException(404, f"no device is configured for the {output} output")
    return entity


@router.get("/cast/outputs")
async def outputs():
    config = await current_runtime()
    out: list[dict] = [{"id": "browser"}]
    for oid in OUTPUT_KEYS:
        entity = config.get(OUTPUT_KEYS[oid])
        if entity == TV:
            out.append({"id": oid, "entity": TV, "name": "OPUS TV"})
        elif entity == DAC:
            out.append({"id": oid, "entity": DAC, "name": _dac_name(config)})
        elif entity:
            out.append({"id": oid, "entity": entity,
                        "name": await _entity_name(config, entity)})
    return {"outputs": out}


# what an adapter is called when its name has to stand beside a device's — the
# same proper nouns DIDA's own surfaces use
ADAPTER_NAMES = {"heos": "HEOS", "denon": "Denon/Marantz",
                 "cast": "Cast", "dlna": "DLNA", "announce": "Announce",
                 "androidtv": "Android TV"}


@router.get("/cast/options")
async def options():
    """What the audio settings can point at, in the house's own words: DIDA's
    media devices by their names (twins told apart by adapter, rooms where the
    room has a name), the amplifier's own input list, and the boxes that have
    come to this player's door."""
    config = await current_runtime()
    try:
        gathered = await asyncio.gather(house.entities(config), house.areas(config))
    except dida.DidaError as exc:
        raise HTTPException(502, str(exc))
    ents, rooms_raw = gathered
    choices = _media_choices(ents, rooms_raw)
    # our own screen and our own DAC lead the list — they are the player's, not
    # the house's
    choices[:0] = [{"value": TV, "label": "OPUS TV"}, {"value": DAC, "label": _dac_name(config)}]
    sources = await _amp_sources(config)
    boxes = sorted(({"value": str(c.box.id), "label": c.box.name} for c in _boxes.values()),
                   key=lambda b: b["label"].lower())
    return {"media": choices, "sources": sources, "boxes": boxes}


def _device_name(entity: dict) -> str:
    return (entity.get("label") or entity.get("name") or entity["entity_id"]).strip()


def _media_choices(ents: list[dict], rooms_raw: list[dict]) -> list[dict]:
    rooms = {a["id"]: (a.get("name") or "").strip() for a in rooms_raw}
    # a media device that can actually play — a remote's D-pad buttons carry
    # the media type too, and none of them is a place sound can go
    media = [e for e in ents if e.get("device_type") == "media"
             and "media_transport" in (e.get("capabilities") or [])]
    counts: dict[str, int] = {}
    for e in media:
        base = _device_name(e)
        counts[base] = counts.get(base, 0) + 1
    choices = []
    for e in media:
        label = _device_name(e)
        if counts[label] > 1:
            adapter = e.get("adapter") or e["entity_id"].partition(":")[0]
            label = f"{label} ({ADAPTER_NAMES.get(adapter, adapter)})"
        room = rooms.get(e.get("area_id"))
        if room:
            label = f"{label} · {room}"
        choices.append({"value": e["entity_id"], "label": label})
    choices.sort(key=lambda c: c["label"].lower())
    return choices


async def _amp_sources(config) -> list:
    amp = config.get("audio_amp_entity")
    if not amp:
        return []
    try:
        raw = (await house.state(config, amp))["values"].get("source_options")
        return json.loads(raw) if isinstance(raw, str) and raw else (raw or [])
    except (dida.DidaError, ValueError):
        return []


class CastTrack(BaseModel):
    id: int
    title: str = ""
    artist: str = ""
    album: str = ""
    cover_url: str | None = None
    codec: str | None = None
    # a station is a stream somebody else keeps alive: there is no file of ours
    # to hand a ticket for, only an address to pass on
    url: str | None = None


async def _vetted(tracks: list[CastTrack]) -> None:
    """Only what this player hands out itself reaches a device in the house: a
    song of the library's by its id, a station this player lists, and a picture
    its picture route would fetch. An address from a request is not a sentence
    to hand an amplifier or a television."""
    listed: set[str] | None = None
    for t in tracks:
        if t.url is not None:
            if listed is None:
                async with SessionLocal() as session:
                    listed = set((await session.execute(select(RadioStation.url))).scalars())
            if t.url not in listed:
                raise HTTPException(400, "not a station this player lists")
        elif t.id <= 0:
            raise HTTPException(400, "not a song of the library's")
        if t.cover_url and await asked_for(t.cover_url) is None:
            raise HTTPException(400, "not a picture the catalogue uses")


def _addresses(config, tracks: list[CastTrack]) -> list[str]:
    # the DAC plays DSD natively — nothing else in the house can — so it is
    # the one renderer that asks the library for that edition rather than the
    # stereo one the queue was built from. A track with no DSD edition gets
    # back whatever it does hold, same fallback `prefer` has everywhere else.
    return [t.url or stream_url(config, t.id, t.codec, prefer="dsd") for t in tracks]


def _art(t: CastTrack) -> str:
    # a renderer fetches a picture by address; a relative one is nothing to it
    return t.cover_url if (t.cover_url or "").startswith("http") else ""


def _station(t: CastTrack) -> dict:
    return {"uri": t.url, "title": t.title, "art": _art(t)}


def _told(tracks: list[CastTrack]) -> list[dict]:
    """The tracks as the television opens them: a station with the address it is
    opened from, whoever ordered it."""
    return [{**t.model_dump(), "play_url": play_url(t.url) if t.url else None} for t in tracks]


class PlayBody(BaseModel):
    output: str
    tracks: list[CastTrack]
    start: int = 0


async def _wiring(box: int) -> BoxPreference | None:
    async with SessionLocal() as session:
        return await session.get(BoxPreference, box)


async def _wired(box: int | None) -> str:
    """The receiver's input a box arrives on; nothing for a box wired to a
    screen of its own, for no box at all, or for a box now plugged into
    something other than what it was wired on."""
    kept = await _wiring(box) if box is not None else None
    if kept is None:
        return ""
    channel = _boxes.get(box)
    now = channel.sink if channel else ""
    # a box that cannot say what it is plugged into keeps its input
    if kept.amp_sink and now and now != kept.amp_sink:
        return ""
    return kept.amp_source


async def _to_box(config, box: int | None) -> bool:
    """Turn the receiver to the box about to play, picture and sound off its one
    input. Whether it was turned: a box the receiver does not carry is left to
    its own screen, and so is the receiver."""
    amp = config.get("audio_amp_entity")
    source = await _wired(box)
    if not amp or not source:
        return False
    await house.command(config, amp, "on_off", "turn_on")
    await house.command(config, amp, "source", "set_source", {"value": source})
    await house.command(config, amp, "video_select", "set_video_select", {"value": "off"})
    return True


async def _play_on_tv(config, channel: _TvChannel, tracks: list[CastTrack], start: int) -> None:
    """Our own screen plays this. An order posted to a mailbox nobody is reading
    is a press of play that does nothing and says nothing: the television is
    another face of this player, not a device that might be off, so if it is not
    asking, that is said before this is reached. The amplifier still has to be on
    and listening to the streamer's HDMI input before the first note."""
    try:
        await _to_box(config, channel.box.id)
    except dida.DidaError as exc:
        raise HTTPException(502, str(exc)) from exc
    channel.post(order={"tracks": _told(tracks), "start": start})


@router.post("/cast/play")
async def play(body: PlayBody, who: User = Depends(require_picked)):
    config = await current_runtime()
    entity = _entity(config, body.output)
    if not body.tracks:
        raise HTTPException(400, "nothing to play")
    await _vetted(body.tracks)
    start = max(0, min(body.start, len(body.tracks) - 1))
    if entity == TV:
        await _play_on_tv(config, _listening(config), body.tracks, start)
        return {"ok": True}
    try:
        if body.output == "stereo":
            # the amplifier has to be listening to the DAC before the first note;
            # a discrete power-on to a receiver already on is a no-op
            amp = config.get("audio_amp_entity")
            source = config.get("audio_amp_source")
            if amp:
                await house.command(config, amp, "on_off", "turn_on")
                if source:
                    await house.command(config, amp, "source", "set_source",
                                       {"value": source})
                # The DAC is wired to an analogue input, and the receiver takes
                # picture and sound off the same one — so listening to it blanked
                # the screen the record was being read on. The eye is sent back
                # to the streamer that carries this player's own face.
                chosen = config.get("tv_box")
                screen = await _wired(int(chosen) if chosen else None)
                if screen:
                    await house.command(config, amp, "video_select",
                                       "set_video_select", {"value": screen})
        if entity == DAC:
            await dac.play(_addresses(config, body.tracks), start)
        else:
            # the receiver's own player holds no queue of ours: it is handed one
            # track, and the surface hands it the next when this one is done
            t = body.tracks[start]
            await house.command(config, entity, "media_transport", "play_media",
                               _station(t) if t.url
                               else {"uri": stream_url(config, t.id, t.codec),
                                     "title": t.title, "art": _art(t)})
    except (dida.DidaError, dac.DacError) as exc:
        raise HTTPException(502, str(exc))
    # The device plays; the television shows. A record on the DAC still has a
    # sleeve, songs and words, and the big screen is the place to read them —
    # so the same sentence goes to the mailbox marked as something to watch
    # rather than something to play. A screen that is not there simply does not
    # show it; that is no reason for the sound to fail.
    shown = _mirror(config)
    if shown is not None:
        shown.post(order={"tracks": _told(body.tracks), "start": start, "watch": body.output})
    return {"ok": True}


class ControlBody(BaseModel):
    output: str
    command: str


CONTROLS = {"play", "pause", "play_pause", "stop", "next", "previous"}


@router.post("/cast/control")
async def control(body: ControlBody, who: User = Depends(require_picked)):
    config = await current_runtime()
    entity = _entity(config, body.output)
    if body.command not in CONTROLS:
        raise HTTPException(400, "no such command")
    if entity == TV:
        _listening(config).post(control={"command": body.command})
        return {"ok": True}
    try:
        if entity == DAC:
            await dac.control(body.command)
        else:
            await house.command(config, entity, "media_transport", body.command)
    except (dida.DidaError, dac.DacError) as exc:
        raise HTTPException(502, str(exc))
    # A television showing this record lets go of it only after it has seen
    # the device stopped twice; an ending somebody pressed is said at once.
    if body.command == "stop":
        shown = _mirror(config)
        if shown is not None:
            shown.post(control={"command": "stop"})
    return {"ok": True}


class VolumeBody(BaseModel):
    command: str


@router.post("/cast/volume")
async def volume(body: VolumeBody, who: User = Depends(require_picked)):
    config = await current_runtime()
    entity = config.get("audio_volume_entity")
    if not entity:
        raise HTTPException(404, "no volume device is configured")
    try:
        if body.command in ("up", "down"):
            await house.command(config, entity, "volume", f"volume_{body.command}")
        elif body.command == "mute":
            await house.command(config, entity, "mute", "toggle")
        else:
            raise HTTPException(400, "no such command")
    except dida.DidaError as exc:
        raise HTTPException(502, str(exc))
    return {"ok": True}


def _fresh(channel: _TvChannel | None) -> dict:
    """What a television last said of itself, while that is recent: silence for
    too long means the screen is gone, and saying "playing" past that would be a
    guess."""
    if channel is None or time.monotonic() - channel.state_at >= 15:
        return {}
    return channel.state


async def _volume(config) -> dict:
    """The amplifier's level, which is where the volume is for every output.
    Not being able to read it is no reason not to say what is playing."""
    entity = config.get("audio_volume_entity")
    if not entity:
        return {}
    try:
        return (await house.state(config, entity))["values"]
    except dida.DidaError:
        return {}


# what the DAC's MPD calls a kind of thing, in the words the screens take up
_DAC_SOURCE = {"track": "library", "station": "radio", "external": "external"}


@router.get("/cast/state")
async def state(output: str):
    config = await current_runtime()
    entity = _entity(config, output)
    if entity == DAC:
        try:
            now, vol = await asyncio.gather(dac.now(), _volume(config))
        except dac.DacError as exc:
            raise HTTPException(502, str(exc))
        return {
            "name": _dac_name(config), "transport": now["transport"],
            "title": now["title"], "artist": now["artist"], "album": now["album"],
            "source": _DAC_SOURCE.get(now["kind"]),
            "position": now["position"], "duration": now["duration"], "index": now["index"],
            "volume": vol.get("volume"), "mute": vol.get("mute"),
            "track_id": now["track_id"], "release_id": now["release_id"],
            "cover_url": now["cover_url"],
        }
    if entity == TV:
        # a film on the television is not a record the music screens should take
        # up as their own
        said = _fresh(_house(config))
        told = said if said.get("kind") in MUSIC else {}
        vol = (await _volume(config)).get("volume")
        return {
            "name": "OPUS TV",
            "transport": ("playing" if told.get("playing") else "paused") if told else "stopped",
            "title": told.get("title") or "", "artist": told.get("artist") or "",
            "album": told.get("album") or "", "source": "library" if told else None,
            "position": told.get("position"), "duration": told.get("duration"),
            "index": told.get("index"), "volume": vol, "mute": None,
            "track_id": told.get("track_id"), "release_id": told.get("release_id"),
            "cover_url": told.get("cover_url"),
        }
    try:
        device, vol = await asyncio.gather(house.state(config, entity), _volume(config))
    except dida.DidaError as exc:
        raise HTTPException(502, str(exc))
    values = device["values"]
    index = None
    raw_queue = values.get("media_queue")
    if isinstance(raw_queue, str) and raw_queue:
        try:
            index = json.loads(raw_queue).get("current")
        except ValueError:
            index = None
    return {
        "name": device["name"],
        "transport": values.get("media_transport") or "stopped",
        "title": values.get("media_title") or "",
        "artist": values.get("media_artist") or "",
        "album": values.get("media_album") or "",
        "source": values.get("media_source"),
        "position": values.get("media_position"),
        "duration": values.get("media_duration"),
        "index": index,
        "volume": vol.get("volume"),
        "mute": vol.get("mute"),
        # a station has a picture too, and a screen following the house needs
        # something to show that is not the last record it happened to hold
        "cover_url": values.get("media_art") or None,
    }


# --- the house's half of the DAC -------------------------------------------
#
# What the house has of the television, for the DAC: what is on, the keys, and
# a record or a station put on, answering the household's service token. The
# house wakes the amplifier itself — it owns every path to it and knows which
# of its zones is meant — so nothing here touches it.


@router.get("/dac/now")
async def dac_now():
    config = await current_runtime()
    try:
        now = await dac.now()
    except dac.DacError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"name": _dac_name(config), **now}


class DacControl(BaseModel):
    command: str


@router.post("/dac/control")
async def dac_control(body: DacControl):
    if body.command not in CONTROLS:
        raise HTTPException(400, "no such command")
    try:
        await dac.control(body.command)
    except dac.DacError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True}


class DacPlay(BaseModel):
    tracks: list[CastTrack]
    start: int = 0


@router.post("/dac/play")
async def dac_play(body: DacPlay):
    if not body.tracks:
        raise HTTPException(400, "nothing to play")
    await _vetted(body.tracks)
    config = await current_runtime()
    try:
        await dac.play(_addresses(config, body.tracks),
                       max(0, min(body.start, len(body.tracks) - 1)))
    except dac.DacError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True}


# --- the television's half of the mailbox --------------------------------


@router.get("/tv/inbox")
async def tv_inbox(request: Request, seq: int | None = None, boot: str = "", sink: str = ""):
    """What the other screens want of this one. Long-polled: the wrapper asks
    with the last seq it acted on and the answer arrives the moment there is
    one, or empty after a while so the connection never grows old.

    A screen that has acted on nothing yet, or is counting from before this
    process began, is told where the count stands and handed no order: the
    last one posted is history by then."""
    tv = await _this_box(request)
    tv.seen_at = time.monotonic()
    # asleep, a box cannot say what it is plugged into; it is still where it
    # last said it was
    if sink:
        tv.sink = sink[:160]
    if seq is None or boot != tv.boot:
        return {"boot": tv.boot, "seq": tv.seq, "order": None, "control": None}
    waiting = _waiting.pop(tv.box.id, None)
    if waiting and time.monotonic() - waiting[1] < WAKE_S:
        tv.post(order=waiting[0])
    if tv.seq <= seq:
        try:
            await asyncio.wait_for(tv.wake.wait(), 25)
        except TimeoutError:
            pass
    order = tv.order if tv.order and tv.order["seq"] > seq else None
    control = tv.control if tv.control and tv.control["seq"] > seq else None
    return {"boot": tv.boot, "seq": tv.seq, "order": order, "control": control}


# what the television reports that is music, which the other screens mirror
MUSIC = ("track", "station")


class TvState(BaseModel):
    # what is on: a song, a station, a film, an episode, or `none` once it
    # stopped — the house shows each and the music screens take up only the first
    # two
    kind: str = "track"
    item_id: int | None = None
    playing: bool
    title: str = ""
    artist: str = ""
    album: str = ""
    position: float | None = None
    duration: float | None = None
    index: int | None = None
    # which song and which record, so a screen that arrives afterwards can show
    # its sleeve and its words rather than a title and nothing else
    track_id: int | None = None
    release_id: int | None = None
    cover_url: str | None = None
    # the photograph a phone is showing on it, which is beside what is on rather
    # than one of the things that can be: the radio goes on under a picture
    photo: str | None = None


@router.post("/tv/state")
async def tv_state(body: TvState, request: Request):
    tv = await _this_box(request)
    tv.state = body.model_dump()
    tv.state_at = time.monotonic()
    return {"ok": True}


# --- the house's half of the television ------------------------------------
#
# The house controls the television the way it controls everything else, from
# its own screens and its own automations, and it has no profile to pick: these
# answer the household's service token as well as a door. What is on, the keys,
# and a record or a station put on — through the same mailbox the other screens
# use, so the television has one master and never two. Each names the box it
# means, or means the house's television.


@router.get("/tv/boxes")
async def tv_boxes():
    config = await current_runtime()
    try:
        television = _house(config)
    except HTTPException:
        television = None
    boxes = [{"id": c.box.id, "name": c.box.name, "listening": c.listening,
              "house": c is television, "wakes": c is television and _wakes(config, c.box.id)}
             for c in _boxes.values()]
    # the house's television has not come to the door since this process began:
    # it is asleep, or in another app, and the house can still wake it
    chosen = config.get("tv_box")
    if chosen and int(chosen) not in _boxes and _wakes(config, int(chosen)):
        try:
            name = (await house.state(config, config.get("tv_box_entity")))["name"]
        except dida.DidaError:
            name = ""
        boxes.append({"id": int(chosen), "name": name or "OPUS TV", "listening": False,
                      "house": True, "wakes": True})
    return {"boxes": boxes}


def _wakes(config, box: int) -> bool:
    """Whether the house can wake this box and open the player on it: only the
    house's own television, and only once the house's name for it is known."""
    chosen = config.get("tv_box")
    return bool(chosen and int(chosen) == box and config.get("tv_box_entity"))


async def _send(config, box: int | None, order: dict) -> None:
    """Hand an order to a television, waking it for it when it is not listening:
    asleep, on its screensaver, in another app. The house wakes it and opens the
    player; the order waits in the mailbox until the screen asks for it."""
    channel = _house(config, box)
    if channel is not None and channel.listening:
        channel.post(order=order)
        return
    target = box if box is not None else int(config.get("tv_box") or 0)
    if not target or not _wakes(config, target):
        raise HTTPException(503, "the television is not listening")
    # a phone going through photographs sends the next before the television is
    # up; the newest order takes the place of the last, and the box already
    # being woken is not woken again
    pending = _waiting.get(target)
    if pending and time.monotonic() - pending[1] < WAKE_S:
        _waiting[target] = (order, pending[1])
        return
    try:
        await house.command(config, config.get("tv_box_entity"), "source", "set_source",
                            {"value": TV_APP})
    except dida.DidaError as exc:
        raise HTTPException(502, f"the house could not wake the television: {exc}") from exc
    _waiting[target] = (order, time.monotonic())


@router.get("/tv/now")
async def tv_now(box: int | None = None):
    """What the television is doing, for a caller that is not one of our screens.
    `listening` is whether the player is open on it at all; a television that is
    not asking for its mail cannot be told anything."""
    channel = _house(await current_runtime(), box)
    listening = channel is not None and channel.listening
    said = _fresh(channel)
    told = said if said.get("kind") != "none" else {}
    if not listening or not told:
        transport = "idle"
    else:
        transport = "playing" if told.get("playing") else "paused"
    return {
        "box": channel.box.id if channel else None,
        "listening": listening,
        "transport": transport,
        "kind": told.get("kind"),
        "item_id": told.get("item_id"),
        "title": told.get("title") or "",
        "artist": told.get("artist") or "",
        "album": told.get("album") or "",
        "cover_url": told.get("cover_url"),
        "position": told.get("position"),
        "duration": told.get("duration"),
        "index": told.get("index"),
        "track_id": told.get("track_id"),
        "release_id": told.get("release_id"),
        "photo": said.get("photo"),
    }


class TvPhoto(BaseModel):
    # the photograph to show, or none to put the one shown away
    id: str | None = Field(None, pattern=r"^[0-9a-f]{1,128}$")
    box: int | None = None


@router.post("/tv/photo")
async def tv_photo(body: TvPhoto):
    """A photograph a phone is looking at, shown on the television as well —
    the next one each time the phone moves on. The television opens it in its
    own viewer through its own door; the order carries nothing but its name."""
    config = await current_runtime()
    if body.id is not None:
        await _send(config, body.box, {"photo": body.id})
        return {"ok": True}
    channel = _house(config, body.box)
    if channel is not None and channel.listening:
        channel.post(order={"photo": None})
    return {"ok": True}


class TvShow(BaseModel):
    # somebody of the household by the name the family calls them, or the
    # family; neither is this day through the years
    person: str | None = Field(None, min_length=1, max_length=100)
    family: bool = False
    box: int | None = None


async def _of_the_family(name: str) -> int:
    """The person a name means among the family. Asked aloud, a name is all
    there is; outside the family it would reach into everybody the album has a
    face of, which is not what the house may ask for."""
    try:
        people = await library.get("/photos/people")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    said = name.casefold()
    found = {p["id"] for p in people if p.get("family")
             and said in {(p.get("given_name") or "").casefold(), (p.get("name") or "").casefold()}}
    if not found:
        raise HTTPException(404, f"nobody of the family is called {name}")
    if len(found) > 1:
        raise HTTPException(409, f"more than one of the family is called {name}")
    return found.pop()


@router.post("/tv/show")
async def tv_show(body: TvShow):
    """Photographs one after another on the television, the way its
    screensaver shows them: somebody of the family through the years, the
    family, or this day. The television opens them through its own door; the
    order carries only who."""
    if body.person and body.family:
        raise HTTPException(400, "a person or the family, not both")
    show: dict = {}
    if body.person:
        show = {"person": await _of_the_family(body.person)}
    elif body.family:
        show = {"family": True}
    await _send(await current_runtime(), body.box, {"show": show})
    return {"ok": True}


class TvBox(BaseModel):
    box: int | None = None


@router.post("/tv/resume")
async def tv_resume(body: TvBox):
    """What was being watched, put on again. Whose it was is known only on the
    television, where somebody picked who is sitting in front of it, so it is
    told to go on and finds its own place."""
    await _send(await current_runtime(), body.box, {"resume": True})
    return {"ok": True}


# a film on the television can also be sent to a place in it, and an episode
# on to the next one, which a record on the house's other outputs cannot
TV_CONTROLS = CONTROLS | {"seek", "next_episode"}


class TvControl(BaseModel):
    command: str
    box: int | None = None
    # where a seek goes, in seconds from the start
    at: float | None = None


@router.post("/tv/control")
async def tv_control(body: TvControl):
    if body.command not in TV_CONTROLS:
        raise HTTPException(400, "no such command")
    control: dict = {"command": body.command}
    if body.command == "seek":
        if body.at is None or body.at < 0:
            raise HTTPException(400, "a seek needs a place to go to")
        control["at"] = body.at
    _listening(await current_runtime(), body.box).post(control=control)
    return {"ok": True}


class TvPlay(BaseModel):
    tracks: list[CastTrack]
    start: int = 0
    box: int | None = None


@router.post("/tv/play")
async def tv_play(body: TvPlay):
    if not body.tracks:
        raise HTTPException(400, "nothing to play")
    await _vetted(body.tracks)
    config = await current_runtime()
    await _play_on_tv(config, _listening(config, body.box), body.tracks,
                      max(0, min(body.start, len(body.tracks) - 1)))
    return {"ok": True}


@router.post("/tv/video")
async def tv_video(request: Request):
    """Turn the receiver to the box asking, before its own engine starts a film.

    The box that decodes the film is the one whose input carries it — the
    Shield's for the Shield, the terrace's for the terrace — and turning the
    receiver to another sends the picture nowhere while the film plays on.
    Stopping MPD prevents the previous iFi record from continuing underneath
    the picture it has just been turned away from."""
    config = await current_runtime()
    box = await auth.device(request.cookies.get(auth.DEVICE_COOKIE))
    try:
        if await _to_box(config, box.id if box else None):
            try:
                await dac.control("stop")
            except dac.DacError:
                # The video must still be allowed to start when MPD is already down;
                # there is simply no iFi stream left to silence.
                log.info("iFi was not running while routing video", exc_info=True)
    except dida.DidaError as exc:
        # the page that asked is behind the picture by now and says it to nobody
        log.warning("the receiver was not turned to box %s: %s", box.id if box else None, exc)
        raise HTTPException(502, str(exc)) from exc
    return {"ok": True, "output": "tv"}


class BoxWiring(BaseModel):
    source: str = Field(default="", max_length=32)


@router.get("/cast/boxes")
async def cast_boxes():
    """The televisions and the receiver's input each arrives on, with the inputs
    the receiver has, for the page an admin wires the house on."""
    config = await current_runtime()
    boxes = (await tv_boxes())["boxes"]
    async with SessionLocal() as session:
        kept = {row.box_id: row for row in (await session.execute(select(BoxPreference))).scalars()}

    def wired(box: dict) -> dict:
        row, channel = kept.get(box["id"]), _boxes.get(box["id"])
        return {"id": box["id"], "name": box["name"],
                "source": row.amp_source if row else "",
                "wired_on": row.amp_sink if row else "",
                "sink": channel.sink if channel else ""}

    return {"sources": await _amp_sources(config),
            "boxes": [wired(b) for b in sorted(boxes, key=lambda b: b["name"].lower())]}


@router.put("/cast/boxes/{box_id}")
async def wire_box(box_id: int, body: BoxWiring):
    config = await current_runtime()
    sources = await _amp_sources(config)
    if body.source and sources and body.source not in sources:
        raise HTTPException(400, "the receiver has no such input")
    async with SessionLocal() as session:
        kept = await session.get(BoxPreference, box_id) or BoxPreference(box_id=box_id)
        kept.amp_source = body.source
        # wired where it is plugged in now; carried elsewhere, it is on no input
        channel = _boxes.get(box_id)
        kept.amp_sink = channel.sink if channel else ""
        session.add(kept)
        await session.commit()
    return {"id": box_id, "source": body.source}


# Where the house can send the television, in the order its own menu has them,
# and whether there is something in that place to open from afar.
LINKS = [
    {"key": "home", "path": "/", "items": False},
    {"key": "movies", "path": "/movies", "items": True},
    {"key": "series", "path": "/series", "items": True},
    {"key": "music", "path": "/music", "items": True},
    {"key": "radio", "path": "/music?find=radio", "items": True},
    {"key": "photos", "path": "/photos", "items": False},
]
_LINK = {link["key"]: link for link in LINKS}


async def _may_open_photos(request: Request) -> bool:
    return await auth.allowed(
        "/api/photos", person_cookie=request.cookies.get(opus_auth.SESSION_COOKIE),
        box=request.cookies.get(auth.DEVICE_COOKIE),
        token=request.headers.get(opus_auth.TOKEN_HEADER), bearer=auth.bearer_of(request))


@router.get("/tv/links")
async def tv_links(request: Request):
    photos = await _may_open_photos(request)
    return {"links": [link for link in LINKS if link["key"] != "photos" or photos]}


async def _shelf(key: str, lang: str) -> list[dict]:
    if key == "movies":
        return [movie_card(m) for m in await library.get("/video/movies", lang=lang)]
    if key == "series":
        return [series_card(s) for s in await library.get("/video/series", lang=lang)]
    if key == "music":
        return [artist_card(a) for a in await library.get("/music/artists")]
    if key == "radio":
        async with SessionLocal() as session:
            rows = (await session.execute(select(RadioStation))).scalars().all()
        return [{"kind": "station", "id": s.id, "title": s.name,
                 "subtitle": s.genre or s.country or "", "image": s.logo, "url": s.url}
                for s in rows]
    raise HTTPException(404, "nothing to open in that place")


@router.get("/tv/items/{key}")
async def tv_items(key: str, lang: str = "en"):
    """What can be opened in one of those places, alphabetically — a list
    somebody reads down on a phone, not a shelf walked with a remote."""
    try:
        cards = await _shelf(key, lang)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    cards.sort(key=lambda c: croatian(c.get("title") or ""))
    return {"items": [{"kind": c["kind"], "id": c["id"], "title": c.get("title") or "",
                       "subtitle": c.get("subtitle")} for c in cards]}


class TvOpen(BaseModel):
    link: str | None = None
    kind: str | None = None
    id: int | None = None
    lang: str = "en"
    box: int | None = None
    # where a film sent from another screen had got to there
    at: float | None = None


async def _film_order(body: TvOpen, sender: User | None) -> dict:
    try:
        if body.kind == "movie":
            films = await library.get("/video/movies", lang=body.lang)
            found = next((m for m in films if m["id"] == body.id), None)
            card = movie_card(found) if found else None
        else:
            episodes = await library.get("/video/episodes", ids=str(body.id), lang=body.lang)
            card = episode_card(episodes[0]) if episodes else None
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    if card is None:
        raise HTTPException(404, f"no such {body.kind}")
    order = {"film": card}
    if body.at:
        order["at"] = body.at
    if sender is not None:
        order["sent"] = auth.lend(profile_key(sender), body.kind, body.id, card.get("series_id"))
    return order


@router.post("/tv/open")
async def tv_open(body: TvOpen, request: Request):
    """Take the television somewhere, or open a thing on it — what a press on
    the television itself would do: a film or an episode plays, a series and an
    artist open their page, a station comes on."""
    if body.link == "photos" and not await _may_open_photos(request):
        raise HTTPException(403, "not yours to open")
    config = await current_runtime()
    if body.link is None and body.id is None:
        raise HTTPException(400, "nothing to open")
    # a film is sent from somebody's hand, and is worth waking the television for
    if body.link is None and body.kind in ("movie", "episode"):
        async with SessionLocal() as session:
            sender = await picked(request, session)
        await _send(config, body.box, await _film_order(body, sender))
        return {"ok": True}
    tv = _listening(config, body.box)
    if body.link is not None:
        link = _LINK.get(body.link)
        if link is None:
            raise HTTPException(404, "no such place")
        tv.post(order={"go": link["path"]})
        return {"ok": True}
    if body.kind == "series":
        tv.post(order={"go": f"/series/{body.id}"})
    elif body.kind == "artist":
        tv.post(order={"go": f"/music?open=artist:{body.id}"})
    elif body.kind == "station":
        async with SessionLocal() as session:
            station = await session.get(RadioStation, body.id)
        if station is None:
            raise HTTPException(404, "no such station")
        await _play_on_tv(config, tv, [CastTrack(id=-station.id, title=station.name,
                                                 artist=station.genre or "", cover_url=station.logo,
                                                 url=station.url)], 0)
    else:
        raise HTTPException(400, "that cannot be opened on the television")
    return {"ok": True}
