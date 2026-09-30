"""Who is watching.

The list is the roster's, not this module's. Everybody with an account next door
is somebody who can be picked here, without anybody typing their name a second
time — and without this module keeping a copy of that list, which is the copy
that would still be saying the old name a year after a rename. What is kept here
is only what the roster has no opinion about: a colour, a language order, where
somebody got to.

A profile is picked rather than proved. On a television the only input is four
arrow keys, and a lock nobody can operate from the sofa is a lock that gets left
open. What the profile decides is whose half-finished films these are, which is
a question of bookkeeping and not of secrecy — the questions that are about
secrecy are asked at the door, and answered by whether somebody signed in as
themselves.

Somebody with no account at all can still be here: a guest on the sofa is a
person to keep a place in a film for. Those are the only rows this module makes
on purpose, and the only ones it will remove — removing anybody else is done
where they exist, which is next door.

An admin is not offered. The account that keeps the place is not a person who
watches — it is how the library is maintained, and its half-finished films are
nobody's. In this house the same man is `bacinac` at the roster and `filip` on the
sofa, and offering both put the wrong one on the television.

The consequence is worth saying out loud: make somebody an admin and their
profile stops being offered, taking their place in every half-watched film with
it. The row is not deleted, so it comes back if they stop being one — but for as
long as they are, the television will not show them."""

import json
import re
from typing import Annotated

import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from opus_auth import ADMIN, GUEST
from opus_auth.authority import Person
from pydantic import BaseModel, Field, StringConstraints, field_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth
from opus.config import settings
from opus.db import get_session
from opus.models import User

router = APIRouter()


Colour = Annotated[str, Field(pattern=r"^(#[0-9a-fA-F]{6})?$")]

SHELVES = ("movies", "series", "music")
_SHELF_ORDER = re.compile(r"^(added|title|year)(:(asc|desc))?$")


def orders_of(stored: str) -> dict[str, str]:
    try:
        said = json.loads(stored or "{}")
    except ValueError:
        return {}
    if not isinstance(said, dict):
        return {}
    return {shelf: order for shelf, order in said.items()
            if shelf in SHELVES and isinstance(order, str) and _SHELF_ORDER.match(order)}


def checked_orders(given: str) -> str:
    try:
        said = json.loads(given)
    except ValueError:
        raise ValueError("shelf_orders is not JSON")
    if not isinstance(said, dict) or orders_of(given) != said:
        raise ValueError("shelf_orders names a shelf or an order there is none of")
    return json.dumps(said, separators=(",", ":"))


# whoever the profile is, the household, or one person by the id the library
# knows them by
SCREENSAVER = r"^(|household|[1-9][0-9]{0,9}(,[1-9][0-9]{0,9})*)$"


class NewUser(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
    colour: Colour = ""


class UserPatch(BaseModel):
    colour: Colour | None = None
    audio_languages: str | None = None
    subtitle_languages: str | None = None
    shelf_orders: str | None = None
    screensaver: Annotated[str, Field(pattern=SCREENSAVER, max_length=160)] | None = None

    @field_validator("shelf_orders")
    @classmethod
    def _one_order_per_shelf(cls, given: str | None) -> str | None:
        return None if given is None else checked_orders(given)

    @field_validator("screensaver")
    @classmethod
    def _each_person_once(cls, given: str | None) -> str | None:
        return None if given is None else ",".join(dict.fromkeys(given.split(",")))


def _order(given: str) -> str:
    """An order of languages, kept as one field. Blanks and repeats fall out —
    naming the same language twice is not a second answer."""
    seen: list[str] = []
    for code in given.lower().split(","):
        code = code.strip()[:8]
        if code and code not in seen:
            seen.append(code)
    return ",".join(seen[:3])


def _watches(said: Person) -> bool:
    """Whether somebody on the roster is offered a place on a television: not
    an admin, for the reason in this module's own docstring. Nobody switched off
    is on the roster at all — a tile that refuses is worse than no tile."""
    return said.role != ADMIN


def profile_key(user: User) -> str:
    """What a profile is called from outside. The roster name where there is
    one, so the same person is the same key on every surface and survives this
    database being rebuilt; the local name otherwise."""
    return user.person or user.name


def _json(user: User, display: str | None = None) -> dict:
    return {"key": profile_key(user),
            "name": display or user.name or user.person,
            "colour": user.colour,
            # whether the roster is what says this person exists, which is the
            # difference between a profile that can be removed here and one that
            # cannot
            "roster": user.person is not None,
            "audio_languages": user.audio_languages,
            "subtitle_languages": user.subtitle_languages,
            "screensaver": user.screensaver}


async def _rows(session) -> dict[str, User]:
    result = await session.execute(select(User))
    return {profile_key(u): u for u in result.scalars()}


async def _adopt(session, person: str) -> User:
    """The row behind a name on the roster, found or made the first time that
    person is picked.

    Lazily on purpose: making one for everybody the moment the roster is read
    would be this module deciding who exists, which is the one thing it must
    not do — and it would leave rows behind for people who were removed next
    door before ever sitting down here.

    Found first, because this module kept its own list of names before it kept
    none: a profile called "Filip" with a year of half-finished films behind it is
    the roster's `filip`, and making a second row beside it would strand every one
    of them. Matched without regard to case, which is the only way the two lists
    ever differed — the roster keeps one spelling and nobody typing at a
    television did."""
    mine = await session.execute(
        select(User).where(User.person.is_(None), func.lower(User.name) == person.lower()))
    user = mine.scalar_one_or_none()
    if user is not None:
        user.person = person
        user.name = ""
    else:
        user = User(person=person, name="")
        session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _may_be(person: Person | None, key: str) -> bool:
    """A guest is handed the address, not the household's profiles: whoever
    signed in as one is their own profile and nobody else's."""
    return person is None or person.role != GUEST or key == person.name


async def _signed_in(request: Request) -> Person | None:
    return await auth.person(request.cookies.get(opus_auth.SESSION_COOKIE), auth.bearer_of(request))


async def chosen(session: AsyncSession, marker: str | None, person: Person | None) -> User | None:
    """The profile a marker names, if it still exists and whoever is signed in
    may be it. A profile that went away while its cookie was still out there is
    nobody, not an error."""
    if not marker or not _may_be(person, marker):
        return None
    return (await _rows(session)).get(marker)


async def picked(request: Request, session: AsyncSession) -> User | None:
    cookie = request.cookies.get(auth.SESSION_COOKIE)
    return await chosen(session, auth.session_user(cookie) if cookie else None,
                        await _signed_in(request))


async def require_picked(request: Request,
                         session: AsyncSession = Depends(get_session)) -> User:
    who = await picked(request, session)
    if who is None:
        raise HTTPException(409, "nobody is watching; pick a profile first")
    return who


async def watching(request: Request, session: AsyncSession, lent: str | None, kind: str,
                   item_id: int, series_id: int | None) -> User:
    """Whose place in a film this is: the profile that sent it here from another
    screen, while it plays on for them, or the one picked here."""
    marker = auth.lent_to(lent, kind, item_id, series_id) if lent else None
    found = (await _rows(session)).get(marker) if marker else None
    return found or await require_picked(request, session)


@router.get("/users")
async def list_users(request: Request, session: AsyncSession = Depends(get_session)):
    """Everybody on the roster, then anybody here who is on no roster.

    The roster's order is kept as it arrives — it already sorts by standing and
    then by name, and re-sorting it here would be a second opinion about a list
    this module does not own."""
    people = await auth.authority.people()
    rows = await _rows(session)
    me = await _signed_in(request)
    out = [_json(rows.get(name) or User(person=name, name=""), said.display)
           for name, said in people.items() if _watches(said) and _may_be(me, name)]
    out += [_json(u) for key, u in rows.items()
            if u.person is None and key not in people and _may_be(me, key)]
    return out


async def _refuse_guest(request: Request, key: str | None = None) -> None:
    found = await _signed_in(request)
    if found is not None and found.role == GUEST and key != found.name:
        raise HTTPException(403, "a guest is their own profile and nobody else's")


@router.post("/users", status_code=201)
async def add_user(body: NewUser, request: Request, session: AsyncSession = Depends(get_session)):
    """Somebody with no account, for the evening. Anybody who came through the
    door may make one, because that is all a profile has ever been — except a
    guest, who is somebody with an account and only that."""
    await _refuse_guest(request)
    name = body.name
    if name in await auth.authority.people():
        # they exist already and are already in the list; a second row under the
        # same name would be a second person as far as everything here can tell
        raise HTTPException(409, "somebody on the roster is already called that")
    if name in await _rows(session):
        raise HTTPException(409, "somebody here is already called that")
    user = User(name=name, colour=body.colour)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return _json(user)


@router.post("/users/{key}/pick")
async def pick_user(key: str, request: Request, response: Response,
                    session: AsyncSession = Depends(get_session)):
    """Say who is watching. The same session, re-signed to carry the choice —
    picking a profile is not proving anything, so it does not open the door
    again; it only writes down who came through it."""
    await _refuse_guest(request, key)
    people = await auth.authority.people()
    user = (await _rows(session)).get(key)
    # not offered, so not pickable. A list that hides a tile while the route
    # behind it still answers is two answers to one question
    if key in people and not _watches(people[key]):
        raise HTTPException(404, "no such profile")
    if user is None:
        if key not in people:
            raise HTTPException(404, "no such profile")
        user = await _adopt(session, key)
    elif user.person is not None and user.person not in people:
        raise HTTPException(404, "no such profile")
    opus_auth.set_cookie(response, request, settings.cookie_domain, auth.SESSION_COOKIE,
                         auth.issue(profile_key(user)), auth.SESSION_MAX_AGE)
    return _json(user, people[key].display if key in people else None)


@router.patch("/users/{key}")
async def edit_user(key: str, body: UserPatch, request: Request,
                    session: AsyncSession = Depends(get_session)):
    """What this module is allowed an opinion about: a colour, a language order,
    the arrangement of a shelf. Not a name — whoever is on the roster is called
    what the roster calls them, and answering that here as well is how two
    answers start out agreeing and then stop."""
    await _refuse_guest(request, key)
    people = await auth.authority.people()
    if key in people and not _watches(people[key]):
        raise HTTPException(404, "no such profile")
    user = (await _rows(session)).get(key)
    if user is None:
        if key not in people:
            raise HTTPException(404, "no such profile")
        user = await _adopt(session, key)
    if body.colour is not None:
        user.colour = body.colour
    if body.audio_languages is not None:
        user.audio_languages = _order(body.audio_languages)
    if body.subtitle_languages is not None:
        user.subtitle_languages = _order(body.subtitle_languages)
    if body.shelf_orders is not None:
        user.shelf_orders = body.shelf_orders
    if body.screensaver is not None:
        user.screensaver = body.screensaver
    await session.commit()
    return _json(user, people[key].display if key in people else None)


@router.delete("/users/{key}", status_code=204)
async def remove_user(key: str, request: Request, session: AsyncSession = Depends(get_session)):
    """Only somebody who is on no roster. Everybody else exists next door, and a
    row removed here would simply be made again the next time they sat down —
    which is the right answer, and the reason not to pretend this removes
    anybody."""
    await _refuse_guest(request)
    user = (await _rows(session)).get(key)
    if user is None:
        return
    if user.person is not None:
        raise HTTPException(409, "this person is on the roster; remove them there")
    left = (await session.execute(select(func.count()).select_from(User))).scalar() or 0
    if left <= 1:
        raise HTTPException(409, "somebody has to be here")
    await session.delete(user)
    await session.commit()
