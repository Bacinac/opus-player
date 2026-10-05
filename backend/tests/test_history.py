"""What was heard and seen, told to where somebody keeps their history: the
listens and viewings as the services take them, the code Simkl links with, and
what becomes of a row the service would not take."""
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import HTTPException

from conftest import BOX_TOKEN, person_cookie, request, run
from opus import history
from opus.api.routers import history as routes, users
from opus.db import get_session
from opus.main import app
from opus.models import HistoryLink, HistorySend, User
from opus.settings_store import RuntimeConfig

AT = datetime(2026, 9, 24, 18, 30, tzinfo=UTC)
CONFIG = RuntimeConfig(values={"simkl_client_id": "cid"})


@pytest.mark.parametrize(("cookies", "profile", "expected"), [
    ({"opus_device": BOX_TOKEN}, "filip", False),
    ({"opus_session": person_cookie("filip")}, "filip", True),
    ({"opus_session": person_cookie("filip")}, "jana", False),
    ({"opus_session": person_cookie("gost")}, "gost", True),
    ({"opus_session": person_cookie("gost")}, "filip", False),
    ({"opus_session": person_cookie("boss")}, "filip", True),
    ({"opus_session": person_cookie("boss")}, None, True),
    ({}, "filip", False),
])
def test_history_management_requires_the_profile_person_or_an_admin(house, cookies, profile, expected):
    who = User(id=1, person=profile, name="Local")
    if expected:
        assert run(routes.require_history_profile(request(cookies), who)) is who
    else:
        with pytest.raises(HTTPException) as refused:
            run(routes.require_history_profile(request(cookies), who))
        assert refused.value.status_code == 403


@pytest.mark.parametrize("cookies", [
    {"opus_device": BOX_TOKEN}, {"opus_session": person_cookie("gost")},
    {"opus_session": person_cookie("filip")},
])
def test_unauthorized_history_routes_do_not_read_write_or_contact_a_provider(house, monkeypatch, cookies):
    who = User(id=1, person="jana", name="")

    class Session:
        async def execute(self, *args):
            pytest.fail("an unauthorized request reached history storage")

    async def provider(*args):
        pytest.fail("an unauthorized request reached the history provider")

    monkeypatch.setattr(app, "dependency_overrides", {
        users.require_picked: lambda: who, get_session: lambda: Session(),
    })
    for name in ("listenbrainz_account", "simkl_code", "simkl_grant"):
        monkeypatch.setattr(history, name, provider)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                    base_url="http://player", cookies=cookies) as client:
            for method, path, body in [
                ("GET", "/api/history", None),
                ("PUT", "/api/history/listenbrainz", {"token": "synthetic"}),
                ("POST", "/api/history/simkl/code", {}),
                ("POST", "/api/history/simkl/token", {"device_code": "synthetic"}),
                ("DELETE", "/api/history/listenbrainz", None),
                ("POST", "/api/history/retry", {}),
            ]:
                answer = await client.request(method, path, json=body)
                assert answer.status_code == 403, path

    run(scenario())


def row(kind: str, item_id: int) -> HistorySend:
    return HistorySend(user_id=1, service="x", kind=kind, item_id=item_id, at=AT)


@pytest.fixture
def web(monkeypatch):
    """The services, answered here: every request is kept, and answered by
    whatever the test put under its path."""
    asked: list[httpx.Request] = []
    answers: dict[str, httpx.Response] = {}

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(request)
        return answers[request.url.path]

    monkeypatch.setattr(history, "_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(answer)))
    return asked, answers


def test_a_listen_names_the_recording_by_its_musicbrainz_ids_where_the_file_had_them():
    tracks = {7: {"id": 7, "title": "Radio", "artist": "Haustor", "album": "Treći Svijet",
                  "duration_s": 220, "mbids": {"recording": "r-1", "release": "l-1", "artists": ["a-1"]}},
              8: {"id": 8, "title": "Take", "artist": "Haustor", "album": "Treći Svijet",
                  "duration_s": None, "mbids": {"recording": None, "release": None, "artists": []}}}
    gone = row("track", 9)
    made, unknown = history.listens([row("track", 7), row("track", 8), gone], tracks)
    assert unknown == [gone]
    assert made[0] == {"listened_at": int(AT.timestamp()), "track_metadata": {
        "artist_name": "Haustor", "track_name": "Radio", "release_name": "Treći Svijet",
        "additional_info": {"media_player": "OPUS", "submission_client": "OPUS Player",
                            "duration_ms": 220000, "recording_mbid": "r-1",
                            "release_mbid": "l-1", "artist_mbids": ["a-1"]}}}
    assert made[1]["track_metadata"]["additional_info"] == {
        "media_player": "OPUS", "submission_client": "OPUS Player"}


def test_one_listen_is_sent_as_one_and_several_as_an_import(web, monkeypatch):
    asked, answers = web
    answers["/1/submit-listens"] = httpx.Response(200, json={"status": "ok"})

    async def tracks(path, **params):
        return [{"id": int(i), "title": "T", "artist": "A", "album": "R"} for i in params["ids"].split(",")]

    monkeypatch.setattr(history.library, "get", tracks)
    link = HistoryLink(service="listenbrainz", token="tok")
    run(history._to_listenbrainz(link, [row("track", 1)]))
    run(history._to_listenbrainz(link, [row("track", 1), row("track", 2)]))
    assert [json.loads(r.content)["listen_type"] for r in asked] == ["single", "import"]
    assert asked[0].headers["Authorization"] == "Token tok"


def test_a_token_listenbrainz_does_not_know_is_refused_in_so_many_words(web):
    asked, answers = web
    answers["/1/validate-token"] = httpx.Response(200, json={"valid": False, "message": "Token invalid."})
    with pytest.raises(history.Refused):
        run(history.listenbrainz_account("nope"))
    answers["/1/validate-token"] = httpx.Response(200, json={"valid": True, "user_name": "filip"})
    assert run(history.listenbrainz_account("tok")) == "filip"


def test_episodes_go_under_their_series_and_season_and_films_by_their_ids_title_and_year():
    movies = {1: {"id": 1, "tmdb_id": 603, "imdb_id": "tt0133093", "title": "The Matrix", "year": 1999},
              2: {"id": 2, "tmdb_id": None, "title": "Nameless", "year": None}}
    episodes = {10: {"id": 10, "series_tmdb_id": 1399, "series_title": "Game of Thrones", "year": 2011,
                     "season_number": 2, "number": 3},
                11: {"id": 11, "series_tmdb_id": 1399, "series_title": "Game of Thrones", "year": 2011,
                     "season_number": 2, "number": 4}}
    nameless = row("movie", 2)
    body, unknown = history.viewings(
        [row("movie", 1), row("episode", 10), row("episode", 11), nameless, row("episode", 99)],
        movies, episodes)
    at = "2026-09-24T18:30:00Z"
    assert body == {
        "movies": [{"title": "The Matrix", "year": 1999, "ids": {"tmdb": 603, "imdb": "tt0133093"},
                    "watched_at": at}],
        "shows": [{"title": "Game of Thrones", "year": 2011, "ids": {"tmdb": 1399},
                   "seasons": [{"number": 2, "episodes": [
                       {"number": 3, "watched_at": at}, {"number": 4, "watched_at": at}]}]}],
    }
    assert [(r.kind, r.item_id) for r in unknown] == [("movie", 2), ("episode", 99)]


def test_what_simkl_never_heard_of_or_filed_as_the_wrong_kind_is_traced_back_to_its_rows():
    movies = {1: {"tmdb_id": 603}, 2: {"tmdb_id": 604}, 3: {"tmdb_id": 605}}
    episodes = {10: {"series_tmdb_id": 1399}, 11: {"series_tmdb_id": 1400}}
    rows = [row("movie", 1), row("movie", 2), row("movie", 3), row("episode", 10), row("episode", 11)]
    answer = {
        "added": {"statuses": [
            {"request": {"type": "movie", "ids": {"tmdb": 603}}, "response": {"simkl_type": "movie"}},
            {"request": {"type": "movie", "ids": {"tmdb": 605}}, "response": {"simkl_type": "tv"}},
            {"request": {"type": "show", "ids": {"tmdb": 1400}}, "response": {"simkl_type": "anime"}}]},
        "not_found": {"movies": [{"ids": {"tmdb": "604"}}], "shows": [{"ids": {"tmdb": 1399}}], "episodes": []},
    }
    assert history.not_taken(rows, movies, episodes, answer) == [rows[1], rows[2], rows[3]]


def test_the_simkl_code_is_asked_for_with_write_in_its_scope(web):
    asked, answers = web
    answers["/oauth2/device"] = httpx.Response(200, json={
        "device_code": "dev", "user_code": "BDWP-HQPK", "verification_uri": "https://simkl.com/pin",
        "verification_uri_complete": "https://simkl.com/pin?user_code=BDWP-HQPK",
        "expires_in": 900, "interval": 5})
    assert run(history.simkl_code(CONFIG))["user_code"] == "BDWP-HQPK"
    assert asked[0].content.decode() == "client_id=cid&scope=media%3Aread+media%3Awrite"
    assert dict(asked[0].url.params) == {"app-name": "opus-player", "app-version": "1"}


def test_the_simkl_code_waits_then_links_or_says_why_it_never_will(web):
    asked, answers = web
    answers["/oauth2/token"] = httpx.Response(400, json={"error": "authorization_pending"})
    assert run(history.simkl_grant(CONFIG, "dev")) is None
    answers["/oauth2/token"] = httpx.Response(400, json={"error": "slow_down"})
    assert run(history.simkl_grant(CONFIG, "dev")) == "slow"
    answers["/oauth2/token"] = httpx.Response(400, json={"error": "expired_token"})
    assert run(history.simkl_grant(CONFIG, "dev")) == "expired"
    answers["/oauth2/token"] = httpx.Response(401, json={"error": "invalid_client"})
    with pytest.raises(history.Refused):
        run(history.simkl_grant(CONFIG, "dev"))
    answers["/oauth2/token"] = httpx.Response(200, json={
        "access_token": "simkl_at_a", "refresh_token": "simkl_rt_r", "expires_in": 604800,
        "scope": "media:read media:write"})
    grant = run(history.simkl_grant(CONFIG, "dev"))
    assert dict(asked[-1].url.params) == {"app-name": "opus-player", "app-version": "1"}
    assert asked[-1].content.decode() == (
        "grant_type=urn%3Aietf%3Aparams%3Aoauth%3Agrant-type%3Adevice_code&client_id=cid&device_code=dev")
    link = HistoryLink(service="simkl")
    history.keep_grant(link, grant)
    assert (link.token, link.refresh) == ("simkl_at_a", "simkl_rt_r")
    assert timedelta(days=6) < link.expires_at - datetime.now(UTC) <= timedelta(days=7)


def test_a_simkl_token_that_can_only_read_is_refused_before_it_is_kept(web):
    asked, answers = web
    answers["/oauth2/token"] = httpx.Response(200, json={
        "access_token": "a", "refresh_token": "r", "expires_in": 604800, "scope": "media:read"})
    with pytest.raises(history.Refused):
        run(history.simkl_grant(CONFIG, "dev"))


def test_a_simkl_token_about_to_lapse_is_renewed_before_it_is_used(web):
    asked, answers = web
    answers["/oauth2/token"] = httpx.Response(200, json={
        "access_token": "new", "refresh_token": "r1", "expires_in": 604800, "scope": "media:read media:write"})
    lasting = HistoryLink(token="old", refresh="r1", expires_at=datetime.now(UTC) + timedelta(days=3))
    assert run(history._simkl_token(CONFIG, lasting)) == "old"
    assert asked == []
    lapsing = HistoryLink(token="old", refresh="r1", expires_at=datetime.now(UTC) + timedelta(hours=5))
    assert run(history._simkl_token(CONFIG, lapsing)) == "new"
    assert "grant_type=refresh_token" in asked[0].content.decode()
    assert "refresh_token=r1" in asked[0].content.decode()
    assert lapsing.expires_at - datetime.now(UTC) > timedelta(days=6)


def test_a_failure_is_tried_again_later_each_time_and_never_later_than_hours():
    assert history.retry_after(1) == timedelta(minutes=1)
    assert history.retry_after(3) == timedelta(minutes=4)
    assert history.retry_after(40) == timedelta(hours=6)


def test_a_service_just_linked_is_owed_what_came_before_it_each_at_its_own_time():
    march, may = datetime(2026, 3, 1, 20, tzinfo=UTC), datetime(2026, 5, 2, 21, tzinfo=UTC)
    heard = [(7, march)]
    seen = [("episode", 3, march), ("movie", 9, may)]
    assert [(s.kind, s.item_id, s.at) for s in history.owed(1, "listenbrainz", heard, seen)] == [
        ("track", 7, march)]
    assert [(s.kind, s.item_id, s.at) for s in history.owed(1, "simkl", heard, seen)] == [
        ("episode", 3, march), ("movie", 9, may)]
