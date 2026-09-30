import pytest
from fastapi import HTTPException

from conftest import PEOPLE, person_cookie, request, run
from opus import auth
from opus import library
from opus.api.routers import favorites


def test_available_tracks_keep_the_order_somebody_saved_them_in():
    cards = [
        {"id": 8, "title": "older", "artist": "a", "album": "b", "codec": "flac", "playable": True},
        {"id": 4, "title": "gone", "playable": False},
        {"id": 12, "title": "newer", "artist": "a", "album": "b", "codec": "flac", "playable": True},
    ]
    assert [row["id"] for row in favorites.in_saved_order([12, 4, 99, 8], cards)] == [12, 8]


def test_a_playable_favorite_with_a_broken_android_contract_is_refused():
    with pytest.raises(library.LibraryError, match="music-track contract missing codec"):
        favorites.in_saved_order([8], [{"id": 8, "playable": True, "title": "x", "artist": "a", "album": "b"}])


def test_a_favorite_needs_a_person_not_a_household_box_or_module(house):
    with pytest.raises(HTTPException) as refused:
        run(favorites.person_of(request()))
    assert refused.value.status_code == 401
    assert run(favorites.person_of(request({"opus_session": person_cookie("filip")}))) == PEOPLE["filip"]


def test_a_paired_car_is_the_person_its_bearer_was_minted_for(house, monkeypatch):
    async def car(bearer):
        return ("gost", PEOPLE["gost"].version) if bearer == "paired" else None

    monkeypatch.setattr(auth, "car_session", car)
    assert run(favorites.person_of(request(headers={"authorization": "Bearer paired"}))) == PEOPLE["gost"]
