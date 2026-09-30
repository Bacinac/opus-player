"""The client for OPUS · Library.

The player stores no catalogue of its own. What exists, what is complete, what
arrived yesterday — all of it is asked, every time, because the Library is the
one that knows. The same relationship Library has with Downloads, one floor up."""

import httpx
import opus_auth

from opus.config import settings


class LibraryError(Exception):
    """The library could not be reached or refused. Never swallowed."""


class NotInLibrary(LibraryError):
    """The library answered, and what was asked for is not in it. A different
    thing entirely from a library that cannot be reached, and it must read as a
    different thing on the screen — "no words for this song" is not "the
    catalogue is down"."""


class AlreadyThere(LibraryError):
    """The library answered that what was asked for is already done or already
    under way. Whether that is a success is the caller's to say."""


class Invalid(LibraryError):
    """The library answered that what was asked for does not make sense. That is
    the asker's mistake, not a library that is down, and it is said as one."""


def _refusal(path: str, resp: httpx.Response) -> str:
    try:
        said = resp.json()
    except ValueError:
        said = None
    detail = said.get("detail") if isinstance(said, dict) else None
    if isinstance(detail, list):
        detail = "; ".join(str(one.get("msg")) for one in detail
                           if isinstance(one, dict) and one.get("msg")) or None
    return f"library {path}: {detail if isinstance(detail, str) else resp.status_code}"


def _raise_for(path: str, resp: httpx.Response) -> None:
    if resp.status_code == 404:
        raise NotInLibrary(_refusal(path, resp))
    if resp.status_code == 409:
        raise AlreadyThere(_refusal(path, resp))
    if resp.status_code == 422:
        raise Invalid(_refusal(path, resp))
    if resp.is_error:
        raise LibraryError(_refusal(path, resp))


# One connection per timeout, kept open. Every screen here is several questions
# to the library and every question was opening a socket of its own — a hundred
# and forty milliseconds of handshake on a fifty-millisecond answer, paid again
# for the next row of the same screen.
_kept: dict[float, httpx.AsyncClient] = {}


def client(timeout: float = 30) -> httpx.AsyncClient:
    """A client to talk to the library with. Shared, and therefore **not** to be
    closed by the caller."""
    kept = _kept.get(timeout)
    if kept is None or kept.is_closed:
        _kept[timeout] = kept = httpx.AsyncClient(
            base_url=f"{settings.library_url.rstrip('/')}/api", timeout=timeout,
            headers={opus_auth.TOKEN_HEADER: settings.library_token},
            limits=httpx.Limits(max_keepalive_connections=8, max_connections=32),
        )
    return kept


async def get(path: str, **params) -> list | dict:
    try:
        resp = await client().get(path, params=params or None)
    except httpx.HTTPError as exc:
        raise LibraryError(f"library {path} failed: {exc}") from exc
    _raise_for(path, resp)
    return resp.json()


async def patch(path: str, body: dict) -> dict:
    """Changing something the library keeps, rather than adding to it."""
    try:
        resp = await client().patch(path, json=body)
    except httpx.HTTPError as exc:
        raise LibraryError(f"library {path} refused: {exc}") from exc
    _raise_for(path, resp)
    return resp.json() if resp.content else {}


async def post(path: str, body: dict | None = None) -> dict:
    """Asking the library to do something, rather than to say something. The
    player never writes to a catalogue of its own — there is none — so wanting a
    film is a sentence spoken to the module that keeps them."""
    try:
        resp = await client(90).post(path, json=body or {})
    except httpx.HTTPError as exc:
        raise LibraryError(f"library {path} refused: {exc}") from exc
    _raise_for(path, resp)
    return resp.json() if resp.content else {}
