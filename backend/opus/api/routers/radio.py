"""Stations, which are the one thing to listen to that has no file.

The list is the Library's, like everything else that exists to be listened to.
What stays here is the one thing a list cannot do: carry a stream somebody else
keeps alive to a screen that may not open it for itself.
"""

import asyncio
import ipaddress
import socket
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from opus import library, stations

router = APIRouter()


async def _asked(found):
    try:
        return await found
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc


def play_url(url: str) -> str:
    """Where a client opens a station: its own address when that is https, the
    relay below when it is not, because neither a page served over https nor an
    Android app will open plain http."""
    if url.startswith("https://"):
        return url
    return f"/api/radio/stream?{urlencode({'u': url})}"


def _card(s: dict) -> dict:
    return {
        "kind": "station",
        "id": s["id"],
        "title": s["name"],
        "subtitle": " · ".join(part for part in (s["genre"], s["country"]) if part),
        "image": s["logo"],
        "backdrop": None,
        "state": None,
        "overview": "",
        "url": s["url"],
        "play_url": play_url(s["url"]),
        # a station's picture is its logo, which is square the way a sleeve is
        "square": True,
    }


@router.get("/radio/stations")
async def every_station():
    """Every station. Not one profile's: the list is the house's, and the
    house's automation asks for it with no profile picked."""
    return {"stations": [_card(s) for s in await _asked(stations.listed())]}


@router.get("/radio/stations/{station_id}")
async def station(station_id: int):
    """One station, as the list draws it. The car asks for it by the id it
    remembered when it comes back up in the middle of playing one."""
    found = await _asked(stations.by_id(station_id))
    if found is None:
        raise HTTPException(404, "no such station")
    return _card(found)


@router.get("/radio/stream")
async def stream(u: str = Query(...)):
    """A station the page is not allowed to open for itself.

    Some are served over plain http and the player is not: a browser refuses to
    open them from a page that is, and an Android app refuses cleartext
    altogether. The bytes come through here instead.

    Only a station the Library lists — a route that fetches what it is told is
    an open proxy — and a redirect is followed only to a public
    address, so a listed station cannot hand the relay a machine in the house."""
    if await _asked(stations.by_address(u)) is None:
        raise HTTPException(400, "not a station the library lists")

    asked = httpx.URL(u)

    async def public(request: httpx.Request) -> None:
        if request.url == asked:
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
        upstream = await client.send(client.build_request("GET", u), stream=True)
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
