from __future__ import annotations

import unittest

from qmtserver.events import Event, EventBus
from qmtserver.miniqmt import MiniQmtCallback


class EventBusTests(unittest.IsolatedAsyncioTestCase):
    async def test_broadcasts_to_multiple_subscribers(self) -> None:
        bus = EventBus()
        first = await bus.subscribe()
        second = await bus.subscribe()

        await bus.publish("qmt_connected", {"ok": True})

        self.assertEqual((await first.get()).type, "qmt_connected")
        self.assertEqual((await second.get()).data, {"ok": True})

    async def test_unsubscribe_stops_delivery(self) -> None:
        bus = EventBus()
        queue = await bus.subscribe()
        bus.unsubscribe(queue)

        await bus.publish("qmt_connected")

        self.assertTrue(queue.empty())

    async def test_drops_oldest_event_when_queue_is_full(self) -> None:
        bus = EventBus(queue_size=1)
        queue = await bus.subscribe()

        await bus.publish("first")
        await bus.publish("second")

        self.assertEqual((await queue.get()).type, "second")


class EventModelTests(unittest.TestCase):
    def test_event_is_json_friendly(self) -> None:
        event = Event("heartbeat", {"service": "qmtserver"}, {"sequence": 1})

        self.assertEqual(event.to_dict()["type"], "heartbeat")
        self.assertEqual(event.to_dict()["data"], {"service": "qmtserver"})

    def test_callback_records_event_types(self) -> None:
        callback = MiniQmtCallback()

        callback.on_connected()
        callback.on_stock_order({"order_id": 1})
        callback.on_stock_trade({"trade_id": 2})
        callback.on_order_error({"error": "bad order"})
        callback.on_cancel_error({"error": "bad cancel"})

        self.assertIn("connected", callback.events)
        self.assertIn("stock_order:{'order_id': 1}", callback.events)
        self.assertIn("stock_trade:{'trade_id': 2}", callback.events)
        self.assertIn("order_error:{'error': 'bad order'}", callback.events)
        self.assertIn("cancel_error:{'error': 'bad cancel'}", callback.events)


if __name__ == "__main__":
    unittest.main()
