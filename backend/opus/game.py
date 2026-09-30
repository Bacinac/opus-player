"""Who, where, when — a round of questions built out of the family archive.

The library knows three things about a photograph that a person can be asked to
remember: who is in it, where it was taken and when. This builds the questions
from exactly those facts and nothing else, so a question is never asked of a
picture whose answer nobody holds.

What makes it a game is the wrong answers. A toddler in 2003 offered against
somebody born in 2011 is not a question, it is a spelling test — so the people
offered are the people who were being photographed in that year, and the places
offered are often places in the same country. The right answer is drawn from
the picture; the wrong ones are drawn from the archive around it."""

import random

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

KINDS = ("who", "where", "when")
OPTIONS = 4
# how many photographs to draw for each question wanted, per kind
SPARES = {"who": 6, "where": 3, "when": 3}
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
    known = {p["id"]: p for p in people if p["faces"] >= KNOWN_FACES}
    if truth["id"] not in known:
        return None
    year = _year(photo["taken_at"])

    def lived(who: dict) -> bool:
        """Was being photographed the year this was taken."""
        return (who["years"][0] is not None
                and who["years"][0] <= year <= who["years"][1])

    # The people this face is actually NEAR, nearest first — the library says
    # who looks like whom, and three names picked at random are three names
    # ruled out without looking at the picture.
    alike = [known[one["id"]] for one in truth.get("like", [])
             if one["id"] in known and one["id"] != truth["id"]]
    era = [p for p in alike if lived(p)]
    wrong = (era if len(era) >= OPTIONS - 1 else alike)[:OPTIONS - 1]
    if len(wrong) < OPTIONS - 1:
        # nobody near enough who is also known: fall back to whoever was being
        # photographed that year, which is the weaker question but a question
        others = [p for p in known.values()
                  if p["id"] != truth["id"] and p not in wrong]
        wrong += _pick([p for p in others if lived(p)], OPTIONS - 1 - len(wrong))
    if len(wrong) < OPTIONS - 1:
        return None
    # Names, and nothing else. A portrait beside each name is the answer twice:
    # the question is already a face, and matching a face to a face is not
    # remembering anybody.
    options = [{"key": f"p{p['id']}", "label": p["name"]} for p in wrong]
    options.append({"key": f"p{truth['id']}", "label": truth["name"]})
    random.shuffle(options)
    return {"kind": "who", "answer": f"p{truth['id']}", "options": options,
            # the face is the question. The whole photograph would answer it
            # for anybody who recognises the room, the day or who else is in it.
            "face": truth.get("face"),
            # the rectangle that face was cut out of, for the photograph shown
            # once it has been answered: not "somebody is here" but "this is
            # the piece you were looking at". The library works it out, being
            # the one that cuts it.
            "frame": truth.get("frame")}


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


def _facts(photo: dict) -> dict:
    """What the picture turns out to be, shown once it has been answered. All
    of it, not only the fact that was asked about — the photograph is the point
    of the game, and half of what it is would be a poor reward."""
    return {
        "taken_at": photo["taken_at"],
        "place": photo["place"], "country": photo["country"],
        "people": [{"id": p["id"], "name": p["name"]} for p in photo["people"]],
    }


async def build(count: int = 10, kinds: tuple[str, ...] = KINDS,
                hard: float | None = None) -> list[dict]:
    """A round: `count` questions, drawn across the kinds asked for.

    Everything is asked of the library up front — the two vocabularies once,
    and one draw per kind — because a question built halfway through a round is
    a pause in the middle of a game."""
    kinds = tuple(k for k in kinds if k in KINDS) or KINDS
    people, places, buckets = await _vocabulary()
    years = sorted({int(m["month"][:4]) for m in buckets["months"]})

    wants = {k: 0 for k in kinds}
    for i in range(count):
        wants[kinds[i % len(kinds)]] += 1

    knows = {"who": "person", "where": "place", "when": "date"}
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
        extra = {"hard": hard} if kind == "who" and hard is not None else {}
        drawn = await library.get("/photos/draw", knows=knows[kind],
                                  count=want * SPARES[kind], **extra)
        pool = []
        for photo in drawn["photos"]:
            if photo["id"] in seen:
                continue
            made = (_who(photo, people) if kind == "who" else
                    _where(photo, places) if kind == "where" else
                    _when(photo, years))
            if made is None:
                continue
            seen.add(photo["id"])
            made["photo"] = {"id": photo["id"], "w": photo["w"], "h": photo["h"],
                             "hash": photo["hash"], "turn": photo["turn"]}
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
        questions += taken
    random.shuffle(questions)
    for i, question in enumerate(questions):
        question["n"] = i
    return questions


async def _vocabulary() -> tuple[list[dict], list[dict], dict]:
    """Everybody the archive has named, everywhere it has been, and every month
    it holds. The player keeps none of it: it is the library's answer to what
    exists, and a copy here would be a copy that goes stale between rounds."""
    people = await library.get("/photos/people")
    places = await library.get("/photos/places")
    buckets = await library.get("/photos/timeline/buckets")
    return people, places, buckets


def asked(question: dict) -> dict:
    """The half of a question a player may see. The answer stays here: a round
    whose answers travel to the screen is a round played against the screen."""
    return {"n": question["n"], "kind": question["kind"],
            "photo": question["photo"], "options": question["options"],
            "face": question.get("face"), "frame": question.get("frame")}
