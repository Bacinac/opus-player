from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.responses import Response

from conftest import request, run
from opus import library
from opus.api.routers import system


@pytest.fixture
def clock(monkeypatch):
    now = {"at": 5000.0}
    monkeypatch.setattr(system, "time", SimpleNamespace(monotonic=lambda: now["at"]))
    monkeypatch.setattr(system, "_asked", {})
    monkeypatch.setattr(system, "_recent", [])
    return now


def refused(address: str) -> HTTPException:
    with pytest.raises(HTTPException) as caught:
        system._admit_pairing(address)
    assert caught.value.status_code == 429
    return caught.value


def test_one_address_asks_for_a_few_codes(clock):
    for _ in range(system.PAIR_PER_ADDRESS):
        system._admit_pairing("192.168.1.38")
    assert int(refused("192.168.1.38").headers["Retry-After"]) == system.PAIR_WINDOW + 1
    system._admit_pairing("192.168.1.30")
    clock["at"] += system.PAIR_WINDOW
    system._admit_pairing("192.168.1.38")


def test_an_ipv6_network_is_one_caller(clock):
    for n in range(system.PAIR_PER_ADDRESS):
        system._admit_pairing(f"2001:db8:1:2::{n + 1:x}")
    refused("2001:db8:1:2:ffff:ffff:ffff:ffff")
    system._admit_pairing("2001:db8:1:3::1")


def test_a_few_callers_cannot_lock_everybody_out(clock):
    callers = system.PAIR_BURST // system.PAIR_PER_ADDRESS - 1
    for n in range(callers):
        for _ in range(system.PAIR_PER_ADDRESS):
            system._admit_pairing(f"10.0.{n}.1")
        refused(f"10.0.{n}.1")
    system._admit_pairing("192.168.1.38")


def test_asks_at_once_are_bounded_for_a_minute(clock):
    for n in range(system.PAIR_BURST):
        system._admit_pairing(f"10.0.{n}.1")
    said = refused("10.1.0.1")
    assert "at once" in said.detail
    assert int(said.headers["Retry-After"]) == system.PAIR_BURST_WINDOW + 1
    clock["at"] += system.PAIR_BURST_WINDOW
    system._admit_pairing("10.1.0.1")
    assert len(system._recent) == 1


def test_a_slot_given_back_is_room_again(clock):
    slots = [system._admit_pairing(f"10.0.{n}.1") for n in range(system.PAIR_BURST)]
    system._recent.remove(slots[0])
    system._admit_pairing("10.2.0.1")


@pytest.mark.parametrize("answer", [library.LibraryError("down"), {"code": "ABCD-EFGH"}])
def test_a_code_the_library_did_not_give_hands_its_slot_back(clock, monkeypatch, answer):
    async def ask(path, body):
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(library, "post", ask)
    with pytest.raises(HTTPException) as failed:
        run(system.auth_pair(request(method="POST", path="/api/auth/pair"), Response()))
    assert failed.value.status_code == 502
    assert system._recent == []
