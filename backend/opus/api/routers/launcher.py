"""Small household facts for the native television launcher.

The Shield already has a revocable OPUS box session.  It asks this endpoint,
and Player uses its existing machine credential to ask DIDA; no DIDA secret is
put in the APK. The result is deliberately narrow: a few household facts and
the camera wall, not the complete state of the house.
"""

import asyncio
import json
import re
from typing import Literal
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from opus_core import dida
from pydantic import BaseModel

from opus import house
from opus.settings_store import current_runtime

router = APIRouter()


class CameraOrder(BaseModel):
    order: list[str]


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sensor(entity: dict, values: dict[str, dict[str, object]], area_kind: dict[object, str]) -> dict | None:
    current = values.get(entity.get("entity_id", ""), {})
    temperature = _number(current.get("temperature"))
    if temperature is None:
        return None
    wind_ms = _number(current.get("wind_speed"))
    return {
        "id": entity.get("entity_id", ""),
        "area": area_kind.get(entity.get("area_id")),
        "temperature_c": temperature,
        "humidity_pct": _number(current.get("humidity")),
        "wind_kmh": round(wind_ms * 3.6, 2) if wind_ms is not None else None,
        "rain_mm": _number(current.get("rain_daily")),
    }


def camera_list(entities: list[dict], states: list[dict]) -> list[dict]:
    """Camera names and sites only; upstream addresses never leave DIDA."""
    descriptors = {
        row.get("entity_id", ""): row.get("value")
        for row in states if row.get("capability") == "camera"
    }
    cameras = []
    for entity in entities:
        entity_id = entity.get("entity_id", "")
        if ("camera" not in (entity.get("capabilities") or []) or
                entity.get("exposed") is False or entity_id not in descriptors):
            continue
        try:
            descriptor = json.loads(descriptors[entity_id]) if isinstance(descriptors[entity_id], str) else descriptors[entity_id]
        except (TypeError, ValueError):
            descriptor = {}
        if not isinstance(descriptor, dict):
            descriptor = {}
        cameras.append({
            "id": entity_id,
            "name": entity.get("label") or entity.get("name") or entity_id,
            "site": descriptor.get("site"),
            "live": next((kind for kind in ("mp4", "mjpeg") if descriptor.get(kind)), None),
        })
    return sorted(cameras, key=lambda item: ((item["site"] or "").casefold(), item["name"].casefold()))


def ordered_cameras(cameras: list[dict], order: list[str]) -> list[dict]:
    """Apply DIDA's saved order without losing newly discovered cameras."""
    remaining = {camera["id"]: camera for camera in cameras}
    result = [remaining.pop(entity_id) for entity_id in order if entity_id in remaining]
    return result + sorted(
        remaining.values(),
        key=lambda item: ((item["site"] or "").casefold(), item["name"].casefold()),
    )


def summarize(entities: list[dict], states: list[dict], areas: list[dict]) -> dict:
    """Turn DIDA's generic capability rows into a stable launcher contract."""
    values: dict[str, dict[str, object]] = {}
    for row in states:
        values.setdefault(row.get("entity_id", ""), {})[row.get("capability", "")] = row.get("value")

    area_kind = {area.get("id"): area.get("kind", "") for area in areas}
    candidates = [
        (entity, _sensor(entity, values, area_kind))
        for entity in entities if entity.get("exposed") is not False
    ]
    candidates = [(entity, sensor) for entity, sensor in candidates if sensor is not None]

    living_candidates = [pair for pair in candidates if pair[1]["area"] == "living"]
    living_candidates.sort(key=lambda pair: (
        pair[1]["humidity_pct"] is None,
        pair[0].get("adapter") != "ecowitt",
        pair[0].get("entity_id", ""),
    ))
    living = living_candidates[0][1] if living_candidates else None

    outside_candidates = [pair for pair in candidates if pair[1]["area"] == "outdoor"]
    living_ids = {pair[0].get("entity_id", "") for pair in living_candidates}
    outside_candidates.sort(key=lambda pair: (
        pair[0].get("entity_id", "").removesuffix(":outdoor") + ":indoor" not in living_ids,
        pair[1]["wind_kmh"] is None,
        pair[1]["humidity_pct"] is None,
        pair[0].get("entity_id", ""),
    ))
    outside = outside_candidates[0][1] if outside_candidates else None

    return {"outside": outside, "living": living}


@router.get("/launcher/glance")
async def glance():
    config = await current_runtime()
    try:
        entities, states, areas = await asyncio.gather(
            house.entities(config),
            house.snapshot(config),
            house.areas(config),
        )
    except dida.DidaError:
        # The clock and the launcher remain useful when DIDA or the network is
        # down. An empty answer is a temporary absence, not a launcher failure.
        return {"outside": None, "living": None}
    return summarize(entities, states, areas)


@router.get("/launcher/cameras")
async def cameras():
    config = await current_runtime()
    try:
        entities, states = await asyncio.gather(house.entities(config), house.snapshot(config))
    except dida.DidaError:
        return {"cameras": []}
    try:
        layout = await house.camera_layout(config)
    except dida.DidaError:
        layout = {}
    cameras = ordered_cameras(camera_list(entities, states), layout.get("order") or [])
    spans = layout.get("spans") if isinstance(layout.get("spans"), dict) else {}
    return {"cameras": [
        {**camera, "span": spans.get(camera["id"], {})}
        for camera in cameras
    ]}


@router.put("/launcher/cameras/order")
async def save_camera_order(wanted: CameraOrder):
    config = await current_runtime()
    try:
        entities, states, layout = await asyncio.gather(
            house.entities(config), house.snapshot(config), house.camera_layout(config))
        visible = {camera["id"] for camera in camera_list(entities, states)}
        order = []
        for entity_id in wanted.order[:128]:
            if entity_id in visible and entity_id not in order:
                order.append(entity_id)
        order.extend(sorted(visible - set(order)))
        await house.set_camera_layout(config, order, layout.get("spans") or {})
    except dida.DidaError as exc:
        raise HTTPException(502, "camera order unavailable") from exc
    return {"order": order}


async def _camera_path(config, entity_id: str, kind: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_:.-]{1,128}", entity_id) or entity_id in (".", ".."):
        raise HTTPException(404, "no camera")
    entities = await house.entities(config)
    if not any(entity.get("entity_id") == entity_id
               and "camera" in (entity.get("capabilities") or [])
               and entity.get("exposed") is not False for entity in entities):
        raise HTTPException(404, "no camera")
    return f"/api/camera/{quote(entity_id, safe='')}/{kind}"


@router.get("/launcher/cameras/{entity_id}/snapshot")
async def camera_snapshot(entity_id: str, w: int = Query(640, ge=160, le=1920)):
    config = await current_runtime()
    try:
        path = await _camera_path(config, entity_id, "snapshot")
        body, media_type = await dida.content(config, f"{path}?{urlencode({'w': w})}")
    except dida.DidaError as exc:
        raise HTTPException(502, "camera unavailable") from exc
    return Response(body, media_type=media_type, headers={"Cache-Control": "no-store"})


@router.get("/launcher/cameras/{entity_id}/{kind}")
async def camera_stream(entity_id: str, kind: Literal["mp4", "mjpeg"]):
    config = await current_runtime()
    try:
        path = await _camera_path(config, entity_id, kind)
        body, media_type = await dida.stream(config, path)
    except dida.DidaError as exc:
        raise HTTPException(502, "camera stream unavailable") from exc
    return StreamingResponse(body, media_type=media_type, headers={"Cache-Control": "no-store"})
