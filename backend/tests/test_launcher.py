from opus.api.routers.launcher import camera_list, ordered_cameras, summarize


def test_launcher_selects_outside_and_living_room_sensors():
    areas = [
        {"id": 17, "kind": "living"},
        {"id": 19, "kind": "outdoor"},
    ]
    entities = [
        {"entity_id": "ecowitt:home:outdoor", "name": "Home Outdoor",
         "label": "Zagreb", "adapter": "ecowitt", "area_id": 19, "exposed": True},
        {"entity_id": "ecowitt:home:indoor", "name": "Home Indoor",
         "adapter": "ecowitt", "area_id": 17, "exposed": True},
        {"entity_id": "ecowitt:hidden:outdoor", "name": "Hidden Outdoor",
         "adapter": "ecowitt", "area_id": 19, "exposed": False},
    ]
    states = [
        {"entity_id": "ecowitt:home:outdoor", "capability": "temperature", "value": 24.61},
        {"entity_id": "ecowitt:home:outdoor", "capability": "humidity", "value": 67},
        {"entity_id": "ecowitt:home:outdoor", "capability": "wind_speed", "value": 3.2},
        {"entity_id": "ecowitt:home:outdoor", "capability": "rain_daily", "value": 4.7},
        {"entity_id": "ecowitt:home:indoor", "capability": "temperature", "value": 22.4},
        {"entity_id": "ecowitt:home:indoor", "capability": "humidity", "value": 48},
        {"entity_id": "ecowitt:hidden:outdoor", "capability": "temperature", "value": 30},
    ]

    assert summarize(entities, states, areas) == {
        "outside": {
            "id": "ecowitt:home:outdoor",
            "area": "outdoor",
            "temperature_c": 24.61,
            "humidity_pct": 67.0,
            "wind_kmh": 11.52,
            "rain_mm": 4.7,
        },
        "living": {
            "id": "ecowitt:home:indoor",
            "area": "living",
            "temperature_c": 22.4,
            "humidity_pct": 48.0,
            "wind_kmh": None,
            "rain_mm": None,
        },
    }


def test_launcher_returns_no_facts_when_dida_has_none():
    assert summarize([], [], []) == {"outside": None, "living": None}


def test_launcher_lists_only_exposed_cameras_without_their_upstream_urls():
    entities = [
        {"entity_id": "baba:door", "name": "Door", "label": None,
         "capabilities": ["camera", "motion"], "exposed": True},
        {"entity_id": "baba:hidden", "name": "Hidden",
         "capabilities": ["camera"], "exposed": False},
    ]
    states = [
        {"entity_id": "baba:door", "capability": "camera",
         "value": '{"site":"Home","snapshot":"http://private/frame.jpg"}'},
        {"entity_id": "baba:hidden", "capability": "camera", "value": '{}'},
    ]
    assert camera_list(entities, states) == [
        {"id": "baba:door", "name": "Door", "site": "Home", "live": None},
    ]


def test_launcher_names_the_live_stream_a_camera_actually_has():
    entity = {"name": "Cam", "capabilities": ["camera"]}
    states = [
        {"entity_id": "baba:gate", "capability": "camera",
         "value": '{"mjpeg":"http://g/api/stream.mjpeg","mp4":"http://g/api/stream.mp4"}'},
        {"entity_id": "frigate:drive", "capability": "camera",
         "value": '{"mjpeg":"https://nvr/api/drive"}'},
    ]
    live = {camera["id"]: camera["live"] for camera in camera_list(
        [{**entity, "entity_id": "baba:gate"}, {**entity, "entity_id": "frigate:drive"}], states)}
    assert live == {"baba:gate": "mp4", "frigate:drive": "mjpeg"}


def test_launcher_applies_saved_camera_order_and_appends_new_cameras():
    cameras = [
        {"id": "baba:door", "name": "Door", "site": "Home"},
        {"id": "baba:gate", "name": "Gate", "site": "Home"},
        {"id": "frigate:terrace", "name": "Terrace", "site": "Cabin"},
    ]

    assert [camera["id"] for camera in ordered_cameras(
        cameras, ["baba:gate", "missing", "baba:door"]
    )] == ["baba:gate", "baba:door", "frigate:terrace"]
