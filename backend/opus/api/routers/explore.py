"""What exists in the world, as opposed to what this house owns.

The catalogue is TMDB's and the asking is the Library's; the player only puts it
on a screen and passes on what was wanted. Nothing is stored here — a row of
things coming out next month is not a fact worth keeping a copy of."""

import asyncio
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from opus import library
from opus.api.routers.home import heard_most
from opus.api.routers.users import picked
from opus.cards import artist_card, release_card, track_card
from opus.db import get_session
from opus.plugins import OPENED_MUSIC_WAYS

router = APIRouter()

# the rows worth opening on, and what each asks the library for
# a row is what fits across the screen at once, the same as everywhere else
ROW_ACROSS = 5

# What there is more of, per shelf. Films and series are looked for from the
# shelf they belong to rather than from one screen holding all of it — when you
# are standing at the films, more films is the next thing you want.
ROWS = {
    "movie": {
        "movies_popular": ("/video/discover/popular", {"type": "movie"}),
        "movies_upcoming": ("/video/discover/upcoming", {"type": "movie"}),
        "trending": ("/video/discover/trending", {"type": "movie"}),
    },
    "tv": {
        "series_popular": ("/video/discover/popular", {"type": "tv"}),
        "series_upcoming": ("/video/discover/upcoming", {"type": "tv"}),
        "trending": ("/video/discover/trending", {"type": "tv"}),
    },
}


async def _held() -> dict[str, dict[int, dict]]:
    """What the house already has, by TMDB id. Asked once per request: the rows
    of things in the world are mostly things somebody has never heard of, and
    the few that are here must not look the same as the rest — which is also
    why a library that cannot say what it holds is an error and not an empty
    shelf."""
    try:
        movies, series = await asyncio.gather(library.get("/video/movies"),
                                              library.get("/video/series"))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {
        "movie": {m["tmdb_id"]: m for m in movies if m.get("tmdb_id")},
        "series": {s["tmdb_id"]: s for s in series if s.get("tmdb_id")},
    }


async def _answered(asked: list) -> list:
    """Every question that could be asked, and an error only when none of them
    could: one row the library refused is a screen with a row fewer, and every
    row refused is a library that is not answering."""
    answers = await asyncio.gather(*asked, return_exceptions=True)
    for answer in answers:
        if isinstance(answer, BaseException) and not isinstance(answer, library.LibraryError):
            raise answer
    if answers and all(isinstance(answer, BaseException) for answer in answers):
        raise HTTPException(502, str(answers[0]))
    return [None if isinstance(answer, BaseException) else answer for answer in answers]


def _card(item: dict, held: dict[str, dict[int, dict]]) -> dict:
    kind = "series" if item.get("media_type") == "tv" else "movie"
    mine = held[kind].get(item["tmdb_id"])
    card = {
        "kind": kind,
        # TMDB's id, in the field a library card carries the library's own id in:
        # `owned` is what tells the two apart, and asking the library about a
        # series by the wrong one is asking about a different series
        "id": item["tmdb_id"],
        "owned": False,
        "tmdb_id": item["tmdb_id"],
        "title": item.get("title") or "",
        "subtitle": item.get("year"),
        "image": item.get("poster_url"),
        "backdrop": None,
        "state": None,
        "overview": item.get("overview") or "",
        "streaming": item.get("streaming"),
    }
    if mine is None:
        return card
    # held: the card stops being a thing in the world and becomes the shelf's,
    # id and all, so opening it opens what we have rather than offering it again
    return {**card, "owned": True, "id": mine["id"], "state": mine.get("status"),
            "streaming": None,
            "badge": f"{mine.get('episodes_have') or 0}/{mine.get('episodes_known') or 0}"
                     if kind == "series" else "✓"}


@router.get("/explore")
async def explore(type: str = "movie"):
    wanted = ROWS.get(type, ROWS["movie"])
    held, found = await asyncio.gather(
        _held(),
        _answered([library.get(path, **params) for path, params in wanted.values()]))
    rows = []
    for key, items in zip(wanted, found):
        cards = [_card(i, held) for i in items or [] if i.get("tmdb_id")]
        if cards:
            rows.append({"key": key, "cards": cards})
    return {"rows": rows}


@router.get("/explore/search")
async def search(q: str, type: str = ""):
    wanted = [w for w in (("/video/search/movies", "movie"), ("/video/search/series", "tv"))
              if not type or w[1] == type]
    held, found = await asyncio.gather(
        _held(), _answered([library.get(path, q=q) for path, _ in wanted]))
    return [_card({**i, "media_type": kind}, held)
            for (_, kind), listed in zip(wanted, found) for i in listed or []
            if i.get("tmdb_id")]


# what an offered card opens to is the Library's to answer; the address asked
# of it here is only ever one kind and one item
OPENS_KIND = re.compile(r"^[a-z]{1,16}$")
OPENS_ITEM = re.compile(r"^[0-9A-Za-z-]{1,64}$")


@router.get("/explore/music/{kind}/{item_id}")
async def music_inside(kind: str, item_id: str):
    if not (OPENS_KIND.match(kind) and OPENS_ITEM.match(item_id)):
        raise HTTPException(404, "nothing of that kind can be opened")
    try:
        return await library.get(f"/music/discover/{kind}/{item_id}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/explore/genres")
async def genres(type: str = "movie"):
    """The kinds of thing there are. TMDB keeps a list for films and another for
    series; the same word in both is one kind here, because nobody is in the
    mood for a thriller only if it is ninety minutes long."""
    kinds = [type] if type else ["movie", "tv"]
    found = await _answered([library.get("/video/discover/genres", type=kind)
                             for kind in kinds])
    seen: dict[str, dict] = {}
    for kind, listed in zip(kinds, found):
        for genre in listed or []:
            at = seen.setdefault(genre["name"], {"name": genre["name"], "ids": {}})
            at["ids"][kind] = genre["id"]
    return sorted(seen.values(), key=lambda g: g["name"])


@router.get("/explore/genre")
async def genre(movie: int | None = None, tv: int | None = None):
    asked = [(kind, tmdb_genre) for kind, tmdb_genre in (("movie", movie), ("tv", tv))
             if tmdb_genre is not None]
    held, found = await asyncio.gather(
        _held(),
        _answered([library.get("/video/discover/browse", type=kind, genre=tmdb_genre)
                   for kind, tmdb_genre in asked]))
    return [_card({**i, "media_type": kind}, held)
            for (kind, _), listed in zip(asked, found) for i in listed or []
            if i.get("tmdb_id")]


@router.get("/explore/awarded")
async def awarded(type: str = "movie"):
    """Everything a shelf's awards went to, and the awards to filter it by. Which
    awards there are is the Library's word; what each is called is this
    screen's."""
    held = await _held()
    try:
        found = await library.get("/video/discover/awarded", type=type)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return {"awards": found["awards"],
            "cards": [{**_card(i, held), "won": i["won"]}
                      for i in found["titles"] if i.get("tmdb_id")]}


@router.get("/explore/people")
async def people(type: str = ""):
    """Who is in the house. Not who is popular in the world — that is a list
    nobody here has any use for."""
    try:
        return await library.get("/video/discover/held/people", type=type)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/explore/studios")
async def studios(type: str = ""):
    try:
        return await library.get("/video/discover/held/studios", type=type)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


def _music_card(item: dict) -> dict:
    return {
        "kind": "music", "id": item["id"], "owned": False,
        "title": item["title"],
        "subtitle": item["artist"] or None,
        "image": item.get("cover_url"), "backdrop": None, "state": "wanted",
        "overview": "", "round": item["kind"] == "artist",
        # a cover is square, whatever it covers
        "square": item["kind"] != "artist",
        "artist": item["artist"],
        # a mix, a playlist or an album can be opened to see whose music is
        # in it; an artist or a single track has nothing further inside
        "holds": item["kind"] if item["kind"] in ("mix", "playlist", "album") else None,
        "person": item["kind"] == "artist",
        "album": item["title"] if item["kind"] == "album" else "",
    }


@router.get("/explore/ways")
async def ways():
    """The ways into a section that stand on what the installation added."""
    return {"music": list(OPENED_MUSIC_WAYS)}


@router.get("/explore/music")
async def music():
    """What the Library's catalogue is putting in front of us — the same service
    the music is downloaded from, so everything offered here can actually be
    had."""
    try:
        found = await library.get("/music/discover")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    rows = []
    for row in found.get("rows", []):
        cards = [_music_card(item) for item in row.get("items", [])][:ROW_ACROSS]
        if cards:
            rows.append({"key": row.get("title", ""), "label": row.get("title", ""),
                         "cards": cards})
    return {"rows": rows}


# news is what came out lately, and a season of it is what a person misses
# between two looks
FRESH_DAYS = 90
# the artists whose neighbours are asked for
SIMILAR_SEEDS = 10


@router.get("/explore/music/releases")
async def music_releases():
    """What the artists the house follows put out lately, on the shelf or not
    yet — a record that is not here is the news worth having."""
    try:
        found = await library.get("/music/releases", fresh=FRESH_DAYS)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return [release_card(r) for r in found]


@router.get("/explore/music/similar")
async def music_similar(request: Request, session: AsyncSession = Depends(get_session)):
    """Artists close to the ones this person keeps playing and not on the
    shelf; the Library makes up a short list from what the house follows."""
    who = await picked(request, session)
    seeds = await heard_most(session, who, SIMILAR_SEEDS) if who is not None else []
    try:
        found = await library.get("/music/similar", ids=",".join(map(str, seeds)))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return [_music_card(item) for item in found]


@router.get("/explore/music/search")
async def music_search(q: str):
    """Music looked for by name, the way the library looks for it: the artists
    and the songs already on the shelf first, then the records a catalogue has
    that the shelf does not, each one something that can be asked for. A film
    search was answering here, because the page asked TMDB whatever it showed."""
    try:
        found = await library.get("/music/search", q=q)
        shelf = await library.get("/music/artists", ids=",".join(map(str, found["artists"])))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    held = {a["id"]: a for a in shelf}
    return ([artist_card(held[i]) for i in found["artists"] if i in held]
            + [track_card(t) for t in found["tracks"]]
            + [_music_card(r) for r in found["records"]])


def _who(found: dict, held) -> dict:
    """Somebody, or some studio, and everything of theirs — who they are on top
    and the work under it."""
    return {
        "name": found.get("name", ""),
        "about": found.get("about", ""),
        "image": found.get("profile_url"),
        "born": found.get("born"),
        "died": found.get("died"),
        "from": found.get("from", ""),
        "cards": [_card(c, held) for c in found.get("credits", []) if c.get("tmdb_id")],
    }


@router.get("/explore/company/{company_id}")
async def company(company_id: int):
    """What a studio made. The same screen, the same wall of posters, and the
    ones we hold marked as ours."""
    held = await _held()
    try:
        found = await library.get(f"/video/discover/company/{company_id}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return _who(found, held)


@router.get("/explore/person/{person_id}")
async def person(person_id: int):
    """Everything else somebody on a film's billing is in. A face on that screen
    is a way into the rest of their work, and the ones we already hold are
    marked as ours the same as anything else found out here."""
    held = await _held()
    try:
        found = await library.get(f"/video/discover/person/{person_id}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return _who(found, held)


@router.get("/explore/series/{tmdb_id}/seasons")
async def seasons(tmdb_id: int):
    """What seasons a series has, for choosing among before anything is held.

    The library's discovery detail already carries them, so nothing is added to
    the catalogue to answer a question about it."""
    try:
        detail = await library.get(f"/video/discover/tv/{tmdb_id}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return {
        "title": detail.get("title") or "",
        # held already, the catalogue is the one that knows what is on disk: the
        # panel asks it instead, so a series is never offered back to the person
        # who has it
        "in_library": bool(detail.get("in_library")),
        "library_id": detail.get("library_id"),
        "seasons": [
            {"number": s["number"], "episodes": s.get("episodes") or 0,
             "year": s.get("year")}
            for s in detail.get("seasons", [])
        ],
    }


@router.get("/explore/series/{tmdb_id}/season/{number}")
async def season(tmdb_id: int, number: int):
    """One season of a series nobody holds, in the shape the panel lists episodes
    in — so the same list renders whether or not the library has taken it on."""
    try:
        found = await library.get(f"/video/discover/tv/{tmdb_id}/season/{number}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return [
        {"kind": "episode", "id": 0, "number": e["number"], "title": e.get("title") or "",
         "overview": e.get("overview") or "", "state": "wanted", "playable": False,
         "resolution": None, "air_date": e.get("air_date")}
        for e in found
    ]


class Wanted(BaseModel):
    kind: str  # movie | series
    tmdb_id: int
    # which seasons of a series to go after; empty means all of them
    seasons: list[int] = []
    # whether the seasons named are the only ones wanted, which is a sentence
    # about the whole series — taking one on says what to follow, while fetching
    # a season of one already held says nothing about the rest
    only: bool = False


async def _ask_for_seasons(series_id: int, wanted: set[int] | None,
                           only: bool) -> int:
    """Wanting a series means wanting the episodes, one season at a time because
    that is the sentence the library has. What has not aired and what is already
    on disk it declines by itself, so the number that comes back is the truth of
    what is now being looked for.

    Taking a series on, the seasons left out are told to stop being followed —
    the monitor pass goes after every season it is not told to leave alone, and a
    choice it would undo six hours later is not a choice. Asking for a season of
    a series already held is the other case entirely: it says nothing about the
    seasons it does not name, and must not quietly unfollow them."""
    detail = await library.get(f"/video/series/{series_id}")
    queued = 0
    for season in detail.get("seasons", []):
        number = season["number"]
        follow = wanted is None or number in wanted
        if (only or follow) and bool(season.get("monitored")) != follow:
            await library.patch(f"/video/series/{series_id}/seasons/{number}",
                                {"monitored": follow})
        if not follow:
            continue
        answer = await library.post(f"/video/series/{series_id}/seasons/{number}/search")
        queued += answer.get("queued") or 0
    return queued


async def _ask_for_film(added: dict | None, tmdb_id: int) -> dict:
    """A film in the catalogue with no file is asked for again, the same as a
    series: being followed is not being looked for, and the dead posts the
    library has already refused are what makes the next search find another."""
    film = added or next((m for m in await library.get("/video/movies")
                          if m.get("tmdb_id") == tmdb_id), None)
    if film is None:
        raise HTTPException(502, "the library says it holds this film and lists no such film")
    answer = {"added": added is not None, "queued": 0, "id": film["id"],
              "title": film.get("title")}
    if film.get("status") in ("complete", "waiting_subtitles"):
        return answer
    if film.get("monitored") is False:
        await library.patch(f"/video/movies/{film['id']}", {"monitored": True})
    try:
        await library.post(f"/video/movies/{film['id']}/search")
    except library.AlreadyThere:
        return answer | {"coming": True}
    except library.NotInLibrary:
        # nothing to be had tonight is still a film the library follows
        return answer | {"found": False}
    return answer | {"found": True}


class WantedRecord(BaseModel):
    artist: str
    album: str


@router.post("/explore/want/episode/{episode_id}", status_code=202)
async def want_episode(episode_id: int):
    """One episode of a series the house already holds. The whole of what is
    missing is one button above the list; this is the other sentence somebody
    standing in front of a list says — that one, now."""
    try:
        got = await library.post(f"/video/episodes/{episode_id}/search")
    except library.NotInLibrary:
        return {"found": False, "already": False, "release": None}
    except library.AlreadyThere:
        return {"found": True, "already": True, "release": None}
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return {"found": True, "already": False, "release": got.get("release")}


async def _download(release_id: int) -> None:
    """A record fetched, or the library's own reason why not, said as the
    library said it: a record it has never heard of, or one already on its
    way or standing in for an edition nobody holds."""
    try:
        await library.post(f"/music/releases/{release_id}/download")
    except library.NotInLibrary as exc:
        raise HTTPException(404, str(exc))
    except library.AlreadyThere as exc:
        raise HTTPException(409, str(exc))
    except library.Invalid as exc:
        raise HTTPException(422, str(exc))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.post("/explore/want/release/{release_id}", status_code=202)
async def want_release(release_id: int):
    """A record the catalogue already knows, pointed at rather than described.

    The route beside this one exists for a record nobody here has heard of: a
    name off a screen, an artist who may not be in the catalogue at all, and a
    search to tie the two together. Nothing of that applies to a record the
    artist's own page is already showing — it has an id, and asking for it by
    name again would be a lookup that can fail where a number cannot."""
    await _download(release_id)
    return {"asked": True}


@router.post("/explore/want/music", status_code=202)
async def want_music(body: WantedRecord):
    """One record, never a whole artist.

    An artist is a career and a career is terabytes; what somebody means when
    they point at something a catalogue is offering them is that record. The artist
    still has to exist in the catalogue for the record to hang off, so they are
    found by name and added if missing — but added UNWATCHED, so nothing beyond
    the one record follows them in."""
    if not body.album.strip():
        raise HTTPException(422, "a record, not an artist")
    try:
        found = await library.get("/music/search/artists", q=body.artist)
    except library.Invalid as exc:
        raise HTTPException(422, str(exc))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    exact = next((a for a in found
                  if a["name"].casefold() == body.artist.casefold() and a.get("deezer_id")), None)
    if exact is None:
        raise HTTPException(404, f"{body.artist}: the catalogue knows nobody by that name")

    try:
        added = await library.post("/music/artists",
                                   {"deezer_id": exact["deezer_id"], "monitored": False})
        artist = await library.get(f"/music/artists/{added['id']}")
    except library.Invalid as exc:
        raise HTTPException(422, str(exc))
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))

    wanted = body.album.casefold().strip()
    record = next((r for r in artist.get("releases", [])
                   if (r.get("title") or "").casefold().strip() == wanted), None)
    if record is None:
        raise HTTPException(
            404, f"{body.artist} — {body.album}: the catalogue has no record by that name")
    await _download(record["id"])
    return {"added": True, "name": f"{artist.get('name')} — {record['title']}"}


@router.post("/explore/want", status_code=202)
async def want(body: Wanted):
    """Take this one. The library adds it to its catalogue and goes looking; from
    here on it is a download like any other, and the queue that shows it is the
    Library's, not the player's.

    Being in the catalogue is not being looked for: a series added and left alone
    sits at nought of a hundred and seventy-nine until the monitor pass happens
    to come round, so a series already held is asked for again rather than
    answered with `already` and nothing done."""
    if body.kind not in ("movie", "series"):
        raise HTTPException(422, "a film or a series, nothing else")
    where = "/video/movies" if body.kind == "movie" else "/video/series"
    try:
        try:
            added = await library.post(where, {"tmdb_id": body.tmdb_id})
        except library.AlreadyThere:
            added = None
        if body.kind == "movie":
            return await _ask_for_film(added, body.tmdb_id)
        series_id = added["id"] if added else next(
            (s["id"] for s in await library.get("/video/series")
             if s.get("tmdb_id") == body.tmdb_id), None)
        if series_id is None:
            raise HTTPException(502, "the library says it holds this series and lists no such series")
        queued = await _ask_for_seasons(series_id, set(body.seasons) or None,
                                        body.only)
        return {"added": added is not None, "queued": queued, "id": series_id,
                "title": (added or {}).get("title")}
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
