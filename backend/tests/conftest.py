import asyncio
import os

os.environ.update({
    "OPUS_SESSION_KEY": "test-session-key-long-enough-to-sign-with",
    "OPUS_LIBRARY_URL": "http://library.invalid:8095",
    "OPUS_LIBRARY_TOKEN": "module-token",
    "OPUS_COOKIE_DOMAIN": "",
    "OPUS_DATABASE_URL": "postgresql+psycopg://nobody:nobody@database.invalid:5432/nothing",
})
os.environ.setdefault("OPUS_PLUGIN_ROOT", "/nonexistent")

import opus_auth
import pytest
from opus_auth.authority import Person
from opus_core.testing import Table
from starlette.requests import Request

from opus import auth, settings_store
from opus.config import settings

PEOPLE = {
    "filip": Person("filip", 3, "user", "Filip"),
    "boss": Person("boss", 1, "admin", "boss"),
    "gost": Person("gost", 2, "guest", "Gost"),
}
BOX_TOKEN = "b" * 43
OTHER_BOX = "c" * 43
HOUSE_TOKEN = "h" * 43
BOXES = {BOX_TOKEN: auth.Box(7, "Dnevni boravak")}


def run(coroutine):
    return asyncio.run(coroutine)


def person_cookie(name: str, version: int | None = None) -> str:
    return opus_auth.issue(settings.session_key, name, PEOPLE[name].version if version is None else version)


def request(cookies: dict[str, str] | None = None, headers: dict[str, str] | None = None,
            method: str = "GET", path: str = "/api/auth/session") -> Request:
    raw = [(name.lower().encode(), value.encode()) for name, value in (headers or {}).items()]
    if cookies:
        raw.append((b"cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()).encode()))
    return Request({"type": "http", "method": method, "path": path, "headers": raw,
                    "query_string": b"", "client": ("10.0.0.5", 50000),
                    "server": ("player", 8098), "scheme": "http"})


class Roster:
    async def people(self, force: bool = False):
        return PEOPLE

    async def current(self, name: str, version: int):
        found = PEOPLE.get(name)
        return found if found is not None and found.version == version else None


@pytest.fixture(autouse=True)
def settings_table(monkeypatch):
    table = Table()
    monkeypatch.setattr(settings_store.store, "sessions", table)
    settings_store.forget_runtime()
    yield table
    settings_store.forget_runtime()


@pytest.fixture
def house(monkeypatch, settings_table):
    monkeypatch.setattr(auth, "authority", Roster())

    async def device(token):
        return BOXES.get(token)

    monkeypatch.setattr(auth, "device", device)

    settings_table.rows[auth.token_key(auth.CONSUMER)] = HOUSE_TOKEN
