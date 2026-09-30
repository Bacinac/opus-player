"""What describes the installation rather than what is in it: liveness, health,
the settings, and the door."""

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone

import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from opus_auth import ADMIN
from opus_auth.authority import AuthorityUnavailable, Person, TooManyAttempts
from pydantic import BaseModel, field_validator
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, library, playback
from opus.api.routers import users
from opus.config import settings
from opus.db import get_session
from opus.models import BoxPreference, CarToken
from opus.settings_store import (SettingsValidationError, current_runtime, get_for_ui,
                                 store_credentials, update_settings)

router = APIRouter()


@router.get("/ping")
async def ping():
    return {"ok": True}


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    """Readiness is a database round trip and, where a GPU was given, a GPU this
    process can open; ``/ping`` remains liveness only."""
    await session.execute(text("SELECT 1"))
    if os.environ.get("OPUS_RENDER_DEVICE") and not playback.gpu_available():
        raise HTTPException(503, "the render node is configured but cannot be opened")
    return {"ok": True}


class Login(BaseModel):
    username: str
    password: str
    # which surface is asking. Not checked and not checkable: claiming to be a
    # television only ever hands back less than the truth would.
    surface: str = ""


class PasskeyAnswer(BaseModel):
    credential: dict
    surface: str = ""


@router.get("/auth/session")
async def auth_session(request: Request, response: Response, surface: str = "",
                       session: AsyncSession = Depends(get_session)):
    """Who this is, asked once by the frame on the way in.

    A television is answered as the box it is, whatever person cookie the
    browser also holds. That cookie is the one all three modules share, and a
    read is no place to take it away.

    Inside is exactly what the guard would let in, asked the same way. The
    profile marker is not a way in, so a marker whose person or box has gone is
    taken out of the jar, and the frame goes back to the door instead of
    drawing a profile every request under it is refused."""
    person_cookie = None if surface in auth.BOXES else request.cookies.get(opus_auth.SESSION_COOKIE)
    came = await auth.way_in(person_cookie, request.cookies.get(auth.DEVICE_COOKIE),
                             request.headers.get(opus_auth.TOKEN_HEADER), auth.bearer_of(request))
    cookie = request.cookies.get(auth.SESSION_COOKIE)
    passkey = surface not in auth.BOXES and _door(request) is not None
    if came is None:
        if cookie:
            _uncookie(response, request, auth.SESSION_COOKIE)
        return {"required": True, "authenticated": False, "box": "", "profile": None,
                "username": "", "person": "", "role": "", "passkey": passkey}
    # the door and the profile are two different questions: through the door
    # with nobody picked is the state the profile chooser exists for
    marker = auth.session_user(cookie) if cookie else None
    who = await users.chosen(session, marker, came.person)
    named = (await auth.authority.people()).get(who.person or "") if who else None
    shown = (named.display if named else who.name) if who else ""
    person = came.person
    kept = await session.get(BoxPreference, came.box.id) if came.box and who is None else None
    return {
        "required": True,
        "authenticated": True,
        # what this box is called, where it is one. The screen says it so
        # somebody can tell which television they are looking at before taking
        # it back from the other room
        "box": came.box.name if came.box else "",
        "profile": {"key": marker, "name": shown, "colour": who.colour} if who else None,
        # how the shelves are arranged for whoever holds this screen: the
        # profile picked on it, or the box itself when nobody is
        "shelf_orders": who.shelf_orders if who else (kept.shelf_orders if kept else "{}"),
        "username": person.name if person else shown,
        # who this is, where anybody is — the screen offers what belongs to one
        # person only when there is one
        "person": person.name if person else "",
        "role": person.role if person else "",
        "passkey": passkey,
    }


def _cookie(response: Response, request: Request, name: str, value: str, max_age: int):
    opus_auth.set_cookie(response, request, settings.cookie_domain, name, value, max_age)


def _uncookie(response: Response, request: Request, name: str):
    opus_auth.delete_cookie(response, request, settings.cookie_domain, name)


class BoxPatch(BaseModel):
    shelf_orders: str | None = None

    @field_validator("shelf_orders")
    @classmethod
    def _one_order_per_shelf(cls, given: str | None) -> str | None:
        return None if given is None else users.checked_orders(given)


@router.patch("/box")
async def edit_box(body: BoxPatch, request: Request, session: AsyncSession = Depends(get_session)):
    """What a television keeps for itself while nobody is picked on it."""
    box = await auth.device(request.cookies.get(auth.DEVICE_COOKIE))
    if box is None:
        raise HTTPException(401, "only a box that was let in keeps anything of its own")
    kept = await session.get(BoxPreference, box.id) or BoxPreference(box_id=box.id)
    if body.shelf_orders is not None:
        kept.shelf_orders = body.shelf_orders
    session.add(kept)
    await session.commit()
    return {"shelf_orders": kept.shelf_orders}


async def _person(request: Request) -> Person:
    """Whoever is signed in as themselves — never a box, a module or a car."""
    found = await auth.person(request.cookies.get(opus_auth.SESSION_COOKIE))
    if found is None:
        raise HTTPException(401, "sign in as yourself first")
    return found


@router.post("/auth/car-token")
async def auth_car_token(request: Request, session: AsyncSession = Depends(get_session)):
    """A bearer for the music app in the car, minted for whoever is signed in.

    Asked once, at pairing, with the person's own cookie: the app signs in on
    the phone, takes this, and forgets the password. Only a person — a box has
    nobody for a car to belong to."""
    found = await _person(request)
    car = CarToken(person=found.name)
    session.add(car)
    await session.commit()
    return {"token": auth.issue_car(found.name, found.version, car.id), "person": found.name}


def _car(row: CarToken) -> dict:
    return {"id": row.id, "person": row.person, "created_at": row.created_at.isoformat(),
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None}


@router.get("/auth/cars")
async def auth_cars(request: Request, session: AsyncSession = Depends(get_session)):
    """The cars still holding a bearer: your own, or every one to an admin."""
    found = await _person(request)
    query = select(CarToken).where(CarToken.revoked_at.is_(None))
    if found.role != ADMIN:
        query = query.where(CarToken.person == found.name)
    rows = (await session.execute(query.order_by(CarToken.created_at.desc()))).scalars()
    return {"cars": [_car(row) for row in rows]}


@router.delete("/auth/cars/{car_id}")
async def auth_take_back_car(car_id: int, request: Request,
                             session: AsyncSession = Depends(get_session)):
    """One car taken back, and nothing else its owner holds."""
    found = await _person(request)
    row = await session.get(CarToken, car_id)
    if row is None or row.revoked_at is not None or (
            found.role != ADMIN and row.person != found.name):
        raise HTTPException(404, "no such car")
    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    auth.forget_car(car_id)
    return {"gone": car_id}


@router.post("/auth/login")
async def auth_login(body: Login, request: Request, response: Response):
    """One form, one credential, and two things it can be worth.

    There is only one password in this house and it is kept next door. What
    differs is what a surface is handed for it. On a phone or a laptop it makes
    a **person**: the daughter signing in as herself, and the only kind of
    session anything private will ever answer to. On a **television** the same
    credential makes an appliance — a session that says this box is one of ours
    and says nothing at all about who is holding the remote.

    That is not a control hiding the vault on a television. There is nobody on a
    television for a vault to belong to, so it is not there — absent rather than
    refused, which is the only version of that promise worth making about a
    screen in a room everybody walks through. And a decade-long session is
    honest for a box that never leaves the house, where a month-long one for a
    person is honest for a phone that does."""
    _not_a_box(body.surface)
    with _asking():
        said = await auth.authority.verify(body.username, body.password,
                                           opus_auth.client_address(request))
    if said is None:
        raise HTTPException(401, "wrong username or password")
    return _signed_in(said, request, response)


def _not_a_box(surface: str):
    if surface in auth.BOXES:
        # a box does not sign in, and this is where that stops being a
        # preference and becomes true. Leaving the password door open on a
        # television would leave the answer to "how does somebody else's
        # television get in" exactly where it was: knowing one password.
        raise HTTPException(409, "a box is let in, not signed in")


@contextmanager
def _asking():
    try:
        yield
    except TooManyAttempts as refused:
        raise HTTPException(429, "too many failed attempts",
                            headers={"Retry-After": refused.retry_after})
    except AuthorityUnavailable as why:
        raise HTTPException(502, str(why))


def _signed_in(said: Person, request: Request, response: Response) -> dict:
    _cookie(response, request, opus_auth.SESSION_COOKIE,
            opus_auth.issue(settings.session_key, said.name, said.version),
            opus_auth.SESSION_MAX_AGE)
    return {"ok": True, "person": said.name, "role": said.role}


def _door(request: Request) -> str | None:
    door = opus_auth.passkey_door(settings.cookie_domain, request)
    return door[1] if door else None


def _passkey_door(request: Request) -> str:
    origin = _door(request)
    if origin is None:
        raise HTTPException(404, "this door takes no passkey")
    return origin


@router.post("/auth/passkey/options")
async def auth_passkey_options(request: Request):
    _passkey_door(request)
    with _asking():
        return await auth.authority.passkey_options()


@router.post("/auth/passkey/login")
async def auth_passkey_login(body: PasskeyAnswer, request: Request, response: Response):
    """The same person the password makes, proved by a key Library keeps and
    checked against this door's own address, so a signature collected on a
    sibling site opens nothing. A box is no more signed in this way than the
    other."""
    _not_a_box(body.surface)
    with _asking():
        said = await auth.authority.passkey(body.credential, _passkey_door(request),
                                            opus_auth.client_address(request))
    if said is None:
        raise HTTPException(401, "the passkey was not accepted")
    return _signed_in(said, request, response)


# Asking needs no credential, and every ask is a row next door. A box asks once
# per code, which lasts a quarter of an hour; a few more from one caller is
# somebody pressing Again. Everybody together is counted by the minute: it keeps
# a flood off the library without a few callers locking every television out.
PAIR_WINDOW = 15 * 60
PAIR_PER_ADDRESS = 5
PAIR_BURST_WINDOW = 60
PAIR_BURST = 60
_asked: dict[str, list[float]] = {}
_recent: list[float] = []


def _admit_pairing(address: str) -> float:
    """Room for one more code, or a refusal saying when there will be. The slot
    it takes is handed back, to be given up if no code comes of it."""
    now = time.monotonic()
    for who in list(_asked):
        _asked[who] = [at for at in _asked[who] if now - at < PAIR_WINDOW]
        if not _asked[who]:
            del _asked[who]
    _recent[:] = [at for at in _recent if now - at < PAIR_BURST_WINDOW]
    caller = opus_auth.address_bucket(address)
    mine = _asked.get(caller, [])
    if len(mine) >= PAIR_PER_ADDRESS:
        raise HTTPException(429, "too many codes asked for from this address",
                            headers={"Retry-After": str(int(PAIR_WINDOW - (now - mine[0])) + 1)})
    if len(_recent) >= PAIR_BURST:
        raise HTTPException(429, "too many codes asked for at once",
                            headers={"Retry-After": str(int(PAIR_BURST_WINDOW - (now - min(_recent))) + 1)})
    _asked.setdefault(caller, []).append(now)
    _recent.append(now)
    return now


@router.post("/auth/pair")
async def auth_pair(request: Request, response: Response):
    """A box asking to be let in. What comes back goes on the screen and is
    worth nothing until somebody says yes to it, which they do next door where
    the list of boxes lives.

    The claim that collects the credential stays with this box, in a cookie the
    page cannot read, and lives exactly as long as the code does."""
    slot = _admit_pairing(opus_auth.client_address(request))
    try:
        said = await library.post("/auth/devices/ask", {"module": "player"})
    except library.LibraryError as exc:
        _recent.remove(slot)
        raise HTTPException(502, str(exc))
    if not said.get("claim") or not said.get("id"):
        _recent.remove(slot)
        raise HTTPException(502, "the library handed back a code without a claim")
    _cookie(response, request, auth.PAIRING_COOKIE, said["claim"],
            int(said.get("minutes") or 15) * 60)
    return {"code": said.get("code"), "id": said["id"], "minutes": said.get("minutes")}


@router.get("/auth/pair/{asked}")
async def auth_paired(asked: int, request: Request, response: Response):
    """Has anybody said yes yet — asked over and over by a screen showing its own
    code.

    The credential comes back exactly once and is put straight into a cookie
    here, so it exists in this module for the length of one response and is
    never handed to the page. A screen that could read it could also be asked
    for it."""
    claim = request.cookies.get(auth.PAIRING_COOKIE)
    if not claim:
        raise HTTPException(404, "that request is gone; ask for a new code")
    try:
        said = await library.post("/auth/devices/claim", {"id": asked, "claim": claim})
    except library.NotInLibrary:
        raise HTTPException(404, "that request is gone; ask for a new code")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    if said.get("token"):
        _cookie(response, request, auth.DEVICE_COOKIE, said["token"], auth.DEVICE_MAX_AGE)
        _uncookie(response, request, auth.PAIRING_COOKIE)
    return {"in": bool(said.get("in")), "name": said.get("name") or ""}


@router.post("/auth/logout")
async def auth_logout(request: Request, response: Response):
    """Let go of whoever is signed in.

    BOTH of them. Signing in writes the person's cookie; this let go of the
    box's and left the person's where it was, so signing out answered OK,
    returned to "who is watching?", and left the session open behind it —
    indistinguishable from merely putting the profile down, which is what it
    was mistaken for.

    The device is not touched. That credential says this television is one of
    ours, and somebody signing out of their own account is no reason to unpair
    the set.
    """
    _uncookie(response, request, opus_auth.SESSION_COOKIE)
    _uncookie(response, request, auth.SESSION_COOKIE)
    return {"ok": True}


@router.get("/storage")
async def storage():
    """Room left on the disks the media sits on, asked of the module that stands
    on them. The player has no libraries mounted and never will — it plays what
    the Library keeps — so this is passed on, not measured."""
    try:
        return await library.get("/storage")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/auth/token")
async def auth_tokens():
    """The token home automation calls with, for an admin to carry to it by
    hand. Empty until one is made."""
    held = (await current_runtime()).get(auth.token_key(auth.CONSUMER))
    return {"tokens": [{"consumer": auth.CONSUMER, "token": held}]}


class TokenFor(BaseModel):
    consumer: str


@router.post("/auth/token")
async def auth_new_token(body: TokenFor):
    """A new token, which ends the old one: home automation is turned away
    until it is given this one."""
    if body.consumer != auth.CONSUMER:
        raise HTTPException(404, "no such consumer")
    value = opus_auth.new_token()
    await store_credentials({auth.token_key(auth.CONSUMER): value})
    return {"consumer": auth.CONSUMER, "token": value}


@router.get("/settings")
async def read_settings():
    return await get_for_ui()


@router.put("/settings")
async def write_settings(updates: dict[str, str]):
    try:
        await update_settings(updates)
    except SettingsValidationError as exc:
        raise HTTPException(400, {"key": exc.key, "code": exc.code})
    return await get_for_ui()
