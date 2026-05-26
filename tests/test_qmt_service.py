from __future__ import annotations

import unittest
from typing import Any

from qmtserver.config import load_settings
from qmtserver.errors import QmtTargetNotConnectedError, QmtTargetNotFoundError
from qmtserver.services.qmt_service import QmtService


class FakeLifecycleService(QmtService):
    def __init__(self) -> None:
        super().__init__(
            load_settings(
                _env_file=None,
                auto_connect=False,
                connect_quote=True,
                connect_trader=False,
            )
        )
        self.disconnect_count = 0
        self.quote_connect_count = 0

    def disconnect(self) -> dict[str, Any]:
        self.disconnect_count += 1
        return super().disconnect()

    def _connect_quote(self) -> None:
        self.quote_connect_count += 1
        self.quote_client = object()
        self.quote_connected = True
        self.quote_address = "127.0.0.1:58610"
        self.quote_data_dir = "datadir"


class FailingQuoteService(QmtService):
    def __init__(self) -> None:
        super().__init__(load_settings(_env_file=None, auto_connect=False, connect_trader=False))

    def _connect_quote(self) -> None:
        raise RuntimeError("quote unavailable")


class QmtServiceLifecycleTests(unittest.TestCase):
    def test_connect_updates_lifecycle(self) -> None:
        service = FakeLifecycleService()

        status = service.connect()

        self.assertEqual(status["lifecycle"]["state"], "connected")
        self.assertTrue(status["quote"]["connected"])
        self.assertEqual(status["quote"]["address"], "127.0.0.1:58610")
        self.assertIsNone(status["lifecycle"]["last_error"])

    def test_connect_failure_records_error_without_raising(self) -> None:
        service = FailingQuoteService()

        status = service.connect()

        self.assertEqual(status["lifecycle"]["state"], "error")
        self.assertIn("quote unavailable", status["lifecycle"]["last_error"])

    def test_disconnect_resets_connections(self) -> None:
        service = FakeLifecycleService()
        service.connect()

        status = service.disconnect()

        self.assertEqual(status["lifecycle"]["state"], "disconnected")
        self.assertFalse(status["quote"]["connected"])
        self.assertFalse(status["trader"]["connected"])

    def test_reconnect_disconnects_before_connecting(self) -> None:
        service = FakeLifecycleService()

        service.reconnect()

        self.assertGreaterEqual(service.disconnect_count, 2)
        self.assertEqual(service.quote_connect_count, 1)

    def test_skips_trader_without_userdata(self) -> None:
        service = FakeLifecycleService()

        status = service.connect()

        self.assertTrue(status["ready"]["trader"])
        self.assertIsNone(status["trader"]["userdata"])

    def test_get_target_raises_stable_errors(self) -> None:
        service = QmtService(load_settings(_env_file=None, auto_connect=False, connect_quote=False))

        with self.assertRaises(QmtTargetNotConnectedError):
            service.get_target("xtdata")
        with self.assertRaises(QmtTargetNotFoundError):
            service.get_target("unknown")


if __name__ == "__main__":
    unittest.main()
