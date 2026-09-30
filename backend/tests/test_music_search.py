from conftest import run
from opus import library
from opus.api.routers import explore


def test_music_is_looked_for_in_music_the_shelf_first(monkeypatch):
    async def asked(path, **params):
        if path == "/music/search":
            assert params == {"q": "prljavo"}
            return {"artists": [1, 99],
                    "tracks": [{"id": 101, "title": "Mi Plešemo", "artist": "Prljavo Kazalište",
                                "album": "Crno-bijeli svijet", "release_id": 11, "position": 1,
                                "cover_url": None, "duration_s": 200, "codec": "flac"}],
                    "records": [{"kind": "album", "source": "deezer", "id": "2", "title": "Heroj ulice",
                                 "artist": "Prljavo Kazaliste", "year": 1981, "cover_url": "https://img/2.jpg"}]}
        assert (path, params) == ("/music/artists", {"ids": "1,99"})
        return [{"id": 1, "name": "Prljavo Kazalište", "image_url": None, "begin_year": 1977}]

    monkeypatch.setattr(library, "get", asked)
    cards = run(explore.music_search("prljavo"))
    assert [(c["kind"], c["title"]) for c in cards] == [
        ("artist", "Prljavo Kazalište"), ("track", "Mi Plešemo"), ("music", "Heroj ulice")]
    record = cards[2]
    assert (record["artist"], record["album"], record["holds"], record["person"], record["square"]) == \
        ("Prljavo Kazaliste", "Heroj ulice", "album", False, True)
