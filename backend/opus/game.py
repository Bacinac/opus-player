"""Who, where, when — a round of questions built out of the family archive.

The library knows three things about a photograph that a person can be asked to
remember: who is in it, where it was taken and when. This builds the questions
from exactly those facts and nothing else, so a question is never asked of a
picture whose answer nobody holds. The same three facts are asked four more
ways: who is missing from a group, where a picture is while it is still only a
detail, which of two was taken first, and how old somebody was in it.

What makes it a game is the wrong answers. A toddler in 2003 offered against
somebody born in 2011 is not a question, it is a spelling test — so the people
offered are the people who were being photographed in that year, and the places
offered are often places in the same country. The right answer is drawn from
the picture; the wrong ones are drawn from the archive around it."""

import random
from datetime import date

from opus import library

SECONDS = 20
# what a right answer is worth before the clock is taken into account, and how
# much of it the clock is
BASE = 100
SPEED = 100
# a run of right answers is worth more than the same answers apart. Capped:
# past a point the multiplier decides the round rather than the answers do.
STREAK_STEP = 0.2
STREAK_CAP = 2.0

KINDS = ("who", "where", "when", "missing", "zoom", "order", "age")
OPTIONS = 4
# how many photographs to draw for each question wanted, per kind
SPARES = {"who": 6, "where": 3, "when": 3, "missing": 4, "zoom": 3, "order": 6, "age": 6}
# how far from the truth a wrong year may be drawn. Wider than this and the
# question answers itself from the clothes in the picture.
YEAR_SPREAD = 6
# Somebody the household would actually recognise, right answer and wrong ones
# alike. Measured: 69 of the 123 named people clear this, and it costs the pool
# of single-person photographs 205 of 13,147 — the archive concentrates on the
# people it is about. Below the bar is somebody who passed through once, and
# neither remembering nor failing to remember them is a game.
KNOWN_FACES = 50
KNOWN_PLACE = 8
# How much of the frame the face has to fill to be worth asking about. Four per
# cent of the width is 80 pixels of a 2048-pixel preview: as the question it is
# a smear, and framed on the photograph afterwards it is a dot that could be
# pointing at anybody. Measured: at twelve per cent the pool is still 5,610
# photographs, which is a family game several hundred times over.
MIN_FACE = 0.12
# and how wide a face in a group has to be to be the one taken out of it.
# Narrower than a portrait's bar: faces in a group are smaller, and the one
# missing is recognised from everything around the gap rather than from the
# gap. The library draws groups by the same number.
HIDEABLE = 0.08
# The patch that covers a missing person, as multiples of the face box. Wider
# than the face and much taller than it, because a face box stops at the brow
# and the chin and the person is recognised from the hair above and the neck
# below as surely as from the face. The clothes stay: that is remembering who
# wore what, which is the game.
COVER_WIDE = 1.8
COVER_UP = 0.5
COVER_DOWN = 0.7
# how far in a picture starts when it is asked about as a detail
ZOOM_FROM = 4.0
# How far apart two photographs have to be to be asked which came first, in
# days. Closer than a year and it is a coin; further than eight and the question
# answers itself from the camera.
ORDER_GAP = (365, 8 * 365)
# no detector's bar on the face for an age question: how clearly the face was
# found says nothing about how old it is
EASIEST_FACE = 0.938
OLDEST = 100


def multiplier(streak: int) -> float:
    """What a run is worth. The first right answer is worth itself."""
    return min(1.0 + STREAK_STEP * max(streak - 1, 0), STREAK_CAP)


def score(elapsed: float, seconds: int, streak: int) -> int:
    """A right answer, priced by what was left on the clock and what run it is
    part of. An answer given as the clock runs out is still a right answer, so
    the base is never at risk — only the bonus is."""
    left = max(0.0, min(1.0, (seconds - elapsed) / seconds))
    return round((BASE + SPEED * left) * multiplier(streak))


def _year(taken_at: str) -> int:
    return int(taken_at[:4])


def _pick(pool: list, n: int) -> list:
    return random.sample(pool, n) if len(pool) > n else list(pool)


def _known(people: list[dict]) -> dict[int, dict]:
    return {p["id"]: p for p in people if p["faces"] >= KNOWN_FACES}


def _lived(who: dict, year: int) -> bool:
    """Was being photographed the year this was taken."""
    return (who["years"][0] is not None
            and who["years"][0] <= year <= who["years"][1])


def _names(wrong: list[dict], truth: dict) -> list[dict]:
    """Names, and nothing else. A portrait beside each name is the answer twice:
    the question is already a face, and matching a face to a face is not
    remembering anybody."""
    options = [{"key": f"p{p['id']}", "label": p["name"]} for p in wrong]
    options.append({"key": f"p{truth['id']}", "label": truth["name"]})
    random.shuffle(options)
    return options


def _who(photo: dict, people: list[dict]) -> dict | None:
    """Who is in this. One named face, so there is one right answer.

    The three offered against them are the people who look most like them and
    who were being photographed that same year — the first is what makes it a
    question, the second is what stops it being a giveaway: somebody who was
    not born yet is not a wrong answer."""
    if not photo["people"]:
        return None
    truth = photo["people"][0]
    if (truth.get("box") or {}).get("w", 0) < MIN_FACE:
        return None
    known = _known(people)
    if truth["id"] not in known:
        return None
    year = _year(photo["taken_at"])

    # The people this face is actually NEAR, nearest first — the library says
    # who looks like whom, and three names picked at random are three names
    # ruled out without looking at the face.
    alike = [known[one["id"]] for one in truth.get("like", [])
             if one["id"] in known and one["id"] != truth["id"]]
    era = [p for p in alike if _lived(p, year)]
    wrong = (era if len(era) >= OPTIONS - 1 else alike)[:OPTIONS - 1]
    if len(wrong) < OPTIONS - 1:
        # nobody near enough who is also known: fall back to whoever was being
        # photographed that year, which is the weaker question but a question
        others = [p for p in known.values()
                  if p["id"] != truth["id"] and p not in wrong]
        wrong += _pick([p for p in others if _lived(p, year)], OPTIONS - 1 - len(wrong))
    if len(wrong) < OPTIONS - 1:
        return None
    return {"kind": "who", "answer": f"p{truth['id']}", "options": _names(wrong, truth),
            # the face is the question. The whole photograph would answer it
            # for anybody who recognises the room, the day or who else is in it.
            "face": truth.get("face"),
            # the rectangle that face was cut out of, for the photograph shown
            # once it has been answered: not "somebody is here" but "this is
            # the piece you were looking at". The library works it out, being
            # the one that cuts it.
            "frame": truth.get("frame")}


def _cover(box: dict) -> dict:
    """The patch over a missing person, as fractions of the picture."""
    wide = box["w"] * COVER_WIDE
    left = box["x"] + box["w"] / 2 - wide / 2
    top = box["y"] - box["h"] * COVER_UP
    bottom = box["y"] + box["h"] * (1 + COVER_DOWN)
    left, top = max(0.0, left), max(0.0, top)
    right, bottom = min(1.0, left + wide), min(1.0, bottom)
    return {"x": left, "y": top, "w": right - left, "h": bottom - top}


def _missing(photo: dict, people: list[dict], company: list[dict]) -> dict | None:
    """Who is missing from this group. One of them is covered, everybody else
    stays — the opposite of "who": there the picture around the face was taken
    away because it answered the question, here it IS the question.

    The three offered against them are the people most often photographed with
    the ones still in the picture, because that is who would plausibly have
    been standing there. Three names from the rest of the archive are three
    names nobody in this picture ever stood beside."""
    known = _known(people)
    year = _year(photo["taken_at"])
    on = {p["id"] for p in photo["people"]}
    takeable = [p for p in photo["people"]
                if p["id"] in known and (p.get("box") or {}).get("w", 0) >= HIDEABLE]
    if len(on) < 2 or not takeable:
        return None
    hidden = random.choice(takeable)
    visible = on - {hidden["id"]}
    weight: dict[int, int] = {}
    for pair in company:
        for near, far in ((pair["a"], pair["b"]), (pair["b"], pair["a"])):
            if near in visible and far not in on:
                weight[far] = weight.get(far, 0) + pair["together"]
    usual = sorted((pid for pid in weight if pid in known and _lived(known[pid], year)),
                   key=lambda pid: -weight[pid])
    wrong = [known[pid] for pid in usual[:OPTIONS - 1]]
    if len(wrong) < OPTIONS - 1:
        others = [p for p in known.values()
                  if p["id"] not in on and p not in wrong and _lived(p, year)]
        wrong += _pick(others, OPTIONS - 1 - len(wrong))
    if len(wrong) < OPTIONS - 1:
        return None
    return {"kind": "missing", "answer": f"p{hidden['id']}",
            "options": _names(wrong, hidden),
            "hide": _cover(hidden["box"]), "frame": hidden.get("frame")}


def _where(photo: dict, places: list[dict]) -> dict | None:
    """Where this was taken. Half the time all four are in the same country,
    which is the difference between remembering a holiday and recognising a
    language on a shopfront."""
    if not photo["place"]:
        return None
    here = photo["place"]
    # Not a district of the same town. The archive names places as finely as
    # the map does — "Paris 16 Passy" against "Paris 02 Bourse" — and nobody
    # remembers which arrondissement a photograph was taken in. Being in the
    # same city is what makes those the same answer.
    town = here.split()[0].lower()
    others = [p for p in places
              if p["place"] != here and p["photographs"] >= KNOWN_PLACE
              and p["place"].split()[0].lower() != town]
    near = [p for p in others if p["country"] == photo["country"]]
    pool = near if len(near) >= OPTIONS - 1 and random.random() < 0.5 else others
    wrong = _pick(pool, OPTIONS - 1)
    if len(wrong) < OPTIONS - 1:
        return None
    options = [{"key": f"l{p['place']}", "label": p["place"],
                "country": p["country"]} for p in wrong]
    options.append({"key": f"l{here}", "label": here, "country": photo["country"]})
    random.shuffle(options)
    return {"kind": "where", "answer": f"l{here}", "options": options}


def _zoom(photo: dict, places: list[dict]) -> dict | None:
    """Where this was taken, asked of a detail that widens as the clock runs.
    The same question as "where", priced differently: the earlier the answer,
    the less of the picture it was given from. The detail starts somewhere in
    the middle half, never a corner — a corner is sky."""
    made = _where(photo, places)
    if made is None:
        return None
    made["kind"] = "zoom"
    made["zoom"] = {"x": round(random.uniform(0.3, 0.7), 3),
                    "y": round(random.uniform(0.3, 0.7), 3), "scale": ZOOM_FROM}
    return made


def _when(photo: dict, years: list[int]) -> dict | None:
    """Which year. The wrong years are years the archive actually has: a year
    the house took no photographs in is a year nobody has to think about."""
    truth = _year(photo["taken_at"])
    near = [y for y in years if y != truth and abs(y - truth) <= YEAR_SPREAD]
    wrong = _pick(near, OPTIONS - 1)
    if len(wrong) < OPTIONS - 1:
        return None
    options = [{"key": f"y{y}", "label": str(y)} for y in wrong + [truth]]
    # years read as years: sorted, not shuffled. Four dates in a jumble is a
    # sorting task laid on top of the question.
    options.sort(key=lambda o: o["label"])
    return {"kind": "when", "answer": f"y{truth}", "options": options}


def _days_apart(one: dict, other: dict) -> int:
    return abs((date.fromisoformat(one["taken_at"][:10])
                - date.fromisoformat(other["taken_at"][:10])).days)


def _order(first: dict, second: dict) -> dict:
    """Which of two was taken first. The two are lettered rather than named by
    where they stand, because they stand side by side on a television and one
    above the other in a hand."""
    a, b = (first, second) if random.random() < 0.5 else (second, first)
    earlier = "a" if a["taken_at"] <= b["taken_at"] else "b"
    return {"kind": "order", "answer": earlier,
            "options": [{"key": "a", "label": "A"}, {"key": "b", "label": "B"}],
            "photo": _picture(a), "second": _picture(b),
            "facts": _facts(a), "second_facts": _facts(b)}


def _pairs(photos: list[dict], want: int, seen: set[str]) -> list[dict]:
    """Pairs far enough apart to be a question and close enough to be one."""
    pool = [p for p in photos if p["id"] not in seen]
    random.shuffle(pool)
    made: list[dict] = []
    while len(made) < want and len(pool) >= 2:
        first = pool.pop()
        partner = next((p for p in pool
                        if ORDER_GAP[0] <= _days_apart(first, p) <= ORDER_GAP[1]), None)
        if partner is None:
            continue
        pool.remove(partner)
        seen.update((first["id"], partner["id"]))
        made.append(_order(first, partner))
    return made


def _age_at(born_on: str, taken_at: str) -> int:
    born = date.fromisoformat(born_on)
    taken = date.fromisoformat(taken_at[:10])
    return taken.year - born.year - ((taken.month, taken.day) < (born.month, born.day))


def _age(photo: dict, people: list[dict]) -> dict | None:
    """How old somebody was in this. Asked with the whole photograph and the
    face framed on it: the room and the others in it are what the age is
    judged from, and the name is given — this is not "who".

    The four ages step by one for a child, by two for a teenager and by three
    for anybody older, because that is how finely anybody can tell. Where the
    truth sits among the four moves, or the middle would always be the answer."""
    if not photo["people"]:
        return None
    truth = photo["people"][0]
    if not truth.get("born_on") or (truth.get("box") or {}).get("w", 0) < MIN_FACE:
        return None
    if truth["id"] not in _known(people):
        return None
    age = _age_at(truth["born_on"], photo["taken_at"])
    if not 0 <= age <= OLDEST:
        return None
    step = 1 if age < 10 else 2 if age < 20 else 3
    lowest = max(0, age - step * random.randint(0, OPTIONS - 1))
    options = [{"key": f"a{lowest + step * i}", "label": str(lowest + step * i)}
               for i in range(OPTIONS)]
    return {"kind": "age", "answer": f"a{age}", "options": options,
            "name": truth["name"], "frame": truth.get("frame")}


def _picture(photo: dict) -> dict:
    return {"id": photo["id"], "w": photo["w"], "h": photo["h"],
            "hash": photo["hash"], "turn": photo["turn"]}


def _facts(photo: dict) -> dict:
    """What the picture turns out to be, shown once it has been answered. All
    of it, not only the fact that was asked about — the photograph is the point
    of the game, and half of what it is would be a poor reward."""
    return {
        "taken_at": photo["taken_at"],
        "place": photo["place"], "country": photo["country"],
        "people": [{"id": p["id"], "name": p["name"]} for p in photo["people"]],
    }


# what each kind asks the library to draw
KNOWS = {"who": "person", "where": "place", "when": "date", "missing": "group",
         "zoom": "place", "order": "date", "age": "person"}


async def build(count: int = 10, kinds: tuple[str, ...] = KINDS,
                hard: float | None = None) -> list[dict]:
    """A round: `count` questions, drawn across the kinds asked for.

    Everything is asked of the library up front — the vocabularies once, and
    one draw per kind — because a question built halfway through a round is a
    pause in the middle of a game."""
    kinds = tuple(k for k in kinds if k in KINDS) or KINDS
    people, places, buckets, company = await _vocabulary("missing" in kinds)
    years = sorted({int(m["month"][:4]) for m in buckets["months"]})

    # Dealt round the kinds in a different order each time: ten questions over
    # seven kinds leave three kinds with one more, and it must not always be
    # the same three.
    dealt = list(kinds)
    random.shuffle(dealt)
    wants = {k: 0 for k in dealt}
    for i in range(count):
        wants[dealt[i % len(dealt)]] += 1

    questions: list[dict] = []
    # photographs already used, and answers already asked for
    seen: set[str] = set()
    answers: set[str] = set()
    for kind, want in wants.items():
        if not want:
            continue
        # More than are needed, because a drawn photograph can still fail to
        # make a question. How many more is not the same per kind: "who" throws
        # away the ones whose face is too small to ask about, which is over half
        # of them, and a round that quietly came back with nine questions was
        # this number being the same for all three.
        # how clearly a face was detected is how hard it is to recognise, so
        # the difficulty is a question about faces and the other kinds do not
        # take it
        extra = ({"hard": hard} if kind == "who" and hard is not None else
                 {"hard": EASIEST_FACE} if kind == "age" else {})
        drawn = await library.get("/photos/draw", knows=KNOWS[kind],
                                  count=want * SPARES[kind], **extra)
        if kind == "order":
            questions += _pairs(drawn["photos"], want, seen)
            continue
        pool = []
        for photo in drawn["photos"]:
            if photo["id"] in seen:
                continue
            made = (_who(photo, people) if kind == "who" else
                    _missing(photo, people, company) if kind == "missing" else
                    _where(photo, places) if kind == "where" else
                    _zoom(photo, places) if kind == "zoom" else
                    _age(photo, people) if kind == "age" else
                    _when(photo, years))
            if made is None:
                continue
            made["photo"] = _picture(photo)
            made["facts"] = _facts(photo)
            pool.append(made)

        # A round that asks who somebody is twice, and it is the same person
        # both times, is nine questions and an echo. Answers already used are
        # passed over while there is anything else to ask — and taken anyway
        # when there is not, because a shorter round is the worse of the two.
        taken = [one for one in pool if one["answer"] not in answers][:want]
        answers.update(one["answer"] for one in taken)
        if len(taken) < want:
            taken += [one for one in pool if one not in taken][:want - len(taken)]
        # only what was taken is used up: two kinds draw from the same well,
        # and the spares one of them threw back are the other's questions
        seen.update(one["photo"]["id"] for one in taken)
        questions += taken
    random.shuffle(questions)
    for i, question in enumerate(questions):
        question["n"] = i
    return questions


async def _vocabulary(groups: bool) -> tuple[list[dict], list[dict], dict, list[dict]]:
    """Everybody the archive has named, everywhere it has been, every month it
    holds — and, when a group is going to be asked about, who is photographed
    with whom. The player keeps none of it: it is the library's answer to what
    exists, and a copy here would be a copy that goes stale between rounds."""
    people = await library.get("/photos/people")
    places = await library.get("/photos/places")
    buckets = await library.get("/photos/timeline/buckets")
    company = await library.get("/photos/people/company") if groups else []
    return people, places, buckets, company


# what travels to the screen besides the picture and the options, where a
# kind has it
SHOWN = ("face", "frame", "hide", "zoom", "second", "name")


def asked(question: dict) -> dict:
    """The half of a question a player may see. The answer stays here: a round
    whose answers travel to the screen is a round played against the screen."""
    return {"n": question["n"], "kind": question["kind"],
            "photo": question["photo"], "options": question["options"],
            **{key: question[key] for key in SHOWN if question.get(key) is not None}}
