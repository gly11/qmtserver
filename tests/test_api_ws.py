from __future__ import annotations

import unittest

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from qmtserver.api import create_app
from qmtserver.config import load_settings


class ApiWebSocketTests(unittest.TestCase):
    def test_websocket_receives_heartbeat(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, ws_heartbeat_seconds=0.01),
            connect_on_startup=False,
        )

        with TestClient(app) as client, client.websocket_connect("/ws/events") as websocket:
            event = websocket.receive_json()

        self.assertEqual(event["type"], "heartbeat")

    def test_v1_websocket_receives_heartbeat(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, ws_heartbeat_seconds=0.01),
            connect_on_startup=False,
        )

        with TestClient(app) as client, client.websocket_connect("/v1/ws/events") as websocket:
            event = websocket.receive_json()

        self.assertEqual(event["type"], "heartbeat")

    def test_websocket_receives_published_event(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with TestClient(app) as client, client.websocket_connect("/ws/events") as websocket:
            app.state.event_bus.publish_threadsafe("qmt_connected", {"ok": True})
            event = websocket.receive_json()

        self.assertEqual(event["type"], "qmt_connected")
        self.assertEqual(event["data"], {"ok": True})

    def test_websocket_filters_event_types(self) -> None:
        app = create_app(load_settings(auto_connect=False), connect_on_startup=False)

        with (
            TestClient(app) as client,
            client.websocket_connect("/ws/events?types=stock_trade") as websocket,
        ):
            app.state.event_bus.publish_threadsafe("stock_order", {"order_id": 1})
            app.state.event_bus.publish_threadsafe("stock_trade", {"trade_id": 2})
            event = websocket.receive_json()

        self.assertEqual(event["type"], "stock_trade")
        self.assertEqual(event["data"], {"trade_id": 2})

    def test_websocket_requires_token_when_configured(self) -> None:
        app = create_app(
            load_settings(auto_connect=False, api_token="dev-token"),
            connect_on_startup=False,
        )

        with TestClient(app) as client:
            with self.assertRaises(WebSocketDisconnect), client.websocket_connect("/ws/events"):
                pass

            with client.websocket_connect("/ws/events?token=dev-token") as websocket:
                app.state.event_bus.publish_threadsafe("qmt_connected", {"ok": True})
                event = websocket.receive_json()

        self.assertEqual(event["type"], "qmt_connected")


if __name__ == "__main__":
    unittest.main()
