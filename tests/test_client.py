from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import TracebackType
from typing import Any

import httpx

from qmtserver.client import QmtAuthError, QmtClient, QmtRpcError
from qmtserver.client.events import build_ws_url
from qmtserver.errors import ERROR_CODE_VALUES


class ClientTests(unittest.TestCase):
    def test_health_calls_endpoint_with_token(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/v1/health")
            self.assertEqual(request.headers["Authorization"], "Bearer dev-token")
            return httpx.Response(200, json={"ok": True, "api_versions": ["v1"]})

        client = QmtClient(
            "http://qmt.test",
            token="dev-token",
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual(client.version(), {"ok": True, "api_versions": ["v1"]})

    def test_rpc_sends_payload_and_returns_data(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            self.assertEqual(request.url.path, "/v1/rpc")
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
                    "meta": {"request_id": "rpc-request"},
                },
            )

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        with self.assertRaises(QmtRpcError) as raised:
            client.rpc("trader", "order_stock")

        self.assertEqual(raised.exception.code, "METHOD_NOT_ALLOWED")
        self.assertEqual(raised.exception.target, "trader")
        self.assertEqual(raised.exception.request_id, "rpc-request")

    def test_auth_error_raises_typed_exception(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401,
                headers={"X-Request-ID": "auth-request"},
                json={"detail": {"code": "UNAUTHORIZED", "message": "bad token"}},
            )

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        with self.assertRaises(QmtAuthError) as raised:
            client.status()

        self.assertEqual(raised.exception.code, "UNAUTHORIZED")
        self.assertEqual(raised.exception.message, "bad token")
        self.assertEqual(raised.exception.request_id, "auth-request")

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

        event = next(iter(client.events(types=["stock_trade"])))

        self.assertEqual(
            seen["url"],
            "ws://qmt.test/v1/ws/events?token=dev-token&types=stock_trade",
        )
        self.assertEqual(seen["headers"], {"Authorization": "Bearer dev-token"})
        self.assertEqual(event["type"], "heartbeat")

    def test_orders_trades_and_recent_events_helpers(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/v1/orders":
                self.assertEqual(request.url.params["limit"], "1")
                return httpx.Response(200, json={"ok": True, "data": [{"order_id": 1}]})
            if request.url.path == "/v1/orders/1":
                return httpx.Response(200, json={"ok": True, "data": {"order_id": 1}})
            if request.url.path == "/v1/trades":
                return httpx.Response(200, json={"ok": True, "data": [{"trade_id": 2}]})
            if request.url.path == "/v1/events/recent":
                self.assertEqual(request.url.params["types"], "stock_trade")
                return httpx.Response(200, json={"ok": True, "data": [{"type": "stock_trade"}]})
            raise AssertionError(request.url.path)

        client = QmtClient("http://qmt.test", transport=httpx.MockTransport(handler))

        self.assertEqual(client.orders(limit=1), [{"order_id": 1}])
        self.assertEqual(client.order("1"), {"order_id": 1})
        self.assertEqual(client.trades(), [{"trade_id": 2}])
        self.assertEqual(client.recent_events(types=["stock_trade"]), [{"type": "stock_trade"}])

    def test_build_ws_url_preserves_https(self) -> None:
        self.assertEqual(
            build_ws_url("https://qmt.test/api", "token"),
            "wss://qmt.test/api/v1/ws/events?token=token",
        )

    def test_client_can_disable_api_version_prefix(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.url.path, "/health")
            return httpx.Response(200, json={"ok": True})

        client = QmtClient(
            "http://qmt.test",
            api_version=None,
            transport=httpx.MockTransport(handler),
        )

        self.assertEqual(client.health(), {"ok": True})

    def test_error_code_docs_match_code_registry(self) -> None:
        docs = (Path(__file__).parents[1] / "docs" / "errors.md").read_text(encoding="utf-8")

        for code in ERROR_CODE_VALUES:
            self.assertIn(f"`{code}`", docs)


if __name__ == "__main__":
    unittest.main()
