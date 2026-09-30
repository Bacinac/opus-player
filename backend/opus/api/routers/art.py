"""Pictures, at the size the screen draws them, off the player's own disk.

What the catalogue keeps is the address of a picture, not the picture. For an
artist that address is a thousand pixels square on Deezer's CDN: 134 kB and a
megapixel to decode for a face a shelf draws at three hundred — and the CDN
dates its own answers in the past and offers nothing to revalidate against, so
the whole shelf is fetched again on every visit. Two hundred and forty-three
artists is thirty megabytes, every time the screen is opened.

So the size is asked for here, and the answer is kept. Nothing is decoded:
every source the catalogue uses names the size in its own address, so the CDN
does the resizing and the player only stores what came back and serves it off
the LAN with a year on it. One file per picture per size, keyed by the address
as the source needs it — anything else somebody appends to it is not a second
picture — and the whole of it held under a bound, the pictures looked at
longest ago going first.

The route asks for no credential. Everything it fetches is a public picture on
a public image service, so a key in front of it protected nothing, while the one
way a car could present that key — in the address — handed it to every app that
reads a browse tree. What keeps it from being an open proxy is that it fetches
only what has the shape of a picture on the hosts the catalogue uses, and
follows no redirect off them."""

import asyncio
import hashlib
import ipaddress
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import APIRouter, HTTPException
from opus_core import plugins
from opus_core.responses import FileResponse
from sqlalchemy import select

from opus.config import settings
from opus.db import SessionLocal
from opus.models import RadioStation
from opus.plugins import ART

router = APIRouter()


@dataclass(frozen=True)
class Source:
    path: re.Pattern
    query: tuple[str, ...] = ()
    # the same picture asked for at another edge, for a source a plugin adds
    sized: Callable[[str, int], str] | None = None


_IMAGE = r"\.(jpe?g|png|gif|webp|svg|tiff?)"
_WIKI_FILE = r"[0-9a-f]/[0-9a-f]{2}/[^/]+" + _IMAGE

# Only the addresses the catalogue itself hands out. Without a list of who it
# will fetch from, a route that fetches what it is told is an open proxy.
SOURCES = {
    "cdn-images.dzcdn.net": Source(re.compile(r"^/images/[a-z]+/[0-9a-f]{32}/\d+x\d+-[0-9a-z-]+\.(jpg|png|webp)$")),
    "e-cdns-images.dzcdn.net": Source(re.compile(r"^/images/[a-z]+/[0-9a-f]{32}/\d+x\d+-[0-9a-z-]+\.(jpg|png|webp)$")),
    "image.tmdb.org": Source(re.compile(r"^/t/p/(w\d+|original)/[A-Za-z0-9_-]+\.(jpg|jpeg|png|webp|svg)$")),
    "i.discogs.com": Source(re.compile(r"^/[A-Za-z0-9_-]{20,}(/[a-z]+:[A-Za-z0-9]+)+(/[A-Za-z0-9_-]+)+\.(jpeg|jpg|png|webp|gif)$")),
    "is1-ssl.mzstatic.com": Source(re.compile(r"^/image/thumb/[A-Za-z0-9._/-]+/\d+x\d+bb\.(jpg|jpeg|png|webp)$")),
    # Library searches Spotify as well as Deezer, so an artist imported from
    # there carries a Spotify face. Its addresses hold no size and no signature:
    # asked for exactly as given.
    "i.scdn.co": Source(re.compile(r"^/image/[0-9a-f]{40}$")),
    "upload.wikimedia.org": Source(re.compile(
        rf"^/wikipedia/[a-z-]+/(thumb/)?{_WIKI_FILE}(/\d+px-[^/]+)?$", re.IGNORECASE)),
    "commons.wikimedia.org": Source(re.compile(
        rf"^/(wiki/Special:FilePath/[^/]+{_IMAGE}|w/index\.php)$", re.IGNORECASE), ("title", "width")),
    "thumb.wikimedia.org": Source(re.compile(
        rf"^/wikipedia/[a-z-]+/thumb/{_WIKI_FILE}/\d+px-[^/]+$", re.IGNORECASE)),
}

PLUGGED = dict(ART)
if clash := set(PLUGGED) & set(SOURCES):
    raise plugins.PluginError(f"a plugin names a picture host the Player already has: {', '.join(sorted(clash))}")


def _source(host: str) -> Source | None:
    if (plugged := PLUGGED.get(host)) is not None:
        return plugins.resolve(plugged)
    return SOURCES.get(host)


# A station's logo lives wherever that station lives — one host per station, and
# the list grows whenever a station is added. Naming those hosts here would be
# writing the catalogue down twice, so the logos the list itself holds are asked
# instead, address for address: only what the list hands out.
_logos: set[str] = set()
_asked_at = 0.0
_LOGOS_TTL = 300


async def _station_logos() -> set[str]:
    global _logos, _asked_at
    if time.monotonic() - _asked_at < _LOGOS_TTL:
        return _logos
    async with SessionLocal() as session:
        rows = (await session.execute(select(RadioStation.logo))).scalars().all()
    _logos = {r for r in rows if r}
    _asked_at = time.monotonic()
    return _logos


# Where a source takes any number the edge is asked for as it is; where it keeps
# a menu, the smallest entry that still covers the screen. Asking one of those
# for a size it does not list answers with a 404 or with the full-size picture,
# depending on the CDN.
TMDB_WIDTHS = (92, 154, 185, 342, 500, 780)

_DEEZER = re.compile(r"/\d+x\d+-")
_TMDB = re.compile(r"/t/p/(?:w\d+|original)/")
_APPLE = re.compile(r"/\d+x\d+bb\.")
_WIKI_THUMB = re.compile(r"/\d+px-")

KINDS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/avif": ".avif",
    "image/gif": ".gif",
}
# A poster at the size a poster is drawn is tens of kilobytes. Anything past this
# is not artwork, whatever it calls itself.
MOST = 12 * 1024 * 1024

# The sizes kept. A width anybody could type would be a file per width anybody
# typed; the screen gets the smallest of these that covers what it draws.
WIDTHS = (160, 320, 480, 640, 960, 1280, 1920)

_http: httpx.AsyncClient | None = None
_opening = asyncio.Lock()


async def _fetcher() -> httpx.AsyncClient:
    global _http
    if _http is None:
        async with _opening:
            if _http is None:
                _http = httpx.AsyncClient(
                    timeout=20, follow_redirects=False,
                    limits=httpx.Limits(max_connections=16),
                    # Wikimedia refuses an anonymous client library by policy and
                    # answers 403; saying who is asking is the price of the two
                    # dozen artists whose only picture is on Commons
                    headers={"User-Agent": "OPUS-Player (https://boskovic.biz)"})
    return _http


def _menu(edge: int, sizes: tuple[int, ...]) -> int:
    return next((s for s in sizes if s >= edge), sizes[-1])


def _literal_inside(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return not address.is_global


def picture(url: str) -> str | None:
    parts = urlsplit(url)
    host = parts.hostname or ""
    source = _source(host)
    if (source is None or parts.scheme not in ("http", "https") or parts.username
            or parts.password or not source.path.match(parts.path)):
        return None
    asked = dict(parse_qsl(parts.query))
    kept = [(name, asked[name]) for name in source.query if name in asked]
    if host == "commons.wikimedia.org" and parts.path.lower() == "/w/index.php" and not (
            dict(kept).get("title", "").startswith("Special:Redirect/file/")):
        return None
    return urlunsplit(("https", host, parts.path, urlencode(kept), ""))


async def asked_for(url: str) -> str | None:
    found = picture(url)
    if found is not None:
        return found
    return url if url in await _station_logos() else None


def _onward(fetching: str, location: str) -> str | None:
    found = picture(location)
    if found is not None:
        return found
    before, after = urlsplit(fetching), urlsplit(location)
    if (before.hostname and after.hostname == before.hostname and _source(before.hostname) is None
            and after.scheme in ("http", "https") and not after.username and not after.password
            and not _literal_inside(after.hostname)):
        return location
    return None


def _sized(url: str, edge: int) -> str:
    """The same picture, asked for at the size it will be drawn.

    Discogs is left alone deliberately: its addresses carry a signature over the
    processing options, so a rewritten width answers 403. It hands over six
    hundred, which is what a backdrop wants anyway. Wikipedia's own uploads are
    left alone for the opposite reason — an original has no size in its path to
    change, and only its thumbnails do."""
    host = urlsplit(url).hostname or ""
    if (plugged := PLUGGED.get(host)) is not None:
        sized = plugins.resolve(plugged).sized
        return sized(url, edge) if sized else url
    if host.endswith("dzcdn.net"):
        return _DEEZER.sub(f"/{edge}x{edge}-", url)
    if host == "image.tmdb.org":
        return _TMDB.sub(f"/t/p/w{_menu(edge, TMDB_WIDTHS)}/", url)
    if host == "is1-ssl.mzstatic.com":
        return _APPLE.sub(f"/{edge}x{edge}bb.", url)
    if host == "commons.wikimedia.org":
        parts = urlsplit(url)
        asked = dict(parse_qsl(parts.query))
        if "width" in asked:
            asked["width"] = str(edge)
            return urlunsplit(parts._replace(query=urlencode(asked)))
        return url
    if host == "upload.wikimedia.org":
        return _WIKI_THUMB.sub(f"/{edge}px-", url)
    return url


def _where(url: str) -> Path:
    name = hashlib.sha256(url.encode()).hexdigest()
    return Path(settings.art_cache) / name[:2] / name


# A year, and it cannot go stale: the address is the key, and a picture that
# changed is a different address in the catalogue.
KEEP = "public, max-age=31536000, immutable"

# When a picture was last looked at is its file's modification time, moved on
# at most this often: a shelf of a hundred thumbnails is not a hundred writes.
TOUCH_EVERY = 3600
SWEEP_TO = 0.9


def _held(kept: Path) -> tuple[Path, str] | None:
    for kind, suffix in KINDS.items():
        held = kept.with_suffix(suffix)
        try:
            seen = held.stat().st_mtime
        except FileNotFoundError:
            continue
        if time.time() - seen > TOUCH_EVERY:
            # A cache can outlive a deployment which changes the UID that runs
            # the backend.  The picture is still perfectly readable in that
            # case; failing to refresh its recency must not turn it into a 500.
            try:
                os.utime(held)
            except OSError:
                pass
        return held, kind
    return None


def _keep(held: Path, body: bytes) -> None:
    held.parent.mkdir(parents=True, exist_ok=True)
    # named after the process so two surfaces asking at once cannot write over
    # each other halfway, and moved into place whole
    part = held.with_suffix(f"{held.suffix}.{id(body)}")
    try:
        part.write_bytes(body)
        part.replace(held)
    finally:
        part.unlink(missing_ok=True)


def sweep(root: Path, bound: int) -> int:
    found = []
    total = 0
    for folder in (root.iterdir() if root.is_dir() else ()):
        if not folder.is_dir():
            continue
        for one in folder.iterdir():
            try:
                seen = one.stat()
            except FileNotFoundError:
                continue
            found.append((seen.st_mtime, seen.st_size, one))
            total += seen.st_size
    if total <= bound:
        return total
    found.sort()
    goal = int(bound * SWEEP_TO)
    for _, size, one in found:
        if total <= goal:
            break
        one.unlink(missing_ok=True)
        total -= size
    return total


_holding: int | None = None
_sweeping = asyncio.Lock()


async def _grown(by: int) -> None:
    global _holding
    async with _sweeping:
        root = Path(settings.art_cache)
        if _holding is None:
            _holding = await asyncio.to_thread(sweep, root, settings.art_cache_bytes)
            return
        _holding += by
        if _holding > settings.art_cache_bytes:
            _holding = await asyncio.to_thread(sweep, root, settings.art_cache_bytes)


# Commons answers its file addresses with a redirect to its redirector and that
# with one to the thumbnail host, so a redirect is followed — by hand, and only
# onto an address this route would have fetched from anyway.
HOPS = 3


@router.get("/art")
async def art(u: str, w: int = 320):
    source = await asked_for(u)
    if source is None:
        raise HTTPException(400, "not a picture the catalogue uses")
    asked = _sized(source, _menu(w, WIDTHS))
    kept = _where(asked)
    found = await asyncio.to_thread(_held, kept)
    if found:
        return FileResponse(found[0], media_type=found[1], headers={"Cache-Control": KEEP})

    http = await _fetcher()
    fetching = asked
    host = urlsplit(asked).hostname
    try:
        for _ in range(HOPS + 1):
            async with http.stream("GET", fetching) as answer:
                if answer.is_redirect:
                    onward = _onward(fetching, str(answer.url.join(answer.headers.get("location", ""))))
                    if onward is None:
                        raise HTTPException(502, "the picture was sent somewhere this does not fetch from")
                    fetching, host = onward, urlsplit(onward).hostname
                    continue
                answer.raise_for_status()
                kind = answer.headers.get("content-type", "").partition(";")[0].strip()
                # An address in the catalogue can turn out to lead to a page
                # rather than a file. There is nothing to draw in that, and the
                # card has a letter to fall back on — better than a broken
                # picture kept for a year.
                suffix = KINDS.get(kind)
                if suffix is None:
                    raise HTTPException(415, f"{host} answered {kind or 'nothing'}, not a picture")
                body = bytearray()
                async for chunk in answer.aiter_bytes():
                    body += chunk
                    if len(body) > MOST:
                        raise HTTPException(413, f"{host} sent more than {MOST} bytes")
                break
        else:
            raise HTTPException(502, f"{host} redirected more than {HOPS} times")
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"picture from {host} failed: {type(exc).__name__}") from None

    held = kept.with_suffix(suffix)
    await asyncio.to_thread(_keep, held, bytes(body))
    await _grown(len(body))
    return FileResponse(held, media_type=kind, headers={"Cache-Control": KEEP})
