from types import SimpleNamespace

import pytest
import httpx
from starlette.requests import Request

from conftest import person_cookie, request, run
from opus import library, playback
from opus.api.routers import photos

SUM = "a" * 40


def test_personal_vault_relay_keeps_resume_metadata_and_range_headers(house, monkeypatch):
    async def scenario():
        def upstream(asked):
            assert asked.headers["range"] == "bytes=4-7"
            assert "x-opus-token" not in asked.headers
            return httpx.Response(200, headers={"X-Vault-At": "12", "X-Vault-Bytes": "20",
                                               "Accept-Ranges": "bytes"})

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        async with httpx.AsyncClient(base_url="http://library/api", transport=httpx.MockTransport(upstream)) as client:
            monkeypatch.setattr(photos, "_personal", lambda: client)
            scope = request({"opus_session": person_cookie("filip")}, {"Range": "bytes=4-7"},
                            method="HEAD", path="/api/photos/vault/123").scope
            response = await photos._as_the_person(Request(scope, receive), "/photos/vault/123", "no person")
            assert response.headers["x-vault-at"] == "12"
            assert response.headers["x-vault-bytes"] == "20"
            assert response.headers["accept-ranges"] == "bytes"
            assert response.headers["cache-control"] == "no-store"
            async for _ in response.body_iterator:
                pass

    run(scenario())


def recording(path, container, codec, width, height, sound=None, transfer=""):
    streams = [{"kind": "video", "position": 0, "codec": codec, "width": width, "height": height,
                "color_transfer": transfer}]
    if sound:
        streams.append({"kind": "audio", "position": 0, "codec": sound, "channels": 2})
    return {"path": str(path), "container": container, "video_codec": codec,
            "width": width, "height": height, "duration_s": 12.0, "streams": streams}


@pytest.fixture
def played(tmp_path, monkeypatch):
    seen = {}
    clip = tmp_path / "clip"
    clip.write_bytes(b"")

    async def facts(path, **params):
        assert path == f"/photos/{SUM}/playback"
        return seen["facts"]

    async def handed(path, kind, keeping=None, asked=None):
        seen.update(mode="direct", path=path)

    async def made(request, command, mode, what):
        seen.update(mode=mode, command=command, what=what)

    monkeypatch.setattr(library, "get", facts)
    monkeypatch.setattr(photos, "_stream", handed)
    monkeypatch.setattr(photos, "rebuilt", made)
    monkeypatch.setattr(playback, "render_node", lambda: "/dev/dri/renderD128")
    monkeypatch.setattr(playback, "render_node_openable", lambda node: True)

    def play(facts, decodes=""):
        seen.clear()
        seen["facts"] = facts
        run(photos.play(SUM, SimpleNamespace(), decodes))
        return seen

    return SimpleNamespace(play=play, clip=clip)


def test_a_phones_h264_goes_through_untouched(played):
    said = played.play(recording(played.clip, "mp4", "h264", 1920, 1080, "aac"))
    assert said["mode"] == "direct" and said["path"] == f"/photos/{SUM}/play"
    assert played.play(recording(played.clip, "mp4", "h264", 1280, 720))["mode"] == "direct"


def test_an_iphone_hevc_with_pcm_sound_keeps_its_picture_on_a_screen_that_decodes_it(played):
    said = played.play(recording(played.clip, "mov", "hevc", 1920, 1080, "pcm_s16le"), decodes="hevc,vp9")
    assert said["mode"] == "remux"
    assert said["command"][said["command"].index("-c:v") + 1] == "copy"
    assert said["what"] == f"photo:{SUM}"


def test_a_divx_is_decoded_on_the_processor_and_encoded_on_the_card(played):
    said = played.play(recording(played.clip, "avi", "mpeg4", 720, 576, "mp3"), decodes="hevc")
    command = said["command"]
    assert said["mode"] == "transcode"
    assert "-hwaccel" not in command
    assert command[command.index("-vf") + 1].startswith("format=nv12,hwupload,scale_vaapi=w=720:h=576")
    assert command[command.index("-c:v") + 1] == "h264_vaapi"


def test_a_4k_hdr_recording_a_screen_cannot_decode_comes_down_to_1080p_and_sdr(played):
    said = played.play(recording(played.clip, "mov", "hevc", 3840, 2160, "aac", transfer="arib-std-b67"))
    command = said["command"]
    picture = command[command.index("-vf") + 1]
    assert said["mode"] == "transcode" and "-hwaccel" in command
    assert "scale_vaapi=w=1920:h=1080" in picture and "tonemap_opencl" in picture


def test_a_recording_the_player_cannot_reach_is_said_so(played, tmp_path):
    with pytest.raises(photos.HTTPException) as refused:
        played.play(recording(tmp_path / "elsewhere", "avi", "mpeg4", 720, 576, "mp3"))
    assert refused.value.status_code == 409
