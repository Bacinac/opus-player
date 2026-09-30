from datetime import UTC, datetime
from types import SimpleNamespace

from conftest import run
from opus import library
from opus.api.routers import home
from opus.models import Progress

DONE = datetime(2026, 9, 1, tzinfo=UTC)


def episode(id, series_id, season, number, playable=True):
    return {"id": id, "series_id": series_id, "season_number": season, "number": number,
            "title": f"E{number}", "series_title": f"Series {series_id}", "playable": playable}


EPISODES = {e["id"]: e for e in (episode(10, 100, 1, 4), episode(11, 100, 1, 3),
                                 episode(20, 200, 1, 1), episode(22, 200, 1, 3),
                                 episode(30, 300, 2, 8))}
TRACKS = {5: {"id": 5, "title": "Balkan", "artist": "Azra", "album": "Ravno do dna",
              "release_id": 7, "playable": True, "duration_s": 200.0},
          6: {"id": 6, "title": "Pavel", "artist": "Azra", "album": "Ravno do dna",
              "release_id": 7, "playable": True},
          8: {"id": 8, "title": "Gone", "artist": "Azra", "album": "Other",
              "release_id": 9, "playable": False}}
SERIES = {
    200: {"seasons": [{"number": 1, "episodes": [
        {"id": 20, "number": 1, "file": "a"}, {"id": 21, "number": 2, "file": "b"},
        {"id": 22, "number": 3, "file": "c"}]}]},
    300: {"seasons": [{"number": 2, "episodes": [{"id": 30, "number": 8, "file": "d"}]}]},
}


def test_the_row_is_where_somebody_left_off(monkeypatch):
    asked = []

    async def get(path, **params):
        asked.append(path)
        if path == "/video/movies/1":
            return {"id": 1, "title": "Tito i ja", "year": 1992}
        if path.startswith("/video/movies/"):
            raise library.NotInLibrary(path)
        ids = [int(i) for i in params.get("ids", "").split(",") if i]
        if path == "/video/episodes":
            return [EPISODES[i] for i in ids if i in EPISODES]
        if path == "/music/tracks":
            return [TRACKS[i] for i in ids]
        return SERIES[int(path.rsplit("/", 1)[1])]

    monkeypatch.setattr(library, "get", get)
    resume = [
        Progress(kind="movie", item_id=1, position_s=100.0),
        Progress(kind="movie", item_id=2, position_s=50.0, finished_at=DONE),
        Progress(kind="movie", item_id=3, position_s=10.0),
        Progress(kind="episode", item_id=10, position_s=60.0, duration_s=2700.0),
        Progress(kind="episode", item_id=11, position_s=60.0),
        Progress(kind="episode", item_id=20, position_s=2600.0, finished_at=DONE),
        Progress(kind="track", item_id=5, position_s=20.0),
        Progress(kind="track", item_id=6, position_s=20.0),
        Progress(kind="track", item_id=8, position_s=20.0),
        Progress(kind="episode", item_id=30, position_s=2600.0, finished_at=DONE),
        Progress(kind="episode", item_id=22, position_s=30.0, duration_s=2500.0),
    ]

    row = run(home._continue_row(resume, {21}, "hr"))

    assert [(c["kind"], c["id"], c["position_s"], c["duration_s"]) for c in row] == [
        ("movie", 1, 100.0, None),
        ("episode", 10, 60.0, 2700.0),
        # the episode after the one finished, past the one already seen, where
        # it was left
        ("episode", 22, 30.0, 2500.0),
        ("track", 5, 20.0, 200.0),
    ]
    assert "/video/movies/2" not in asked
    assert asked.count("/video/series/200") == 1


class _Empty(list):
    def scalars(self):
        return iter(())


class _NoRecords:
    async def execute(self, statement):
        return _Empty()


def test_the_most_heard_row_asks_only_for_its_artists(monkeypatch):
    asked = []

    async def get(path, **params):
        asked.append((path, params))
        if path == "/music/artists":
            return [{"id": 3, "name": "Azra"}, {"id": 1, "name": "Haustor"}]
        return []

    async def who(request, session):
        return SimpleNamespace(id=1)

    async def counted(session, who, limit):
        return [3, 1]

    monkeypatch.setattr(library, "get", get)
    monkeypatch.setattr(home, "picked", who)
    monkeypatch.setattr(home, "heard_most", counted)
    monkeypatch.setattr(home, "artist_card", lambda a: a["name"])

    rows = run(home.section_rows("music", None, session=_NoRecords()))["rows"]

    assert {"key": "most_heard", "cards": ["Azra", "Haustor"]} in rows
    assert ("/music/artists", {"ids": "3,1"}) in asked
