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
in this half.

Played together, the same round is a party: one screen holds the questions and
the clock and everybody answers on a phone of their own. Each player still has
a round — the party's questions, their answers — so the standing counts a party
the way it counts anything else."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, game, library
from opus.api.routers.users import profile_key, require_picked
from opus.db import get_session
from opus.models import GameParty, GameRound, User

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
# how long a party stays open to be joined after the screen opened it: an
# evening, not a day
PARTY_OPEN = timedelta(hours=2)


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


def _mark(playing: GameRound, question: dict, key: str | None, elapsed: float,
          seconds: int) -> dict:
    """One answer, written on the round. The same whether the clock was the
    round's or a party's: what differs is where the clock was read."""
    ran_out = elapsed > seconds + GRACE_S
    right = bool(key) and key == question["answer"] and not ran_out
    streak = _streak(playing) + 1
    entry = {"n": question["n"], "key": key, "right": right,
             "seconds": round(elapsed, 2),
             "points": game.score(elapsed, seconds, streak) if right else 0}
    playing.answers = [*playing.answers, entry]
    if len(playing.answers) == len(playing.questions):
        playing.finished_at = _now()
    return entry


async def _build(body: NewRound) -> list[dict]:
    try:
        questions = await game.build(count=max(1, min(body.count, MOST)),
                                     hard=body.hard, kinds=tuple(body.kinds))
    except library.LibraryError as why:
        raise HTTPException(502, str(why))
    if not questions:
        raise HTTPException(503, "the library has nothing to ask about")
    return questions


async def _mine(round_id: int, user: User, session: AsyncSession) -> GameRound:
    """Held for the rest of the request: two answers to one question arriving
    together must be marked one after the other, or both find it unanswered.

    A round played in a party is not reached this way: its clock is the
    party's, and a phone that could start its own would be timing itself."""
    playing = (await session.execute(select(GameRound).where(
        GameRound.id == round_id, GameRound.user_id == user.id,
        GameRound.party_id.is_(None))
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
    questions = await _build(body)
    # a round nobody finished is not a score and cannot be picked up again
    await session.execute(delete(GameRound).where(
        GameRound.user_id == user.id, GameRound.finished_at.is_(None),
        GameRound.party_id.is_(None),
        GameRound.started_at < _now() - ABANDONED))
    playing = GameRound(user_id=user.id, questions=questions, answers=[],
                        seconds=game.SECONDS, hard=body.hard)
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
        return {**already, **_truth(question), "total": _total(playing),
                "streak": _streak(playing),
                "done": playing.finished_at is not None}

    if playing.asked_n == body.n and playing.asked_at:
        elapsed = (_now() - playing.asked_at).total_seconds()
    else:
        # never handed out, so there is no clock to read. The answer still
        # counts; the bonus for beating a clock that was never running does not.
        elapsed = playing.seconds
    entry = _mark(playing, question, body.key, elapsed, playing.seconds)
    playing.asked_n = None
    playing.asked_at = None
    await session.commit()
    return {**entry, **_truth(question), "total": _total(playing),
            "streak": _streak(playing), "done": playing.finished_at is not None}


def _truth(question: dict) -> dict:
    """What a question turns out to have been, once it may be said."""
    told = {"correct": question["answer"], "facts": question["facts"]}
    if "second_facts" in question:
        told["second_facts"] = question["second_facts"]
    return told


async def _named(session: AsyncSession) -> dict[int, dict]:
    """Everybody here, by what the house calls them. What each of them is
    CALLED is the roster's answer, not this module's: a profile on the roster
    carries no name here on purpose, and a table that printed the key would
    call somebody "filip" in front of the whole house."""
    users = (await session.execute(select(User))).scalars().all()
    roster = await auth.authority.people()
    named = {}
    for who in users:
        key = profile_key(who)
        on = roster.get(key)
        named[who.id] = {"key": key,
                         "name": (on.display if on else "") or who.name or who.person,
                         "colour": who.colour}
    return named


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
    named = await _named(session)
    standing: dict[int, dict] = {}
    for one in rounds:
        who = named.get(one.user_id)
        if who is None:
            continue
        row = standing.setdefault(one.user_id, {
            **who, "rounds": 0, "points": 0, "best": 0, "right": 0, "asked": 0})
        points = _total(one)
        row["rounds"] += 1
        row["points"] += points
        row["best"] = max(row["best"], points)
        row["right"] += sum(1 for a in one.answers if a["right"])
        row["asked"] += len(one.answers)
    table = sorted(standing.values(), key=lambda r: r["points"], reverse=True)
    return {"standing": table, "me": profile_key(user)}


# ---------------------------------------------------------------- together


class Picked(BaseModel):
    n: int
    key: str | None = None


async def _party(party_id: int, session: AsyncSession, lock: bool = False) -> GameParty:
    query = select(GameParty).where(GameParty.id == party_id)
    if lock:
        query = query.with_for_update()
    party = (await session.execute(query)).scalar_one_or_none()
    if party is None:
        raise HTTPException(404, "no such party")
    return party


async def _hosted(party_id: int, user: User, session: AsyncSession) -> GameParty:
    party = await _party(party_id, session, lock=True)
    if party.host_id != user.id:
        raise HTTPException(403, "not this screen's party")
    return party


async def _rounds(party: GameParty, session: AsyncSession, lock: bool = False) -> list[GameRound]:
    query = select(GameRound).where(GameRound.party_id == party.id).order_by(GameRound.id)
    if lock:
        query = query.with_for_update()
    return list((await session.execute(query)).scalars())


async def _view(party: GameParty, user: User, session: AsyncSession) -> dict:
    """The party as one screen sees it. The host is handed every question so
    its pictures are decoded before they come up; a player is handed the one
    on the screen, and what was right only once the screen has said so."""
    rounds = await _rounds(party, session)
    named = await _named(session)
    n = party.asked_n
    question = party.questions[n] if n is not None else None
    players = []
    for one in rounds:
        given = next((a for a in one.answers if a["n"] == n), None) if n is not None else None
        players.append({
            **named.get(one.user_id, {"key": "", "name": "", "colour": ""}),
            "total": _total(one),
            "answered": given is not None,
            # which answer and whether it was right stay unsaid until the reveal:
            # a phone that could see its neighbour's mark could see the answer
            "picked": given["key"] if given and party.revealed else None,
            "right": given["right"] if given and party.revealed else None,
            "points": given["points"] if given and party.revealed else None,
        })
    mine = ("host" if party.host_id == user.id else
            "player" if any(r.user_id == user.id for r in rounds) else None)
    # what is left of the clock, said by the one holding it: a phone that
    # subtracted the server's timestamp from its own time would be out by
    # whatever its clock is out by
    left = None
    if n is not None and party.asked_at and not party.revealed:
        left = max(0.0, party.seconds - (_now() - party.asked_at).total_seconds())
    view = {
        "id": party.id, "seconds": party.seconds, "count": len(party.questions),
        "host": named.get(party.host_id), "mine": mine, "me": profile_key(user),
        "n": n, "left": round(left, 2) if left is not None else None,
        "revealed": party.revealed, "done": party.finished_at is not None,
        "question": game.asked(question) if question else None,
        "players": players,
    }
    if question and party.revealed:
        view.update(_truth(question))
    if mine == "host":
        view["questions"] = [game.asked(q) for q in party.questions]
    return view


@router.post("/game/parties", status_code=201)
async def open_party(body: NewRound, user: User = Depends(require_picked),
                     session: AsyncSession = Depends(get_session)):
    """Open a party on this screen. The questions are built now, before anybody
    has joined: they are nobody's in particular, and the screen has the whole
    wait to decode the pictures."""
    questions = await _build(body)
    # one party per screen. Whatever this screen had open and did not finish
    # goes, rounds and all — they were never scores.
    await session.execute(delete(GameParty).where(
        GameParty.host_id == user.id, GameParty.finished_at.is_(None)))
    party = GameParty(host_id=user.id, questions=questions, seconds=game.SECONDS,
                      hard=body.hard)
    session.add(party)
    await session.commit()
    await session.refresh(party)
    return await _view(party, user, session)


@router.get("/game/parties")
async def open_parties(user: User = Depends(require_picked),
                       session: AsyncSession = Depends(get_session)):
    """The parties a phone could join: open, and opened this evening."""
    parties = (await session.execute(select(GameParty).where(
        GameParty.finished_at.is_(None),
        GameParty.started_at > _now() - PARTY_OPEN).order_by(GameParty.id.desc()))).scalars().all()
    named = await _named(session)
    out = []
    for party in parties:
        rounds = await _rounds(party, session)
        out.append({"id": party.id, "host": named.get(party.host_id),
                    "players": len(rounds), "under_way": party.asked_n is not None,
                    "mine": ("host" if party.host_id == user.id else
                             "player" if any(r.user_id == user.id for r in rounds) else None)})
    return out


@router.get("/game/parties/{party_id}")
async def party_state(party_id: int, user: User = Depends(require_picked),
                      session: AsyncSession = Depends(get_session)):
    return await _view(await _party(party_id, session), user, session)


@router.post("/game/parties/{party_id}/join")
async def join_party(party_id: int, user: User = Depends(require_picked),
                     session: AsyncSession = Depends(get_session)):
    """Sit down at the party: a round of its questions, in this player's name.
    Joining twice is sitting in the same chair. Joining late is allowed — the
    questions already shown are marked as unanswered when the screen reveals
    them, which is what they were."""
    party = await _party(party_id, session, lock=True)
    if party.finished_at is not None:
        raise HTTPException(409, "that party is over")
    if party.host_id == user.id:
        raise HTTPException(409, "the screen asks; it does not answer")
    rounds = await _rounds(party, session)
    if not any(r.user_id == user.id for r in rounds):
        session.add(GameRound(user_id=user.id, party_id=party.id,
                              questions=party.questions, answers=[],
                              seconds=party.seconds, hard=party.hard))
        await session.commit()
    return await _view(party, user, session)


@router.post("/game/parties/{party_id}/ask")
async def ask_party(party_id: int, body: Start, user: User = Depends(require_picked),
                    session: AsyncSession = Depends(get_session)):
    """The screen has put a question up. Its clock starts here, for everybody."""
    party = await _hosted(party_id, user, session)
    if not 0 <= body.n < len(party.questions):
        raise HTTPException(404, "no such question")
    party.asked_n = body.n
    party.asked_at = _now()
    party.revealed = False
    await session.commit()
    return await _view(party, user, session)


@router.post("/game/parties/{party_id}/reveal")
async def reveal_party(party_id: int, user: User = Depends(require_picked),
                       session: AsyncSession = Depends(get_session)):
    """The screen is showing the answer. Whoever has not answered by now has
    not answered — written down as such, so every round keeps step with the
    party and finishes when it does."""
    party = await _hosted(party_id, user, session)
    if party.asked_n is None:
        raise HTTPException(409, "nothing is being asked")
    question = party.questions[party.asked_n]
    for one in await _rounds(party, session, lock=True):
        if not any(a["n"] == party.asked_n for a in one.answers):
            _mark(one, question, None, party.seconds, party.seconds)
    party.revealed = True
    if party.asked_n == len(party.questions) - 1:
        party.finished_at = _now()
    await session.commit()
    return await _view(party, user, session)


@router.post("/game/parties/{party_id}/answer")
async def answer_party(party_id: int, body: Picked, user: User = Depends(require_picked),
                       session: AsyncSession = Depends(get_session)):
    """One player's answer to the question on the screen, timed from when the
    screen put it up. Nothing of the mark comes back yet: the screen reveals,
    and a phone told early is a phone that can be looked at."""
    party = await _party(party_id, session, lock=True)
    if party.asked_n != body.n or party.asked_at is None:
        raise HTTPException(409, "that question is not on the screen")
    if party.revealed:
        raise HTTPException(409, "that one has been revealed")
    playing = (await session.execute(select(GameRound).where(
        GameRound.party_id == party.id, GameRound.user_id == user.id)
        .with_for_update())).scalar_one_or_none()
    if playing is None:
        raise HTTPException(404, "not at this party")
    if any(a["n"] == body.n for a in playing.answers):
        return {"answered": True}
    elapsed = (_now() - party.asked_at).total_seconds()
    _mark(playing, party.questions[body.n], body.key, elapsed, party.seconds)
    await session.commit()
    return {"answered": True}


@router.delete("/game/parties/{party_id}", status_code=204)
async def close_party(party_id: int, user: User = Depends(require_picked),
                      session: AsyncSession = Depends(get_session)):
    """The screen has left. An unfinished party goes with its rounds, which
    were never scores; a finished one stays, being nine or ten of them."""
    party = await _hosted(party_id, user, session)
    if party.finished_at is None:
        await session.delete(party)
        await session.commit()
