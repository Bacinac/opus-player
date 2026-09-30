"""The response shapes the released Android Music app actually reads.

``check.sh`` already makes sure an Android literal has a matching route.  That
does not catch a route that still answers but no longer has a field read by an
APK already installed in a car.  These are deliberately ASGI requests through
the paired-car bearer, rather than calls to router functions, so middleware,
routing and the Player's translations are part of the compatibility check.
"""

import httpx

from conftest import PEOPLE, run
from opus import auth, library
from opus.main import app


def get(path: str) -> httpx.Response:
    async def ask():
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://player") as client:
            return await client.get(path, headers={"authorization": "Bearer paired-car"})

    return run(ask())


def test_released_music_app_can_browse_the_player_contract(house, monkeypatch):
    """Music 0.1.443: artists → records → tracks, and voice search.

    The production app uses ``JSONObject.get*`` for the asserted fields.  A
    missing one is therefore a compatibility break, even though Python and the
    HTTP route would otherwise both still be healthy.
    """
    async def car_session(bearer):
        return ("filip", PEOPLE["filip"].version) if bearer == "paired-car" else None

    async def asked(path, **params):
        if path == "/music/artists":
            return [{"id": 7, "name": "Haustor", "image_url": "https://cover/artist.jpg", "held": 1}]
        if path == "/music/artists/7":
            return {"id": 7, "name": "Haustor", "releases": [{
                "id": 11, "title": "Treći svijet", "record_title": None,
                "release_date": "1984-01-01", "cover_url": "https://cover/release.jpg",
                "files_linked": 6, "stands": True,
            }]}
        if path == "/music/releases/11/playback":
            assert params == {"prefer": "stereo"}
            return {"tracks": [{
                "id": 42, "title": "Radnička klasa odlazi u raj", "artist": "Haustor",
                "album": "Treći svijet", "position": 1, "duration_s": 267,
                "codec": "flac", "cover_url": "https://cover/release.jpg",
            }]}
        if path == "/music/search/library":
            assert params == {"q": "radnička"}
            return [{
                "id": 42, "title": "Radnička klasa odlazi u raj", "artist": "Haustor",
                "album": "Treći svijet", "position": 1, "duration_s": 267,
                "codec": "flac", "cover_url": "https://cover/release.jpg",
            }]
        raise AssertionError(f"unexpected Library request: {path} {params}")

    monkeypatch.setattr(auth, "car_session", car_session)
    monkeypatch.setattr(library, "get", asked)

    artists = get("/api/library/music?order=title")
    assert artists.status_code == 200
    assert artists.json() == [{
        "kind": "artist", "id": 7, "title": "Haustor", "image": "https://cover/artist.jpg",
        "held": 1,
        "subtitle": None, "year": None, "backdrop": None, "state": None,
        "person": True, "overview": "", "end_year": None, "country": None, "country_hr": None,
        "releases": None, "round": True,
    }]

    records = get("/api/library/artist/7")
    assert records.status_code == 200
    assert records.json()["releases"] == [{
        "id": 11, "title": "Treći svijet", "year": "1984",
        "cover": "https://cover/release.jpg", "tracks": 6,
    }]

    tracks = get("/api/library/release/11")
    assert tracks.status_code == 200
    assert tracks.json()["tracks"] == [{
        "id": 42, "title": "Radnička klasa odlazi u raj", "artist": "Haustor",
        "album": "Treći svijet", "position": 1, "duration_s": 267,
        "codec": "flac", "cover_url": "https://cover/release.jpg",
    }]

    search = get("/api/library/search?q=radni%C4%8Dka")
    assert search.status_code == 200
    assert search.json()[0]["id"] == 42
    assert {"title", "artist", "album", "codec"}.issubset(search.json()[0])
