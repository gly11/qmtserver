from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from qmtserver.events.models import Event


class EventBus:
    def __init__(self, *, queue_size: int = 1000) -> None:
        self.queue_size = queue_size
        self._subscribers: set[asyncio.Queue[Event]] = set()
        self._sequence = 0
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue[Event]:
        self._remember_loop()
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self.queue_size)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[Event]) -> None:
        self._subscribers.discard(queue)

    async def publish(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> Event:
        self._remember_loop()
        async with self._lock:
            self._sequence += 1
            event_meta = {"source": "qmtserver", "sequence": self._sequence}
            if meta:
                event_meta.update(meta)
            event = Event(event_type, data or {}, event_meta)

        for queue in list(self._subscribers):
            _put_drop_oldest(queue, event)
        return event

    def publish_threadsafe(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self._loop

        if loop is None:
            return

        if loop.is_running():
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.publish(event_type, data, meta))
            )

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def _remember_loop(self) -> None:
        with contextlib.suppress(RuntimeError):
            self._loop = asyncio.get_running_loop()


def _put_drop_oldest(queue: asyncio.Queue[Event], event: Event) -> None:
    if queue.full():
        with contextlib.suppress(asyncio.QueueEmpty):
            queue.get_nowait()
    with contextlib.suppress(asyncio.QueueFull):
        queue.put_nowait(event)
