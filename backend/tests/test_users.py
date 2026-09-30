import json

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from conftest import PEOPLE, person_cookie, request, run
from opus import auth
from opus.api.routers import users
from opus.api.routers.system import BoxPatch, edit_box
from opus.api.routers.users import NewUser, UserPatch, orders_of


def test_a_new_profile_fits_its_row():
    assert NewUser(name="  Baka  ", colour="#4a90d9").name == "Baka"
    for wrong in ({"name": "   "}, {"name": "x" * 65}, {"name": "Baka", "colour": "red; x"},
                  {"name": "Baka", "colour": "#4a90d9ff"}):
        with pytest.raises(ValidationError):
            NewUser(**wrong)


@pytest.mark.parametrize("patch", [UserPatch, BoxPatch])
def test_shelf_orders_are_validated_not_cut(patch):
    said = patch(shelf_orders='{"movies": "title:asc", "music": "added"}').shelf_orders
    assert json.loads(said) == {"movies": "title:asc", "music": "added"}
    for wrong in ('{"movies": "title:asc"', '["movies"]', '{"films": "title:asc"}',
                  '{"movies": "rating:asc"}', '{"movies": 3}', '"x"' * 150):
        with pytest.raises(ValidationError):
            patch(shelf_orders=wrong)


def test_a_screensaver_is_people_the_library_knows_or_one_of_its_words():
    for said in ("", "household", "7", "1234567890", "87,51,50"):
        assert UserPatch(screensaver=said).screensaver == said
    assert UserPatch(screensaver="87,51,87").screensaver == "87,51"
    for wrong in ("0", "07", "family", "everybody", "7; drop", "12345678901", "-3",
                  "7,", ",7", "7,household", "7,,8"):
        with pytest.raises(ValidationError):
            UserPatch(screensaver=wrong)


def test_only_a_box_keeps_orders_of_its_own(monkeypatch):
    async def nobody(token):
        return None

    monkeypatch.setattr(users.auth, "device", nobody)
    with pytest.raises(HTTPException) as caught:
        run(edit_box(BoxPatch(shelf_orders="{}"), request(method="PATCH", path="/api/box"), None))
    assert caught.value.status_code == 401


def test_reading_shelf_orders_never_breaks_the_shelf():
    assert orders_of('{"movies": "year:desc", "photos": "title"}') == {"movies": "year:desc"}
    assert orders_of('["movies"]') == {}
    assert orders_of('{"movies": "title:asc"') == {}
    assert orders_of("") == {}


@pytest.mark.parametrize(("who", "key", "may"), [
    (None, "filip", True),
    ("filip", "kata", True),
    ("boss", "filip", True),
    ("gost", "gost", True),
    ("gost", "filip", False),
    ("gost", "Baka", False),
])
def test_a_guest_is_only_their_own_profile(who, key, may):
    assert users._may_be(PEOPLE[who] if who else None, key) is may


def test_a_guest_is_refused_everybody_else(house):
    as_guest = request({"opus_session": person_cookie("gost")})
    run(users._refuse_guest(as_guest, "gost"))
    for key in ("filip", None):
        with pytest.raises(HTTPException) as refused:
            run(users._refuse_guest(as_guest, key))
        assert refused.value.status_code == 403
    run(users._refuse_guest(request({"opus_session": person_cookie("filip")}), None))
    run(users._refuse_guest(request(), "filip"))


def test_a_guest_lists_only_themselves(house, monkeypatch):
    async def rows(session):
        return {"Baka": users.User(id=4, person=None, name="Baka", colour="")}

    monkeypatch.setattr(users, "_rows", rows)
    everybody = run(users.list_users(request({"opus_session": person_cookie("filip")}), session=None))
    assert [p["key"] for p in everybody] == ["filip", "gost", "Baka"]
    guest = run(users.list_users(request({"opus_session": person_cookie("gost")}), session=None))
    assert [p["key"] for p in guest] == ["gost"]


def test_a_film_sent_from_a_phone_keeps_its_place_for_whoever_sent_it(house, monkeypatch):
    filip = users.User(id=3, person="filip", name="Filip", colour="")
    nika = users.User(id=9, person=None, name="Nika", colour="")

    async def rows(session):
        return {"filip": filip, "Nika": nika}

    async def picked_on_the_box(asked, session):
        return nika

    monkeypatch.setattr(users, "_rows", rows)
    monkeypatch.setattr(users, "require_picked", picked_on_the_box)
    film = auth.lend("filip", "movie", 128, None)
    episode = auth.lend("filip", "episode", 2934, 13)

    def whose(*asked):
        return run(users.watching(request(), None, *asked)).name

    assert whose(film, "movie", 128, None) == "Filip"
    assert whose(episode, "episode", 2934, 13) == "Filip"
    assert whose(episode, "episode", 2935, 13) == "Filip"
    for other in [(film, "movie", 129, None), (film, "episode", 128, None),
                  (episode, "episode", 2935, 14), (episode, "movie", 2935, 13),
                  (film[:-1] + ("A" if film[-1] != "A" else "B"), "movie", 128, None),
                  (None, "movie", 128, None)]:
        assert whose(*other) == "Nika"
