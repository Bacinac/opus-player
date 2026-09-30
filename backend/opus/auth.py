"""Who may talk to the player.

**One credential, and two things it can be worth.** There is one password in
this house and it is kept next door, on the roster Library keeps. This module
holds none of its own and compares none: it asks, and what it hands back depends
on what is asking.

A phone or a laptop gets a **person** session — the same cookie Library and
Downloads issue, against the same roster, so somebody who signed in there is
signed in here. It proves a person, and it is the only thing anything private
will ever answer to. A month long, because a session that says who somebody is
should not outlive the phone it was made on.

A **television** gets a household session instead: this box is one of ours, and
nothing at all about who is holding the remote. A decade long, because a
television is not a browser you sign into every month and asking somebody to
type a password with a remote is the kind of friction that makes a surface stop
being used.

The distinction is not tidiness. On a sofa a profile is *picked*, not proved —
four arrow keys and nothing else — so a television genuinely has no answer to
"who is this", and the honest thing is for it not to pretend. Anything that
belongs to one person rather than to the house asks for a person and is
therefore simply absent from a television: nothing to switch off, and nothing to
get wrong. A control that hides a vault is a promise about our conduct; having
nobody for the vault to belong to is a fact about the system.

Which surface is asking is taken from the client and cannot be checked. It does
not need to be: claiming to be a television only ever hands back less than the
truth would, and there is no claim in the other direction — nothing turns a box
into a person."""

import hashlib
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import opus_auth
from opus_auth import ADMIN, GUEST
from opus_auth.authority import Authority, Person

from opus.config import settings
from opus.db import SessionLocal
from opus.models import CarToken
from opus.settings_store import current_runtime

log = logging.getLogger(__name__)

# Which profile is watching, and NOTHING ELSE — never a door. A cookie that
# authorises is a cookie that survives a change of doors: a television carrying
# one would be inside without ever having been let in, on no list, and therefore
# impossible to take back. That is the exact failure the device list exists to
# prevent.
#
# It is signed all the same. Not to prove anybody — it proves nothing — but so
# that the marker inside it is one this module wrote, rather than a profile
# somebody named in a request.
SESSION_COOKIE = "opus_player_session"
# A choice of profile is not asked again every month: on a television it is four
# arrow keys once, and re-asking it is friction with nothing bought.
SESSION_MAX_AGE = 3650 * 24 * 3600

# what answers before anyone has proved anything: liveness, and the exchange
# that proves it. Letting go of a session must not be able to fail because the
# session is already gone.
#
# And the pictures. Every one of them is fetched from a public image service the
# catalogue names, so there is nothing behind the route to protect — while a
# credential in its address, which is the only way Android Auto can send one,
# was a credential handed to every app that can read a browse tree.
OPEN_PATHS = ("/api/ping", "/api/ready", "/api/auth/login", "/api/auth/session", "/api/auth/logout",
              "/api/auth/passkey/options", "/api/auth/passkey/login", "/api/art")

# and the exchange a box goes through, which cannot ask for a credential it is
# in the middle of being given. A prefix rather than a name because the second
# half of it carries which request is being watched. Nothing behind these is
# worth anything without somebody next door saying yes.
# and handing the Android app to a phone. It has to be open or it cannot work:
# what scans the square is a camera on a phone that has never signed in here, and
# a download that lands on a login page is not a download. Nothing is given away
# — the APK is signed, carries no credential, and points at a server that asks
# who you are before it says anything.
OPEN_PREFIXES = ("/api/auth/pair", "/api/app/")


# The player belongs to the household and almost all of it is theirs: the films,
# the records, the photographs, who is in the house and what each of them wants
# to hear. These describe the installation instead — how the sound is wired,
# which box is which, how much room is left on the disks it stands on — and they
# are an admin's to read as well as to write. A television has proved a
# household and not a person, so it is nobody here, which is the right answer
# for a screen with a remote.
ADMIN_PATHS = ("/api/settings", "/api/cast/options", "/api/cast/boxes", "/api/storage",
               "/api/auth/token")


# The family album, which is the one shelf here that is not everybody's. A guest
# is somebody the household trusts with the address, not somebody the household
# has handed its photographs to — and the two are different sentences. The game
# is on it because every question it asks is a photograph and every answer a
# name, a place or a year out of the album. Showing a photograph on the
# television is on it because the television opens anything in the album: the
# only guard is on who may name one.
#
# It has to be said HERE and not only next door. Everything on these paths is
# fetched from the library with this module's own token, and a token is trusted
# absolutely over there: the guard that refuses a guest the photographs in the
# library never sees a request that came this way. A rule that only exists on
# the far side of a proxy is a rule the proxy walks straight through.
#
# The vault is not on this list and does not need to be. It is the one thing
# here that forwards the person's own cookie instead of the token, so it is
# already answered by whoever is signed in — which is also why a television
# cannot reach it.
#
# Acquiring is on it for a different reason than the album. It spends the
# household's line and the household's disk, and a guest is somebody trusted
# with the address rather than with the shopping. What bounds it for everybody
# else is not this list but the shape of the route itself — one record, never an
# artist, because an artist is a career and a career is terabytes.
#
# A television still reaches it, and that is the point rather than an oversight:
# a box is nobody here, so refusing nobody would refuse the remote, which is the
# one place somebody actually points at a record they do not have.
HOUSEHOLD_ONLY = ("/api/photos", "/api/explore/want", "/api/game", "/api/tv/photo",
                  "/api/tv/show")


# What of the album the house itself may put on the television: somebody of the
# family through the years, asked for aloud in the living room. The house names
# a person of the household and never a photograph, so it reaches none of the
# album through here — the television fetches the pictures through its own door.
HOUSE_SHOWS = ("/api/tv/show",)


# The surfaces that are a box rather than a person. Somebody proves themselves
# at the door in the ordinary way, and this decides what they are handed for it:
# on a television, a session that says an appliance is one of ours and says
# nothing about who is holding the remote.
#
# Taken from the client, which cannot be checked and does not need to be: saying
# "I am a television" only ever hands back LESS than telling the truth would.
# The lie that would matter is the other way round, and it is not available —
# there is no claim that turns a box into a person.
BOXES = ("tv",)


# Home automation is the one machine that calls the player, and it carries a
# token of its own rather than Library's: it browses the shelf and drives the
# two outputs.
CONSUMER = "house"
HOUSE_MAY = ("/api/library", "/api/play", "/api/radio", "/api/tv", "/api/dac")

# Of the album, the house holds only what a wall in the house shows: a handful
# of the household's photographs, drawn here, and each of those at the one size
# a screen draws. It names no person, album or day, so it can ask for nothing
# narrower than a box's screensaver with nobody picked — and a photograph is
# addressed by the digest of its content, so the only ones it can open are the
# ones it was handed.
HOUSE_WALL = re.compile(r"^/api/photos/(?:wall|[0-9a-f]{40}/preview)$")


def token_key(consumer: str) -> str:
    return f"access_{consumer}_token"


async def from_house(token: str | None) -> bool:
    if not token:
        return False
    known = (await current_runtime()).get(token_key(CONSUMER))
    return opus_auth.same_token(token, known)


# What a box holds once somebody let it in. Not signed here and not ours to
# forge: it was minted next door, where the list of boxes lives, and this module
# can only ask whether it is still on that list. That asymmetry is the feature —
# a television taken back over there is out over here within the minute, and
# nothing on this side had to be told.
DEVICE_COOKIE = "opus_device"
DEVICE_MAX_AGE = 3650 * 24 * 3600

# The claim the library handed back with a box's code, kept on that box alone
# for as long as the code is good. Whoever does not hold it cannot collect the
# token, however well they guess which request is being watched.
PAIRING_COOKIE = "opus_pairing"

# Long enough that a shelf of a hundred thumbnails is not a hundred questions
# about the same television, short enough that taking one back is a minute and
# not an afternoon. Bounded, because the key is whatever a stranger's browser
# sends; a device token that is not even the shape of one is not asked about.
DEVICE_TTL = 60.0
DEVICE_RETRY = 5.0
DEVICE_MAX_STALE = 5 * 60.0
DEVICES_KEPT = 256
_DEVICE_SHAPE = re.compile(r"^[A-Za-z0-9_-]{43}$")


@dataclass(frozen=True)
class Box:
    id: int
    name: str


_devices: OrderedDict[str, tuple[float, float, Box | None]] = OrderedDict()
_device_complaint: str | None = None

# The one exception, and why it is not the same thing. A car has no browser: the
# music app on the phone plays through Android Auto with no cookie jar and no
# login form a driver could fill in, so it is paired once and then carries a
# bearer. It is a person all the same — minted for whoever signed in to pair
# it, and dead the moment their password changes or they leave the roster,
# because it is verified against the same roster version as a cookie. What it
# does not have is the month: a phone in a car that asks to be paired again
# every month is a phone that stops playing music.
#
# Each one is a row of its own, so one lost phone is taken back without signing
# its owner out of everything else. The row is asked about at most once a minute
# per car; taking one back forgets the answer at once.
BEARER = "Bearer "
CAR_MAX_AGE = 3650 * 24 * 3600
CAR_TTL = 60.0
_cars: dict[int, tuple[float, str | None]] = {}

# Signed under names of their own, so a car token is never a cookie and a
# profile marker never opens anything a person does.
PROFILE_PURPOSE = "opus-player-session"
CAR_PURPOSE = "opus-player-car"
TICKET_PURPOSE = "opus-player-ticket"
LENT_PURPOSE = "opus-player-lent"

authority = Authority(settings.library_url, settings.library_token)


def _key(purpose: str) -> bytes:
    return opus_auth.signing_key(settings.session_key, purpose)


def issue_car(who: str, version: int, car: int) -> str:
    return opus_auth.seal(_key(CAR_PURPOSE), CAR_MAX_AGE,
                          opus_auth.encode_name(who), str(version), str(car))


def forget_car(car: int) -> None:
    _cars.pop(car, None)


async def car_session(bearer: str | None) -> tuple[str, int] | None:
    """Who the bearer credibly says this is, and under which version of their
    secret — the car token's reading of the same question the cookie answers,
    plus whether that one car has been taken back."""
    said = opus_auth.unseal(_key(CAR_PURPOSE), bearer, 3)
    if said is None or not said[1].isdigit() or not said[2].isdigit():
        return None
    name, version, car = opus_auth.decode_name(said[0]), int(said[1]), int(said[2])
    if name is None:
        return None
    now = time.monotonic()
    kept = _cars.get(car)
    if kept and now - kept[0] < CAR_TTL:
        holder = kept[1]
    else:
        async with SessionLocal() as session:
            row = await session.get(CarToken, car)
            holder = row.person if row is not None and row.revoked_at is None else None
            if holder is not None:
                row.last_seen_at = datetime.now(timezone.utc)
                await session.commit()
        _cars[car] = (now, holder)
    return (name, version) if holder == name else None


def bearer_of(request) -> str | None:
    said = request.headers.get("authorization", "")
    return said[len(BEARER):] if said.startswith(BEARER) else None


async def person(cookie: str | None, bearer: str | None = None) -> Person | None:
    """Whoever the person cookie — or the car's bearer — belongs to, while the
    roster still carries them at that version. A television has neither and so
    is nobody, which is the whole reason anything personal can be offered here
    at all."""
    said = opus_auth.session_user(settings.session_key, cookie) or await car_session(bearer)
    return None if said is None else await authority.current(*said)


async def owns(cookie: str | None) -> bool:
    """An unrecognised standing is a no: guessing generously at a word this
    module has never heard of is how a door opens by accident."""
    found = await person(cookie)
    return found is not None and found.role == ADMIN


async def device(token: str | None) -> Box | None:
    """The box holding this token, if it is still one of ours.

    Kept briefly and keyed by a digest rather than by the token itself: this
    dictionary lives as long as the process does, and a process holding every
    box's credential in the clear for that long is a worse thing than one round
    trip a minute.

    A refusal is cached exactly as a yes is. Otherwise a television that was
    taken back — or one that never was let in — asks the authority on every
    single request, and the way to make this module hammer next door would be to
    point a stranger's browser at it.

    An authority that does not answer is asked again after a few seconds, not
    on every request of the storm that follows. Its last positive answer has a
    hard lifetime, so taking a box back still wins over a long outage."""
    global _device_complaint
    if not token or not _DEVICE_SHAPE.match(token):
        return None
    key = hashlib.sha256(token.encode()).hexdigest()
    now = time.monotonic()
    kept = _devices.get(key)
    if kept and now < kept[0]:
        _devices.move_to_end(key)
        return kept[2]
    url = f"{authority.url}/api/auth/devices/verify"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            resp = await http.post(url, json={"token": token},
                                   headers={opus_auth.TOKEN_HEADER: authority.token})
            resp.raise_for_status()
            said = resp.json()
        found = Box(int(said["id"]), str(said.get("name") or "device")) if said["ok"] else None
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as why:
        complaint = type(why).__name__
        if complaint != _device_complaint:
            _device_complaint = complaint
            log.warning("device check at %s failed (%s); boxes keep their last answer", url, complaint)
        found = kept[2] if kept and now - kept[1] <= DEVICE_MAX_STALE else None
        confirmed, until = (kept[1] if kept else 0.0), now + DEVICE_RETRY
    else:
        if _device_complaint is not None:
            _device_complaint = None
            log.info("device check at %s answers again", url)
        confirmed, until = now, now + DEVICE_TTL
    _devices[key] = (until, confirmed, found)
    _devices.move_to_end(key)
    while len(_devices) > DEVICES_KEPT:
        _devices.popitem(last=False)
    return found


def issue(who: str) -> str:
    """The profile marker: which profile is watching, so a module that keeps no
    credential can say so without storing a name to go stale."""
    return opus_auth.seal(_key(PROFILE_PURPOSE), SESSION_MAX_AGE, opus_auth.encode_name(who))


def session_user(cookie: str) -> str | None:
    said = opus_auth.unseal(_key(PROFILE_PURPOSE), cookie, 1)
    return opus_auth.decode_name(said[0]) if said else None


# A film sent from somebody's phone is still theirs on the box that plays it:
# where they got to and whether they finished it belong to their profile, not
# to whichever profile the box has picked. The box holds no person, so what it
# is handed is a signature over that profile and that film — or, for an
# episode, its series, so the next one plays on for the same person — good for
# an evening.
LENT_MAX_AGE = 8 * 3600


def lend(profile: str, kind: str, item_id: int, series_id: int | None) -> str:
    return opus_auth.seal(_key(LENT_PURPOSE), LENT_MAX_AGE, opus_auth.encode_name(profile),
                          kind, str(item_id), str(series_id or ""))


def lent_to(token: str | None, kind: str, item_id: int, series_id: int | None) -> str | None:
    """The profile a film was lent by, when this is that film or the next
    episode of its series."""
    said = opus_auth.unseal(_key(LENT_PURPOSE), token, 4)
    if said is None:
        return None
    profile, lent_kind, lent_id, series = said
    same = lent_kind == kind and lent_id == str(item_id)
    next_one = kind == "episode" and series != "" and series == str(series_id)
    return opus_auth.decode_name(profile) if same or next_one else None


def play_prefix(path: str) -> str | None:
    """The one item a path belongs to: /api/play/<kind>/<id>/. A ticket is for a
    film, not for a URL, because playing one means fetching several — the bytes
    and then whichever subtitle track was asked for."""
    parts = path.split("/")
    if len(parts) < 6 or parts[1:3] != ["api", "play"] or not parts[4].isdigit():
        return None
    return "/".join(parts[:5]) + "/"


# What plays a file on a television is not a browser: the native player fetches
# the bytes itself and carries no session of ours. A ticket is a signature over
# the one item it may fetch and the moment it stops being good for anything, so
# handing one over hands over that item and nothing else in the install.
PLAY_TICKET_MAX_AGE = 12 * 3600

# The routes that hand over bytes, and the only ones a ticket opens. Not the
# route that issues tickets: a ticket that could buy the next one would never
# stop being good.
TICKETED = re.compile(r"^/api/play/[a-z]+/\d+/(stream|subs/\d+\.vtt)$")


def _ticket_key(prefix: str) -> bytes:
    return _key(f"{TICKET_PURPOSE}:{prefix}")


def play_ticket(prefix: str) -> str:
    return opus_auth.seal(_ticket_key(prefix), PLAY_TICKET_MAX_AGE)


def valid_ticket(path: str, ticket: str) -> bool:
    prefix = play_prefix(path)
    if prefix is None or not TICKETED.match(path):
        return False
    return opus_auth.unseal(_ticket_key(prefix), ticket, 0) is not None


@dataclass(frozen=True)
class Way:
    """Who came through the door: a person, a box, or neither, which is a module."""
    person: Person | None = None
    box: Box | None = None


async def way_in(person_cookie: str | None, box: str | None = None,
                 token: str | None = None, bearer: str | None = None) -> Way | None:
    """The one answer to whether a request is inside, which the guard and the
    session the frame asks for must never give differently.

    A person comes before the box: somebody who has said who they are is that
    person, whatever else they are also holding. A guest sitting in front of a
    television that was let in is still a guest."""
    if await from_house(token):
        return Way()
    if person_cookie or bearer:
        found = await person(person_cookie, bearer)
        if found is not None:
            return Way(person=found)
    if box:
        held = await device(box)
        if held is not None:
            return Way(box=held)
    return None


async def allowed(path: str, person_cookie: str | None = None, ticket: str | None = None,
                  box: str | None = None, token: str | None = None,
                  bearer: str | None = None) -> bool:
    """Any of the ways in opens the player. What is behind them differs
    elsewhere: a route that hands over something belonging to one person asks
    for the person itself, not merely for a door to have opened.

    A box is one of the ways in and is never one of the people. It can watch and
    it can listen; it cannot read what describes the installation and there is
    nothing of anybody's for it to reach.

    A module is a way in for a machine: it reads the shelf, the stations and the
    address of the bytes, and like the box it is refused what describes the
    installation — that is an admin's, and a token is not an admin."""
    if path in OPEN_PATHS or opus_auth.under(path, OPEN_PREFIXES):
        return True
    if opus_auth.under(path, ADMIN_PATHS):
        return bool(person_cookie) and await owns(person_cookie)
    came = await way_in(person_cookie, box, token, bearer)
    if came is not None:
        if came.person is None and came.box is None:
            return bool(HOUSE_WALL.match(path)) or (
                opus_auth.under(path, HOUSE_MAY)
                and (not opus_auth.under(path, HOUSEHOLD_ONLY)
                     or opus_auth.under(path, HOUSE_SHOWS)))
        return (came.person is None or came.person.role != GUEST
                or not opus_auth.under(path, HOUSEHOLD_ONLY))
    # A ticket opens the exact item it was signed for, and only on the routes
    # that hand over its bytes, so a leaked ticket is a file for an afternoon
    # rather than a way into the catalogue.
    return bool(ticket) and valid_ticket(path, ticket)
