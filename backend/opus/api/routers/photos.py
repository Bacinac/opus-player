"""The household's photographs, asked of the library like everything else.

The player kept a client for Immich here once, because the pictures were the one
part of the catalogue nobody had published. They are published now — catalogued
by content, with faces gathered into people, places worked out from coordinates
and dates read off the cameras — so this is a proxy and nothing more. Nothing is
cached: the library serves its derivatives off local disk and the two run on the
same machine, so a copy here would only be a copy to fall behind.

The pictures themselves are streamed rather than read into memory. A shelf of
photographs is a hundred requests for a hundred thumbnails, and a screen that
holds each one whole before passing it on is a screen that holds a hundred.
A recording a screen cannot open is the one thing rebuilt here, from the file."""

import asyncio
import os
import random
import re
from dataclasses import dataclass
from typing import Annotated

import httpx
import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, library, playback
from opus.api.routers.play import rebuilt
from opus.api.routers.users import picked
from opus.config import settings
from opus.db import get_session

router = APIRouter()

# A derivative of a photograph is named by the digest of what it was made from,
# so it can never change and the browser may keep it for as long as it likes.
FOREVER = "private, max-age=31536000, immutable"

# A face and a person are named by their id, not by their content. A portrait is
# stable in practice and a day is a fair bet on it; a morph is remade whenever
# somebody gains a year or a group is corrected, and marking that immutable
# would mean the new one is never seen. It is asked about every time and answered
# from the cache when it has not changed.
A_DAY = "private, max-age=86400"
ASK_AGAIN = "private, no-cache"

# what the library calls the two sizes it keeps
SIZES = {"tile", "preview"}

CHECKSUM = re.compile(r"^[0-9a-f]{40}$")


def _checked(checksum: str) -> str:
    if not CHECKSUM.match(checksum):
        raise HTTPException(404, "no such photograph")
    return checksum


async def _ask(path: str, **params):
    try:
        return await library.get(path, **params)
    except library.NotInLibrary:
        raise HTTPException(404, "the library has no such thing")
    except library.LibraryError as why:
        # the catalogue being unreachable is not an empty catalogue, and the
        # screen has to be able to tell the two apart
        raise HTTPException(502, str(why))


@dataclass(frozen=True)
class Whose:
    """Whose photographs a screen is narrowed to — any of a few people, the
    family or the household — in the library's words and passed on as they
    came: what each of them means is said once, there, for every screen."""

    person: Annotated[list[int] | None, Query()] = None
    family: bool = False
    household: bool = False

    def params(self) -> dict[str, object]:
        said: dict[str, object] = {}
        if self.person:
            said["person"] = self.person
        if self.family:
            said["family"] = "true"
        if self.household:
            said["household"] = "true"
        return said


@router.get("/photos/search")
async def search(q: str = Query(max_length=200)):
    """How the library read a search: who, where and when each word named."""
    return await _ask("/photos/search", q=q)


@router.get("/photos/timeline/buckets")
async def buckets(place: str = "", whose: Whose = Depends(),
                  q: str = Query("", max_length=200)):
    """How many photographs fall in each month, which is what a rail is drawn
    from and what says which years the house even has.

    Narrowed exactly as the pages are, or the rail counts one library while the
    shelf shows another: a rail offering 2001 to somebody born in 2005 is a
    scrubber that lies about where there is anything to find."""
    params = whose.params()
    if place:
        params["place"] = place
    if q:
        params["q"] = q
    return await _ask("/photos/timeline/buckets", **params)


@router.get("/photos/timeline")
async def shelf(before: str = "", before_id: int | None = None, place: str = "",
                whose: Whose = Depends(), month: str = "",
                q: str = Query("", max_length=200), limit: int = Query(120, le=500)):
    """A page of the shelf, newest first.

    The cursor is the pair the library handed back, carried through untouched: a
    caller that worked out where it had got to would be a second place that has
    to agree about how a burst sharing one second is ordered."""
    params = {"limit": limit, **whose.params()}
    if before:
        params["before"] = before
    if before_id is not None:
        params["before_id"] = before_id
    if place:
        params["place"] = place
    if month:
        params["month"] = month
    if q:
        params["q"] = q
    return await _ask("/photos/timeline", **params)


@router.get("/photos/onthisday")
async def on_this_day(month: int | None = None, day: int | None = None,
                      span: int | None = None, least: int = 0,
                      whose: Whose = Depends(), limit: int = Query(400, le=500)):
    """This day, through the years it has been photographed.

    The day is the library's to decide when it is not given: it keeps the
    household's zone, and a browser that sent its own idea of today would put
    a photograph taken at half past eleven at night on the following morning."""
    params: dict[str, object] = {"limit": limit, **whose.params()}
    if month is not None:
        params["month"] = month
    if day is not None:
        params["day"] = day
    if span is not None:
        params["span"] = span
    if least:
        params["least"] = least
    return await _ask("/photos/onthisday", **params)


@router.get("/photos/years")
async def years(whose: Whose = Depends(), each: int = Query(12, ge=1, le=100)):
    """One person through the years, or the family: a handful out of each year,
    drawn afresh every time it is asked."""
    return await _ask("/photos/years", each=each, **whose.params())


@router.get("/photos/screensaver")
async def screensaver(request: Request, session: AsyncSession = Depends(get_session)):
    """Whose photographs a box's screensaver shows while a profile is picked
    on it, as the narrowing the library's day takes. A profile left as it came
    is whoever it is — the face the roster's account points at — and one the
    library has no face for is the household, as a box with nobody picked is."""
    who = await picked(request, session)
    chosen = who.screensaver if who else ""
    if chosen == "household":
        return {"household": True}
    if chosen:
        return {"person": [int(one) for one in chosen.split(",")]}
    if who is not None and who.person:
        own = [p["id"] for p in await _ask("/photos/people") if p.get("account") == who.person]
        if own:
            return {"person": own[:1]}
    return {"household": True}


# a handful from every year, so a wall that is left on takes the years in turns
WALL_EACH = 4


@router.get("/photos/wall")
async def wall(count: int = Query(30, ge=1, le=100)):
    """The household's photographs for a screen in the house that is nobody's —
    the wall panel home automation drives. The same draw a box's screensaver
    takes with nobody picked, and nothing narrower: whoever asks can only ask
    for another handful. Only what a still frame can show: a recording, or a
    photograph whose derivatives are not made or never will be, is left out."""
    drawn = await _ask("/photos/years", each=WALL_EACH, household="true")
    shown = [p for year in drawn.get("years") or [] for p in year.get("photographs") or []
             if p.get("kind") != "video" and p.get("ready") and not p.get("undecodable")]
    random.shuffle(shown)
    told = await asyncio.gather(*(_ask(f"/photos/{p['id']}") for p in shown[:count]))
    return {"photos": [{"id": one["id"], "taken_at": one.get("taken_at"),
                        "place": one.get("place"), "country": one.get("country")}
                       for one in told]}


@router.get("/photos/people")
async def people():
    """Everyone the library has gathered a face into, each with the portrait it
    would show them by."""
    return await _ask("/photos/people")


@router.get("/photos/places")
async def places():
    return await _ask("/photos/places")


async def _send(http: httpx.AsyncClient, request: httpx.Request) -> httpx.Response:
    try:
        return await http.send(request, stream=True)
    except httpx.HTTPError as why:
        raise HTTPException(502, f"the library could not be reached ({type(why).__name__})")


def _passed_on(status: int) -> int:
    """What the library said, as this module says it. A refusal of this
    module's own credentials is this module failing, not the person asking."""
    return 502 if status in (401, 403) else status


async def _stream(path: str, kind: str, keeping: str = FOREVER, asked: Request | None = None):
    http = library.client(timeout=60)
    # A player asks for the middle of a recording before it has the beginning,
    # and gets nothing if the range is dropped on the way through.
    passing = {}
    if asked and (span := asked.headers.get("range")):
        passing["Range"] = span
    resp = await _send(http, http.build_request("GET", path, headers=passing))
    if resp.status_code not in (200, 206):
        await resp.aclose()
        raise HTTPException(_passed_on(resp.status_code), "the library would not give that picture")

    async def bytes_through():
        # the response is closed, the client is not: it is shared, and closing it
        # would hang up on every other picture on the same screen. A hundred and
        # twenty thumbnails opening a connection each was two and a quarter
        # seconds where the pool is one and a quarter.
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()

    carried = {"Cache-Control": keeping}
    for name in ("content-range", "accept-ranges", "content-length"):
        if name in resp.headers:
            carried[name] = resp.headers[name]
    return StreamingResponse(
        bytes_through(), status_code=resp.status_code,
        media_type=resp.headers.get("content-type", kind),
        headers=carried,
    )


# Everything a vault answers to, carried through untouched. One route rather
# than a dozen because this module decides nothing about a vault: it holds no
# key, cannot read a byte of one, and its only contribution is to say which
# person is asking. Library owns every rule, and a rule copied here would be a
# rule that can disagree.
VAULT = "/photos/vault"

# What may follow the vault's own address: its fixed words and the ids of files,
# and nothing that a URL parser would resolve into a different route.
VAULT_REST = re.compile(r"^(/[A-Za-z0-9_-]+)*$")

# The connection a person's own requests go down. Not the one in opus.library:
# that one carries this module's token, and the library trusts a token before it
# asks who anybody is — a person's request carried with it would be the module
# acting, with every rule about that person skipped.
_as_people: httpx.AsyncClient | None = None


def _personal() -> httpx.AsyncClient:
    global _as_people
    if _as_people is None or _as_people.is_closed:
        _as_people = httpx.AsyncClient(
            base_url=f"{settings.library_url.rstrip('/')}/api", timeout=600,
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=32))
    return _as_people


async def _as_the_person(request: Request, path: str, refusal: str) -> StreamingResponse:
    """Carry a request to the library under the name of whoever is signed in.

    The **person's** cookie goes with it, never this module's token: a token is
    not a person, and both the things carried this way — a vault and a gift to
    the household — belong to one. That is also why a television reaches
    neither: it came through the household door and has no such cookie.

    Streamed in both directions, so a video passes through rather than being
    held whole at either end."""
    person = request.cookies.get(opus_auth.SESSION_COOKIE)
    if not person or await auth.person(person) is None:
        raise HTTPException(403, refusal)

    headers = {"content-type": request.headers.get("content-type", "application/json"),
               "X-Forwarded-For": opus_auth.client_address(request)}
    # the size the device announced goes on with the body: without it the
    # library can only refuse a file too large for it after it has all arrived
    if "content-length" in request.headers:
        headers["content-length"] = request.headers["content-length"]
    for name in ("range", "if-range"):
        if name in request.headers:
            headers[name] = request.headers[name]
    http = _personal()
    upstream = http.build_request(
        request.method, path,
        params=dict(request.query_params),
        content=request.stream(),
        headers=headers,
        cookies={opus_auth.SESSION_COOKIE: person},
    )
    resp = await _send(http, upstream)

    async def through():
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()

    return StreamingResponse(
        through(), status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
        headers={"Cache-Control": "no-store", **{
            name: resp.headers[name] for name in
            ("x-vault-at", "x-vault-bytes", "content-range", "accept-ranges") if name in resp.headers
        }},
    )


@router.post("/photos/offer")
async def offer(request: Request):
    """A photograph given straight to the household, without a vault in the way.

    Keeping and giving are separate wishes, and the second must not wait on the
    first: somebody who will never want a private corner still has the evening
    everyone else is asking for. The library decides everything about what
    arrives — this only says whose it is."""
    return await _as_the_person(request, "/photos/offer",
                                "a picture is given by somebody, and none is signed in")


@router.get("/photos/vault{rest:path}")
@router.head("/photos/vault{rest:path}")
@router.post("/photos/vault{rest:path}")
@router.put("/photos/vault{rest:path}")
@router.patch("/photos/vault{rest:path}")
@router.delete("/photos/vault{rest:path}")
async def vault(rest: str, request: Request):
    """A person's own corner of the photographs, which is theirs and not the
    house's.

    The **person's** cookie goes with the request, never this module's token: a
    token is not a person, and a vault belongs to one. That is also why a
    television cannot reach any of this — it came through the household door and
    has no such cookie to forward. Nothing is switched off; there is simply
    nobody to be.

    Streamed in both directions. A picture goes up sealed in pieces of four
    megabytes and comes back the same way, and a module that held either end
    whole would put a phone's memory problem on the server."""
    if not VAULT_REST.match(rest):
        raise HTTPException(404, "no such place in a vault")
    return await _as_the_person(request, f"{VAULT}{rest}",
                                "a vault belongs to a person, and none is signed in")


@router.get("/photos/{checksum}")
async def photograph(checksum: str):
    """One photograph and what the library knows about it: who is in it, where
    it was taken, how it was dated. What the viewer draws its face boxes and its
    place name from — and what it was asking for and not getting, which is why a
    picture opened with "Not Found" beside it."""
    return await _ask(f"/photos/{_checked(checksum)}")


# what a browser plays inside an mp4 without being given anything else
BROWSER_SOUND = {"aac", "mp3", "opus", "flac"}
# a recording rebuilt for a browser is rebuilt for a screen, not for a 4K master
REBUILT_BOX = (1920, 1080)


@router.get("/photos/{checksum}/play")
async def play(checksum: str, request: Request, decodes: str = ""):
    """The recording, in the form this screen can play. `decodes` is what the
    device said it decodes efficiently; the rest is decided the way a film is. A
    phone's h264 goes through untouched, with ranges, as it always did. A DivX
    from 2005, a 3GP, an iPhone's HEVC on a screen without the codec, or a
    picture carried with PCM sound is rebuilt — and was a black box before."""
    checked = _checked(checksum)
    media = await _ask(f"/photos/{checked}/playback")
    codec = (media.get("video_codec") or "").lower()
    sound = next((s for s in media.get("streams") or [] if s["kind"] == "audio"), None)
    chosen = playback.decide(
        media, max_height=None,
        can_decode=codec in {c.strip().lower() for c in decodes.split(",") if c.strip()})
    if chosen.mode == "direct" and sound and (sound["codec"] or "").lower() not in BROWSER_SOUND:
        chosen = playback.Plan("remux", f"a browser does not play {sound['codec']} sound",
                               chosen.width, chosen.height, codec)
    if chosen.mode == "direct":
        return await _stream(f"/photos/{checked}/play", "video/mp4", FOREVER, request)

    if not await asyncio.to_thread(os.path.exists, media["path"]):
        raise HTTPException(409, f"the library says the recording is at {media['path']}, "
                                 "and it is not reachable from here")
    width, height = chosen.width or REBUILT_BOX[0], chosen.height or REBUILT_BOX[1]
    if width > REBUILT_BOX[0] or height > REBUILT_BOX[1]:
        width, height = playback.fit(width, height, *REBUILT_BOX)
    hdr = any(s["kind"] == "video" and s.get("color_transfer") in playback.HDR_TRANSFERS
              for s in media.get("streams") or [])
    try:
        command = (playback.remux_command(media["path"])
                   if chosen.mode == "remux"
                   else playback.transcode_command(media["path"], width, height, hdr=hdr,
                                                   codec=codec))
    except playback.PlaybackError as exc:
        raise HTTPException(503, str(exc))
    return await rebuilt(request, command, chosen.mode, f"photo:{checked}")


@router.get("/photos/{checksum}/{size}")
async def picture(checksum: str, size: str):
    """One photograph at the size the screen draws it.

    Only the two the library actually keeps: a route that forwards whatever size
    it is handed is a route that asks the library to encode anything anybody
    types."""
    if size not in SIZES:
        raise HTTPException(404, "no such size")
    return await _stream(f"/photos/{_checked(checksum)}/{size}", "image/avif")


@router.get("/photos/faces/{face_id}/crop")
async def crop(face_id: int):
    """A rectangle around the face box. What a grid of people is drawn from,
    because it needs nothing but the box the face was found in."""
    return await _stream(f"/photos/faces/{face_id}/crop", "image/jpeg", A_DAY)


@router.get("/photos/faces/{face_id}/portrait")
async def portrait(face_id: int):
    """The same face turned upright and framed like every other, which needs the
    mesh the library computes lazily — so it is asked for where one face is
    looked at, never for a screenful."""
    return await _stream(f"/photos/faces/{face_id}/portrait", "image/jpeg", A_DAY)


@router.get("/photos/people/{person_id}/morph")
async def morph(person_id: int, size: int = 448):
    """A person's face carried through every year there is one of them. The
    library makes it once and keeps it; this hands it over.

    The size is carried because a wall of them asks for the width it will draw:
    a hundred and twenty-three at full size is a stall, and the library keeps
    each width as its own file."""
    return await _stream(f"/photos/people/{person_id}/morph?size={size}",
                         "image/webp", ASK_AGAIN)
