import pytest
from fastapi import HTTPException

from conftest import run
from opus import settings_store
from opus.api.routers import system


def test_the_route_says_which_key_and_why():
    with pytest.raises(HTTPException) as refused:
        run(system.write_settings({"nope": "1"}))
    assert refused.value.status_code == 400
    assert refused.value.detail == {"key": "nope", "code": "unknown_key"}


@pytest.mark.parametrize("value", ["x", "1.5", "²"])
def test_the_television_is_a_box_number(settings_table, value):
    with pytest.raises(settings_store.SettingsValidationError):
        run(settings_store.update_settings({"tv_box": value}))
    assert settings_table.rows == {}


def test_the_television_may_be_left_to_whichever_box_listens(settings_table):
    run(settings_store.update_settings({"tv_box": "7"}))
    run(settings_store.update_settings({"tv_box": ""}))
    assert settings_table.rows == {"tv_box": ""}


def test_the_house_token_is_neither_shown_nor_typed(settings_table):
    settings_table.rows["access_house_token"] = "minted"
    assert "access_house_token" not in {s["key"] for s in run(settings_store.get_for_ui())}
    with pytest.raises(settings_store.SettingsValidationError) as refused:
        run(settings_store.update_settings({"access_house_token": "chosen"}))
    assert refused.value.code == "not_editable"
