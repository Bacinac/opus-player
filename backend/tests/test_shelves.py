from types import SimpleNamespace

from conftest import run
from opus import auth, library, stations
from opus.api.routers import home

ANSWERS = {
    "/video/movies": [{"status": "complete", "runtime_min": 100, "year": 1971},
                      {"status": "waiting_subtitles", "runtime_min": 80, "year": 1980},
                      {"status": "wanted", "runtime_min": 600, "year": 2020}],
    "/video/series": [{"episodes_have": 10, "minutes_have": 300, "year": 1975},
                      {"episodes_have": 4, "minutes_have": 150, "year": 1989},
                      {"episodes_have": 0, "minutes_have": 0, "year": 2024}],
    "/music/library/stats": {"artists": 3, "albums": 12, "hours": 41, "span": [1979, 1990]},
    "/photos/timeline/buckets": {"total": 0, "months": []},
    "/photos/people": [],
    "/photos/places": [],
}


def test_every_shelf_that_can_be_watched_or_heard_says_how_long(monkeypatch):
    async def get(path, **params):
        return ANSWERS[path]

    async def nobody(request):
        return None

    async def listed():
        return []

    async def people():
        return {}

    monkeypatch.setattr(library, "get", get)
    monkeypatch.setattr(auth, "asking_for", nobody)
    monkeypatch.setattr(auth.authority, "people", people)
    monkeypatch.setattr(stations, "listed", listed)

    counted = run(home.shelves(SimpleNamespace()))

    assert counted["movies"]["hours"] == 3
    assert (counted["series"]["episodes"], counted["series"]["hours"]) == (14, 8)
    assert (counted["music"]["releases"], counted["music"]["hours"]) == (12, 41)
