"""The Library's radio stations, as the player plays them."""

import time

from opus import library

# the list changes when somebody adds a station, and the DAC and the house ask
# what is on every two seconds
_kept: tuple[float, list[dict]] = (0.0, [])
_KEPT_FOR = 60


async def listed() -> list[dict]:
    """Every station, in the Library's order. Raises library.LibraryError."""
    global _kept
    at, kept = _kept
    if kept and time.monotonic() - at < _KEPT_FOR:
        return kept
    found = (await library.get("/music/radio/stations"))["stations"]
    _kept = (time.monotonic(), found)
    return found


async def by_address(url: str) -> dict | None:
    return next((s for s in await listed() if s["url"] == url), None)


async def by_id(station_id: int) -> dict | None:
    return next((s for s in await listed() if s["id"] == station_id), None)
