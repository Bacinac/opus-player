"""Where you stopped, and what you finished.

The only thing the player keeps that is its own, and it is kept per person and
per item rather than per device: stopping on the sofa and carrying on in the
kitchen is the point, and two people watching the same series are not in the
same place in it. One row per person per item, so nothing anybody does to their
own row is visible in anybody else's.

Getting to the end clears the position and does not clear the row. Where
somebody stopped stops being true the moment they finish; that they have seen
it goes on being true. A row with a position is a thing to carry on with, and a
row with a date on it is a thing already seen."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from opus import history
from opus.api.routers.users import require_picked, watching
from opus.db import get_session
from opus.models import Progress, User

router = APIRouter()

KINDS = ("movie", "episode", "track")

# what the columns the ids are kept in can hold
Id = Annotated[int, Field(ge=-(2**31), le=2**31 - 1)]
MOST_AT_ONCE = 1000
_ID = re.compile(r"^-?[0-9]{1,10}$")


def ids_of(given: str) -> list[int]:
    found = [int(one) for one in (part.strip() for part in given.split(",")[:MOST_AT_ONCE])
             if _ID.match(one)]
    return [n for n in found if -(2**31) <= n < 2**31]

# near enough to the end that offering to resume would be an insult: closing
# credits run longer than this, so it is measured from the end and not as a
# fraction, which would let a three-hour film keep nagging with ten minutes left
FINISHED_WITHIN_S = 90.0


def _finished(position: float, duration: float | None, credits: float | None = None) -> bool:
    """A song is not a film. Ninety seconds from the end of a three-minute
    record is halfway through it, so the tail is whichever is the shorter of
    the credits and a tenth of the thing — and where the library found where
    the credits begin, they are the end, however long they run."""
    if duration is None:
        return False
    if credits is not None and position >= credits:
        return True
    return position >= duration - min(FINISHED_WITHIN_S, duration * 0.1)


class Report(BaseModel):
    kind: str
    item_id: Id
    position_s: float
    duration_s: float | None = None
    surface: str = Field("", max_length=16)
    # the series an episode belongs to, said while it is known
    parent_id: Id | None = None
    credits_s: float | None = None
    # the mark a box is handed with a film sent from somebody's phone
    sent: str | None = Field(None, max_length=512)


async def _mark(session: AsyncSession, who: User, kind: str, item_ids: list[int],
                watched: bool, parent_id: int | None = None) -> None:
    """Seen, or not seen after all. Marking clears the position with it: a thing
    finished is not a thing to carry on with, and a thing nobody has seen has no
    end to have stopped near."""
    if not item_ids:
        return
    kept = False
    if watched and kind in history.SEEN:
        # the credits are reported every few seconds while they run; what is
        # sent on is finishing it, once, and not every report after
        finished = set((await session.execute(select(Progress.item_id).where(
            Progress.user_id == who.id, Progress.kind == kind, Progress.item_id.in_(item_ids),
            Progress.finished_at.is_not(None), Progress.position_s == 0))).scalars())
        kept = await history.note(session, who.id, kind, [i for i in item_ids if i not in finished])
    if watched:
        stmt = insert(Progress).values([
            {"user_id": who.id, "kind": kind, "item_id": item_id,
             "position_s": 0.0, "duration_s": None, "surface": "",
             "finished_at": func.now(), "parent_id": parent_id}
            for item_id in item_ids
        ])
        await session.execute(stmt.on_conflict_do_update(
            index_elements=["user_id", "kind", "item_id"],
            set_={"position_s": 0.0, "finished_at": func.now(),
                  "updated_at": func.now(),
                  # a row written before anybody said what it belongs to
                  "parent_id": func.coalesce(
                      sa.literal(parent_id), Progress.parent_id)},
        ))
    else:
        await session.execute(delete(Progress).where(
            Progress.user_id == who.id, Progress.kind == kind,
            Progress.item_id.in_(item_ids)))
    await session.commit()
    if kept:
        history.sender.kick()


class Seen(BaseModel):
    kind: str
    item_ids: list[Id] = Field(max_length=MOST_AT_ONCE)
    watched: bool = True
    parent_id: Id | None = None


@router.get("/progress/watched/{kind}")
async def watched(kind: str, ids: str = "", who: User = Depends(require_picked),
                  session: AsyncSession = Depends(get_session)):
    """Which of these this person has seen. Asked for a whole list at once — a
    season is twenty-two questions and the answer to all of them is one row of
    the same table."""
    wanted = ids_of(ids)
    if not wanted:
        return {"watched": [], "partly": {}}
    rows = await session.execute(
        select(Progress.item_id, Progress.finished_at, Progress.position_s,
               Progress.duration_s).where(
            Progress.user_id == who.id, Progress.kind == kind,
            Progress.item_id.in_(wanted))
    )
    seen, partly = [], {}
    for item_id, finished_at, position, duration in rows:
        if finished_at is not None:
            seen.append(item_id)
        elif position and duration:
            partly[item_id] = round(min(position / duration, 1.0), 3)
    return {"watched": seen, "partly": partly}


@router.post("/progress/watched", status_code=200)
async def set_watched(body: Seen, who: User = Depends(require_picked),
                      session: AsyncSession = Depends(get_session)):
    """Said by hand: a season watched somewhere else years ago, or one marked by
    mistake. One sentence for one episode and for a whole season, because from
    in front of a list those are the same sentence."""
    if body.kind not in KINDS:
        raise HTTPException(400, "nothing of that kind is watched")
    await _mark(session, who, body.kind, body.item_ids, body.watched, body.parent_id)
    return {"watched": body.watched, "n": len(body.item_ids)}


@router.get("/progress/{kind}/{item_id}")
async def read_progress(kind: str, item_id: int, request: Request, sent: str | None = None,
                        parent: int | None = None,
                        session: AsyncSession = Depends(get_session)):
    who = await watching(request, session, sent, kind, item_id, parent)
    row = (await session.execute(
        select(Progress).where(Progress.user_id == who.id, Progress.kind == kind,
                               Progress.item_id == item_id)
    )).scalar_one_or_none()
    if row is None:
        return {"position_s": 0.0, "duration_s": None, "surface": "", "watched": False}
    return {"position_s": row.position_s, "duration_s": row.duration_s,
            "surface": row.surface, "watched": row.finished_at is not None}


@router.post("/progress")
async def report_progress(body: Report, request: Request,
                          session: AsyncSession = Depends(get_session)):
    if body.kind not in KINDS:
        raise HTTPException(400, "nothing of that kind keeps a position")
    who = await watching(request, session, body.sent, body.kind, body.item_id, body.parent_id)
    if _finished(body.position_s, body.duration_s, body.credits_s):
        await _mark(session, who, body.kind, [body.item_id], True, body.parent_id)
        return {"kept": False, "watched": True}
    if body.position_s <= 0:
        # nothing to carry on from. The row goes only if it has nothing else to
        # say — one that remembers being finished is not a bookmark to tidy away
        await session.execute(delete(Progress).where(
            Progress.user_id == who.id, Progress.kind == body.kind,
            Progress.item_id == body.item_id, Progress.finished_at.is_(None)))
        await session.commit()
        return {"kept": False}
    stmt = insert(Progress).values(
        user_id=who.id, kind=body.kind, item_id=body.item_id,
        position_s=body.position_s, duration_s=body.duration_s,
        surface=body.surface, parent_id=body.parent_id,
    )
    await session.execute(stmt.on_conflict_do_update(
        index_elements=["user_id", "kind", "item_id"],
        # finished_at is not in the set: watching something again is not
        # unwatching it, and this sentence is only about where somebody is now
        set_={"position_s": stmt.excluded.position_s,
              "duration_s": stmt.excluded.duration_s,
              "surface": stmt.excluded.surface,
              "parent_id": func.coalesce(stmt.excluded.parent_id, Progress.parent_id),
              # the model's onupdate never fires on an upsert, so the row would
              # keep the timestamp of the first time it was ever touched
              "updated_at": func.now()},
    ))
    await session.commit()
    return {"kept": True}
