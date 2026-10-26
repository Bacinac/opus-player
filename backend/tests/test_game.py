"""The questions, built out of a small library that answers like the real one."""

import random

import pytest

from conftest import run
from opus import game, library

PEOPLE = [
    {"id": 1, "name": "Ana", "faces": 400, "years": [1998, 2024]},
    {"id": 2, "name": "Bruno", "faces": 300, "years": [1998, 2024]},
    {"id": 3, "name": "Cvita", "faces": 200, "years": [2005, 2024]},
    {"id": 4, "name": "Dino", "faces": 150, "years": [1998, 2024]},
    {"id": 5, "name": "Ema", "faces": 120, "years": [1998, 2024]},
    {"id": 9, "name": "Prolaznik", "faces": 3, "years": [2010, 2010]},
]
PLACES = [{"place": p, "country": c, "photographs": 20} for p, c in (
    ("Zagreb", "HR"), ("Split", "HR"), ("Rijeka", "HR"), ("Beč", "AT"), ("Pariz", "FR"))]
BUCKETS = {"months": [{"month": f"{y}-06"} for y in range(2000, 2016)]}
COMPANY = [{"a": 1, "b": 2, "together": 500}, {"a": 1, "b": 4, "together": 80},
           {"a": 2, "b": 5, "together": 60}, {"a": 1, "b": 3, "together": 40},
           {"a": 1, "b": 9, "together": 30}]


def photo(n: int, taken: str, people: list[dict], place: str | None = "Zagreb") -> dict:
    return {"id": f"{n:040x}", "taken_at": f"{taken}T12:00:00", "dated": "exif",
            "place": place, "country": "HR" if place else None,
            "w": 4000, "h": 3000, "hash": None, "turn": 0, "people": people}


def face(pid: int, w: float = 0.2, **more) -> dict:
    who = next(p for p in PEOPLE if p["id"] == pid)
    return {"id": pid, "name": who["name"], "face": 1000 + pid,
            "frame": {"x": 0.1, "y": 0.1, "w": 0.3, "h": 0.4},
            "box": {"x": 0.3, "y": 0.2, "w": w, "h": w * 1.3}, "age": None,
            "born_on": None, "like": [], **more}


GROUP = photo(1, "2010-05-01", [face(1, 0.1), face(2, 0.12), face(9, 0.05)])
SINGLE = photo(2, "2010-05-01", [face(1, born_on="2000-07-15")])
SINGLES = [SINGLE, photo(3, "2011-05-01", [face(2, born_on="1975-01-01")]),
           photo(4, "2012-05-01", [face(4, born_on="1990-12-31")])]
PLACED = [photo(5 + i, "2009-05-01", [], place=where) for i, where in enumerate(("Split", "Beč", "Pariz"))]
DATED = [photo(10 + i, f"{y}-03-03", [], place=None)
         for i, y in enumerate((2001, 2003, 2004, 2012, 2013, 2030))]


@pytest.fixture
def shelf(monkeypatch):
    draws = {"group": [GROUP], "person": SINGLES, "place": PLACED, "date": DATED}

    async def get(path, **params):
        if path == "/photos/draw":
            return {"photos": draws[params["knows"]]}
        return {"/photos/people": PEOPLE, "/photos/places": PLACES,
                "/photos/timeline/buckets": BUCKETS, "/photos/people/company": COMPANY}[path]

    monkeypatch.setattr(library, "get", get)


def test_the_one_missing_is_covered_and_the_usual_company_is_offered():
    random.seed(1)
    made = game._missing(GROUP, PEOPLE, COMPANY)
    assert made["kind"] == "missing"
    hidden = int(made["answer"][1:])
    # the passer-by is too small and too rare to be the one taken out
    assert hidden in (1, 2)
    labels = {o["label"] for o in made["options"]}
    assert len(made["options"]) == 4
    # whoever stays in the picture is not an answer; who usually stands with
    # them is
    assert {"Ana", "Bruno"} - labels == {next(p["name"] for p in PEOPLE if p["id"] != hidden and p["id"] in (1, 2))}
    assert "Prolaznik" not in labels
    cover = made["hide"]
    assert 0 <= cover["x"] and cover["x"] + cover["w"] <= 1
    assert 0 <= cover["y"] and cover["y"] + cover["h"] <= 1
    # taller than the face it covers: hair above, neck below
    taken = next(p for p in GROUP["people"] if p["id"] == hidden)
    assert cover["h"] > taken["box"]["h"] * 2 and cover["w"] > taken["box"]["w"] * 1.5


def test_two_people_too_small_to_take_out_is_no_question():
    small = photo(3, "2010-05-01", [face(1, 0.05), face(2, 0.05)])
    assert game._missing(small, PEOPLE, COMPANY) is None


def test_a_detail_is_where_with_a_starting_point_inside_the_middle():
    made = game._zoom(SINGLE, PLACES)
    assert made["kind"] == "zoom"
    assert 0.3 <= made["zoom"]["x"] <= 0.7 and 0.3 <= made["zoom"]["y"] <= 0.7
    assert made["zoom"]["scale"] == game.ZOOM_FROM
    assert made["answer"] == "lZagreb"


def test_pairs_are_a_year_to_eight_years_apart_and_lettered():
    random.seed(3)
    seen: set[str] = set()
    made = game._pairs(DATED, 3, seen)
    assert made, "something pairs"
    for one in made:
        a, b = one["facts"]["taken_at"], one["second_facts"]["taken_at"]
        apart = abs(int(a[:4]) - int(b[:4]))
        assert 1 <= apart <= 8
        assert [o["key"] for o in one["options"]] == ["a", "b"]
        assert one["answer"] == ("a" if a <= b else "b")
    # a photograph is in one pair only
    used = [one["photo"]["id"] for one in made] + [one["second"]["id"] for one in made]
    assert len(used) == len(set(used))


def test_an_age_is_counted_from_the_birthday_and_stands_among_four():
    random.seed(5)
    made = game._age(SINGLE, PEOPLE)
    assert made["kind"] == "age" and made["name"] == "Ana"
    # born July 2000, photographed May 2010: nine, not ten
    assert made["answer"] == "a9"
    labels = [int(o["label"]) for o in made["options"]]
    assert labels == sorted(labels) and 9 in labels
    assert all(b - a == 1 for a, b in zip(labels, labels[1:]))


def test_no_birthday_is_no_age_question():
    assert game._age(photo(4, "2010-05-01", [face(2)]), PEOPLE) is None


def test_a_round_deals_every_kind_and_shows_no_answers(shelf):
    random.seed(7)
    questions = run(game.build(count=10))
    assert {q["kind"] for q in questions} == set(game.KINDS)
    assert [q["n"] for q in questions] == list(range(len(questions)))
    for q in questions:
        shown = game.asked(q)
        assert "answer" not in shown and "facts" not in shown and "second_facts" not in shown
        if q["kind"] == "order":
            assert "second" in shown
        if q["kind"] == "missing":
            assert "hide" in shown
        if q["kind"] == "age":
            assert shown["name"] and shown["frame"]


def test_the_kinds_dealt_one_more_differ_between_rounds(shelf):
    """ten over seven: which three get a second question moves"""
    extra = set()
    for seed in range(12):
        random.seed(seed)
        dealt = list(game.KINDS)
        random.shuffle(dealt)
        extra.add(tuple(dealt[:3]))
    assert len(extra) > 1
