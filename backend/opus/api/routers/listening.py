"""What each person has been listening to, and what that says about what to
put on next.

Kept per profile, like where somebody stopped a film: two people on one sofa
do not have one taste. The catalogue stays the Library's — a play is ids and a
date, and every name on a screen is asked for when the screen is drawn."""

import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opus import history, library
from opus.api.routers.users import picked, require_picked
from opus.db import get_session
from opus.models import MusicPlay, User

router = APIRouter()

Id = Annotated[int, Field(ge=1, le=2**31 - 1)]
# a queue is kept in the browser between visits, and a career is not a queue
MOST_IN_A_QUEUE = 200


class Heard(BaseModel):
    track_id: Id
    release_id: Id
    artist_id: Id


@router.post("/music/plays", status_code=201)
async def heard(body: Heard, who: User = Depends(require_picked),
                session: AsyncSession = Depends(get_session)):
    session.add(MusicPlay(user_id=who.id, **body.model_dump()))
    kept = await history.note(session, who.id, "track", [body.track_id])
    await session.commit()
    if kept:
        history.sender.kick()
    return {"heard": body.track_id}


def most_heard_first(tracks: list[dict], counts: dict[int, int]) -> list[dict]:
    """The songs this person keeps coming back to, most-played first, and after
    them everything else in no order at all — the whole reason to put on an
    artist rather than an album is not knowing what comes next."""
    known = sorted((t for t in tracks if counts.get(t["id"])),
                   key=lambda t: -counts[t["id"]])
    rest = [t for t in tracks if not counts.get(t["id"])]
    random.shuffle(rest)
    return known + rest


@router.get("/library/artist/{artist_id}/queue")
async def artist_queue(artist_id: int, request: Request, prefer: str = "stereo",
                       shuffle: bool = False,
                       session: AsyncSession = Depends(get_session)):
    try:
        tracks = await library.get(f"/music/artists/{artist_id}/tracks", prefer=prefer)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    who = None if shuffle else await picked(request, session)
    counts: dict[int, int] = {}
    if who is not None:
        counts = dict((await session.execute(
            select(MusicPlay.track_id, func.count())
            .where(MusicPlay.user_id == who.id, MusicPlay.artist_id == artist_id)
            .group_by(MusicPlay.track_id)
        )).all())
    return {"tracks": most_heard_first(tracks, counts)[:MOST_IN_A_QUEUE]}
