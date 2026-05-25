from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.config import load_settings
from qmtserver.errors import QmtTargetNotConnectedError
from qmtserver.rpc import RpcDispatcher, allowed_methods, is_method_allowed
from qmtserver.rpc.dispatcher import RpcCall
from qmtserver.rpc.serializers import convert_input, to_jsonable


class FakeTarget:
    def get_full_tick(self, codes: list[str]) -> dict[str, object]:
        return {"codes": codes}


class FakeService:
    def get_target(self, target: str) -> FakeTarget:
        if target != "xtdata":
            raise QmtTargetNotConnectedError("target is not connected")
        return FakeTarget()


class RpcTests(unittest.TestCase):
    def test_allowed_methods_are_sorted(self) -> None:
        methods = allowed_methods()

        self.assertIn("xtdata", methods)
        self.assertEqual(methods["xtdata"], sorted(methods["xtdata"]))

    def test_rejects_non_whitelisted_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService())
        result = dispatcher.dispatch(
            RpcCall(target="trader", method="order_stock", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "METHOD_NOT_ALLOWED")

    def test_dispatches_whitelisted_method(self) -> None:
        dispatcher = RpcDispatcher(FakeService())
        result = dispatcher.dispatch(
            RpcCall(target="xtdata", method="get_full_tick", args=[["000001.SZ"]], kwargs={})
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], {"codes": ["000001.SZ"]})

    def test_stock_account_conversion(self) -> None:
        account = convert_input(
            {
                "__type__": "StockAccount",
                "account_id": "10001",
                "account_type": "STOCK",
            }
        )

        self.assertEqual(account.account_id, "10001")

    def test_to_jsonable_converts_objects(self) -> None:
        class Item:
            def __init__(self) -> None:
                self.value = Path("x")
                self._hidden = "secret"

        self.assertEqual(to_jsonable(Item()), {"value": "x"})

    def test_method_allowlist(self) -> None:
        self.assertTrue(is_method_allowed("xtdata", "get_full_tick"))
        self.assertFalse(is_method_allowed("trader", "order_stock"))

    def test_returns_stable_target_error_code(self) -> None:
        dispatcher = RpcDispatcher(FakeService())
        result = dispatcher.dispatch(
            RpcCall(target="trader", method="query_stock_asset", args=[], kwargs={})
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "TARGET_NOT_CONNECTED")

    def test_settings_import_keeps_dev_dependency_visible(self) -> None:
        self.assertEqual(load_settings().account_type, "STOCK")


if __name__ == "__main__":
    unittest.main()
