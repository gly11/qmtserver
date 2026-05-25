from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.config import load_settings
from qmtserver.errors import QmtTargetNotConnectedError
from qmtserver.rpc import RpcDispatcher, allowed_methods, is_method_allowed, method_specs
from qmtserver.rpc.dispatcher import RpcCall
from qmtserver.rpc.serializers import convert_input, to_jsonable


class FakeTarget:
    def get_full_tick(self, codes: list[str]) -> dict[str, object]:
        return {"codes": codes}


class FakeTrader:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def query_stock_asset(self, account: object) -> dict[str, object]:
        return {"account_id": getattr(account, "account_id", None)}

    def order_stock(self, *args: object) -> int:
        self.calls.append(("order_stock", args))
        return 10001

    def cancel_order_stock(self, *args: object) -> int:
        self.calls.append(("cancel_order_stock", args))
        return 0


class FakeService:
    def __init__(
        self,
        *,
        enable_trading: bool = False,
        trading_dry_run: bool = True,
        account_id: str | None = None,
        max_order_volume: int = 100000,
        max_order_amount: float = 1000000,
    ) -> None:
        self.settings = load_settings(
            auto_connect=False,
            enable_trading=enable_trading,
            trading_dry_run=trading_dry_run,
            account_id=account_id,
            max_order_volume=max_order_volume,
            max_order_amount=max_order_amount,
        )
        self.trader = FakeTrader()

    def get_target(self, target: str) -> object:
        if target == "trader":
            return self.trader
        if target != "xtdata":
            raise QmtTargetNotConnectedError("target is not connected")
        return FakeTarget()


class DisconnectedTraderService(FakeService):
    def get_target(self, target: str) -> object:
        if target == "trader":
            raise QmtTargetNotConnectedError("target is not connected")
        return super().get_target(target)


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
        self.assertEqual(result["error"]["code"], "TRADING_DISABLED")

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
        self.assertTrue(is_method_allowed("trader", "order_stock"))
        self.assertFalse(is_method_allowed("trader", "unknown_method"))

    def test_method_specs_include_trading_metadata(self) -> None:
        specs = method_specs()
        trader_specs = {item["method"]: item for item in specs["trader"]}

        self.assertEqual(trader_specs["order_stock"]["level"], "trading")
        self.assertTrue(trader_specs["order_stock"]["enabled"])
        self.assertIn("order_stock", allowed_methods()["trader"])

    def test_trading_dry_run_does_not_call_trader(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=True, account_id="10001")
        dispatcher = RpcDispatcher(service)
        result = dispatcher.dispatch(
            RpcCall(
                target="trader",
                method="order_stock",
                args=[
                    {"__type__": "StockAccount", "account_id": "10001"},
                    "000001.SZ",
                    23,
                    100,
                    5,
                    10.5,
                ],
                kwargs={},
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["dry_run"], True)
        self.assertEqual(service.trader.calls, [])

    def test_real_trading_path_calls_trader_when_enabled_and_not_dry_run(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=False, account_id="10001")
        dispatcher = RpcDispatcher(service)
        result = dispatcher.dispatch(
            RpcCall(
                target="trader",
                method="order_stock",
                args=[
                    {"__type__": "StockAccount", "account_id": "10001"},
                    "000001.SZ",
                    23,
                    100,
                    5,
                    10.5,
                ],
                kwargs={},
            )
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], 10001)
        self.assertEqual(service.trader.calls[0][0], "order_stock")

    def test_rejects_non_allowed_account(self) -> None:
        dispatcher = RpcDispatcher(FakeService(enable_trading=True, account_id="10001"))
        result = dispatcher.dispatch(
            RpcCall(
                target="trader",
                method="order_stock",
                args=[
                    {"__type__": "StockAccount", "account_id": "10002"},
                    "000001.SZ",
                    23,
                    100,
                    5,
                    10.5,
                ],
                kwargs={},
            )
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "ACCOUNT_NOT_ALLOWED")

    def test_rejects_order_volume_limit(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", max_order_volume=50)
        )
        result = dispatcher.dispatch(
            RpcCall(
                target="trader",
                method="order_stock",
                args=[
                    {"__type__": "StockAccount", "account_id": "10001"},
                    "000001.SZ",
                    23,
                    100,
                    5,
                    10.5,
                ],
                kwargs={},
            )
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "ORDER_LIMIT_EXCEEDED")

    def test_rejects_order_amount_limit(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", max_order_amount=100)
        )
        result = dispatcher.dispatch(
            RpcCall(
                target="trader",
                method="order_stock",
                args=[
                    {"__type__": "StockAccount", "account_id": "10001"},
                    "000001.SZ",
                    23,
                    100,
                    5,
                    10.5,
                ],
                kwargs={},
            )
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["code"], "ORDER_LIMIT_EXCEEDED")

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
        self.assertEqual(result["error"]["code"], "TARGET_NOT_CONNECTED")

    def test_settings_import_keeps_dev_dependency_visible(self) -> None:
        self.assertEqual(load_settings().account_type, "STOCK")


if __name__ == "__main__":
    unittest.main()
