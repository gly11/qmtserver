from __future__ import annotations

import unittest

from qmtserver.rpc import RpcDispatcher
from qmtserver.rpc.dispatcher import RpcCall
from tests.fakes import FakeService, rpc_error_code


class TransparentRpcTests(unittest.TestCase):
    def test_unknown_method_is_rejected_when_transparent_rpc_disabled(self) -> None:
        dispatcher = RpcDispatcher(FakeService())

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="get_sector_list", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "METHOD_NOT_ALLOWED")
        self.assertNotIn("level", result["meta"])

    def test_dispatches_allowed_xtdata_public_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="get_sector_list", args=[], kwargs={})
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], ["沪深A股"])
        self.assertEqual(result["meta"]["level"], "transparent")

    def test_rejects_target_outside_transparent_allowlist(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(transparent_rpc=True, transparent_rpc_targets="xtdata")
        )

        result = dispatcher.dispatch(
            RpcCall(target="unknown", method="get_sector_list", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_TARGET_NOT_ALLOWED")
        self.assertEqual(result["meta"]["level"], "transparent")

    def test_rejects_private_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="_private", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_METHOD_DENIED")

    def test_rejects_dunder_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="__getattribute__", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_METHOD_DENIED")

    def test_rejects_non_identifier_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="nested.method", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_METHOD_DENIED")

    def test_non_callable_attribute_returns_method_not_found(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="non_callable", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "METHOD_NOT_FOUND")
        self.assertEqual(result["meta"]["level"], "transparent")

    def test_trader_is_denied_by_default(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(transparent_rpc=True, transparent_rpc_targets="xtdata,trader")
        )

        result = dispatcher.dispatch(
            RpcCall(target="trader", method="query_unknown_asset", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_TRADER_DENIED")

    def test_trading_like_method_is_denied_by_default(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="buy_signal", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRANSPARENT_TRADING_DENIED")

    def test_transparent_trading_like_method_cannot_bypass_trading_switch(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(transparent_rpc=True, transparent_rpc_allow_trading=True)
        )

        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="buy_signal", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRADING_DISABLED")

    def test_transparent_call_is_audited(self) -> None:
        dispatcher = RpcDispatcher(FakeService(transparent_rpc=True))

        with self.assertLogs("qmtserver.audit", level="INFO") as logs:
            dispatcher.dispatch(
                RpcCall(target="xtdata", method="get_sector_list", args=[], kwargs={})
            )

        output = "\n".join(logs.output)
        self.assertIn("target=xtdata", output)
        self.assertIn("method=get_sector_list", output)
        self.assertIn("level=transparent", output)
        self.assertIn("ok=True", output)


if __name__ == "__main__":
    unittest.main()
