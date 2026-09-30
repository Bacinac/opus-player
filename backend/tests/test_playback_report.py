import logging

import pytest
from fastapi import HTTPException

from opus import auth
from opus.api.routers import app as app_router

from conftest import BOX_TOKEN, person_cookie, request, run


def report() -> app_router.PlaybackReport:
    return app_router.PlaybackReport(
        app="biz.boskovic.opus.player", version="v0.1.472", device="NVIDIA SHIELD / Android 11",
        url="https://opus.example/api/play/episode/3171/stream",
        events=["+0ms open at 0.0s", "+4100ms no picture drawn for 4000ms while the sound plays"],
    )


def test_a_box_that_was_let_in_is_heard(house, caplog):
    caplog.set_level(logging.WARNING)
    run(app_router.playback_report(report(), request({auth.DEVICE_COOKIE: BOX_TOKEN})))
    assert "reported by Dnevni boravak for https://opus.example/api/play/episode/3171/stream" in caplog.text
    assert "no picture drawn" in caplog.text


def test_a_person_is_heard(house, caplog):
    caplog.set_level(logging.WARNING)
    run(app_router.playback_report(report(), request({"opus_session": person_cookie("filip")})))
    assert "reported by filip" in caplog.text


def test_a_stranger_cannot_fill_the_log(house):
    with pytest.raises(HTTPException) as refused:
        run(app_router.playback_report(report(), request()))
    assert refused.value.status_code == 401
