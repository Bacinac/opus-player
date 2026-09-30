from urllib.parse import unquote

import pytest

from conftest import run
from opus import auth, library
from opus.api.routers import photos
from opus.main import app

CHECKSUM = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def asked(monkeypatch):
    paths: list[str] = []

    async def allowed(path, **given):
        return True

    async def get(path, **params):
        paths.append(path)
        if path.endswith("/playback"):
            return {"path": "/photos/clip.mp4", "container": "mp4", "video_codec": "h264", "streams": []}
        return {}

    async def stream(path, *args, **kwargs):
        paths.append(path)
        return {}

    monkeypatch.setattr(auth, "allowed", allowed)
    monkeypatch.setattr(library, "get", get)
    monkeypatch.setattr(photos, "_stream", stream)
    return paths


def status(raw_path: str) -> int:
    """What the app answers a path exactly as a server hands it over: decoded,
    and with nothing resolved on the way."""
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    run(app({"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET",
             "scheme": "http", "path": unquote(raw_path), "raw_path": raw_path.encode(),
             "root_path": "", "query_string": b"", "headers": [(b"host", b"player")],
             "client": ("10.0.0.5", 50000), "server": ("player", 8098)}, receive, send))
    return next(m["status"] for m in sent if m["type"] == "http.response.start")


@pytest.mark.parametrize("path", [
    "/api/explore/music/album/123456",
    "/api/explore/music/playlist/36ea71a8-445e-41a4-82ab-6628c581535d",
    "/api/explore/music/mix/0063a6b1b8c55f0b0f7e8a26eb1e03",
    f"/api/photos/{CHECKSUM}",
    f"/api/photos/{CHECKSUM}/play",
    f"/api/photos/{CHECKSUM}/tile",
])
def test_a_parameter_of_the_right_shape_reaches_the_library(asked, path):
    assert status(path) == 200
    assert asked[-1].startswith(path.removeprefix("/api").replace("/explore/music/", "/music/discover/"))


@pytest.mark.parametrize("path", [
    "/api/explore/music/Album/1",
    "/api/explore/music/album/a_b",
    "/api/explore/music/album/%2E%2E",
    "/api/explore/music/playlist/..",
    "/api/explore/music/mix/..%3Fx=1",
    "/api/explore/music/mix/a%2Eb",
    "/api/photos/..",
    "/api/photos/%2E%2E/play",
    f"/api/photos/{CHECKSUM.upper()}",
    f"/api/photos/{CHECKSUM}%3Fperson=1/tile",
    f"/api/photos/{CHECKSUM[:-1]}/tile",
    f"/api/photos/{CHECKSUM}/original",
])
def test_anything_else_never_becomes_a_library_address(asked, path):
    assert status(path) == 404
    assert asked == []


def test_every_route_with_a_string_in_its_path_has_been_looked_at():
    reviewed = {
        "/api/explore/music/{kind}/{item_id}", "/api/photos/{checksum}", "/api/photos/{checksum}/play",
        "/api/photos/{checksum}/{size}", "/api/photos/vault{rest}", "/api/play/{kind}/{item_id}/plan",
        "/api/play/{kind}/{item_id}/ticket", "/api/play/{kind}/{item_id}/stream",
        "/api/play/{kind}/{item_id}/subs/{sub_id}.vtt", "/api/library/about/{kind}/{item_id}",
            "/api/library/{section}", "/api/rows/{section}", "/api/progress/watched/{kind}", "/api/progress/{kind}/{item_id}",
            "/api/users/{key}/pick", "/api/users/{key}", "/api/tv/items/{key}",
            "/api/launcher/cameras/{entity_id}/snapshot",
            "/api/launcher/cameras/{entity_id}/{kind}",
            "/api/history/{service}",
        }
    stringly = {path for path, operations in app.openapi()["paths"].items()
                for operation in operations.values()
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "path" and parameter["schema"].get("type") != "integer"}
    assert stringly == reviewed


def test_a_search_of_the_photographs_reaches_the_library_with_its_words(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def get(path, **params):
        calls.append((path, params))
        return {}

    monkeypatch.setattr(library, "get", get)
    run(photos.search(q="Ana na Hvaru"))
    run(photos.buckets(place="", whose=photos.Whose(), q="Ana na Hvaru"))
    run(photos.shelf(before="", before_id=None, place="", whose=photos.Whose(), month="",
                     q="Ana na Hvaru", limit=120))
    assert calls == [
        ("/photos/search", {"q": "Ana na Hvaru"}),
        ("/photos/timeline/buckets", {"q": "Ana na Hvaru"}),
        ("/photos/timeline", {"limit": 120, "q": "Ana na Hvaru"}),
    ]


def test_every_screen_passes_whose_photographs_on_in_the_library_words(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def get(path, **params):
        calls.append((path, params))
        return {}

    monkeypatch.setattr(library, "get", get)
    run(photos.buckets(place="", whose=photos.Whose(person=[7, 9]), q=""))
    run(photos.shelf(before="", before_id=None, place="", whose=photos.Whose(household=True),
                     month="", q="", limit=120))
    run(photos.on_this_day(month=None, day=None, span=None, least=12,
                           whose=photos.Whose(person=[7]), limit=400))
    run(photos.years(whose=photos.Whose(family=True), each=12))
    assert calls == [
        ("/photos/timeline/buckets", {"person": [7, 9]}),
        ("/photos/timeline", {"limit": 120, "household": "true"}),
        ("/photos/onthisday", {"limit": 400, "person": [7], "least": 12}),
        ("/photos/years", {"each": 12, "family": "true"}),
    ]


def test_a_screensaver_shows_whoever_the_profile_is_unless_it_chose_somebody(monkeypatch):
    async def get(path, **params):
        assert path == "/photos/people"
        return [{"id": 3, "account": None}, {"id": 5, "account": "nika"}]

    picked_now: dict = {"who": None}

    async def picked(request, session):
        return picked_now["who"]

    monkeypatch.setattr(library, "get", get)
    monkeypatch.setattr(photos, "picked", picked)

    def profile(person, screensaver=""):
        return type("Profile", (), {"person": person, "screensaver": screensaver})()

    answers = []
    for who in (None, profile("nika"), profile("kata"), profile(None),
                profile("nika", "3"), profile("nika", "3,5"), profile("nika", "household")):
        picked_now["who"] = who
        answers.append(run(photos.screensaver(None, None)))
    # a box with nobody picked, somebody with no face in the library and a
    # profile off the roster all get the household, as the living room always did
    assert answers == [{"household": True}, {"person": [5]}, {"household": True},
                       {"household": True}, {"person": [3]}, {"person": [3, 5]},
                       {"household": True}]
