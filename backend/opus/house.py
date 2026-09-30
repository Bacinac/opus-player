"""What the player asks of DIDA, the house's automation.

The player decides what plays and serves the bytes; the house's devices — the
receiver and its inputs, its zones and its level — answer to DIDA, and every
command to them goes through DIDA's one door. The DAC is the exception because
it is not the house's: it hangs off this host and plays through this module's
own MPD. The bytes never pass through DIDA: renderers pull the stream from this
module with a ticket."""

from opus_core.dida import call


async def command(config, entity_id: str, capability: str, cmd: str,
                  args: dict | None = None) -> None:
    await call(config, "POST", "/api/command", json={
        "entity_id": entity_id, "capability": capability,
        "command": cmd, "args": args or {},
    })


async def state(config, entity_id: str) -> dict:
    """One entity's registry row and live values, flattened to {capability: value}."""
    detail = await call(config, "GET", f"/api/entities/{entity_id}/detail")
    values = {row["capability"]: row["value"] for row in detail.get("state") or []}
    return {"name": detail.get("name") or entity_id, "values": values}


async def entities(config) -> list:
    """Every entity DIDA will show us — name, adapter, device_type, area."""
    return await call(config, "GET", "/api/entities")


async def snapshot(config) -> list:
    """The current values DIDA exposes to this household client."""
    return await call(config, "GET", "/api/state")


async def areas(config) -> list:
    return await call(config, "GET", "/api/areas")


async def camera_layout(config) -> dict:
    """The household camera order shared by DIDA's camera surfaces."""
    return await call(config, "GET", "/api/camera/layout")


async def set_camera_layout(config, order: list[str], spans: dict) -> None:
    """Keep DIDA's existing spans while changing the shared camera order."""
    await call(config, "PUT", "/api/camera/layout", json={
        "order": order,
        "spans": spans,
    })
