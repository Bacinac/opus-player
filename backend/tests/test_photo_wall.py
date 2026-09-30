from conftest import run
from opus import library
from opus.api.routers import photos


def shot(n, kind="photo", ready=True, undecodable=False):
    return {"id": f"{n:040x}", "kind": kind, "taken_at": f"20{n:02d}-06-01T12:00:00",
            "ready": ready, "undecodable": undecodable}


def told(path):
    checksum = path.rsplit("/", 1)[1]
    return {**shot(int(checksum, 16)), "place": "Rovinj", "country": "Hrvatska",
            "files": [{"path": "/archive/" + checksum}]}


def test_the_wall_is_the_households_stills_and_nothing_narrower(monkeypatch):
    asked = {}

    async def years(path, **params):
        if path != "/photos/years":
            return told(path)
        asked.update(path=path, **params)
        return {"years": [
            {"year": 2024, "photographs": [shot(1), shot(2, kind="video"), shot(3, ready=False)]},
            {"year": 2019, "photographs": [shot(4, undecodable=True), shot(5)]},
        ]}

    monkeypatch.setattr(library, "get", years)
    shown = run(photos.wall(count=30))["photos"]
    assert asked == {"path": "/photos/years", "each": photos.WALL_EACH, "household": "true"}
    assert sorted(p["id"] for p in shown) == [shot(1)["id"], shot(5)["id"]]
    assert shown[0]["place"] == "Rovinj" and shown[0]["country"] == "Hrvatska"
    assert set(shown[0]) == {"id", "taken_at", "place", "country"}


def test_the_wall_hands_over_no_more_than_it_was_asked_for(monkeypatch):
    async def years(path, **params):
        if path != "/photos/years":
            return told(path)
        return {"years": [{"year": 2020, "photographs": [shot(n) for n in range(1, 11)]}]}

    monkeypatch.setattr(library, "get", years)
    assert len(run(photos.wall(count=3))["photos"]) == 3
