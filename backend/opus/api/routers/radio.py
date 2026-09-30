"""Stations, which are the one thing to listen to that has no file.

Everything else the player puts on is a row in the library and a file on a
disk; a station is a name and a stream somebody else is keeping alive. That is
the only difference, and it is not a reason for radio to live outside the
player: what exists to listen to is the player's business, and the list moved
here from the house's automation, where it had ended up because that was what
could play it.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from opus.db import SessionLocal, get_session
from opus.models import RadioStation

router = APIRouter()


def play_url(url: str) -> str:
    """Where a client opens a station: its own address when that is https, the
    relay below when it is not, because neither a page served over https nor an
    Android app will open plain http."""
    if url.startswith("https://"):
        return url
    return f"/api/radio/stream?{urlencode({'u': url})}"


def _card(s: RadioStation) -> dict:
    return {
        "kind": "station",
        "id": s.id,
        "title": s.name,
        "subtitle": s.genre or s.country or "",
        "image": s.logo,
        "backdrop": None,
        "state": None,
        "overview": "",
        "url": s.url,
        "play_url": play_url(s.url),
        # a station's picture is its logo, which is square the way a sleeve is
        "square": True,
    }


@router.get("/radio/stations")
async def stations(session: AsyncSession = Depends(get_session)):
    """Every station, in the order they are kept. Not one profile's: the list
    is the house's, and the house's automation asks for it with no profile
    picked."""
    rows = (await session.execute(
        select(RadioStation).order_by(RadioStation.sort_order, RadioStation.id)
    )).scalars().all()
    return {"stations": [_card(s) for s in rows]}


@router.get("/radio/stations/{station_id}")
async def station(station_id: int, session: AsyncSession = Depends(get_session)):
    """One station, as the list draws it. The car asks for it by the id it
    remembered when it comes back up in the middle of playing one."""
    found = await session.get(RadioStation, station_id)
    if found is None:
        raise HTTPException(404, "no such station")
    return _card(found)


@router.get("/radio/stream")
async def stream(u: str = Query(...)):
    """A station the page is not allowed to open for itself.

    Some are served over plain http and the player is not: a browser refuses to
    open them from a page that is, and an Android app refuses cleartext
    altogether. The bytes come through here instead.

    Only a station this player itself lists — a route that fetches what it is
    told is an open proxy — and a redirect is followed only to a public
    address, so a listed station cannot hand the relay a machine in the house."""
    async with SessionLocal() as session:
        known = (await session.execute(
            select(RadioStation.url).where(RadioStation.url == u)
        )).scalar_one_or_none()
    if known is None:
        raise HTTPException(400, "not a station this player lists")

    listed = httpx.URL(known)

    async def public(request: httpx.Request) -> None:
        if request.url == listed:
            return
        if request.url.scheme not in ("http", "https") or request.url.userinfo:
            raise httpx.ConnectError(f"the station redirected to {request.url.scheme}://{request.url.host}",
                                     request=request)
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        try:
            found = await asyncio.get_running_loop().getaddrinfo(
                request.url.host, port, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise httpx.ConnectError(f"{request.url.host} does not resolve: {exc}", request=request) from exc
        if not all(ipaddress.ip_address(sockaddr[0].partition("%")[0]).is_global for *_, sockaddr in found):
            raise httpx.ConnectError(f"{request.url.host} is not a public address", request=request)

    client = httpx.AsyncClient(timeout=httpx.Timeout(15, read=None), follow_redirects=True,
                               max_redirects=3, event_hooks={"request": [public]})
    try:
        upstream = await client.send(client.build_request("GET", known), stream=True)
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(502, f"the station could not be reached: {exc}") from exc
    if upstream.status_code >= 400:
        await upstream.aclose()
        await client.aclose()
        raise HTTPException(502, f"the station answered {upstream.status_code}")

    async def pour():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        pour(),
        media_type=upstream.headers.get("content-type", "audio/mpeg"),
        headers={"Cache-Control": "no-store"},
    )
