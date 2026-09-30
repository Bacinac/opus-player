"""What somebody heard and watched, sent to where they keep that history.

The player already decides both: a song is heard at half its length or four
minutes (MusicPlay), a film or an episode seen at its credits (Progress). A
person who keeps a history elsewhere links their own account — ListenBrainz
for records, Simkl for films and television — and what came before, and each
of those from then on, goes there as well. Through an outbox: a service that
is down or a token that has lapsed costs a delay and never a listen, and what
failed is said on the person's settings rather than dropped."""

import asyncio
import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import delete, select

from opus import library
from opus.db import SessionLocal
from opus.models import HistoryLink, HistorySend, MusicPlay, Progress
from opus.settings_store import current_runtime

log = logging.getLogger("opus.history")

LISTENBRAINZ = "https://api.listenbrainz.org/1"
SIMKL = "https://api.simkl.com"
# Simkl asks every request to name the app, so it can tell the apps apart
SIMKL_APP = {"app-name": "opus-player", "app-version": "1"}
# without write in the asked scope Simkl quietly grants a token that only reads
SIMKL_SCOPE = "media:read media:write"

KEEPS = {"listenbrainz": ("track",), "simkl": ("movie", "episode")}
SEEN = KEEPS["simkl"]
UNKNOWN = "unknown"
BATCH = 100
IDLE_S = 300
FIRST_RETRY_S = 60
LAST_RETRY_S = 6 * 3600
# a Simkl token lives a week; it is renewed on the day before, not after
SIMKL_MARGIN = timedelta(days=1)
SIMKL_CATALOGUE = {"movie": {"movie"}, "episode": {"tv", "anime"}}


class Refused(Exception):
    """The service answered, and the answer was no."""


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(timeout=20, headers={"User-Agent": "opus-player/1"})


def _said(resp: httpx.Response) -> str:
    return f"{resp.status_code} {resp.text[:200]}".strip()


def _is_json(resp: httpx.Response) -> bool:
    return resp.headers.get("content-type", "").startswith("application/json")


def retry_after(tries: int) -> timedelta:
    return timedelta(seconds=min(FIRST_RETRY_S * 2 ** max(tries - 1, 0), LAST_RETRY_S))


async def note(session, user_id: int, kind: str, item_ids: Sequence[int]) -> bool:
    """Put what was just heard or seen on its way to every service this person
    has linked that keeps that kind. The caller commits; says whether anything
    was put on its way, so the caller knows to wake the sender."""
    services = [service for service, kinds in KEEPS.items() if kind in kinds]
    linked = (await session.execute(select(HistoryLink.service).where(
        HistoryLink.user_id == user_id, HistoryLink.service.in_(services)))).scalars().all()
    now = datetime.now(UTC)
    session.add_all(HistorySend(user_id=user_id, service=service, kind=kind, item_id=item_id, at=now)
                    for service in linked for item_id in item_ids)
    return bool(linked and item_ids)


def owed(user_id: int, service: str, heard: Sequence[tuple[int, datetime]],
         seen: Sequence[tuple[str, int, datetime]]) -> list[HistorySend]:
    """What a service just linked is owed of what came before it: every song
    heard and everything seen to its credits, each at the time it happened."""
    kinds = KEEPS[service]
    return ([HistorySend(user_id=user_id, service=service, kind="track", item_id=track_id, at=at)
             for track_id, at in heard if "track" in kinds]
            + [HistorySend(user_id=user_id, service=service, kind=kind, item_id=item_id, at=at)
               for kind, item_id, at in seen if kind in kinds])


async def backlog(session, user_id: int, service: str) -> bool:
    """A history kept elsewhere starts with what the player already knew, not
    on the day it was linked. The caller commits and wakes the sender."""
    heard = (await session.execute(select(MusicPlay.track_id, MusicPlay.played_at).where(
        MusicPlay.user_id == user_id))).all()
    seen = (await session.execute(select(Progress.kind, Progress.item_id, Progress.finished_at).where(
        Progress.user_id == user_id, Progress.kind.in_(SEEN), Progress.finished_at.is_not(None)))).all()
    sends = owed(user_id, service, heard, seen)
    session.add_all(sends)
    return bool(sends)


# ListenBrainz ----------------------------------------------------------------

async def listenbrainz_account(token: str) -> str:
    async with _client() as http:
        resp = await http.get(f"{LISTENBRAINZ}/validate-token",
                              headers={"Authorization": f"Token {token}"})
    if resp.status_code != 200 or not resp.json().get("valid"):
        raise Refused(f"ListenBrainz does not accept this token: {_said(resp)}")
    return resp.json()["user_name"]


def listens(rows: Sequence[HistorySend], tracks: dict[int, dict]) -> tuple[list[dict], list[HistorySend]]:
    """The listens as ListenBrainz takes them, and the rows the library no
    longer has a song for."""
    made, unknown = [], []
    for row in rows:
        track = tracks.get(row.item_id)
        if track is None:
            unknown.append(row)
            continue
        info: dict = {"media_player": "OPUS", "submission_client": "OPUS Player"}
        if track.get("duration_s"):
            info["duration_ms"] = int(track["duration_s"] * 1000)
        ids = track.get("mbids") or {}
        for field, key in (("recording_mbid", "recording"), ("release_mbid", "release"),
                           ("artist_mbids", "artists")):
            if ids.get(key):
                info[field] = ids[key]
        made.append({"listened_at": int(row.at.timestamp()), "track_metadata": {
            "artist_name": track["artist"], "track_name": track["title"],
            "release_name": track["album"], "additional_info": info}})
    return made, unknown


async def _to_listenbrainz(link: HistoryLink, rows: Sequence[HistorySend]) -> list[HistorySend]:
    tracks = await library.get("/music/tracks", ids=",".join(str(r.item_id) for r in rows))
    made, unknown = listens(rows, {t["id"]: t for t in tracks})
    if made:
        async with _client() as http:
            resp = await http.post(
                f"{LISTENBRAINZ}/submit-listens", headers={"Authorization": f"Token {link.token}"},
                json={"listen_type": "single" if len(made) == 1 else "import", "payload": made})
        if resp.status_code != 200:
            raise Refused(f"ListenBrainz refused the listens: {_said(resp)}")
    return unknown


# Simkl -----------------------------------------------------------------------

def simkl_ready(config) -> bool:
    return bool(config.get("simkl_client_id"))


def _simkl(config) -> dict:
    return {"client_id": config.get("simkl_client_id"), **SIMKL_APP}


async def simkl_code(config) -> dict:
    """A code for somebody to approve at simkl.com/pin: how an app with no page
    of its own for Simkl to send them back to gets their permission."""
    async with _client() as http:
        resp = await http.post(f"{SIMKL}/oauth2/device", params=SIMKL_APP,
                               data={"client_id": config.get("simkl_client_id"), "scope": SIMKL_SCOPE})
    if resp.status_code != 200:
        raise Refused(f"Simkl did not give a code: {_said(resp)}")
    return resp.json()


async def simkl_grant(config, device_code: str) -> dict | str | None:
    """The tokens, once the code has been approved; None while it has not been
    yet — which is also all a refusal ever looks like; "slow" when asked too
    often; "expired" when it never will be."""
    async with _client() as http:
        resp = await http.post(f"{SIMKL}/oauth2/token", params=SIMKL_APP, data={
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": config.get("simkl_client_id"), "device_code": device_code})
    if resp.status_code == 200:
        grant = resp.json()
        if "media:write" not in grant.get("scope", "").split():
            raise Refused(f"Simkl granted only {grant.get('scope')!r}; nothing could be written")
        return grant
    error = resp.json().get("error") if resp.status_code == 400 and _is_json(resp) else None
    if error == "authorization_pending":
        return None
    if error == "slow_down":
        return "slow"
    if error == "expired_token":
        return "expired"
    raise Refused(f"Simkl did not answer the code: {_said(resp)}")


async def simkl_account(config, token: str) -> str:
    async with _client() as http:
        resp = await http.get(f"{SIMKL}/users/settings", params=_simkl(config),
                              headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        raise Refused(f"Simkl did not say whose this is: {_said(resp)}")
    return resp.json()["user"]["name"]


def keep_grant(link: HistoryLink, grant: dict) -> None:
    link.token = grant["access_token"]
    link.refresh = grant.get("refresh_token") or link.refresh
    link.expires_at = datetime.now(UTC) + timedelta(seconds=grant["expires_in"])


async def _simkl_token(config, link: HistoryLink) -> str:
    """Only the sender renews: a renewal ends the token before it, so two
    renewing side by side would keep cutting each other off."""
    if link.expires_at is None or link.expires_at - datetime.now(UTC) > SIMKL_MARGIN:
        return link.token
    async with _client() as http:
        resp = await http.post(f"{SIMKL}/oauth2/token", params=SIMKL_APP, data={
            "grant_type": "refresh_token", "client_id": config.get("simkl_client_id"),
            "refresh_token": link.refresh})
    if resp.status_code != 200:
        raise Refused(f"Simkl would not renew the link; link it again: {_said(resp)}")
    keep_grant(link, resp.json())
    return link.token


def _stamp(at: datetime) -> str:
    return at.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def viewings(rows: Sequence[HistorySend], movies: dict[int, dict],
             episodes: dict[int, dict]) -> tuple[dict, list[HistorySend]]:
    """What was seen, as Simkl's history takes it: films by their TMDB and IMDb
    ids, episodes under their series, season and number. A TMDB id alone could
    be a film or a series, so the title and year go with it. The rows nothing
    can be said about come back apart."""
    body: dict = {"movies": [], "shows": []}
    shows: dict[int, dict] = {}
    unknown = []
    for row in rows:
        if row.kind == "movie" and (movie := movies.get(row.item_id)) and movie.get("tmdb_id"):
            ids = {"tmdb": movie["tmdb_id"]}
            if movie.get("imdb_id"):
                ids["imdb"] = movie["imdb_id"]
            body["movies"].append({"title": movie["title"], "year": movie.get("year"), "ids": ids,
                                   "watched_at": _stamp(row.at)})
        elif row.kind == "episode" and (ep := episodes.get(row.item_id)) and ep.get("series_tmdb_id"):
            show = shows.setdefault(ep["series_tmdb_id"], {
                "title": ep["series_title"], "year": ep.get("year"),
                "ids": {"tmdb": ep["series_tmdb_id"]}, "seasons": {}})
            show["seasons"].setdefault(ep["season_number"], []).append(
                {"number": ep["number"], "watched_at": _stamp(row.at)})
        else:
            unknown.append(row)
    body["shows"] = [{**show, "seasons": [{"number": season, "episodes": eps}
                                          for season, eps in show["seasons"].items()]}
                     for show in shows.values()]
    return body, unknown


def not_taken(rows: Sequence[HistorySend], movies: dict[int, dict], episodes: dict[int, dict],
              answer: dict) -> list[HistorySend]:
    """The rows behind what Simkl never heard of, and behind what it filed in
    the wrong catalogue — a series read as a film is a record that lies."""
    missing = answer.get("not_found") or {}
    films = {str(m.get("ids", {}).get("tmdb")) for m in missing.get("movies", [])}
    series = {str(s.get("ids", {}).get("tmdb")) for s in missing.get("shows", [])}
    for status in (answer.get("added") or {}).get("statuses", []):
        asked, got = status.get("request", {}), status.get("response", {}).get("simkl_type")
        kind = "movie" if asked.get("type") == "movie" else "episode"
        if got and got not in SIMKL_CATALOGUE[kind]:
            (films if kind == "movie" else series).add(str(asked.get("ids", {}).get("tmdb")))
    return [row for row in rows
            if (row.kind == "movie" and str(movies.get(row.item_id, {}).get("tmdb_id")) in films)
            or (row.kind == "episode" and str(episodes.get(row.item_id, {}).get("series_tmdb_id")) in series)]


async def _to_simkl(config, link: HistoryLink, rows: Sequence[HistorySend]) -> list[HistorySend]:
    if not simkl_ready(config):
        raise Refused("Simkl is not set up on this install")
    token = await _simkl_token(config, link)
    movies = {}
    for row in rows:
        if row.kind == "movie" and row.item_id not in movies:
            try:
                movies[row.item_id] = await library.get(f"/video/movies/{row.item_id}")
            except library.NotInLibrary:
                pass
    wanted = [str(r.item_id) for r in rows if r.kind == "episode"]
    episodes = {e["id"]: e for e in await library.get("/video/episodes", ids=",".join(wanted))} if wanted else {}
    body, unknown = viewings(rows, movies, episodes)
    if body["movies"] or body["shows"]:
        async with _client() as http:
            resp = await http.post(f"{SIMKL}/sync/history", params=_simkl(config),
                                   headers={"Authorization": f"Bearer {token}"}, json=body)
        if resp.status_code != 201:
            raise Refused(f"Simkl refused the history: {_said(resp)}")
        unknown += not_taken(rows, movies, episodes, resp.json())
    return unknown


# the sender ------------------------------------------------------------------

async def _send(user_id: int, service: str, now: datetime) -> None:
    async with SessionLocal() as session:
        link = (await session.execute(select(HistoryLink).where(
            HistoryLink.user_id == user_id, HistoryLink.service == service))).scalar_one_or_none()
        rows = (await session.execute(select(HistorySend).where(
            HistorySend.user_id == user_id, HistorySend.service == service,
            HistorySend.due_at <= now).order_by(HistorySend.at).limit(BATCH))).scalars().all()
        if link is None:
            await session.execute(delete(HistorySend).where(
                HistorySend.user_id == user_id, HistorySend.service == service))
            await session.commit()
            return
        try:
            if service == "listenbrainz":
                unknown = await _to_listenbrainz(link, rows)
            else:
                unknown = await _to_simkl(await current_runtime(), link, rows)
        except (httpx.HTTPError, library.LibraryError, Refused) as exc:
            log.warning("%d for %s of user %d not sent: %s", len(rows), service, user_id, exc)
            for row in rows:
                row.tries += 1
                row.problem = str(exc) or type(exc).__name__
                row.due_at = now + retry_after(row.tries)
            await session.commit()
            return
        for row in rows:
            if row in unknown:
                row.tries += 1
                row.problem = UNKNOWN
                row.due_at = None
            else:
                await session.delete(row)
        if unknown:
            log.warning("%s does not know %d of user %d's", service, len(unknown), user_id)
        await session.commit()


async def send_due() -> None:
    now = datetime.now(UTC)
    async with SessionLocal() as session:
        due = (await session.execute(select(HistorySend.user_id, HistorySend.service)
                                     .where(HistorySend.due_at <= now).distinct())).all()
    for user_id, service in due:
        await _send(user_id, service, now)


class Sender:
    """Works through the outbox when something is put in it, and every few
    minutes for what is waiting to be tried again."""

    def __init__(self) -> None:
        self._wake = asyncio.Event()

    def kick(self) -> None:
        self._wake.set()

    async def run(self) -> None:
        while True:
            self._wake.clear()
            try:
                await send_due()
            except Exception:
                log.exception("the history outbox could not be worked through")
            try:
                await asyncio.wait_for(self._wake.wait(), IDLE_S)
            except TimeoutError:
                pass


sender = Sender()
