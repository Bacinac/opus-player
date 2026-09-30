import pytest

from conftest import run
from opus import library
from opus.api.routers import explore
from opus.cards import movie_card


def _library(monkeypatch, films, search=None):
    calls = []

    async def post(path, body=None):
        calls.append(("post", path, body))
        if path == "/video/movies":
            raise library.AlreadyThere("already added")
        if search:
            raise search("refused")
        return {"download_id": 1}

    async def get(path, **params):
        assert path == "/video/movies"
        return films

    async def patch(path, body):
        calls.append(("patch", path, body))

    monkeypatch.setattr(library, "post", post)
    monkeypatch.setattr(library, "get", get)
    monkeypatch.setattr(library, "patch", patch)
    return calls


def test_a_film_card_off_the_shelf_carries_what_it_is_asked_for_by():
    assert movie_card({"id": 138, "tmdb_id": 438631, "title": "Dune"})["tmdb_id"] == 438631


def test_a_followed_film_with_no_file_is_looked_for_again(monkeypatch):
    calls = _library(monkeypatch, [{"id": 138, "tmdb_id": 438631, "title": "Dune",
                                    "status": "wanted", "monitored": True}])
    answer = run(explore.want(explore.Wanted(kind="movie", tmdb_id=438631)))
    assert answer == {"added": False, "queued": 0, "id": 138, "title": "Dune", "found": True}
    assert ("post", "/video/movies/138/search", None) in calls


def test_an_unfollowed_film_is_followed_when_asked_for(monkeypatch):
    calls = _library(monkeypatch, [{"id": 138, "tmdb_id": 438631, "title": "Dune",
                                    "status": "wanted", "monitored": False}])
    run(explore.want(explore.Wanted(kind="movie", tmdb_id=438631)))
    assert ("patch", "/video/movies/138", {"monitored": True}) in calls


@pytest.mark.parametrize("status", ["complete", "waiting_subtitles"])
def test_a_film_on_disk_is_not_fetched_twice(monkeypatch, status):
    calls = _library(monkeypatch, [{"id": 42, "tmdb_id": 98, "title": "Gladiator",
                                    "status": status, "monitored": True}])
    answer = run(explore.want(explore.Wanted(kind="movie", tmdb_id=98)))
    assert "found" not in answer and not answer["added"]
    assert [c for c in calls if c[1] != "/video/movies"] == []


@pytest.mark.parametrize("refusal, said", [(library.AlreadyThere, {"coming": True}),
                                           (library.NotInLibrary, {"found": False})])
def test_what_the_search_says_is_said_back(monkeypatch, refusal, said):
    _library(monkeypatch, [{"id": 138, "tmdb_id": 438631, "title": "Dune",
                            "status": "downloading", "monitored": True}], search=refusal)
    answer = run(explore.want(explore.Wanted(kind="movie", tmdb_id=438631)))
    assert said.items() <= answer.items()
