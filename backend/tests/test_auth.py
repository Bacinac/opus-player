import re
import time
from types import SimpleNamespace

import httpx
import opus_auth
import pytest
from starlette.responses import Response

from conftest import BOX_TOKEN, HOUSE_TOKEN, OTHER_BOX, person_cookie, request, run
from opus import auth
from opus.api.routers import system, users
from opus.config import settings

TOKEN = HOUSE_TOKEN


def allowed(path, **given):
    return run(auth.allowed(path, **given))


@pytest.mark.parametrize(("path", "given", "expected"), [
    ("/api/ping", {}, True),
    ("/api/ready", {}, True),
    ("/api/art", {}, True),
    ("/api/auth/pair/12", {}, True),
    ("/api/app/opus.apk", {}, True),
    ("/api/app/opus-tv.apk", {}, True),
    ("/api/apps", {}, False),
    ("/api/home", {}, False),
    ("/api/home", {"person_cookie": "garbage"}, False),
    ("/api/home", {"person_cookie": person_cookie("filip", 2)}, False),
    ("/api/home", {"person_cookie": person_cookie("filip")}, True),
    ("/api/home", {"box": BOX_TOKEN}, True),
    ("/api/home", {"box": OTHER_BOX}, False),
    ("/api/home", {"token": TOKEN}, False),
    ("/api/home", {"token": "not-the-token"}, False),
    ("/api/home", {"token": settings.library_token}, False),
    ("/api/library/music", {"token": TOKEN}, True),
    ("/api/play/queue", {"token": TOKEN}, True),
    ("/api/radio/stations", {"token": TOKEN}, True),
    ("/api/tv/now", {"token": TOKEN}, True),
    ("/api/dac/now", {"token": TOKEN}, True),
    ("/api/auth/token", {"token": TOKEN}, False),
    ("/api/auth/token", {"person_cookie": person_cookie("filip")}, False),
    ("/api/auth/token", {"person_cookie": person_cookie("boss")}, True),
    ("/api/settings", {"person_cookie": person_cookie("boss")}, True),
    ("/api/settings", {"person_cookie": person_cookie("filip")}, False),
    ("/api/settings", {"box": BOX_TOKEN}, False),
    ("/api/settings", {"token": TOKEN}, False),
    ("/api/storage", {"person_cookie": person_cookie("gost")}, False),
    ("/api/photos/people", {"person_cookie": person_cookie("filip")}, True),
    ("/api/photos/people", {"person_cookie": person_cookie("gost")}, False),
    ("/api/photos/people", {"person_cookie": person_cookie("gost"), "box": BOX_TOKEN}, False),
    ("/api/photos/people", {"box": BOX_TOKEN}, True),
    ("/api/photos/people", {"token": TOKEN}, False),
    ("/api/launcher/cameras", {"person_cookie": person_cookie("gost")}, False),
    ("/api/launcher/cameras/baba:door/snapshot", {"person_cookie": person_cookie("gost")}, False),
    ("/api/launcher/cameras/baba:door/mp4", {"person_cookie": person_cookie("gost"), "box": BOX_TOKEN}, False),
    ("/api/launcher/cameras/baba:door/mjpeg", {"person_cookie": person_cookie("filip")}, True),
    ("/api/launcher/cameras/order", {"person_cookie": person_cookie("boss")}, True),
    ("/api/launcher/cameras", {"box": BOX_TOKEN}, True),
    ("/api/launcher/cameras", {"token": TOKEN}, False),
    ("/api/game/scores", {"person_cookie": person_cookie("gost")}, False),
    ("/api/tv/photo", {"person_cookie": person_cookie("gost")}, False),
    ("/api/tv/photo", {"person_cookie": person_cookie("filip")}, True),
    ("/api/tv/photo", {"token": TOKEN}, False),
    ("/api/tv/show", {"token": TOKEN}, True),
    ("/api/tv/show", {"person_cookie": person_cookie("gost")}, False),
    ("/api/tv/show", {"person_cookie": person_cookie("filip")}, True),
    ("/api/photos/years", {"token": TOKEN}, False),
    ("/api/photos/wall", {"token": TOKEN}, True),
    ("/api/photos/wall", {"person_cookie": person_cookie("gost")}, False),
    ("/api/photos/wall/more", {"token": TOKEN}, False),
    (f"/api/photos/{'a' * 40}/preview", {"token": TOKEN}, True),
    (f"/api/photos/{'a' * 40}/tile", {"token": TOKEN}, False),
    (f"/api/photos/{'a' * 40}", {"token": TOKEN}, False),
    (f"/api/photos/{'a' * 40}/play", {"token": TOKEN}, False),
    ("/api/photos/people/1/morph", {"token": TOKEN}, False),
    ("/api/explore/want/music", {"person_cookie": person_cookie("gost")}, False),
    ("/api/explore/wanted", {"person_cookie": person_cookie("gost")}, True),
    ("/api/music", {"person_cookie": person_cookie("gost")}, True),
    ("/api/version", {}, False),
    ("/api/version", {"person_cookie": person_cookie("gost")}, True),
    ("/api/version", {"box": BOX_TOKEN}, True),
])
def test_allowed(house, path, given, expected):
    assert allowed(path, **given) is expected


def test_a_ticket_opens_only_the_bytes_it_was_signed_for(house):
    ticket = auth.play_ticket("/api/play/movie/5/")
    assert allowed("/api/play/movie/5/stream", ticket=ticket)
    assert allowed("/api/play/movie/5/subs/3.vtt", ticket=ticket)
    assert not allowed("/api/play/movie/5/plan", ticket=ticket)
    assert not allowed("/api/play/movie/5/ticket", ticket=ticket)
    assert not allowed("/api/play/movie/6/stream", ticket=ticket)
    assert not allowed("/api/home", ticket=ticket)


def test_valid_ticket(monkeypatch):
    ticket = auth.play_ticket("/api/play/track/9/")
    expires, _, mac = ticket.partition(".")
    assert re.fullmatch(r"\d+\.[0-9a-f]{64}", ticket)
    assert auth.valid_ticket("/api/play/track/9/stream", ticket)
    assert not auth.valid_ticket("/api/play/track/9/stream", f"{expires}.{mac[:-1]}{'1' if mac[-1] == '0' else '0'}")
    assert not auth.valid_ticket("/api/play/track/9/stream", mac)
    assert not auth.valid_ticket("/api/play/track/9/stream", f"²{expires[1:]}.{mac}")
    assert not auth.valid_ticket("/api/play/track/9/stream", f"{int(expires) + 3600}.{mac}")
    assert not auth.valid_ticket("/api/play/track/x/stream", ticket)
    assert not auth.valid_ticket("/api/play/track/9/lyrics", ticket)
    assert not auth.valid_ticket("/api/play/track/19/stream", ticket)
    assert not auth.valid_ticket("/api/play/movie/9/stream", ticket)
    monkeypatch.setattr(opus_auth, "time", SimpleNamespace(time=lambda: int(expires) + 1))
    assert not auth.valid_ticket("/api/play/track/9/stream", ticket)


def test_a_ticket_is_signed_for_tickets_alone(house):
    for other in (opus_auth.seal(auth._key(auth.PROFILE_PURPOSE), 3600),
                  opus_auth.seal(auth._key(auth.CAR_PURPOSE), 3600),
                  opus_auth.seal(opus_auth.signing_key(settings.session_key), 3600),
                  opus_auth.seal(auth._key(auth.TICKET_PURPOSE), 3600),
                  auth.issue("filip")):
        assert not auth.valid_ticket("/api/play/movie/5/stream", other)
        assert not allowed("/api/play/movie/5/stream", ticket=other)


CREDENTIALS = {
    "nothing": {},
    "marker only": {"marker": "filip"},
    "stale person": {"person": person_cookie("filip", 2), "marker": "filip"},
    "person": {"person": person_cookie("filip"), "marker": "filip"},
    "guest": {"person": person_cookie("gost"), "marker": "filip"},
    "box": {"box": BOX_TOKEN, "marker": "filip"},
    "taken-back box": {"box": OTHER_BOX, "marker": "filip"},
    "token": {"token": TOKEN},
}


def _session(credentials: dict, surface: str = ""):
    cookies = {}
    if "person" in credentials:
        cookies["opus_session"] = credentials["person"]
    if "marker" in credentials:
        cookies[auth.SESSION_COOKIE] = auth.issue(credentials["marker"])
    if "box" in credentials:
        cookies[auth.DEVICE_COOKIE] = credentials["box"]
    headers = {"X-OPUS-Token": credentials["token"]} if "token" in credentials else {}
    response = Response()
    said = run(system.auth_session(request(cookies, headers), response, surface=surface, session=None))
    return said, response


@pytest.fixture
def profiles(monkeypatch):
    async def rows(session):
        return {"filip": users.User(id=1, person="filip", name="", colour="#4a90d9", shelf_orders="{}")}

    monkeypatch.setattr(users, "_rows", rows)


@pytest.mark.parametrize("name", list(CREDENTIALS))
def test_the_session_says_what_the_guard_opens(house, profiles, name):
    credentials = CREDENTIALS[name]
    said, response = _session(credentials)
    opens = allowed("/api/library/music", person_cookie=credentials.get("person"), box=credentials.get("box"),
                    token=credentials.get("token"))
    assert said["authenticated"] is opens
    cleared = any(value.startswith(f"{auth.SESSION_COOKIE}=") for value in response.headers.getlist("set-cookie"))
    assert cleared is (not opens and "marker" in credentials)


def test_a_television_is_answered_as_its_box_and_keeps_the_shared_cookie(house, profiles):
    said, response = _session({"person": person_cookie("filip"), "marker": "filip"}, surface="tv")
    assert not said["authenticated"]
    assert not any(value.startswith("opus_session=") for value in response.headers.getlist("set-cookie"))
    said, response = _session({"person": person_cookie("filip"), "box": BOX_TOKEN, "marker": "filip"}, surface="tv")
    assert said["authenticated"] and said["person"] == "" and said["role"] == "" and said["box"] == "Dnevni boravak"
    assert said["profile"]["key"] == "filip"
    assert response.headers.getlist("set-cookie") == []


def test_a_guest_is_not_somebody_elses_profile(house, profiles):
    said, _ = _session({"person": person_cookie("gost"), "marker": "filip"})
    assert said["authenticated"] and said["role"] == "guest" and said["profile"] is None


class Verifier:
    def __init__(self):
        self.asked = 0
        self.answer = lambda: httpx.Response(200, json={"ok": True, "id": 3, "name": "Terasa"})

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked += 1
        return self.answer()


@pytest.fixture
def verifier(monkeypatch):
    kept = Verifier()
    real = httpx.AsyncClient
    monkeypatch.setattr(auth.httpx, "AsyncClient",
                        lambda **kw: real(transport=httpx.MockTransport(kept), **kw))
    monkeypatch.setattr(auth, "_devices", type(auth._devices)())
    clock = {"now": 1000.0}
    monkeypatch.setattr(auth, "time", SimpleNamespace(time=time.time, monotonic=lambda: clock["now"]))
    return kept, clock


def test_a_box_is_asked_about_once_a_minute(verifier):
    kept, clock = verifier
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    assert kept.asked == 1
    clock["now"] += auth.DEVICE_TTL + 1
    kept.answer = lambda: httpx.Response(200, json={"ok": False})
    assert run(auth.device(BOX_TOKEN)) is None
    assert run(auth.device(BOX_TOKEN)) is None
    assert kept.asked == 2


def test_an_outage_keeps_the_last_answer_and_is_not_asked_every_request(verifier):
    kept, clock = verifier
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    clock["now"] += auth.DEVICE_TTL + 1

    def down():
        raise httpx.ConnectError("down")

    kept.answer = down
    for _ in range(5):
        assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    assert kept.asked == 2
    clock["now"] += auth.DEVICE_RETRY + 1
    assert run(auth.device(OTHER_BOX)) is None
    assert run(auth.device(OTHER_BOX)) is None
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    assert kept.asked == 4


def test_a_box_expires_after_a_bounded_authority_outage(verifier):
    kept, clock = verifier
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    clock["now"] += auth.DEVICE_TTL + 1
    kept.answer = lambda: (_ for _ in ()).throw(httpx.ConnectError("down"))
    assert run(auth.device(BOX_TOKEN)) == auth.Box(3, "Terasa")
    clock["now"] += auth.DEVICE_MAX_STALE
    assert run(auth.device(BOX_TOKEN)) is None


def test_a_token_that_is_not_the_shape_of_one_is_not_asked_about(verifier):
    kept, _ = verifier
    assert run(auth.device("short")) is None
    assert run(auth.device("x" * 42 + "/")) is None
    assert kept.asked == 0
