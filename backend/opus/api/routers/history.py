"""Where somebody's listening and watching is kept as well: their own
ListenBrainz and Simkl, linked from their settings. What is sent, and when, is
opus.history's."""

import httpx
import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, history
from opus.api.routers.users import require_picked
from opus.db import get_session
from opus.models import HistoryLink, HistorySend, User
from opus.settings_store import current_runtime

router = APIRouter()


async def require_history_profile(request: Request, who: User = Depends(require_picked)) -> User:
    person = await auth.person(request.cookies.get(opus_auth.SESSION_COOKIE), auth.bearer_of(request))
    if person is None or (person.role != opus_auth.ADMIN and who.person != person.name):
        raise HTTPException(403, "only the person or an admin may manage this history")
    return who


async def _state(session: AsyncSession, who: User) -> dict:
    linked = dict((await session.execute(select(HistoryLink.service, HistoryLink.account)
                                         .where(HistoryLink.user_id == who.id))).all())
    stuck = HistorySend.due_at.is_(None)
    counted = {(service, unknown): n for service, unknown, n in (await session.execute(
        select(HistorySend.service, stuck, func.count()).where(HistorySend.user_id == who.id)
        .group_by(HistorySend.service, stuck))).all()}
    problems = dict((await session.execute(
        select(HistorySend.service, HistorySend.problem)
        .where(HistorySend.user_id == who.id, HistorySend.problem != "",
               HistorySend.problem != history.UNKNOWN)
        .order_by(HistorySend.service, HistorySend.id.desc())
        .distinct(HistorySend.service))).all())
    return {
        "simkl_ready": history.simkl_ready(await current_runtime()),
        "services": [{"service": service, "account": linked.get(service),
                      "waiting": counted.get((service, False), 0),
                      "unknown": counted.get((service, True), 0),
                      "problem": problems.get(service, "")}
                     for service in history.KEEPS],
    }


async def _link(session: AsyncSession, who: User, service: str) -> HistoryLink:
    link = (await session.execute(select(HistoryLink).where(
        HistoryLink.user_id == who.id, HistoryLink.service == service))).scalar_one_or_none()
    if link is None:
        await history.backlog(session, who.id, service)
        link = HistoryLink(user_id=who.id, service=service)
        session.add(link)
    return link


async def _simkl():
    config = await current_runtime()
    if not history.simkl_ready(config):
        raise HTTPException(409, "Simkl is not set up on this install")
    return config


@router.get("/history")
async def linked(who: User = Depends(require_history_profile), session: AsyncSession = Depends(get_session)):
    return await _state(session, who)


class Token(BaseModel):
    token: str = Field(min_length=1, max_length=200)


@router.put("/history/listenbrainz")
async def link_listenbrainz(body: Token, who: User = Depends(require_history_profile),
                            session: AsyncSession = Depends(get_session)):
    token = body.token.strip()
    try:
        account = await history.listenbrainz_account(token)
    except history.Refused as exc:
        raise HTTPException(400, str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"ListenBrainz could not be reached: {exc}") from exc
    link = await _link(session, who, "listenbrainz")
    link.account, link.token, link.refresh, link.expires_at = account, token, "", None
    await session.commit()
    history.sender.kick()
    return await _state(session, who)


@router.post("/history/simkl/code")
async def simkl_code(who: User = Depends(require_history_profile)):
    config = await _simkl()
    try:
        code = await history.simkl_code(config)
    except (history.Refused, httpx.HTTPError) as exc:
        raise HTTPException(502, str(exc)) from exc
    return {key: code[key] for key in ("device_code", "user_code", "verification_uri",
                                       "verification_uri_complete", "expires_in", "interval")}


class Code(BaseModel):
    device_code: str = Field(min_length=1, max_length=200)


@router.post("/history/simkl/token")
async def simkl_token(body: Code, who: User = Depends(require_history_profile),
                      session: AsyncSession = Depends(get_session)):
    """Asked every few seconds while the code waits to be approved."""
    config = await _simkl()
    try:
        grant = await history.simkl_grant(config, body.device_code)
        if grant is None:
            return {"linked": False}
        if grant == "slow":
            return {"linked": False, "slower": True}
        if isinstance(grant, str):
            return {"linked": False, "ended": grant}
        account = await history.simkl_account(config, grant["access_token"])
    except (history.Refused, httpx.HTTPError) as exc:
        raise HTTPException(502, str(exc)) from exc
    link = await _link(session, who, "simkl")
    link.account = account
    history.keep_grant(link, grant)
    await session.commit()
    history.sender.kick()
    return {"linked": True}


@router.delete("/history/{service}", status_code=204)
async def unlink(service: str, who: User = Depends(require_history_profile),
                 session: AsyncSession = Depends(get_session)):
    """What had not gone yet goes nowhere now: it was on its way to an account
    that is no longer this person's to write to."""
    if service not in history.KEEPS:
        raise HTTPException(404, "no such service")
    for table in (HistoryLink, HistorySend):
        await session.execute(delete(table).where(table.user_id == who.id, table.service == service))
    await session.commit()


@router.post("/history/retry", status_code=204)
async def retry(who: User = Depends(require_history_profile), session: AsyncSession = Depends(get_session)):
    """Everything waiting, now — including what a service said it did not know,
    which it may since have learnt."""
    await session.execute(update(HistorySend).where(HistorySend.user_id == who.id)
                          .values(due_at=func.now()))
    await session.commit()
    history.sender.kick()
