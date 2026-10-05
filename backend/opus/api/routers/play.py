"""Playing a thing: what we would do, and then the bytes.

Two calls on purpose. The plan is asked first so the surface can say plainly
what is about to happen — direct, repackaged, or re-encoded and why — and so a
refusal (no GPU for a file that needs one) arrives as an answer rather than as a
video element that never starts."""

import asyncio
import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from opus_core.responses import FileResponse

from opus import auth, library, playback
from opus.api.routers.users import require_picked
from opus.models import RadioStation, User
from opus.db import SessionLocal
from opus.settings_store import current_runtime

router = APIRouter()

KINDS = {"movie": "/video/movies", "episode": "/video/episodes",
         "track": "/music/tracks"}

# what is decided about, and what is simply handed over. The whole music library
# is FLAC and every browser this runs in decodes it, so sound has no plan worth
# making: the picture is where the GPU, the screen and the container all have an
# opinion, and sound is a file.
AUDIO_KINDS = {"track"}

AUDIO_TYPES = {"flac": "audio/flac", "mp3": "audio/mpeg", "opus": "audio/ogg",
               "vorbis": "audio/ogg", "aac": "audio/mp4", "alac": "audio/mp4",
               # MPD's dsf/dsdiff decoders pick by MIME, not by the URI's
               # suffix — confirmed against its own `decoders` listing. Get
               # this wrong and ffmpeg answers instead, decoding the DSD
               # stream to float PCM rather than handing it to the DAC native
               "dsf": "audio/x-dsf", "dff": "audio/x-dff"}

VIDEO_TYPES = {"mp4": "video/mp4", "m4v": "video/mp4", "mkv": "video/x-matroska",
               "webm": "video/webm", "m2ts": "video/mp2t", "ts": "video/mp2t",
               "avi": "video/x-msvideo", "mov": "video/quicktime"}


async def _media(kind: str, item_id: int, lang: str = "en", prefer: str | None = None) -> dict:
    if kind not in KINDS:
        raise HTTPException(404, "nothing of that kind can be played yet")
    # which edition of a song — DSD for the DAC — is a question only a track
    # has an answer to; a film has no "prefer" the library would understand
    params = {"lang": lang, **({"prefer": prefer} if kind in AUDIO_KINDS and prefer else {})}
    try:
        media = await library.get(f"{KINDS[kind]}/{item_id}/playback", **params)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    if not await asyncio.to_thread(os.path.exists, media["path"]):
        raise HTTPException(
            409,
            f"the library says the file is at {media['path']}, and it is not "
            "reachable from here",
        )
    return media


def _first_held(wanted: str, held: list[str]) -> str:
    for code in (c.strip() for c in (wanted or "").split(",")):
        if code and code in held:
            return code
    return ""


def _from_library(media: dict) -> dict:
    """What the library recorded about the file, in the shape this module reads.

    It used to open the file and run ffprobe on every play — an 89 GB remux, to
    learn what the library already knew. The library owns what a file is; if a
    field is missing here it is missing THERE, and the answer is to record it
    rather than to go behind its back."""
    streams = media.get("streams") or []
    return {
        "duration_s": media.get("duration_s"),
        "audio": [
            {"index": s["position"], "lang": s["lang"], "codec": s["codec"],
             "channels": s["channels"], "title": s.get("title") or ""}
            for s in streams if s["kind"] == "audio"
        ],
        "hdr": any(s["kind"] == "video" and s.get("color_transfer") in playback.HDR_TRANSFERS
                   for s in streams),
        # a television can run at the film's own rate, but only if something
        # tells it what that is — and the container usually does not
        "frame_rate": next((s.get("frame_rate") for s in streams
                            if s["kind"] == "video" and s.get("frame_rate")), None),
    }


@router.get("/play/{kind}/{item_id}/plan")
async def plan(kind: str, item_id: int, can_decode: bool = False,
               max_height: int | None = None, max_width: int | None = None,
               audio: int = 0, native: bool = False, rebuild_audio: bool = False, lang: str = "en",
               who: User = Depends(require_picked)):
    media = await _media(kind, item_id, lang)
    if kind in AUDIO_KINDS:
        return {
            "title": media["title"], "artist": media.get("artist"),
            "album": media.get("album"), "cover_url": media.get("cover_url"),
            "duration_s": media.get("duration_s"),
            "audio": [], "subtitles": [], "running": playback.running(),
            "mode": "direct", "reason": "the browser decodes this itself",
            "width": None, "height": None, "gpu": playback.gpu_available(),
            "source": {"container": media.get("codec"), "video_codec": None,
                       "width": None, "height": None, "size": media.get("size"),
                       "bitrate_kbps": media.get("bitrate_kbps"),
                       "sample_rate_hz": media.get("sample_rate_hz"),
                       "bit_depth": media.get("bit_depth")},
        }
    facts = _from_library(media)
    chosen = playback.decide(media, can_decode=can_decode, max_height=max_height,
                             max_width=max_width, audio=audio, native=native,
                             rebuild_audio=rebuild_audio)
    # by the library's own id for the track: its place in a list is not
    # something the next request can count on, and asking for Croatian and
    # being read Bulgarian is what trusting it looked like
    subs = [
        {"id": sub["id"], "lang": sub["lang"], "codec": sub.get("format") or "",
         "title": "", "external": sub.get("source") == "external",
         "forced": sub["forced"]}
        for sub in media.get("subtitles") or []
        if sub.get("path")
    ]
    return {
        "title": media["title"],
        "audio": facts["audio"],
        "duration_s": facts["duration_s"],
        "subtitles": subs,
        "running": playback.running(),
        "year": media.get("year"),
        "runtime_min": media.get("runtime_min"),
        "backdrop_url": media.get("backdrop_url"),
        "details": media.get("details") or {},
        "source": {
            "container": media.get("container"),
            "video_codec": media.get("video_codec"),
            "width": media.get("width"),
            "height": media.get("height"),
            "size": media.get("size"),
            "frame_rate": facts["frame_rate"],
        },
        # where the film changes scene, as the disc that made it said. Ten
        # seconds at a time is how you look for something you nearly remember;
        # chapters are how you find it.
        "chapters": media.get("chapters") or [],
        "credits_s": media.get("credits_s"),
        "intro_s": media.get("intro_s"),
        "intro_end_s": media.get("intro_end_s"),
        # an episode's place in its season, and the one after it if it is here
        "season_left": media.get("season_left"),
        "next": media.get("next"),
        "mode": chosen.mode,
        "reason": chosen.reason,
        "width": chosen.width,
        "height": chosen.height,
        "gpu": playback.gpu_available(),
        # what the house comes up in when a film offers a choice — answered once
        # in settings rather than per film
        # the profile answers with an order; what is asked for is the first of
        # them this file actually has, because a second choice only means
        # anything once the first one is missing
        "preferred": {
            "audio": _first_held(who.audio_languages,
                                 [a["lang"] for a in facts["audio"]]),
            "subtitle": _first_held(who.subtitle_languages,
                                    [s["lang"] for s in subs]),
        },
    }


def stream_url(config, track_id: int, codec: str | None, prefer: str = "stereo") -> str:
    """The address a renderer in the house fetches a song from: this module's
    LAN face, the item's ticket, and the format spelled at the very end — kept
    for the Android app's own player, which reads it; MPD on the DAC picks its
    decoder from this response's own MIME type (AUDIO_TYPES), not the address.

    `prefer` asks the library for a specific edition of the track — "dsd" for
    the DAC, which plays it natively, never for a renderer that cannot. A track
    with no such edition gets back whatever it does hold, same as `prefer`
    everywhere else in this player."""
    base = (config.get("stream_base") or "").rstrip("/")
    if not base:
        raise HTTPException(503, "stream_base is not configured, and a renderer "
                                 "cannot fetch from a relative path")
    prefix = f"/api/play/track/{track_id}/"
    ticket = auth.play_ticket(prefix)
    suffix = (codec or "").strip(".").lower() or "flac"
    return f"{base}{prefix}stream?ticket={ticket}&prefer={prefer}&fmt=.{suffix}"


def _queued(config, t: dict, prefer: str) -> dict:
    return {
        "id": t["id"], "release_id": t.get("release_id"),
        "title": t.get("title") or "", "artist": t.get("artist") or "",
        "album": t.get("album") or "", "art": t.get("cover_url") or "",
        "duration_s": t.get("duration_s"), "codec": t.get("codec"),
        "channels": t.get("channels"), "live": False,
        "uri": stream_url(config, t["id"], t.get("codec"), prefer=prefer),
    }


@router.get("/play/queue")
async def queue(kind: str, id: int, prefer: str = "stereo"):
    """A record, a song or a station as the house's own devices can be handed
    it: every row with the address its bytes are fetched from.

    For the house, not for this player's screens — they build their queue
    themselves and cast it through `/cast/play`, which also wakes the amplifier.
    The house already owns the amplifier and every path to it, so it is handed
    the sentence and nothing else: what to play, in what order, from where.
    The ticket on every address is twelve hours, and a station carries the
    address somebody else keeps alive, exactly as the cast does."""
    async with SessionLocal() as session:
        config = await current_runtime()
        if kind == "station":
            found = await session.get(RadioStation, id)
            if found is None:
                raise HTTPException(404, "no such station")
            return {"kind": kind, "id": id, "title": found.name, "tracks": [{
                "id": -found.id, "release_id": None, "title": found.name,
                "artist": found.genre or "", "album": "", "art": found.logo or "",
                "duration_s": None, "codec": None, "channels": None,
                "live": True, "uri": found.url,
            }]}
    if kind == "release":
        try:
            record = await library.get(f"/music/releases/{id}/playback",
                                       prefer=prefer)
        except library.NotInLibrary:
            raise HTTPException(404, "no such record")
        except library.LibraryError as exc:
            raise HTTPException(502, str(exc))
        return {"kind": kind, "id": id, "title": record.get("title") or "",
                "artist": record.get("artist") or "", "art": record.get("cover_url") or "",
                "tracks": [_queued(config, t, prefer) for t in record.get("tracks") or []]}
    if kind == "track":
        try:
            song = await library.get(f"/music/tracks/{id}/playback", prefer=prefer)
        except library.NotInLibrary:
            raise HTTPException(404, "no such song")
        except library.LibraryError as exc:
            raise HTTPException(502, str(exc))
        return {"kind": kind, "id": id, "title": song.get("title") or "",
                "artist": song.get("artist") or "", "art": song.get("cover_url") or "",
                "tracks": [_queued(config, song, prefer)]}
    raise HTTPException(404, "nothing of that kind can be queued")


@router.get("/play/{kind}/{item_id}/ticket")
async def ticket(kind: str, item_id: int):
    """A URL the television's own engine can fetch.

    The native TV engine opens the file itself and has no session to carry, so
    the bytes have to be reachable by something holding only a link. The ticket signs the stream
    path, not the query on it — seeking and switching audio track re-ask the
    same path, and re-issuing a ticket for every seek would be a round trip in
    the middle of watching."""
    if kind not in KINDS:
        raise HTTPException(404, "unknown kind")
    prefix = f"/api/play/{kind}/{item_id}/"
    return {"prefix": prefix, "ticket": auth.play_ticket(prefix)}


# HEAD as well as GET: an engine that fetches the bytes itself asks what is there
# before asking for it, and a 405 to that question is an answer we do not mean.
async def rebuilt(request: Request, command: list[str], mode: str, what: str,
                  media_type: str = "video/mp4") -> StreamingResponse:
    """A remux or a transcode, answered while it is being made."""
    async def gone() -> bool:
        return await request.is_disconnected()

    # the same viewer starting the same title again HAS abandoned their old
    # stream, whether or not the hops between the browser and here say so
    bearer = auth.bearer_of(request)
    car = bearer if bearer and await auth.person(None, bearer) is not None else None
    marker = (car or request.cookies.get(auth.SESSION_COOKIE)
              or request.cookies.get(auth.DEVICE_COOKIE)
              or request.query_params.get("ticket"))
    viewer = f"{hashlib.sha256(marker.encode()).hexdigest()}:{what}" if marker else None
    try:
        body = playback.stream(command, is_gone=gone, kind=mode, viewer=viewer)
        first = await body.__anext__()
    except playback.PlaybackError as exc:
        raise HTTPException(503, str(exc))
    except StopAsyncIteration:
        raise HTTPException(502, "the encoder produced nothing; see the player log")

    async def rest():
        yield first
        async for chunk in body:
            yield chunk

    return StreamingResponse(
        rest(), media_type=media_type, headers={"Cache-Control": "no-store"}
    )


@router.get("/play/{kind}/{item_id}/stream")
@router.head("/play/{kind}/{item_id}/stream")
async def stream(kind: str, item_id: int, request: Request, can_decode: bool = False,
                 max_height: int | None = None, max_width: int | None = None,
                 t: float = 0, audio: int = 0, native: bool = False,
                 rebuild_audio: bool = False, accepts: str = "", channels: int = 0,
                 prefer: str = "stereo", compact: bool = False):
    media = await _media(kind, item_id, prefer=prefer)
    if kind in AUDIO_KINDS:
        return await _audio_stream(request, kind, item_id, media, compact)
    facts = _from_library(media)
    chosen = playback.decide(media, can_decode=can_decode, max_height=max_height,
                             max_width=max_width, audio=audio, native=native,
                             rebuild_audio=rebuild_audio)

    # Starlette answers HEAD for a file by itself, but a re-encode has no length
    # to declare and no reason to start an encoder nobody is going to read.
    if request.method == "HEAD" and chosen.mode != "direct":
        return Response(status_code=200, media_type="video/mp4")

    if chosen.mode == "direct":
        # the file as it is, and Starlette answers Range for it, so seeking is
        # the client's own business and costs nothing here. The type is the one
        # the file actually is: a television engine handed video/mp4 for a
        # Matroska file believes the label over the bytes.
        return FileResponse(media["path"],
                            media_type=VIDEO_TYPES.get(
                                (media.get("container") or "").lower(),
                                "application/octet-stream"))

    command = await _rebuild_command(media, chosen, facts, t, audio,
                                     _sound(facts, audio, accepts, channels))
    return await rebuilt(request, command, chosen.mode, f"{kind}:{item_id}")


async def _audio_stream(request: Request, kind: str, item_id: int, media: dict,
                        compact: bool):
    # A car asks explicitly for this path after its owner enables Data
    # Saver. ``fmt`` describes the source suffix in old Android URLs, so a
    # separate boolean keeps every installed client on direct-file playback.
    if compact:
        # Like video remuxes, an audio conversion has no size to declare;
        # HEAD must describe it without starting an encoder that nobody
        # will drain.
        if request.method == "HEAD":
            return Response(status_code=200, media_type="audio/ogg")
        return await rebuilt(
            request, playback.compact_audio_command(media["path"]), "audio",
            f"{kind}:{item_id}", media_type="audio/ogg",
        )
    # Starlette answers Range for a file, which is the whole of what seeking
    # in a song needs
    return FileResponse(
        media["path"],
        media_type=AUDIO_TYPES.get(media.get("codec") or "", "application/octet-stream"))


def _sound(facts: dict, audio: int, accepts: str, channels: int) -> playback.Sound:
    """What the renderer can be handed decides what the sound becomes: a box
    wired to an amplifier keeps the film's channels, a browser gets the two
    its speakers have. Asked of the renderer, never assumed."""
    track = next((a for a in facts["audio"] if a["index"] == audio),
                 facts["audio"][0] if facts["audio"] else None)
    return playback.sound_for((track or {}).get("codec", ""),
                              (track or {}).get("channels") or 0,
                              accepts.split(","), channels)


async def _rebuild_command(media: dict, chosen: playback.Plan, facts: dict, t: float,
                           audio: int, sound: playback.Sound) -> list[str]:
    try:
        if chosen.mode == "remux" and t:
            t = await playback.snap_start(media["path"], t)
        return (
            playback.remux_command(media["path"], t, audio, sound)
            if chosen.mode == "remux"
            else playback.transcode_command(media["path"], chosen.width or 1920,
                                            chosen.height or 1080, t, audio,
                                            hdr=facts["hdr"], sound=sound,
                                            codec=(media.get("video_codec") or "").lower())
        )
    except playback.PlaybackError as exc:
        raise HTTPException(503, str(exc))


@router.get("/play/track/{track_id}/lyrics")
async def lyrics(track_id: int, refresh: bool = False):
    """The words to a song, from the library that keeps them. Passed through
    rather than fetched here: which words belong to which recording is a fact
    about the catalogue, and the player has none — the same reason it asks what
    an album holds instead of remembering it."""
    try:
        return await library.get(f"/music/tracks/{track_id}/lyrics",
                                 refresh=refresh)
    except library.NotInLibrary as exc:
        raise HTTPException(404, str(exc))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/play/release/{release_id}/lyrics")
async def release_lyrics(release_id: int):
    """Which songs on a record have words, for the mark beside each of them.
    Asked once as the record opens rather than a song at a time: the mark is
    drawn before anything is pressed."""
    try:
        return await library.get(f"/music/releases/{release_id}/lyrics")
    except library.NotInLibrary as exc:
        raise HTTPException(404, str(exc))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/play/stats")
async def stats():
    """What the box is doing, for the panel that shows it. Deliberately about
    processes and not about taste: how many pictures are being re-encoded, what
    each costs, and what the machine as a whole is carrying."""
    return {
        "gpu": playback.render_node(),
        "transcodes": playback.in_flight(),
        "other": playback.in_flight(kind=None),
        "limit": playback.MAX_CONCURRENT,
        **playback.host_load(),
    }


@router.get("/play/{kind}/{item_id}/subs/{sub_id}.vtt")
async def subtitles(kind: str, item_id: int, sub_id: int, t: float = 0,
                    snap: bool = False):
    """One subtitle track as WebVTT.

    Only tracks that already exist as a FILE are served: pulling one out of an
    89 GB remux means reading the whole container, measured at 183 seconds,
    which is about 180 seconds after the browser has given up and shown
    nothing. Getting the embedded ones out is the library's job, once."""
    media = await _media(kind, item_id)
    track = next((sub for sub in media.get("subtitles") or [] if sub["id"] == sub_id), None)
    if track is None or not track.get("path"):
        raise HTTPException(404, "no such subtitle track")
    if not await asyncio.to_thread(os.path.exists, track["path"]):
        raise HTTPException(
            409, f"the library says the subtitle is at {track['path']}, "
                 "and it is not reachable from here")
    try:
        if t and snap:
            # a remux started at t actually begins on the keyframe before it, and
            # the cues must agree with the stream, not with the request
            t = await playback.snap_start(media["path"], t)
        body = playback.stream(playback.subtitle_command(track["path"], None), kind="subtitle")
        first = await body.__anext__()
    except playback.PlaybackError as exc:
        raise HTTPException(503, str(exc))
    except StopAsyncIteration:
        first = b""
    if not t:
        async def rest():
            yield first
            async for chunk in body:
                yield chunk

        return StreamingResponse(rest(), media_type="text/vtt")
    # a whole subtitle track is a couple of hundred kilobytes; collecting it to
    # rebase the cues costs nothing next to the film it belongs to
    whole = first + b"".join([chunk async for chunk in body])
    return Response(playback.shift_vtt(whole.decode("utf-8", "replace"), t),
                    media_type="text/vtt")
