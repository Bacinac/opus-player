"""Pictures and map tiles, which are the Library's.

Every picture the catalogue hands out is the Library's own address,
/api/pictures/{id}. This module answers on the same path, so an address the
Library wrote opens unchanged on either origin, and the bytes come through on
this module's token.

The picture route asks for no credential. A car can present one only in the
address, where every app that reads a browse tree would read it too, and what
stands behind it is a cover by its number — the Library decides what a number
is, so nothing here can be steered anywhere else."""

import re
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from opus import library

router = APIRouter()

ADDRESS = re.compile(r"^/api/pictures/\d+$")

# what the Library says about a picture that a browser needs in order to keep it
CARRIED = ("content-length", "cache-control", "etag", "last-modified")


def ours(address: str | None) -> bool:
    return bool(address) and ADDRESS.match(address) is not None


def named_by(address: str | None) -> str | None:
    """The picture an address names, whichever origin it was written for: a
    device in the house hands back the whole address it was given."""
    path = urlsplit(address or "").path
    return path if ADDRESS.match(path) else None


async def _through(path: str, kind: str, **params) -> StreamingResponse:
    http = library.client()
    try:
        resp = await http.send(http.build_request("GET", path, params=params or None), stream=True)
    except httpx.HTTPError as why:
        raise HTTPException(502, f"the library could not be reached ({type(why).__name__})") from None
    if resp.status_code != 200:
        await resp.aread()
        await resp.aclose()
        # a refusal of this module's own token is this module failing, not the
        # screen that asked
        status = 502 if resp.status_code in (401, 403) else resp.status_code
        raise HTTPException(status, library.refusal(path, resp))

    async def bytes_through():
        # the response is closed, the client is not: it is shared by every
        # picture on the same screen
        try:
            async for chunk in resp.aiter_bytes():
                yield chunk
        finally:
            await resp.aclose()

    return StreamingResponse(
        bytes_through(), media_type=resp.headers.get("content-type", kind),
        headers={name: resp.headers[name] for name in CARRIED if name in resp.headers})


@router.get("/pictures/{picture_id}")
async def picture(picture_id: int, w: int = Query(320, ge=1, le=4096)):
    return await _through(f"/pictures/{picture_id}", "image/jpeg", w=w)


@router.get("/tiles/{z}/{x}/{y}.png")
async def tile(z: int, x: int, y: int):
    return await _through(f"/tiles/{z}/{x}/{y}.png", "image/png")
