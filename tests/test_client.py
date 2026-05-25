from __future__ import annotations

import json
import unittest
from types import TracebackType
from typing import Any

import httpx

from qmtserver.client import QmtAuthError, QmtClient, QmtRpcError
from qmtserver.client.events import build_ws_url


class ClientTests(unittest.TestCase):
    def test_health_calls_endpoint_with_token(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/health")
            self.assertEqual(request.headers["Authorization"], "Bearer dev-token")
            return httpx.Response(200, json={"ok": True})

        client = QmtClient(
            "http://qmt.test",
            token="dev-token",
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual(client.health(), {"ok": True})

    def test_rpc_sends_payload_and_returns_data(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(payload["target"], "xtdata")
            self.assertEqual(payload["method"], "get_full_tick")
            self.assertEqual(payload["args"], [["000001.SZ"]])
            return httpx.Response(200, json={"ok": True, "data": {"tick": 1}})

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        self.assertEqual(
            client.rpc("xtdata", "get_full_tick", [["000001.SZ"]]),
            {"tick": 1},
        )

    def test_rpc_error_raises_typed_exception(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "ok": False,
                    "data": None,
                    "error": {"code": "METHOD_NOT_ALLOWED", "message": "blocked"},
                },
            )

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        with self.assertRaises(QmtRpcError) as raised:
            client.rpc("trader", "order_stock")

        self.assertEqual(raised.exception.code, "METHOD_NOT_ALLOWED")
        self.assertEqual(raised.exception.target, "trader")

    def test_auth_error_raises_typed_exception(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"detail": {"code": "UNAUTHORIZED"}})

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        with self.assertRaises(QmtAuthError):
            client.status()

    def test_dynamic_proxy_calls_rpc(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(payload["target"], "xtdata")
            self.assertEqual(payload["method"], "get_full_tick")
            return httpx.Response(200, json={"ok": True, "data": {"codes": ["000001.SZ"]}})

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        self.assertEqual(
            client.xtdata.get_full_tick(["000001.SZ"]),
            {"codes": ["000001.SZ"]},
        )

    def test_event_stream_parses_events(self) -> None:
        seen: dict[str, Any] = {}

        class FakeWebSocket:
            def __enter__(self) -> FakeWebSocket:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                traceback: TracebackType | None,
            ) -> None:
                return None

            def recv(self) -> str:
                return json.dumps({"type": "heartbeat", "data": {"service": "qmtserver"}})

        def connect_factory(*args: Any, **kwargs: Any) -> FakeWebSocket:
            seen["url"] = args[0]
            seen["headers"] = kwargs["additional_headers"]
            return FakeWebSocket()

        client = QmtClient(
            "http://qmt.test",
            token="dev-token",
            event_connect_factory=connect_factory,
        )

        event = next(iter(client.events()))

        self.assertEqual(seen["url"], "ws://qmt.test/ws/events?token=dev-token")
        self.assertEqual(seen["headers"], {"Authorization": "Bearer dev-token"})
        self.assertEqual(event["type"], "heartbeat")

    def test_build_ws_url_preserves_https(self) -> None:
        self.assertEqual(
            build_ws_url("https://qmt.test/api", "token"),
            "wss://qmt.test/ws/events?token=token",
        )


if __name__ == "__main__":
    unittest.main()
