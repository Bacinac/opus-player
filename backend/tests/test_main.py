import json
from compression import zstd

import httpx
import opus_auth
import pytest
from fastapi.responses import JSONResponse, StreamingResponse

from conftest import HOUSE_TOKEN, PEOPLE, person_cookie, run
from opus import auth, library, main
from opus.api.routers import photos, system
from opus.config import settings

HEADERS = {"x-content-type-options": "nosniff", "referrer-policy": "same-origin",
           "content-security-policy": "frame-ancestors 'self'"}
CROSS_SITE = {"sec-fetch-site": "cross-site"}
SAME_SITE = {"sec-fetch-site": "same-site"}
SAME_ORIGIN = {"sec-fetch-site": "same-origin"}
FOREIGN_ORIGIN = {"origin": "https://elsewhere.example"}


@pytest.fixture
def client(house, monkeypatch):
    async def verify(username, password, address):
        return PEOPLE.get(username) if password == "right" else None

    async def ask(path, body):
        return {"code": "ABCD-EFGH", "id": 4, "claim": "claim", "minutes": 15}

    monkeypatch.setattr(auth.authority, "verify", verify, raising=False)
    monkeypatch.setattr(library, "post", ask)
    monkeypatch.setattr(system, "_asked", {})
    return Client(main.app)


class Client:
    def __init__(self, app):
        self.app = app
        self.cookies: dict[str, str] = {}

    def request(self, method: str, path: str, headers: dict | None = None, json=None) -> httpx.Response:
        sent = dict(headers or {})
        if self.cookies:
            sent["cookie"] = "; ".join(f"{name}={value}" for name, value in self.cookies.items())

        async def ask():
            transport = httpx.ASGITransport(app=self.app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://player") as http:
                return await http.request(method, path, headers=sent, json=json)

        return run(ask())

    def get(self, path: str, **given) -> httpx.Response:
        return self.request("GET", path, **given)

    def post(self, path: str, **given) -> httpx.Response:
        return self.request("POST", path, **given)


def secured(response) -> bool:
    return all(response.headers.get(name) == value for name, value in HEADERS.items())


@pytest.mark.parametrize("headers", [CROSS_SITE, SAME_SITE, FOREIGN_ORIGIN])
@pytest.mark.parametrize("cookies", [
    {},
    {"opus_session": "anything"},
    {auth.SESSION_COOKIE: "anything"},
    {auth.DEVICE_COOKIE: "anything"},
    {auth.PAIRING_COOKIE: "anything"},
])
@pytest.mark.parametrize(("path", "body"), [
    ("/api/auth/logout", None),
    ("/api/auth/login", {"username": "filip", "password": "right"}),
    ("/api/auth/pair", None),
    ("/api/auth/passkey/login", {"credential": {}}),
])
def test_an_unsafe_request_from_another_site_is_refused(client, headers, cookies, path, body):
    client.cookies.update(cookies)
    response = client.post(path, json=body, headers=headers)
    assert response.status_code == 403
    assert "set-cookie" not in response.headers
    assert secured(response)


@pytest.mark.parametrize("headers", [SAME_ORIGIN, {"origin": "http://player"}, {}])
def test_an_unsafe_request_from_this_module_or_no_browser_is_heard(client, headers):
    client.cookies.update({"opus_session": person_cookie("filip"), auth.PAIRING_COOKIE: "claim"})
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    login = client.post("/api/auth/login", json={"username": "filip", "password": "right"}, headers=headers)
    assert login.status_code == 200 and "opus_session=" in login.headers["set-cookie"]
    assert client.post("/api/auth/pair", headers=headers).status_code == 200


SIGNED = {"id": "a2V5", "rawId": "a2V5", "type": "public-key", "response": {}}
HERE = {"x-forwarded-host": "opus.example.com"}


@pytest.fixture
def passkeys(client, monkeypatch):
    monkeypatch.setattr(settings, "cookie_domain", "example.com")
    asked = []

    async def options():
        return {"challenge": "c2lnbg", "rpId": "example.com"}

    async def passkey(credential, origin, address):
        asked.append(origin)
        return PEOPLE["filip"] if credential == SIGNED else None

    monkeypatch.setattr(auth.authority, "passkey_options", options, raising=False)
    monkeypatch.setattr(auth.authority, "passkey", passkey, raising=False)
    return asked


def test_a_passkey_makes_the_person_it_belongs_to_on_this_door(client, passkeys):
    assert client.post("/api/auth/passkey/options", headers=HERE).json()["rpId"] == "example.com"
    entered = client.post("/api/auth/passkey/login", json={"credential": SIGNED}, headers=HERE)
    assert entered.status_code == 200 and "opus_session=" in entered.headers["set-cookie"]
    assert entered.json()["person"] == "filip"
    refused = client.post("/api/auth/passkey/login", json={"credential": {}}, headers=HERE)
    assert refused.status_code == 401 and "set-cookie" not in refused.headers
    assert passkeys == ["https://opus.example.com"] * 2


def test_a_box_or_a_door_off_the_domain_takes_no_passkey(client, passkeys):
    lan = {"x-forwarded-host": "192.168.1.102:5290"}
    box = client.post("/api/auth/passkey/login", json={"credential": SIGNED, "surface": "tv"},
                      headers=HERE)
    assert box.status_code == 409
    assert client.post("/api/auth/passkey/options", headers=lan).status_code == 404
    assert client.post("/api/auth/passkey/login", json={"credential": SIGNED},
                       headers=lan).status_code == 404
    assert client.get("/api/auth/session", headers=HERE).json()["passkey"] is True
    assert client.get("/api/auth/session?surface=tv", headers=HERE).json()["passkey"] is False
    assert client.get("/api/auth/session", headers=lan).json()["passkey"] is False
    assert passkeys == []


def test_a_token_or_a_car_is_not_asked_where_it_came_from(client, monkeypatch):
    async def car(bearer):
        return ("filip", PEOPLE["filip"].version) if bearer == "car" else None

    monkeypatch.setattr(auth, "car_session", car)
    assert client.post("/api/auth/logout", headers={**CROSS_SITE, "X-OPUS-Token": HOUSE_TOKEN}).status_code == 200
    assert client.post("/api/auth/logout", headers={**CROSS_SITE, "Authorization": "Bearer car"}).status_code == 200
    assert client.post("/api/auth/logout", headers={**CROSS_SITE, "X-OPUS-Token": "wrong"}).status_code == 403


def test_a_read_from_another_site_is_not_refused_at_the_door(client):
    assert client.get("/api/ping", headers=CROSS_SITE).status_code == 200


def test_ready_needs_a_database_answer_but_reveals_nothing_else():
    class Session:
        async def execute(self, statement):
            assert str(statement) == "SELECT 1"

    assert run(system.ready(Session())) == {"ok": True}


def test_every_answer_carries_the_security_headers(client):
    assert secured(client.get("/api/ping"))
    refused = client.get("/api/home")
    assert refused.status_code == 401 and secured(refused)
    client.cookies.update({"opus_session": person_cookie("filip")})
    forbidden = client.get("/api/settings")
    assert forbidden.status_code == 403 and secured(forbidden)


def test_a_json_answer_leaves_the_door_compressed(client):
    client.cookies.update({"opus_session": person_cookie("boss")})
    answer = client.get("/api/settings", headers={"accept-encoding": "zstd"})
    assert answer.headers["content-encoding"] == "zstd"
    assert json.loads(zstd.decompress(answer.content))


def test_the_headers_reach_streams_failures_and_leave_a_routes_own_policy():
    app = main._Player()

    @app.get("/stream")
    async def stream():
        async def body():
            yield b"one"
            yield b"two"

        return StreamingResponse(body(), media_type="video/mp4")

    @app.get("/own")
    async def own():
        return JSONResponse({}, headers={"Content-Security-Policy": "default-src 'none'"})

    @app.get("/broken")
    async def broken():
        raise RuntimeError("broken")

    client = Client(app)
    streamed = client.get("/stream")
    assert streamed.content == b"onetwo" and secured(streamed)
    failed = client.get("/broken")
    assert failed.status_code == 500 and secured(failed)
    kept = client.get("/own")
    assert kept.headers.get_list("content-security-policy") == ["default-src 'none'"]
    assert kept.headers["x-content-type-options"] == "nosniff"


def test_the_api_does_not_describe_itself(client):
    client.cookies.update({"opus_session": person_cookie("boss")})
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


def test_a_gift_reaches_the_library_with_the_size_it_was_announced_at(house, monkeypatch):
    seen = []

    async def library_side(request):
        seen.append((request.headers.get("content-length"), request.headers.get("transfer-encoding"),
                     await request.aread()))
        return httpx.Response(413, json={"detail": "a file this large is not taken"})

    upstream = httpx.AsyncClient(transport=httpx.MockTransport(library_side), base_url="http://library/api")
    monkeypatch.setattr(photos, "_personal", lambda: upstream)

    async def give():
        transport = httpx.ASGITransport(app=main.app)
        cookie = f"{opus_auth.SESSION_COOKIE}={person_cookie('filip')}"
        async with httpx.AsyncClient(transport=transport, base_url="http://player") as http:
            return await http.post("/api/photos/offer", params={"name": "big.mov"}, content=b"x" * 10,
                                   headers={**SAME_ORIGIN, "cookie": cookie})

    answer = run(give())
    assert answer.status_code == 413
    assert seen == [("10", None, b"x" * 10)]
