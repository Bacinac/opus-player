from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from conftest import request, run
from opus import auth
from opus.api.routers import cast
from opus.api.routers.cast import CastTrack
from opus.models import BoxPreference

STATION = "http://live.radio101.hr:9531/"
LOGO = "http://cdn-profiles.tunein.com/s8910/images/logoq.jpg"


class Config:
    def __init__(self, **values):
        self.values = values

    def get(self, key):
        return self.values.get(key, "")


@pytest.fixture
def boxes(monkeypatch):
    monkeypatch.setattr(cast, "_boxes", {})
    now = {"at": 1000.0}
    monkeypatch.setattr(cast, "time", SimpleNamespace(monotonic=lambda: now["at"]))

    def box(id: int, listening: bool = True) -> cast._TvChannel:
        channel = cast._boxes[id] = cast._TvChannel(auth.Box(id, f"box {id}"))
        channel.seen_at = now["at"] if listening else 1.0 - 120
        return channel

    return box


def test_an_order_goes_to_the_box_it_names(boxes):
    living, terrace = boxes(7), boxes(9)
    assert cast._house(Config(), 9) is terrace
    assert cast._house(Config(tv_box="7"), None) is living
    assert cast._house(Config(tv_box="7"), 9) is terrace
    assert cast._house(Config(), 12) is None


def test_the_house_television_is_the_one_set_or_the_only_one_listening(boxes):
    assert cast._house(Config()) is None
    only = boxes(7)
    boxes(9, listening=False)
    assert cast._house(Config()) is only
    boxes(11)
    with pytest.raises(HTTPException) as refused:
        cast._house(Config())
    assert refused.value.status_code == 409
    assert cast._mirror(Config()) is None
    assert cast._house(Config(tv_box="11")).box.id == 11


def test_a_box_that_is_not_listening_is_said_to_be(boxes):
    boxes(9, listening=False)
    with pytest.raises(HTTPException) as refused:
        cast._listening(Config(tv_box="9"))
    assert refused.value.status_code == 503


def test_posting_wakes_only_that_box(boxes):
    living, terrace = boxes(7), boxes(9)
    cast._listening(Config(tv_box="7")).post(control={"command": "pause"})
    assert living.seq == 1 and living.control == {"command": "pause", "seq": 1}
    assert terrace.seq == 0 and terrace.control is None


def test_only_a_box_that_was_let_in_has_a_mailbox(monkeypatch, boxes):
    async def device(token):
        return auth.Box(7, "Dnevni boravak") if token == "b" * 43 else None

    monkeypatch.setattr(auth, "device", device)
    held = SimpleNamespace(cookies={auth.DEVICE_COOKIE: "b" * 43})
    first = run(cast._this_box(held))
    assert first.box.id == 7 and run(cast._this_box(held)) is first
    with pytest.raises(HTTPException) as refused:
        run(cast._this_box(SimpleNamespace(cookies={})))
    assert refused.value.status_code == 403


@pytest.fixture
def listed(monkeypatch):
    class Rows:
        def scalars(self):
            return [STATION]

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def execute(self, query):
            return Rows()

    async def asked_for(url):
        return url if url in (LOGO, "https://image.tmdb.org/t/p/w342/a.jpg") else None

    monkeypatch.setattr(cast, "SessionLocal", Session)
    monkeypatch.setattr(cast, "asked_for", asked_for)


@pytest.mark.parametrize("track", [
    CastTrack(id=11731, title="A song", cover_url="https://image.tmdb.org/t/p/w342/a.jpg"),
    CastTrack(id=-2, title="Radio 101", url=STATION, cover_url=LOGO),
    CastTrack(id=5, cover_url=None),
])
def test_what_the_player_hands_out_may_be_cast(listed, track):
    run(cast._vetted([track]))


@pytest.mark.parametrize("track", [
    CastTrack(id=-1, url="http://192.168.1.12:8123/api/services/lock/open"),
    CastTrack(id=5, cover_url="http://attacker.example/pixel.gif"),
    CastTrack(id=-1, title="no id and no station"),
    CastTrack(id=-2, url=STATION, cover_url="file:///etc/passwd"),
])
def test_anything_else_is_refused(listed, track):
    with pytest.raises(HTTPException) as refused:
        run(cast._vetted([CastTrack(id=1), track]))
    assert refused.value.status_code == 400


def test_the_dac_asks_the_library_for_the_dsd_edition_of_each_track():
    config = Config(stream_base="http://media:8098")
    urls = cast._addresses(config, [CastTrack(id=4211, codec="flac"), CastTrack(id=9, codec="flac")])
    assert [u.split("prefer=")[1].split("&")[0] for u in urls] == ["dsd", "dsd"]


def test_a_stations_own_address_is_used_as_is_dsd_or_not():
    urls = cast._addresses(Config(), [CastTrack(id=-1, url=STATION)])
    assert urls == [STATION]


@pytest.fixture
def house_tv(monkeypatch, boxes):
    async def runtime():
        return Config(tv_box="7")

    monkeypatch.setattr(cast, "current_runtime", runtime)
    return boxes(7)


def test_a_film_on_the_television_is_sent_to_a_place_in_it(house_tv):
    run(cast.tv_control(cast.TvControl(command="seek", at=1834.5)))
    assert house_tv.control == {"command": "seek", "at": 1834.5, "seq": 1}
    run(cast.tv_control(cast.TvControl(command="pause", at=12.0)))
    assert house_tv.control == {"command": "pause", "seq": 2}


@pytest.mark.parametrize("at", [None, -1.0])
def test_a_seek_with_nowhere_to_go_is_refused(house_tv, at):
    with pytest.raises(HTTPException) as refused:
        run(cast.tv_control(cast.TvControl(command="seek", at=at)))
    assert refused.value.status_code == 400
    assert house_tv.seq == 0


def test_an_episode_is_played_on_the_television_as_its_card(monkeypatch, house_tv):
    asked = []

    async def get(path, **params):
        asked.append((path, params))
        return [{"id": 2934, "series_id": 13, "series_title": "Silo", "season_number": 2,
                 "number": 4, "title": "Kapsula", "poster_url": None, "backdrop_url": None}]

    monkeypatch.setattr(cast.library, "get", get)
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr"), request()))
    assert asked == [("/video/episodes", {"ids": "2934", "lang": "hr"})]
    card = house_tv.order["film"]
    assert (card["kind"], card["id"], card["series_id"], card["season_number"], card["number"]) == (
        "episode", 2934, 13, 2, 4)


def test_an_episode_the_library_does_not_know_is_not_sent(monkeypatch, house_tv):
    async def get(path, **params):
        return []

    monkeypatch.setattr(cast.library, "get", get)
    with pytest.raises(HTTPException) as refused:
        run(cast.tv_open(cast.TvOpen(kind="episode", id=1, lang="hr"), request()))
    assert refused.value.status_code == 404
    assert house_tv.order is None


def test_a_film_sent_from_another_screen_plays_on_from_where_it_was(monkeypatch, house_tv):
    async def get(path, **params):
        return [{"id": 2934, "series_id": 13, "series_title": "Silo", "season_number": 2,
                 "number": 4, "title": "Kapsula", "poster_url": None, "backdrop_url": None}]

    monkeypatch.setattr(cast.library, "get", get)
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr", at=1312.5), request()))
    assert house_tv.order["at"] == 1312.5
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr"), request()))
    assert "at" not in house_tv.order


def test_a_film_sent_from_a_phone_is_watched_for_whoever_sent_it(monkeypatch, house_tv):
    async def get(path, **params):
        return [SILO]

    async def sender(asked, session):
        return cast.User(id=3, person="filip", name="Filip", colour="")

    monkeypatch.setattr(cast.library, "get", get)
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr"), request()))
    assert "sent" not in house_tv.order
    monkeypatch.setattr(cast, "picked", sender)
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr"), request()))
    assert auth.lent_to(house_tv.order["sent"], "episode", 2934, 13) == "filip"


SILO = {"id": 2934, "series_id": 13, "series_title": "Silo", "season_number": 2,
        "number": 4, "title": "Kapsula", "poster_url": None, "backdrop_url": None}


@pytest.fixture
def asleep(monkeypatch, boxes):
    """The house's television has not come to the door: it sleeps, dreams or
    shows another app, and the house knows it as a device it can wake."""
    told = []

    async def runtime():
        return Config(tv_box="7", tv_box_entity="androidtv:streamer_living_room")

    async def command(config, entity, capability, cmd, args=None):
        told.append((entity, capability, cmd, args))

    async def episodes(path, **params):
        return [SILO]

    async def device(cookie):
        return auth.Box(7, "Dnevni boravak")

    monkeypatch.setattr(cast, "current_runtime", runtime)
    monkeypatch.setattr(cast.house, "command", command)
    monkeypatch.setattr(cast.library, "get", episodes)
    monkeypatch.setattr(cast.auth, "device", device)
    monkeypatch.setattr(cast, "_waiting", {})
    return told


def test_a_film_sent_to_a_sleeping_television_wakes_it_and_waits_for_it(asleep):
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr", box=7, at=600.0), request()))
    assert asleep == [("androidtv:streamer_living_room", "source", "set_source",
                       {"value": cast.TV_APP})]
    door = SimpleNamespace(cookies={})
    # the screen's first question only learns where the count stands; an order
    # posted before it would be history to it
    first = run(cast.tv_inbox(door))
    assert first["order"] is None
    said = run(cast.tv_inbox(door, seq=first["seq"], boot=first["boot"]))
    assert (said["order"]["film"]["id"], said["order"]["at"]) == (2934, 600.0)
    assert cast._waiting == {}


def test_a_television_the_house_cannot_wake_is_not_sent_a_film(asleep, monkeypatch):
    async def runtime():
        return Config(tv_box="7")

    monkeypatch.setattr(cast, "current_runtime", runtime)
    with pytest.raises(HTTPException) as refused:
        run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr", box=7), request()))
    assert refused.value.status_code == 503
    assert asleep == [] and cast._waiting == {}


def test_a_house_that_cannot_wake_the_television_says_so(asleep, monkeypatch):
    async def command(config, entity, capability, cmd, args=None):
        raise cast.dida.DidaError("androidtv: not connected")

    monkeypatch.setattr(cast.house, "command", command)
    with pytest.raises(HTTPException) as refused:
        run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr", box=7), request()))
    assert refused.value.status_code == 502
    assert cast._waiting == {}


def test_a_listening_television_is_not_woken(asleep, boxes):
    living = boxes(7)
    run(cast.tv_open(cast.TvOpen(kind="episode", id=2934, lang="hr", box=7), request()))
    assert asleep == [] and living.order["film"]["id"] == 2934


def test_the_house_television_is_offered_while_it_sleeps(asleep, monkeypatch):
    async def state(config, entity):
        return {"name": "Streamer Living Room", "values": {}}

    monkeypatch.setattr(cast.house, "state", state)
    assert run(cast.tv_boxes())["boxes"] == [
        {"id": 7, "name": "Streamer Living Room", "listening": False, "house": True, "wakes": True}]


PHOTO = "9f86d081884c7d659a2feaa0c55ad015"


def test_a_photograph_is_shown_on_a_listening_television(house_tv):
    run(cast.tv_photo(cast.TvPhoto(id=PHOTO)))
    assert house_tv.order == {"photo": PHOTO, "seq": 1}


def test_a_photograph_is_put_away_without_waking_anybody(asleep, boxes):
    run(cast.tv_photo(cast.TvPhoto(box=7)))
    assert asleep == [] and cast._waiting == {}
    living = boxes(7)
    run(cast.tv_photo(cast.TvPhoto(box=7)))
    assert living.order == {"photo": None, "seq": 1}


def test_a_photograph_is_named_by_its_checksum_and_nothing_else():
    with pytest.raises(ValueError):
        cast.TvPhoto(id="../../settings")


def test_the_phone_moving_on_while_the_television_wakes_wakes_it_once(asleep):
    run(cast.tv_photo(cast.TvPhoto(id=PHOTO, box=7)))
    run(cast.tv_photo(cast.TvPhoto(id="ab" * 16, box=7)))
    assert len(asleep) == 1
    assert cast._waiting[7][0] == {"photo": "ab" * 16}


def test_the_television_says_which_photograph_it_shows(house_tv, monkeypatch):
    async def device(cookie):
        return auth.Box(7, "Dnevni boravak")

    monkeypatch.setattr(cast.auth, "device", device)
    door = SimpleNamespace(cookies={})
    run(cast.tv_state(cast.TvState(kind="none", playing=False, photo=PHOTO), door))
    now = run(cast.tv_now())
    assert (now["transport"], now["photo"]) == ("idle", PHOTO)


FAMILY = [{"id": 37, "name": "Kata Babić", "given_name": "Kata", "family": True},
          {"id": 41, "name": "Kata Vuk", "given_name": "Kata", "family": False},
          {"id": 52, "name": "Eva Babić", "given_name": "Eva", "family": True},
          {"id": 53, "name": "Eva Horvat", "given_name": "Eva", "family": True}]


@pytest.fixture
def family(monkeypatch):
    async def people(path, **params):
        assert path == "/photos/people"
        return FAMILY

    monkeypatch.setattr(cast.library, "get", people)


def test_somebody_of_the_family_is_shown_by_the_name_the_house_says(house_tv, family):
    run(cast.tv_show(cast.TvShow(person="kata")))
    assert house_tv.order == {"show": {"person": 37}, "seq": 1}
    run(cast.tv_show(cast.TvShow(family=True)))
    assert house_tv.order == {"show": {"family": True}, "seq": 2}
    run(cast.tv_show(cast.TvShow()))
    assert house_tv.order == {"show": {}, "seq": 3}


@pytest.mark.parametrize(("name", "status"), [("Nika", 404), ("Eva", 409)])
def test_a_name_that_is_nobody_or_two_of_the_family_is_refused(house_tv, family, name, status):
    with pytest.raises(HTTPException) as refused:
        run(cast.tv_show(cast.TvShow(person=name)))
    assert refused.value.status_code == status
    assert house_tv.seq == 0


def test_the_television_is_woken_to_go_on_with_what_was_watched(asleep):
    run(cast.tv_resume(cast.TvBox()))
    assert asleep == [("androidtv:streamer_living_room", "source", "set_source",
                       {"value": cast.TV_APP})]
    assert cast._waiting[7][0] == {"resume": True}


def test_an_episode_is_sent_on_to_the_next(house_tv):
    run(cast.tv_control(cast.TvControl(command="next_episode")))
    assert house_tv.control == {"command": "next_episode", "seq": 1}


MARANTZ = "marantz-AVR · MJI 77"


@pytest.fixture
def receiver(monkeypatch):
    """The Shield and the terrace's box on one receiver, on two inputs, and a
    third box wired straight to a screen of its own. The terrace's box was
    wired while it said it was plugged into the receiver; the Shield cannot
    say."""
    told = []
    asking = {"box": None}

    async def runtime():
        return Config(audio_amp_entity="denon:marantz_main", tv_box="2")

    async def command(config, entity, capability, cmd, args=None):
        told.append((cmd, args))

    async def wiring(box):
        return {2: BoxPreference(box_id=2, amp_source="SHIELD", amp_sink=""),
                7: BoxPreference(box_id=7, amp_source="Chromecast", amp_sink=MARANTZ)}.get(box)

    async def device(cookie):
        return auth.Box(asking["box"], "box") if asking["box"] else None

    async def control(action):
        told.append(("dac", action))

    monkeypatch.setattr(cast, "current_runtime", runtime)
    monkeypatch.setattr(cast.house, "command", command)
    monkeypatch.setattr(cast, "_wiring", wiring)
    monkeypatch.setattr(cast.auth, "device", device)
    monkeypatch.setattr(cast.dac, "control", control)
    return told, asking


@pytest.mark.parametrize(("box", "source"), [(2, "SHIELD"), (7, "Chromecast")])
def test_a_film_turns_the_receiver_to_the_box_that_plays_it(receiver, box, source):
    told, asking = receiver
    asking["box"] = box
    run(cast.tv_video(SimpleNamespace(cookies={})))
    assert told == [("turn_on", None), ("set_source", {"value": source}),
                    ("set_video_select", {"value": "off"}), ("dac", "stop")]


@pytest.mark.parametrize("box", [9, None])
def test_a_box_the_receiver_does_not_carry_leaves_the_receiver_and_the_record_alone(receiver, box):
    told, asking = receiver
    asking["box"] = box
    run(cast.tv_video(SimpleNamespace(cookies={})))
    assert told == []


@pytest.mark.parametrize(("sink", "turned"), [(MARANTZ, True), ("", True), ("SAMSUNG · SAM 3421", False)])
def test_a_box_carried_to_another_screen_leaves_the_receiver_alone(receiver, monkeypatch, sink, turned):
    """The terrace's box taken to a bedroom panel plays its film there; the
    receiver in the living room is not switched on for a film nobody there
    watches. A box that cannot say where it is keeps its input."""
    told, asking = receiver
    asking["box"] = 7
    monkeypatch.setitem(cast._boxes, 7, SimpleNamespace(sink=sink))
    run(cast.tv_video(SimpleNamespace(cookies={})))
    assert bool(told) is turned


def test_a_box_asleep_is_still_where_it_last_said_it_was(monkeypatch):
    box = auth.Box(7, "Patio")
    tv = cast._TvChannel(box)

    async def this_box(request):
        return tv

    monkeypatch.setattr(cast, "_this_box", this_box)
    run(cast.tv_inbox(SimpleNamespace(), sink=MARANTZ))
    run(cast.tv_inbox(SimpleNamespace(), sink=""))
    assert tv.sink == MARANTZ


def test_a_box_is_wired_only_to_an_input_the_receiver_has(monkeypatch):
    async def runtime():
        return Config(audio_amp_entity="denon:marantz_main")

    async def sources(config):
        return ["SHIELD", "Chromecast", "MUSIC"]

    monkeypatch.setattr(cast, "current_runtime", runtime)
    monkeypatch.setattr(cast, "_amp_sources", sources)
    with pytest.raises(HTTPException) as caught:
        run(cast.wire_box(7, cast.BoxWiring(source="Kitchen")))
    assert caught.value.status_code == 400
