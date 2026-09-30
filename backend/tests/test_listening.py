import pytest
from pydantic import ValidationError

from opus.api.routers.listening import Heard, most_heard_first
from opus.cards import release_card


def test_an_artist_plays_what_this_person_keeps_going_back_to_first():
    tracks = [{"id": n} for n in range(1, 21)]
    order = [t["id"] for t in most_heard_first(tracks, {7: 2, 3: 9, 15: 5})]
    assert order[:3] == [3, 15, 7]
    assert sorted(order[3:]) == [n for n in range(1, 21) if n not in (3, 7, 15)]


def test_nobody_heard_anything_is_the_whole_artist_shuffled():
    tracks = [{"id": n} for n in range(1, 41)]
    order = [t["id"] for t in most_heard_first(tracks, {})]
    assert sorted(order) == list(range(1, 41))
    assert order != list(range(1, 41))


def test_a_play_names_the_song_its_record_and_whose_it_is():
    Heard(track_id=1, release_id=2, artist_id=3)
    with pytest.raises(ValidationError):
        Heard(track_id=1, release_id=2)
    with pytest.raises(ValidationError):
        Heard(track_id=0, release_id=2, artist_id=3)


def test_a_record_on_a_shelf_is_a_square_sleeve_that_knows_its_artist():
    card = release_card({"id": 4, "title": "Bolero", "artist": "Haustor", "artist_id": 9,
                         "year": "1985", "cover_url": "https://img/b.jpg"})
    assert (card["kind"], card["artist_id"], card["subtitle"], card["square"]) == (
        "release", 9, "Haustor", True)
