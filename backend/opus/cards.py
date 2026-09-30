"""What a thing from the library looks like on a shelf of this player, and the
order a shelf of them is read in. Built in one place because every router that
hands out a card must hand out the same card."""

import unicodedata


def movie_card(m: dict, seen: set[int] = frozenset()) -> dict:
    return {
        "kind": "movie", "id": m["id"], "tmdb_id": m.get("tmdb_id"),
        "title": m["title"], "subtitle": m.get("year"),
        # this person has seen it; another profile in the same house has not
        "seen": 1 if m["id"] in seen else 0,
        "year": m.get("year"),
        "image": m.get("poster_url"), "backdrop": m.get("backdrop_url"),
        "state": m.get("status"), "overview": m.get("overview") or "",
        "runtime_min": m.get("runtime_min"),
        "genres": m.get("genres") or [], "directors": m.get("directors") or [],
    }


def series_card(s: dict, seen: dict[int, int] | None = None) -> dict:
    # how much of the series is here, out of what it has — not how much of what
    # is here is here, which is what a count taken twice off the disk says
    have, total = s.get("episodes_have") or 0, s.get("episodes_known") or 0
    return {
        "kind": "series", "id": s["id"], "tmdb_id": s.get("tmdb_id"),
        "title": s["title"], "subtitle": s.get("year"), "year": s.get("year"),
        "image": s.get("poster_url"), "backdrop": s.get("backdrop_url"),
        "state": s.get("status"), "overview": s.get("overview") or "",
        "genres": s.get("genres") or [], "directors": s.get("directors") or [],
        "badge": f"{have}/{total}" if total else None,
        "seen": (seen or {}).get(s["id"], 0),
        "episodes": have,
    }


def artist_card(a: dict) -> dict:
    return {
        "kind": "artist", "id": a["id"], "title": a["name"], "subtitle": None,
        # for an artist the year is when they turned up, which is the only
        # reading of "year" a shelf of people can have
        "year": a.get("begin_year"),
        "image": a.get("image_url"), "backdrop": a.get("backdrop_url"), "state": None,
        # a person is never asked for. A career is terabytes; what somebody
        # means when they point at somebody is one of their records
        "person": True,
        "overview": a.get("blurb") or "",
        "end_year": a.get("end_year"), "country": a.get("country"), "country_hr": a.get("country_hr"),
        # what the catalogue knows of them, and of that what is on the shelf: a
        # panel adding up the first says twenty thousand albums of three and a half
        "releases": a.get("releases"), "held": a.get("held"),
        "round": True,
    }


def track_card(t: dict) -> dict:
    # the record it is on, because that is what is put back on: one song out of
    # an album is a place in the album, not a thing of its own
    return {
        "kind": "track", "id": t["id"], "title": t["title"],
        "subtitle": f'{t["artist"]} · {t["album"]}',
        "artist": t["artist"], "album": t["album"],
        "position": t.get("position"), "codec": t.get("codec"),
        "image": t.get("cover_url"), "backdrop": None, "state": None,
        "overview": "", "release_id": t.get("release_id"),
        "duration_s": t.get("duration_s"), "square": True,
    }


def release_card(r: dict) -> dict:
    return {
        "kind": "release", "id": r["id"], "title": r["title"],
        "subtitle": r["artist"], "artist": r["artist"], "artist_id": r["artist_id"],
        "year": r.get("year"), "image": r.get("cover_url"), "backdrop": None,
        "state": None, "overview": "", "square": True,
    }


def episode_card(e: dict) -> dict:
    return {
        "kind": "episode", "id": e["id"], "title": e["series_title"],
        "season_number": e["season_number"], "number": e["number"],
        "episode_title": e["title"] or "",
        "image": e.get("poster_url"), "backdrop": e.get("backdrop_url"),
        "state": "complete", "overview": e.get("overview") or "",
        "year": e.get("year"), "genres": e.get("genres") or [],
        "series_id": e["series_id"],
    }


# The Croatian alphabet, in its own order — č and ć between c and d, š after s,
# ž last — with the letters foreign titles bring with them slotted into their
# Latin places. Codepoint order puts all five of those after z, and Šehić and
# Žmegač past the end of the shelf.
_ALPHABET = [
    "a", "b", "c", "č", "ć", "d", "dž", "đ", "e", "f", "g", "h", "i", "j", "k",
    "l", "lj", "m", "n", "nj", "o", "p", "q", "r", "s", "š", "t", "u", "v", "w",
    "x", "y", "z", "ž",
]
_RANK = {letter: place for place, letter in enumerate(_ALPHABET)}
_DIGRAPHS = ("dž", "lj", "nj")

# what sits either side of the alphabet: the punctuation a title starts with
# first, then anything that is a number, then the letters, and a script this
# alphabet has no place for after all of them
_MARK = -2
_DIGIT = -1
_FOREIGN = len(_ALPHABET)


def croatian(text: str) -> list[tuple[int, str]]:
    """A sort key that reads the way the alphabet is recited, whoever is
    looking: the three digraphs are single letters, and a number is compared as
    a number, so 300 sorts before 1917."""
    lowered = unicodedata.normalize("NFC", (text or "").casefold())
    key: list[tuple[int, str]] = []
    at = 0
    while at < len(lowered):
        letter = lowered[at]

        if "0" <= letter <= "9":
            run = at
            while run < len(lowered) and "0" <= lowered[run] <= "9":
                run += 1
            number = lowered[at:run].lstrip("0") or "0"
            key.append((_DIGIT, f"{len(number):04d}{number}"))
            at = run
            continue

        pair = lowered[at:at + 2]
        if pair in _DIGRAPHS:
            key.append((_RANK[pair], pair))
            at += 2
            continue

        at += 1
        if letter in _RANK:
            key.append((_RANK[letter], letter))
            continue
        stripped = unicodedata.normalize("NFD", letter)[0]
        if stripped in _RANK:
            key.append((_RANK[stripped], letter))
        elif letter.isalnum():
            key.append((_FOREIGN, letter))
        else:
            key.append((_MARK, letter))
    return key
