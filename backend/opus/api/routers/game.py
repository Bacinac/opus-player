"""Who, where, when.

The archive as a game: a photograph, four answers, twenty seconds. The
questions are built next door in `game.py` out of what the library knows; this
holds the round while it is being played, keeps the clock, and marks the
answers.

The clock is the server's. A screen that reported how long it had taken would
be reporting the number it is being scored on — so a question is handed out at
`start`, and what counts is the time between that and the answer arriving.

The answers never leave here until they have been answered. The round travels
to the screen with its pictures and its options; which of them is right stays
in this half."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, game, library
from opus.api.routers.users import profile_key, require_picked
from opus.db import get_session
from opus.models import GameRound, User

router = APIRouter()

# what the network is allowed to cost somebody. An answer sent at nineteen
# seconds and nine hundred milliseconds must not become a timeout because it
# spent a moment on the wire.
GRACE_S = 1.5


# Ten is the round. Longer and the last questions are answered by somebody who
# has stopped looking at the photographs.
MOST = 10

# long past the longest a round of ten can take, so a round still being played on
# another screen is never the one taken away
ABANDONED = timedelta(hours=6)


class NewRound(BaseModel):
    count: int = MOST
    hard: float | None = None
    kinds: list[str] = list(game.KINDS)


class Start(BaseModel):
    n: int


class Answer(BaseModel):
    n: int
    # nothing, where the clock ran out. Said outright rather than left to a
    # missing request: a question nobody answered is an answer.
    key: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _total(playing: GameRound) -> int:
    return sum(a["points"] for a in playing.answers)


def _streak(playing: GameRound) -> int:
    """How long the run ending with the last answer is."""
    run = 0
    for answer in reversed(playing.answers):
        if not answer["right"]:
            break
        run += 1
    return run


async def _mine(round_id: int, user: User, session: AsyncSession) -> GameRound:
    """Held for the rest of the request: two answers to one question arriving
    together must be marked one after the other, or both find it unanswered."""
    playing = (await session.execute(select(GameRound).where(
        GameRound.id == round_id, GameRound.user_id == user.id)
        .with_for_update())).scalar_one_or_none()
    if playing is None:
        raise HTTPException(404, "no such round")
    return playing


@router.post("/game/rounds", status_code=201)
async def new_round(body: NewRound, user: User = Depends(require_picked),
                    session: AsyncSession = Depends(get_session)):
    """Build a round and hand over the half that may be seen.

    Every question at once, pictures and all, so the screen can have the next
    photograph decoded before it is asked for. A game with a clock on it cannot
    also have a spinner."""
    try:
        questions = await game.build(count=max(1, min(body.count, MOST)),
                                     hard=body.hard,
                                     kinds=tuple(body.kinds))
    except library.LibraryError as why:
        raise HTTPException(502, str(why))
    if not questions:
        raise HTTPException(503, "the library has nothing to ask about")
    # a round nobody finished is not a score and cannot be picked up again
    await session.execute(delete(GameRound).where(
        GameRound.user_id == user.id, GameRound.finished_at.is_(None),
        GameRound.started_at < _now() - ABANDONED))
    playing = GameRound(user_id=user.id, questions=questions, answers=[],
                        seconds=game.SECONDS)
    session.add(playing)
    await session.commit()
    await session.refresh(playing)
    return {"id": playing.id, "seconds": playing.seconds,
            "questions": [game.asked(q) for q in questions]}


@router.post("/game/rounds/{round_id}/start")
async def start(round_id: int, body: Start, user: User = Depends(require_picked),
                session: AsyncSession = Depends(get_session)):
    """The question is on the screen now. This is where its clock starts."""
    playing = await _mine(round_id, user, session)
    if not 0 <= body.n < len(playing.questions):
        raise HTTPException(404, "no such question")
    if any(a["n"] == body.n for a in playing.answers):
        raise HTTPException(409, "that one has been answered")
    playing.asked_n = body.n
    playing.asked_at = _now()
    await session.commit()
    return {"seconds": playing.seconds}


@router.post("/game/rounds/{round_id}/answer")
async def answer(round_id: int, body: Answer, user: User = Depends(require_picked),
                 session: AsyncSession = Depends(get_session)):
    """Mark one answer, and say what the photograph actually was.

    Marking is what the reveal is made of, so everything the picture turned out
    to be goes back with it — who, where and when, not only the fact that was
    asked about."""
    playing = await _mine(round_id, user, session)
    if not 0 <= body.n < len(playing.questions):
        raise HTTPException(404, "no such question")
    question = playing.questions[body.n]
    already = next((a for a in playing.answers if a["n"] == body.n), None)
    if already:
        # the same answer twice is the same answer: a screen that retried a
        # request must not be able to score the question twice
        return {**already, "correct": question["answer"],
                "facts": question["facts"], "total": _total(playing),
                "streak": _streak(playing),
                "done": playing.finished_at is not None}

    if playing.asked_n == body.n and playing.asked_at:
        elapsed = (_now() - playing.asked_at).total_seconds()
    else:
        # never handed out, so there is no clock to read. The answer still
        # counts; the bonus for beating a clock that was never running does not.
        elapsed = playing.seconds
    ran_out = elapsed > playing.seconds + GRACE_S
    right = bool(body.key) and body.key == question["answer"] and not ran_out
    streak = _streak(playing) + 1
    entry = {"n": body.n, "key": body.key, "right": right,
             "seconds": round(elapsed, 2),
             "points": game.score(elapsed, playing.seconds, streak) if right else 0}
    playing.answers = [*playing.answers, entry]
    if len(playing.answers) == len(playing.questions):
        playing.finished_at = _now()
    playing.asked_n = None
    playing.asked_at = None
    await session.commit()
    return {**entry, "correct": question["answer"], "facts": question["facts"],
            "total": _total(playing), "streak": _streak(playing),
            "done": playing.finished_at is not None}


@router.get("/game/scores")
async def scores(user: User = Depends(require_picked),
                 session: AsyncSession = Depends(get_session)):
    """The house's standing. Finished rounds only — a round somebody walked
    away from halfway is not a score, and counting it would make quitting a
    tactic.

    Totals are added up from the answers rather than read from a column that
    claims to know them, which is the same reason there is no such column."""
    rounds = (await session.execute(select(GameRound.user_id, GameRound.answers).where(
        GameRound.finished_at.isnot(None)))).all()
    users = {u.id: u for u in (await session.execute(select(User))).scalars()}
    # what each of them is CALLED is the roster's answer, not this module's: a
    # profile on the roster carries no name here on purpose, and a table of
    # scores that printed the key would call somebody "filip" in front of the
    # whole house
    roster = await auth.authority.people()
    standing: dict[int, dict] = {}
    for one in rounds:
        who = users.get(one.user_id)
        if who is None:
            continue
        key = profile_key(who)
        named = roster.get(key)
        row = standing.setdefault(one.user_id, {
            "key": key,
            "name": (named.display if named else "") or who.name or who.person,
            "colour": who.colour,
            "rounds": 0, "points": 0, "best": 0, "right": 0, "asked": 0})
        points = _total(one)
        row["rounds"] += 1
        row["points"] += points
        row["best"] = max(row["best"], points)
        row["right"] += sum(1 for a in one.answers if a["right"])
        row["asked"] += len(one.answers)
    table = sorted(standing.values(), key=lambda r: r["points"], reverse=True)
    return {"standing": table, "me": profile_key(user)}
