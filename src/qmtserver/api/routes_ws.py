from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from qmtserver.events import Event, EventBus
from qmtserver.security import authenticate_websocket

router = APIRouter(tags=["events"])


@router.websocket("/ws/events")
async def events(websocket: WebSocket) -> None:
    if not authenticate_websocket(websocket):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    bus: EventBus = websocket.app.state.event_bus
    queue = await bus.subscribe()
    heartbeat_seconds: float = websocket.app.state.settings.ws_heartbeat_seconds
    event_types = _parse_types(websocket.query_params.get("types"))

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=heartbeat_seconds)
            except TimeoutError:
                event = Event(
                    "heartbeat",
                    {"service": "qmtserver"},
                    {"source": "qmtserver", "sequence": None},
                )
            if event.type != "heartbeat" and event_types and event.type not in event_types:
                continue
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        return
    finally:
        bus.unsubscribe(queue)


def _parse_types(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {item.strip() for item in value.split(",") if item.strip()}
