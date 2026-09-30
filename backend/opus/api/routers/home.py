"""The one screen the player is for: what to watch or listen to now.

Every row is assembled from the Library on the spot. The player caches nothing
about the catalogue — if a film was imported a minute ago it is here a minute
later, because there is no copy to fall behind."""

import asyncio
from datetime import timedelta

import opus_auth
from fastapi import APIRouter, Depends, HTTPException, Request
from opus_auth import GUEST
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from opus import auth, library
from opus.api.routers.users import orders_of, picked
from opus.cards import (artist_card, croatian, episode_card, movie_card, release_card,
                        series_card, track_card)
from opus.db import get_session
from opus.models import MusicPlay, Progress, RadioStation

router = APIRouter()

# A row is a glance, and a glance is what fits on the screen at once. Anything
# past that is what the shelf is for — a row you have to travel sideways along
# is a shelf pretending to be a glance.
ROW_LIMIT = 5


async def _safe(coro, fallback):
    """One row of a screen that has several: the rest of them are still worth
    drawing. A screen that is only this row says so instead."""
    try:
        return await coro
    except library.LibraryError:
        return fallback


async def _unless_gone(coro):
    """What the library holds under an id it handed out earlier, or None when it
    has since let go of it. A library that cannot be reached is not that."""
    try:
        return await coro
    except library.NotInLibrary:
        return None


async def _nothing() -> list:
    """A row not asked for, in the place of one asked for alongside others."""
    return []


async def _all(*asked):
    """What several sections answered, and an error if none of them did. A
    library that cannot be reached is not a library with nothing in it, and
    an empty screen is how that lie would be told."""
    answers = await asyncio.gather(*(coro for coro, _ in asked),
                                   return_exceptions=True)
    for answer in answers:
        if isinstance(answer, BaseException) and not isinstance(
                answer, library.LibraryError):
            raise answer
    if all(isinstance(answer, BaseException) for answer in answers):
        raise HTTPException(502, str(answers[0]))
    return [fallback if isinstance(answer, BaseException) else answer
            for answer, (_, fallback) in zip(answers, asked)]


async def _seen(session: AsyncSession, who, kind: str) -> set[int]:
    """What this person has already got to the end of. One question for a whole
    shelf: a tick on a poster is not worth a request per poster."""
    if who is None:
        return set()
    rows = await session.execute(
        select(Progress.item_id).where(
            Progress.user_id == who.id, Progress.kind == kind,
            Progress.finished_at.is_not(None))
    )
    return {r[0] for r in rows}


async def _seen_within(session: AsyncSession, who, kind: str) -> dict[int, int]:
    """How many of each thing's parts this person has finished — episodes per
    series. The player wrote down what an episode belongs to when it wrote that
    it was watched, so a shelf of series can say how far somebody got without
    holding a catalogue to work it out from."""
    if who is None:
        return {}
    rows = await session.execute(
        select(Progress.parent_id, func.count()).where(
            Progress.user_id == who.id, Progress.kind == kind,
            Progress.finished_at.is_not(None), Progress.parent_id.is_not(None))
        .group_by(Progress.parent_id)
    )
    return {row[0]: row[1] for row in rows}


def _next_episode(tree: dict, season: int, number: int, seen: set[int]) -> int | None:
    """The episode after the one just finished, skipping what this person has
    already seen. Only if it is on the disk: the next episode still being chased
    is not something to put on tonight. Specials sit outside the running order,
    so finishing one leads nowhere."""
    if season == 0:
        return None
    later = sorted(
        ((s["number"], e["number"], e) for s in tree.get("seasons", []) if s["number"] > 0
         for e in s["episodes"]
         if (s["number"], e["number"]) > (season, number) and e["id"] not in seen),
        key=lambda row: row[:2])
    if not later:
        return None
    upcoming = later[0][2]
    return upcoming["id"] if upcoming.get("file") else None


class _Walk:
    """One pass along somebody's history towards a full row. A series and a
    record each take one place however many of their rows the history holds, so
    what was already placed is remembered across the batches the walk reads."""

    def __init__(self, seen_episodes: set[int], lang: str):
        self.seen_episodes = seen_episodes
        self.lang = lang
        self.series: set[int] = set()
        self.records: set[int] = set()

    async def _by_ids(self, path: str, ids: list[int], **params) -> dict[int, dict]:
        if not ids:
            return {}
        found = await library.get(path, ids=",".join(str(i) for i in ids), **params)
        return {row["id"]: row for row in found}

    async def cards(self, batch: list[Progress], kept: dict) -> list[dict]:
        films = [p for p in batch
                 if p.kind == "movie" and p.finished_at is None and p.position_s > 0]
        movies, episodes, tracks = await asyncio.gather(
            asyncio.gather(*(_unless_gone(library.get(
                f"/video/movies/{p.item_id}", lang=self.lang)) for p in films)),
            self._by_ids("/video/episodes",
                         [p.item_id for p in batch if p.kind == "episode"], lang=self.lang),
            self._by_ids("/music/tracks", [p.item_id for p in batch if p.kind == "track"]),
        )
        by_movie = {p.item_id: m for p, m in zip(films, movies) if m is not None}
        # Each place is a card, or a series waiting to be told which of its
        # episodes comes next — the order is settled before the library is asked.
        places = [place for p in batch
                  if (place := self._place(p, by_movie, episodes, tracks)) is not None]
        return await self._told_what_is_next(places, kept)

    def _place(self, p: Progress, by_movie: dict, episodes: dict, tracks: dict) -> dict | None:
        if p.kind == "movie" and p.item_id in by_movie:
            card = movie_card(by_movie[p.item_id])
        elif p.kind == "episode" and p.item_id in episodes:
            card = self._episode(p, episodes[p.item_id])
        elif p.kind == "track" and p.item_id in tracks:
            card = self._track(tracks[p.item_id])
        else:
            return None
        if card is None or "after" in card:
            return card
        return {**card, "position_s": p.position_s,
                "duration_s": p.duration_s or card.get("duration_s")}

    def _episode(self, p: Progress, found: dict) -> dict | None:
        # the series is where somebody is, and the episode touched last says
        # where in it: an older row of it is a place already left
        if found["series_id"] in self.series:
            return None
        self.series.add(found["series_id"])
        if p.finished_at is not None:
            return {"after": found}
        if not found["playable"] or p.position_s <= 0:
            return None
        return episode_card(found)

    def _track(self, found: dict) -> dict | None:
        if not found["playable"]:
            return None
        card = track_card(found)
        record = card.get("release_id")
        if record is not None:
            if record in self.records:
                return None
            self.records.add(record)
        return card

    async def _told_what_is_next(self, places: list[dict], kept: dict) -> list[dict]:
        waiting = [place["after"] for place in places if "after" in place]
        trees = await asyncio.gather(*(
            _unless_gone(library.get(f"/video/series/{e['series_id']}", lang=self.lang))
            for e in waiting))
        upcoming = {
            e["id"]: _next_episode(tree, e["season_number"], e["number"], self.seen_episodes)
            for e, tree in zip(waiting, trees) if tree
        }
        following = await self._by_ids(
            "/video/episodes", [i for i in upcoming.values() if i is not None], lang=self.lang)

        cards = []
        for place in places:
            if "after" not in place:
                cards.append(place)
                continue
            found = following.get(upcoming.get(place["after"]["id"]))
            if found and found["playable"]:
                cards.append(_resumed(found, kept))
        return cards


def _resumed(found: dict, kept: dict) -> dict:
    started = kept.get(("episode", found["id"]))
    return {**episode_card(found),
            "position_s": started.position_s if started and started.finished_at is None else 0.0,
            "duration_s": started.duration_s if started else None}


async def _continue_row(resume: list[Progress], seen_episodes: set[int],
                        lang: str) -> list[dict]:
    """What to put on next, in the order it was last touched: a film or an
    episode left in the middle, and for a series whose last episode was watched
    to the end, the one after it. A thing finished is not a place to go back to.

    Read a few rows at a time until the row is full: a series finished with
    nothing after it on the disk takes no place in it."""
    kept = {(p.kind, p.item_id): p for p in resume}
    walk = _Walk(seen_episodes, lang)
    cards: list[dict] = []
    at = 0
    while len(cards) < ROW_LIMIT and at < len(resume):
        batch = resume[at:at + ROW_LIMIT * 2]
        at += len(batch)
        cards += await walk.cards(batch, kept)
    return cards[:ROW_LIMIT]


def _shorthand(height: int | None) -> str:
    if not height:
        return ""
    for edge, said in ((2000, "4K"), (1000, "1080p"), (700, "720p"), (0, "SD")):
        if height > edge:
            return said
    return ""


def _file_facts(media: dict | None) -> dict:
    """What the copy on the disk actually is. A person deciding whether to watch
    something tonight asks two questions, and the second one is whether this is
    the good copy — which is the resolution, what it is encoded with, how big it
    is, and which languages the sound comes in."""
    if not media:
        return {}
    streams = media.get("streams") or []
    return {
        # a film's own row says 1080p; an episode answers with the numbers the
        # file has, and the shorthand is what a person reads
        "resolution": media.get("resolution") or _shorthand(media.get("height")),
        "video_codec": media.get("video_codec") or "",
        "container": media.get("container") or "",
        "size": media.get("size"),
        "duration_s": media.get("duration_s"),
        "audio": [
            {"lang": s["lang"], "codec": s["codec"], "channels": s.get("channels"),
             # what it is beyond its core — DTS-HD MA, TrueHD with Atmos — which
             # is what decides the mark the screen draws for it. The stream's
             # own title is the fallback: a remux nearly always writes it there
             # even when the probe cannot name the profile.
             "profile": s.get("profile") or (s.get("title") or None)}
            for s in streams if s.get("kind") == "audio"
        ],
        "subtitles": sorted({s["lang"] for s in (media.get("subtitles") or []) if s.get("lang")}),
    }


def _about(item: dict, file: dict | None) -> dict:
    return {
        "overview": item.get("overview") or "",
        "year": item.get("year"),
        "runtime_min": item.get("runtime_min"),
        "genres": item.get("genres") or [],
        "studios": item.get("studios") or [],
        "directors": item.get("directors") or [],
        "cast": item.get("cast") or [],
        "file": _file_facts(file),
    }


@router.get("/library/series/{series_id}")
async def series_detail(series_id: int, lang: str = "en"):
    """The seasons and episodes of one series, as the surface needs them: an
    episode carries whether it can be played at all, so the list can offer the
    ones that are here and say what the others are waiting for."""
    try:
        series = await library.get(f"/video/series/{series_id}", lang=lang)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return {
        "id": series["id"], "tmdb_id": series.get("tmdb_id"),
        "title": series["title"], "year": series.get("year"),
        "overview": series.get("overview") or "",
        "backdrop": series.get("backdrop_url"), "image": series.get("poster_url"),
        "about": _about(series, None),
        "seasons": [
            {"number": s["number"],
             # whether the library is still following this season. A season
             # watched and then deleted is not a season with something missing
             # from it, and the one place that is decided is the catalogue
             "followed": bool(s.get("monitored")),
             "overview": s.get("overview") or "", "poster": s.get("poster"),
             "episodes": [
                {"kind": "episode", "id": e["id"], "number": e["number"],
                 "title": e["title"], "overview": e.get("overview") or "",
                 "state": e["status"], "playable": bool(e.get("file")),
                 "resolution": (e.get("file") or {}).get("resolution"),
                 "size": (e.get("file") or {}).get("size") or 0,
                 # what is on the file and what the policy still wants: an
                 # episode is on disk long before it is finished
                 "subs": e.get("present_subs") or [],
                 "missing_subs": e.get("missing_subs") or [],
                 "air_date": e.get("air_date"),
                 "still": e.get("still_url"), "runtime_min": e.get("runtime_min")}
                for e in s["episodes"]
            ]}
            for s in series.get("seasons", [])
        ],
    }


ABOUT = {"movie": "/video/movies", "episode": "/video/episodes"}


@router.get("/library/about/{kind}/{item_id}")
async def about(kind: str, item_id: int, lang: str = "en"):
    """What a thing IS, for the screen a person opens before deciding: the whole
    overview rather than the two lines a shelf shows, who made it, and the
    billing with faces. Asked when that screen opens rather than carried by
    every card on the shelf — twelve portraits times a hundred and thirty-four
    films is a listing nobody can afford."""
    if kind not in ABOUT:
        raise HTTPException(404, "nothing of that kind has anything to tell")
    try:
        if kind == "episode":
            found = await library.get("/video/episodes", ids=str(item_id),
                                      lang=lang)
            if not found:
                raise HTTPException(404, "no such episode")
            item = found[0]
            series = await library.get(f"/video/series/{item['series_id']}",
                                       lang=lang)
            played = await _safe(
                library.get(f"/video/episodes/{item_id}/playback"), None)
            return _about({**series, "overview": item.get("overview"),
                           "year": item.get("year"), "runtime_min": None}, played)
        item = await library.get(f"{ABOUT[kind]}/{item_id}", lang=lang)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return _about(item, (item.get("files") or [None])[0])


@router.get("/library/artist/{artist_id}")
async def artist_detail(artist_id: int):
    """One artist's records, newest first: the ones there is something to play,
    and after them the ones there is not.

    The shelf used to be all of it, on the grounds that a discography belongs on
    the library's own page. That holds for a discography — every pressing, every
    single, a career laid out — and not for the plain question somebody asks
    with a remote in their hand, which is what of this artist is missing. So the
    second list is the canonical records only, minus the pressings that stand
    behind another, and minus whatever is already on its way."""
    try:
        artist = await library.get(f"/music/artists/{artist_id}")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    # A pressing that does not stand for its record is not a line of its own —
    # a remaster is not a second album — and the name and year come off the
    # record rather than off the pressing, which carries the reissue's date and
    # would run a band's history backwards.
    releases = [
        {"id": r["id"], "title": r.get("record_title") or r["title"],
         "year": (r.get("record_date") or r.get("release_date") or "")[:4],
         "cover": r.get("cover_url"), "tracks": r["files_linked"]}
        for r in artist.get("releases", [])
        if r.get("files_linked") and r.get("stands", True)
    ]
    releases.sort(key=lambda r: r["year"], reverse=True)
    # `coming` covers both halves of the wait: the library has been told to want
    # it, or a download is already running. Either way it is answered, and a row
    # that still offered it would be offering a second copy of the same record.
    # `coming` is the fact that something is on its way; `progress` is how far
    # it has got. Saying only the first is what a tile reading "on its way" for
    # twenty minutes with nothing else to tell looks like.
    missing = [
        {"id": r["id"], "title": r.get("record_title") or r["title"],
         "year": (r.get("record_date") or r.get("release_date") or "")[:4],
         "cover": r.get("cover_url"),
         "coming": r.get("status") not in (None, "none", "failed"),
         "state": r.get("status"), "progress": r.get("progress")}
        for r in artist.get("releases", [])
        if not r.get("files_linked") and r.get("canonical") and r.get("stands", True)
    ]
    missing.sort(key=lambda r: r["year"], reverse=True)
    return {
        "id": artist["id"], "name": artist["name"],
        "image": artist.get("image_url"), "releases": releases, "missing": missing,
        # everything the catalogue credits them with, which is what the line
        # under the name counts — not the two lists this page happens to split
        # it into
        "releases_total": len(artist.get("releases") or []),
        # who they are
        "bio": artist.get("bio") or "",
        "country": artist.get("country"),
        "begin_year": artist.get("begin_year"),
        "end_year": artist.get("end_year"),
        "artist_type": artist.get("artist_type"),
        # with their ids, because a name is something to read and an artist is
        # somewhere to go: Haustor and the Cargo Trio are two more shelves, not
        # two more words under this one
        "members": [{"id": m["id"], "name": m["name"]} for m in artist.get("members") or []],
        "groups": [{"id": g["id"], "name": g["name"]} for g in artist.get("groups") or []],
    }


@router.get("/library/search")
async def library_search(q: str):
    """Songs on the shelf that say the words — asked of the library, which is
    the only thing that knows what is here. The voice in the car asks this."""
    try:
        found = await library.get("/music/search/library", q=q)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))
    return [track_card(t) for t in found]


@router.get("/library/release/{release_id}/about")
async def release_about(release_id: int):
    """What the record is, in a paragraph. Asked after the music started, by a
    screen with room to say it, so nothing waits on it."""
    try:
        return await library.get(f"/music/releases/{release_id}/about")
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


@router.get("/library/release/{release_id}")
async def release_detail(release_id: int, prefer: str = "stereo"):
    """An album as the queue it is about to become.

    A record may be held in two editions, and which one to hand over is the
    surface's business: a browser folds every channel down to two before the
    sound leaves it, so only a screen with the box's own player behind it can
    ask for the surround mix and mean it."""
    try:
        return await library.get(f"/music/releases/{release_id}/playback",
                                 prefer=prefer)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc))


def _arranged(cards: list[dict], order: str) -> list[dict]:
    """The order a viewer walks past a shelf in, and which way round.

    Not asked of the library: the catalogue owns what a thing IS, and how it is
    laid out is the person looking at it. What comes back is newest-first, which
    is the right answer for a page showing what is new and the wrong one for a
    shelf being looked along for something in particular — and either of those
    is worth reading backwards, which is why the direction travels with the key
    rather than being a second question."""
    key, _, direction = order.partition(":")
    backwards = direction == "asc" if key in ("added", "year") else direction == "desc"
    if key == "title":
        arranged = sorted(cards, key=lambda c: croatian(c.get("title") or ""))
    elif key == "year":
        # the year itself, not the line it happens to be printed on: an artist
        # shows no year under their name and a film shows it as its subtitle
        arranged = sorted(cards, key=lambda c: (c.get("year") or 0), reverse=True)
    else:
        arranged = list(cards)
    return arranged[::-1] if backwards else arranged


@router.get("/library/{section}")
async def section(section: str, request: Request, order: str = "", lang: str = "en",
                  session: AsyncSession = Depends(get_session)):
    """One kind of thing, ALL of it. The home page shows rails and a rail is cut
    at two dozen because it is a glance; a section is the opposite — it is where
    you go when you know the library holds more than you can see."""
    # who is asking decides both the order they left the shelf in and which of
    # it they have already seen, so it is asked whether or not an order came
    # with the request
    who = await picked(request, session)
    if not order:
        order = orders_of(who.shelf_orders).get(section, "added") if who else "added"
    try:
        if section == "movies":
            found = await library.get("/video/movies", lang=lang)
            seen = await _seen(session, who, "movie")
            return _arranged([movie_card(m, seen) for m in found], order)
        if section == "series":
            found = await library.get("/video/series", lang=lang)
            seen = await _seen_within(session, who, "episode")
            return _arranged([series_card(s, seen) for s in found], order)
        if section == "music":
            found = await library.get("/music/artists")
            return _arranged([artist_card(a) for a in found], order)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    raise HTTPException(404, "no such section")


@router.get("/shelves")
async def shelves(request: Request, lang: str = "en",
                  session: AsyncSession = Depends(get_session)):
    """How much is on each shelf, and nothing else — the one place the player
    counts what the house holds, for the home screen and for the panel that
    answers the moment the remote passes a section in the menu.

    The album is counted only for somebody it belongs to: how many people and
    places the family has photographed is the album talking."""
    found = await auth.person(request.cookies.get(opus_auth.SESSION_COOKIE), auth.bearer_of(request))
    album = found is None or found.role != GUEST
    movies, series, shelf, *photos = await _all(
        (library.get("/video/movies", lang=lang), []),
        (library.get("/video/series", lang=lang), []),
        # what is ON the music shelf, which the artist listing cannot say: its
        # `releases` is every record the catalogue knows of that artist, held or
        # not, and summing it reported twenty thousand albums for a shelf of
        # three and a half
        (library.get("/music/library/stats"), {}),
        *([(library.get("/photos/timeline/buckets"), {}),
           (library.get("/photos/people"), []),
           (library.get("/photos/places"), [])] if album else []),
    )
    # a film with no file is something the library is still chasing; the player
    # counts what can be played, not what has been asked for
    playable = [m for m in movies if m.get("status") in ("complete", "waiting_subtitles")]

    def _years(months):
        years = sorted({m["month"][:4] for m in months if m.get("month")})
        return [int(years[0]), int(years[-1])] if len(years) > 1 else None

    def span(things, key="year"):
        years = sorted({t.get(key) for t in things if t.get(key)})
        return [years[0], years[-1]] if len(years) > 1 and years[0] != years[-1] else None

    # the one shelf the player holds itself: a station is a name and somebody
    # else's stream, so there is nothing to ask the library about
    stations, countries = (await session.execute(
        select(func.count(RadioStation.id),
               func.count(func.distinct(RadioStation.country)))
    )).one()

    counted = {
        "radio": {"count": stations, "countries": countries, "span": None},
        "movies": {"count": len(playable),
                   "hours": round(sum(m.get("runtime_min") or 0 for m in playable) / 60),
                   "span": span(playable)},
        "series": {"count": len(series),
                   "episodes": sum(s.get("episodes_have") or 0 for s in series),
                   "span": span(series)},
        "music": {"count": shelf.get("artists") or 0,
                  "releases": shelf.get("albums") or 0,
                  "span": shelf.get("span")},
    }
    if album:
        buckets, faces, wheres = photos
        counted["photos"] = {"count": buckets.get("total") or 0,
                             "people": len(faces),
                             "places": len(wheres),
                             "span": _years(buckets.get("months") or [])}
    return counted


# what a section's own continue row is made of
CARRIED_ON = {"movies": ("movie",), "series": ("episode",), "music": ("track",)}
# how far back "most listened" looks: a year is a taste, a lifetime is a history
HEARD_WITHIN = timedelta(days=365)


async def heard_most(session: AsyncSession, who, limit: int) -> list[int]:
    """The artists this person has played most in the last year, most first."""
    return list((await session.execute(
        select(MusicPlay.artist_id)
        .where(MusicPlay.user_id == who.id,
               MusicPlay.played_at > func.now() - HEARD_WITHIN)
        .group_by(MusicPlay.artist_id)
        .order_by(func.count().desc()).limit(limit)
    )).scalars())


@router.get("/rows/{section}")
async def section_rows(section: str, request: Request, lang: str = "en",
                       session: AsyncSession = Depends(get_session)):
    """The rows a section opens on, above the whole of it: what this person was
    in the middle of, and for music what they keep going back to and what the
    house has just got."""
    if section not in CARRIED_ON:
        raise HTTPException(404, "no such section")
    who = await picked(request, session)
    rows: list[dict] = []
    try:
        # the box's own records first, on the one session; then every row asks
        # the library at once, since none of them waits for another's answer
        resume: list[Progress] = []
        seen: set[int] = set()
        counted: list[int] = []
        if who is not None:
            resume = list((await session.execute(
                select(Progress).where(Progress.user_id == who.id,
                                       Progress.kind.in_(CARRIED_ON[section]))
                .order_by(Progress.updated_at.desc()).limit(ROW_LIMIT * 10)
            )).scalars())
            seen = await _seen(session, who, "episode")
            if section == "music":
                counted = await heard_most(session, who, ROW_LIMIT * 3)
        music = section == "music"
        continuing, artists, fresh = await asyncio.gather(
            _continue_row(resume, seen, lang),
            library.get("/music/artists", ids=",".join(map(str, counted))) if counted
            else _nothing(),
            library.get("/music/releases", recent=ROW_LIMIT * 3) if music else _nothing(),
        )
        if continuing and music:
            rows.append({"key": "listening", "cards": continuing})
        elif continuing:
            rows.append({"key": "watching", "cards": continuing})
        by_id = {a["id"]: a for a in artists}
        most = [artist_card(by_id[artist]) for artist in counted if artist in by_id]
        if most:
            rows.append({"key": "most_heard", "cards": most})
        if fresh:
            rows.append({"key": "just_in", "cards": [release_card(r) for r in fresh]})
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"rows": rows}


@router.get("/home")
async def home(request: Request, lang: str = "en",
               session: AsyncSession = Depends(get_session)):
    """The screen you arrive at is not a shelf, and how much the shelves hold is
    `/shelves`' to say: what belongs here is the one thing you were in the
    middle of."""
    who = await picked(request, session)
    if who is None:
        return {"rows": []}
    # More rows than the row holds are read: finished films, and the older
    # episodes of a series already on it, are passed over on the way to five.
    resume = list((await session.execute(
        select(Progress).where(Progress.user_id == who.id)
        .order_by(Progress.updated_at.desc()).limit(ROW_LIMIT * 10)
    )).scalars())
    try:
        continuing = await _continue_row(resume,
                                         await _seen(session, who, "episode"), lang)
    except library.LibraryError as exc:
        raise HTTPException(502, str(exc)) from exc
    return {"rows": [{"key": "continue", "cards": continuing}] if continuing else []}
