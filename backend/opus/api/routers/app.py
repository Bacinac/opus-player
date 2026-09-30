"""Handing the Android app to a phone that is standing in the room.

A television is installed once by somebody with a cable; a phone is installed by
whoever is holding it, and telling them a path to type is how it does not happen.
So the install page shows a square to point a camera at, and what the camera
finds is this file.

Unauthenticated on purpose, like the version endpoint: an APK is not a secret,
it is signed, and the phone asks what version is here before it has any session
to ask with. A missing artifact answers 404 and says so in the log — a download
that silently hands back nothing is worse than one that fails.
"""

import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Annotated

import opus_auth
import segno
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from opus_core.responses import FileResponse
from pydantic import BaseModel, Field

from opus import auth

log = logging.getLogger(__name__)
router = APIRouter()

# where android/build.sh's output is mounted, read-only
SHELF = Path("/apk")
APK = SHELF / "opus-player.apk"
META = SHELF / "apk.json"
# the second app on the shelf: the one the car runs, which has no screen of
# ours and needs none — it is Android Auto's browse tree over this library
MUSIC_APK = SHELF / "opus-music.apk"
MUSIC_META = SHELF / "music.json"


def _origin(request: Request) -> str:
    """The address the phone will use, which is the one the browser is already
    on — not this container's idea of itself. Behind Caddy that is only knowable
    from what Caddy forwarded."""
    head = request.headers
    # Two proxies stand in front of this, and the second appends rather than
    # replaces: what arrives is "https,http" — the browser's hop first, then the
    # node server's own. The first is the one the phone will use.
    said = head.get("x-forwarded-proto", "")
    scheme = said.split(",")[0].strip() or request.url.scheme
    host = (head.get("x-forwarded-host") or head.get("host")
            or request.url.netloc).split(",")[0].strip()
    return f"{scheme}://{host}"


@router.get("/app/apk.json")
async def apk_meta():
    """Which version is on the shelf. Read from the file the build wrote rather
    than worked out here: the version is decided where it is stamped."""
    if not META.exists():
        log.error("no APK metadata at %s — android/build.sh has not run here", META)
        raise HTTPException(404, "no app has been built for this install")
    return json.loads(META.read_text())


@router.get("/app/opus.apk")
async def apk():
    if not APK.exists():
        log.error("no APK at %s — android/build.sh has not run here", APK)
        raise HTTPException(404, "no app has been built for this install")
    return FileResponse(
        APK, media_type="application/vnd.android.package-archive",
        filename="opus-player.apk")


@router.get("/app/opus-tv.apk")
async def tv_apk():
    """The same signed universal Player binary under its television-facing
    product name. Keeping one package identity means an existing installation
    upgrades normally instead of becoming a second app."""
    if not APK.exists():
        log.error("no APK at %s — android/build.sh has not run here", APK)
        raise HTTPException(404, "no app has been built for this install")
    return FileResponse(
        APK, media_type="application/vnd.android.package-archive",
        filename="opus-tv.apk")


@router.get("/app/music.json")
async def music_meta():
    if not MUSIC_META.exists():
        log.error("no music app metadata at %s — android/build.sh has not run here", MUSIC_META)
        raise HTTPException(404, "no music app has been built for this install")
    return json.loads(MUSIC_META.read_text())


@router.get("/app/opus-music.apk")
async def music_apk():
    if not MUSIC_APK.exists():
        log.error("no music APK at %s — android/build.sh has not run here", MUSIC_APK)
        raise HTTPException(404, "no music app has been built for this install")
    return FileResponse(
        MUSIC_APK, media_type="application/vnd.android.package-archive",
        filename="opus-music.apk")


class Crash(BaseModel):
    app: str = Field(..., max_length=100)
    version: str = Field("", max_length=50)
    thread: str = Field("", max_length=200)
    stack: str = Field(..., min_length=1, max_length=16000)
    occurred_at_ms: int = Field(..., ge=0)
    device: str = Field("", max_length=200)


async def _reporter(request: Request) -> str:
    """Who is reporting, under an open prefix: the car's bearer, a person's
    cookie or a box that was let in. A stranger cannot fill the log."""
    found = await auth.person(request.cookies.get(opus_auth.SESSION_COOKIE), auth.bearer_of(request))
    box = None if found else await auth.device(request.cookies.get(auth.DEVICE_COOKIE))
    if found is None and box is None:
        raise HTTPException(401, "authentication required")
    return found.name if found else box.name


@router.post("/app/crash-report", status_code=204)
async def crash_report(body: Crash, request: Request):
    """An app that died says so on its next start."""
    who = await _reporter(request)
    log.error("crash in %s %s (%s, %s) reported by %s at %d:\n%s",
              body.app, body.version, body.device, body.thread, who,
              body.occurred_at_ms, body.stack)


class PlaybackReport(BaseModel):
    app: str = Field(..., max_length=100)
    version: str = Field("", max_length=50)
    device: str = Field("", max_length=200)
    url: str = Field("", max_length=500)
    events: list[Annotated[str, Field(max_length=1000)]] = Field(..., min_length=1, max_length=200)


@router.post("/app/playback-report", status_code=204)
async def playback_report(body: PlaybackReport, request: Request):
    """A film the box could not show properly, told from its open to its stop.
    The box overwrites its own log within hours; this is what is left to read
    the morning after."""
    who = await _reporter(request)
    log.warning("playback trouble in %s %s (%s) reported by %s for %s:\n%s",
                body.app, body.version, body.device, who, body.url, "\n".join(body.events))


@router.get("/app/qr.svg")
async def qr(request: Request):
    """The square. It carries the download address and nothing else — no token,
    no session: what it opens is a public file, so a photograph of this screen
    gives away nothing that the address itself does not."""
    if not APK.exists():
        raise HTTPException(404, "no app has been built for this install")
    drawn = segno.make(f"{_origin(request)}/api/app/opus.apk", error="m")
    out = BytesIO()
    drawn.save(out, kind="svg", scale=1, border=2, svgclass=None, xmldecl=False)
    square = out.getvalue().decode()

    # Two things segno will not do itself. The ink is the page's, so the square
    # reads on a dark screen as well as a light one — and it will not take a
    # keyword for a colour. And a fixed width in a stylesheet's way is a square
    # that cannot grow: swapped for a viewBox, it becomes whatever the page
    # gives it.
    square = square.replace('"#000"', '"currentColor"')
    side = re.search(r'width="(\d+)" height="(\d+)"', square)
    if side:
        square = square.replace(
            side.group(0), f'viewBox="0 0 {side.group(1)} {side.group(2)}"')

    return Response(square, media_type="image/svg+xml",
                    headers={"Cache-Control": "no-cache"})
