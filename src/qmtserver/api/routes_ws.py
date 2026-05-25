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
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        return
    finally:
        bus.unsubscribe(queue)
