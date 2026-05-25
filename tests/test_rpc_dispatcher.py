from __future__ import annotations

import unittest

from qmtserver.rpc import RpcDispatcher
from qmtserver.rpc.dispatcher import RpcCall
from tests.fakes import DisconnectedTraderService, FakeService, rpc_error_code


class RpcDispatcherTests(unittest.TestCase):
    def test_rejects_trading_when_disabled(self) -> None:
        dispatcher = RpcDispatcher(FakeService())
        result = dispatcher.dispatch(
            RpcCall(target="trader", method="order_stock", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRADING_DISABLED")

    def test_dispatches_whitelisted_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService())
        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="get_full_tick", args=[["000001.SZ"]], kwargs={})
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], {"codes": ["000001.SZ"]})

    def test_audit_log_records_rpc_summary(self) -> None:
        dispatcher = RpcDispatcher(FakeService())

        with self.assertLogs("qmtserver.audit", level="INFO") as logs:
            dispatcher.dispatch(
                RpcCall(
                    target="xtdata",
                    method="get_full_tick",
                    args=[["000001.SZ"]],
                    kwargs={},
                )
            )

        output = "\n".join(logs.output)
        self.assertIn("target=xtdata", output)
        self.assertIn("method=get_full_tick", output)
        self.assertIn("level=readonly", output)
        self.assertIn("ok=True", output)

    def test_returns_stable_target_error_code(self) -> None:
        dispatcher = RpcDispatcher(DisconnectedTraderService())
        result = dispatcher.dispatch(
            RpcCall(target="trader", method="query_stock_asset", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TARGET_NOT_CONNECTED")


if __name__ == "__main__":
    unittest.main()
