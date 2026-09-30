"""A person's music favourites.

The preference belongs to a roster account, including a paired car bearer.  A
Player profile is intentionally not involved: Android Auto proves who owns its
token but cannot safely guess which profile was last picked on a television.
Only ids live here; the Library remains the catalogue and supplies the current
title, artwork and availability when a list is read.
"""

from typing import Annotated

import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from opus_auth.authority import Person
from pydantic import Field
from sqlalchemy import delete, desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, library
from opus.db import get_session
from opus.models import MusicFavorite

router = APIRouter()

TrackId = Annotated[int, Field(ge=1, le=2_147_483_647)]
MAX_FAVORITES = 1_000
ANDROID_TRACK_FIELDS = frozenset({"id", "playable", "title", "artist", "album", "codec"})


async def person_of(request: Request) -> Person:
    """The account behind a cookie or paired-car bearer, never a box/token."""
    found = await auth.person(
        request.cookies.get(opus_auth.SESSION_COOKIE), auth.bearer_of(request)
    )
    if found is None:
        raise HTTPException(401, "sign in to manage music favorites")
    return found


def in_saved_order(ids: list[int], tracks: list[dict]) -> list[dict]:
    """Library SQL has no reason to retain preference order; the Player does."""
    by_id = {track.get("id"): track for track in tracks}
    chosen = [by_id[track_id] for track_id in ids
              if track_id in by_id and by_id[track_id].get("playable")]
    for card in chosen:
        missing = ANDROID_TRACK_FIELDS.difference(card)
        if missing:
            raise library.LibraryError(
                "library music-track contract missing " + ", ".join(sorted(missing)))
    return chosen


async def track(track_id: int) -> dict:
    try:
        found = await library.get("/music/tracks", ids=str(track_id))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    card = next((row for row in found if row.get("id") == track_id), None)
    if card is None or not card.get("playable"):
        raise HTTPException(404, "no playable track by that id")
    return card


@router.get("/music/favorites")
async def favorites(who: Person = Depends(person_of),
                    session: AsyncSession = Depends(get_session)):
    rows = await session.execute(
        select(MusicFavorite.track_id)
        .where(MusicFavorite.person == who.name)
        .order_by(desc(MusicFavorite.created_at), desc(MusicFavorite.id))
        .limit(MAX_FAVORITES)
    )
    ids = list(rows.scalars())
    if not ids:
        return {"tracks": []}
    try:
        found = await library.get("/music/tracks", ids=",".join(map(str, ids)))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return {"tracks": in_saved_order(ids, found)}


@router.put("/music/favorites/{track_id}", status_code=status.HTTP_201_CREATED)
async def add_favorite(track_id: TrackId, who: Person = Depends(person_of),
                       session: AsyncSession = Depends(get_session)):
    """Save a currently playable track. Repeating PUT is deliberately safe."""
    await track(track_id)
    already = await session.scalar(select(MusicFavorite.id).where(
        MusicFavorite.person == who.name, MusicFavorite.track_id == track_id
    ))
    if already is not None:
        return {"track_id": track_id, "favorite": True}
    session.add(MusicFavorite(person=who.name, track_id=track_id))
    try:
        await session.commit()
    except IntegrityError:
        # Two controllers can tap the same favourite at once.  They both asked
        # for the same final state, so a unique-key race is still success.
        await session.rollback()
    return {"track_id": track_id, "favorite": True}


@router.delete("/music/favorites/{track_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_favorite(track_id: TrackId, who: Person = Depends(person_of),
                          session: AsyncSession = Depends(get_session)):
    await session.execute(delete(MusicFavorite).where(
        MusicFavorite.person == who.name, MusicFavorite.track_id == track_id
    ))
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
