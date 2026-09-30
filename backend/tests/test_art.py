import os

import pytest

from conftest import run
from opus.api.routers import art
from opus.api.routers.art import picture, sweep

@pytest.mark.parametrize(("given", "kept"), [
    ("https://image.tmdb.org/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg?junk=1&more=2",
     "https://image.tmdb.org/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg"),
    ("http://cdn-images.dzcdn.net:443/images/artist/03380466e2b2c6c681357f0de682b320/1000x1000-000000-80-0-0.jpg#x",
     "https://cdn-images.dzcdn.net/images/artist/03380466e2b2c6c681357f0de682b320/1000x1000-000000-80-0-0.jpg"),
    ("https://i.discogs.com/00NWGWOl0rvOLJqdDi6DW8MxkKIvowaDlVlhR6KjWZc/rs:fit/g:sm/q:40/h:150/w:150/"
     "czM6Ly9kaXNjb2dz/LWRhdGFiYXNlLWlt/YWdlcy9SLTEwOTUx/MjI1LTE1MjQ3NDU1/NDUtOTgyNy5qcGVn.jpeg",
     "https://i.discogs.com/00NWGWOl0rvOLJqdDi6DW8MxkKIvowaDlVlhR6KjWZc/rs:fit/g:sm/q:40/h:150/w:150/"
     "czM6Ly9kaXNjb2dz/LWRhdGFiYXNlLWlt/YWdlcy9SLTEwOTUx/MjI1LTE1MjQ3NDU1/NDUtOTgyNy5qcGVn.jpeg"),
    ("https://i.scdn.co/image/ab67616d0000b27300d511262ef13eadf75c0da7?x=1",
     "https://i.scdn.co/image/ab67616d0000b27300d511262ef13eadf75c0da7"),
    ("https://is1-ssl.mzstatic.com/image/thumb/Music211/v4/99/8a/b0/998ab039-cdf1-89f5-7037-b2d24b048dda/"
     "cover.jpg/3000x3000bb.jpg",
     "https://is1-ssl.mzstatic.com/image/thumb/Music211/v4/99/8a/b0/998ab039-cdf1-89f5-7037-b2d24b048dda/"
     "cover.jpg/3000x3000bb.jpg"),
    ("https://upload.wikimedia.org/wikipedia/hr/3/32/Toma_Bebi%C4%87.jpg?utm_source=hr.wikipedia.org",
     "https://upload.wikimedia.org/wikipedia/hr/3/32/Toma_Bebi%C4%87.jpg"),
    ("https://commons.wikimedia.org/wiki/Special:FilePath/ZZ%20Top.jpg?width=1000&utm=x",
     "https://commons.wikimedia.org/wiki/Special:FilePath/ZZ%20Top.jpg?width=1000"),
    ("https://commons.wikimedia.org/w/index.php?title=Special:Redirect/file/10,000_Maniacs.jpg&width=320&x=y",
     "https://commons.wikimedia.org/w/index.php?title=Special%3ARedirect%2Ffile%2F10%2C000_Maniacs.jpg&width=320"),
    ("https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b3/10%2C000_Maniacs.jpg/330px-10%2C000_Maniacs.jpg"
     "?utm_source=commons.wikimedia.org",
     "https://thumb.wikimedia.org/wikipedia/commons/thumb/b/b3/10%2C000_Maniacs.jpg/330px-10%2C000_Maniacs.jpg"),
])
def test_a_picture_is_kept_under_the_address_its_source_reads(given, kept):
    assert picture(given) == kept


@pytest.mark.parametrize("given", [
    "https://image.tmdb.org/t/p/w342/../../3/movie/550",
    "https://image.tmdb.org/3/movie/550?api_key=x",
    "https://i.scdn.co/image/../v1/me",
    "https://user:pass@image.tmdb.org/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg",
    "ftp://image.tmdb.org/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg",
    "https://image.tmdb.org.evil.example/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg",
    "https://commons.wikimedia.org/wiki/Special:Search/anything",
    "https://commons.wikimedia.org/w/index.php?title=Special:UserLogin",
    "https://upload.wikimedia.org/wikipedia/commons/3/33/notes.txt",
    "http://192.168.1.103:8095/api/settings",
    "not an address",
])
def test_what_is_not_a_picture_is_not_fetched(given):
    assert picture(given) is None


def test_a_station_logo_is_fetched_only_as_listed(monkeypatch):
    async def logos():
        return {"http://cdn-profiles.tunein.com/s15643/images/logoq.jpg?t=1"}

    monkeypatch.setattr(art, "_station_logos", logos)
    assert run(art.asked_for("http://cdn-profiles.tunein.com/s15643/images/logoq.jpg?t=1"))
    assert run(art.asked_for("http://cdn-profiles.tunein.com/s15643/images/logoq.jpg?t=2")) is None
    assert run(art.asked_for("http://cdn-profiles.tunein.com/private/admin")) is None


def test_a_redirect_is_followed_only_where_the_route_would_fetch():
    station = "http://logos.example/one.png"
    assert art._onward(station, "https://logos.example/one.png") == "https://logos.example/one.png"
    assert art._onward(station, "http://elsewhere.example/one.png") is None
    assert art._onward("http://10.0.0.1/x.png", "http://10.0.0.1/y.png") is None
    tmdb = "https://image.tmdb.org/t/p/w342/o2yCU9XwakKnpD33D8TxenRSiNM.jpg"
    assert art._onward(tmdb, "https://image.tmdb.org/3/configuration") is None


def test_every_width_is_one_of_the_menu():
    kept = {art._sized("https://image.tmdb.org/t/p/w780/a.jpg", art._menu(w, art.WIDTHS)) for w in range(1, 5000, 7)}
    assert len(kept) <= len(art.WIDTHS)


def _file(root, name: str, size: int, used: float):
    folder = root / name[:2]
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_bytes(b"x" * size)
    os.utime(path, (used, used))
    return path


def test_the_pictures_looked_at_longest_ago_go_first(tmp_path):
    old = _file(tmp_path, "aa1.jpg", 400, 1000)
    middle = _file(tmp_path, "bb1.jpg", 400, 2000)
    new = _file(tmp_path, "cc1.jpg", 400, 3000)
    assert sweep(tmp_path, 2000) == 1200
    assert old.exists() and middle.exists() and new.exists()
    assert sweep(tmp_path, 1000) == 800
    assert not old.exists() and middle.exists() and new.exists()
    assert sweep(tmp_path, 500) == 400
    assert not middle.exists() and new.exists()


def test_looking_at_a_picture_makes_it_recent(tmp_path, monkeypatch):
    kept = tmp_path / "ab" / "abcdef"
    held = _file(tmp_path, "abcdef.jpg", 10, 1000)
    assert art._held(kept) == (held, "image/jpeg")
    assert held.stat().st_mtime > 1000
    assert art._held(tmp_path / "ab" / "nothing") is None


def test_a_readable_picture_survives_an_old_cache_owner(tmp_path, monkeypatch):
    kept = tmp_path / "ab" / "abcdef"
    held = _file(tmp_path, "abcdef.jpg", 10, 1000)

    def refused(_path):
        raise PermissionError("owned by the previous deployment")

    monkeypatch.setattr(art.os, "utime", refused)
    assert art._held(kept) == (held, "image/jpeg")


def test_the_cache_is_swept_when_it_grows_past_its_bound(tmp_path, monkeypatch):
    monkeypatch.setattr(art.settings, "art_cache", str(tmp_path))
    monkeypatch.setattr(art.settings, "art_cache_bytes", 1000)
    monkeypatch.setattr(art, "_holding", None)
    first = _file(tmp_path, "aa1.jpg", 600, 1000)
    run(art._grown(600))
    assert art._holding == 600
    _file(tmp_path, "bb1.jpg", 600, 2000)
    run(art._grown(600))
    assert art._holding == 600 and not first.exists()
