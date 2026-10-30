import httpx
import pytest
from fastapi import HTTPException

from conftest import run
from opus.api.routers import pictures, play, radio


def _library(monkeypatch, answer):
    seen = []

    def upstream(asked: httpx.Request):
        seen.append(asked)
        return answer(asked)

    client = httpx.AsyncClient(base_url="http://library/api", transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(pictures.library, "client", lambda timeout=30: client)
    return seen


async def _drained(response) -> bytes:
    return b"".join([chunk async for chunk in response.body_iterator])


def test_a_picture_comes_through_at_the_size_asked_with_the_library_s_keeping(monkeypatch):
    seen = _library(monkeypatch, lambda asked: httpx.Response(
        200, content=b"jpeg", headers={"content-type": "image/jpeg", "cache-control": "public, max-age=604800",
                                       "etag": '"a1"', "set-cookie": "nope=1"}))

    async def scenario():
        response = await pictures.picture(42, w=640)
        assert await _drained(response) == b"jpeg"
        return response

    response = run(scenario())
    assert str(seen[0].url) == "http://library/api/pictures/42?w=640"
    assert response.media_type == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=604800"
    assert response.headers["etag"] == '"a1"'
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize(("library_said", "said"), [(404, 404), (503, 503), (401, 502), (403, 502)])
def test_a_refusal_is_said_as_the_library_said_it_unless_it_refused_this_module(monkeypatch, library_said, said):
    _library(monkeypatch, lambda asked: httpx.Response(library_said, json={"detail": "not taken yet"}))
    with pytest.raises(HTTPException) as refused:
        run(pictures.picture(42, w=320))
    assert refused.value.status_code == said


def test_a_map_tile_is_the_library_s(monkeypatch):
    seen = _library(monkeypatch, lambda asked: httpx.Response(200, content=b"png", headers={"content-type": "image/png"}))

    async def scenario():
        return await _drained(await pictures.tile(12, 2200, 1400))

    assert run(scenario()) == b"png"
    assert seen[0].url.path == "/api/tiles/12/2200/1400.png"


@pytest.mark.parametrize(("address", "named"), [
    ("http://192.168.1.102:8098/api/pictures/7?w=640", "/api/pictures/7"),
    ("/api/pictures/7", "/api/pictures/7"),
    ("https://image.tmdb.org/t/p/w342/a.jpg", None),
    ("http://x/api/pictures/7/../../tv", None),
    (None, None),
])
def test_a_device_hands_back_the_picture_it_was_given(address, named):
    assert pictures.named_by(address) == named


class Config:
    def __init__(self, **values):
        self.values = values

    def get(self, key):
        return self.values.get(key, "")


def test_the_house_is_handed_whole_addresses(monkeypatch):
    async def runtime():
        return Config(stream_base="http://media:8098")

    async def by_id(station_id):
        return {"id": 3, "name": "Yammat FM", "genre": "Rock", "country": "HR",
                "url": "https://stream.yammat.fm/radio/8000/yammat.mp3", "logo": "/api/pictures/9"}

    monkeypatch.setattr(play, "current_runtime", runtime)
    monkeypatch.setattr(play.stations, "by_id", by_id)
    queued = run(play.queue("station", 3))
    assert queued["tracks"][0]["art"] == "http://media:8098/api/pictures/9?w=640"
    assert play.picture_url(Config(stream_base="http://media:8098"), None) == ""


def test_a_station_the_library_does_not_list_is_not_relayed(monkeypatch):
    async def by_address(url):
        return None

    monkeypatch.setattr(radio.stations, "by_address", by_address)
    with pytest.raises(HTTPException) as refused:
        run(radio.stream("http://192.168.1.12:8123/api/services/lock/open"))
    assert refused.value.status_code == 400
