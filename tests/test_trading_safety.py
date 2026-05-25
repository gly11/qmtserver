from __future__ import annotations

import unittest

from qmtserver.rpc import RpcDispatcher
from qmtserver.rpc.dispatcher import RpcCall
from tests.fakes import FakeService, rpc_error_code


def order_call(
    *, kwargs: dict[str, object] | None = None, stock_code: str = "000001.SZ"
) -> RpcCall:
    return RpcCall(
        target="trader",
        method="order_stock",
        args=[
            {"__type__": "StockAccount", "account_id": "10001"},
            stock_code,
            23,
            100,
            5,
            10.5,
        ],
        kwargs=kwargs or {},
    )


class TradingSafetyTests(unittest.TestCase):
    def test_trading_dry_run_does_not_call_trader(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=True, account_id="10001")
        result = RpcDispatcher(service).dispatch(order_call())

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["dry_run"], True)
        self.assertEqual(service.trader.calls, [])

    def test_real_trading_path_calls_trader_when_enabled_and_not_dry_run(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=False, account_id="10001")
        result = RpcDispatcher(service).dispatch(
            order_call(kwargs={"confirm": "I_UNDERSTAND_REAL_TRADING"})
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], 10001)
        self.assertEqual(service.trader.calls[0][0], "order_stock")
        self.assertEqual(len(service.trader.calls[0][1]), 6)

    def test_real_trading_requires_confirmation(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=False, account_id="10001")
        result = RpcDispatcher(service).dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "TRADE_CONFIRMATION_REQUIRED")
        self.assertEqual(service.trader.calls, [])

    def test_dry_run_does_not_require_confirmation(self) -> None:
        service = FakeService(enable_trading=True, trading_dry_run=True, account_id="10001")
        result = RpcDispatcher(service).dispatch(order_call())

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"]["dry_run"], True)

    def test_allowed_symbol_list_rejects_unknown_symbol(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", allowed_symbols="600000.SH")
        )
        result = dispatcher.dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "SYMBOL_NOT_ALLOWED")

    def test_blocked_symbol_list_rejects_symbol(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", blocked_symbols="000001.SZ")
        )
        result = dispatcher.dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "SYMBOL_NOT_ALLOWED")

    def test_rejects_daily_volume_limit(self) -> None:
        service = FakeService(
            enable_trading=True,
            trading_dry_run=False,
            account_id="10001",
            daily_max_order_volume=150,
        )
        dispatcher = RpcDispatcher(service)
        call = order_call(kwargs={"confirm": "I_UNDERSTAND_REAL_TRADING"})

        self.assertTrue(dispatcher.dispatch(call)["ok"])
        rejected = dispatcher.dispatch(call)

        self.assertFalse(rejected["ok"])
        self.assertEqual(rpc_error_code(rejected), "DAILY_LIMIT_EXCEEDED")

    def test_rejects_daily_amount_limit(self) -> None:
        service = FakeService(
            enable_trading=True,
            trading_dry_run=False,
            account_id="10001",
            daily_max_order_amount=1500,
        )
        dispatcher = RpcDispatcher(service)
        call = order_call(kwargs={"confirm": "I_UNDERSTAND_REAL_TRADING"})

        self.assertTrue(dispatcher.dispatch(call)["ok"])
        rejected = dispatcher.dispatch(call)

        self.assertFalse(rejected["ok"])
        self.assertEqual(rpc_error_code(rejected), "DAILY_LIMIT_EXCEEDED")

    def test_rejects_non_allowed_account(self) -> None:
        dispatcher = RpcDispatcher(FakeService(enable_trading=True, account_id="10002"))
        result = dispatcher.dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "ACCOUNT_NOT_ALLOWED")

    def test_rejects_order_volume_limit(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", max_order_volume=50)
        )
        result = dispatcher.dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "ORDER_LIMIT_EXCEEDED")

    def test_rejects_order_amount_limit(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, account_id="10001", max_order_amount=100)
        )
        result = dispatcher.dispatch(order_call())

        self.assertFalse(result["ok"])
        self.assertEqual(rpc_error_code(result), "ORDER_LIMIT_EXCEEDED")

    def test_trade_audit_log_masks_account(self) -> None:
        dispatcher = RpcDispatcher(
            FakeService(enable_trading=True, trading_dry_run=True, account_id="123456789")
        )
        call = RpcCall(
            target="trader",
            method="order_stock",
            args=[
                {"__type__": "StockAccount", "account_id": "123456789"},
                "000001.SZ",
                23,
                100,
                5,
                10.5,
            ],
            kwargs={},
        )

        with self.assertLogs("qmtserver.trade", level="INFO") as logs:
            dispatcher.dispatch(call)

        output = "\n".join(logs.output)
        self.assertIn("method=order_stock", output)
        self.assertIn("account_id=123****789", output)
        self.assertNotIn("123456789", output)


if __name__ == "__main__":
    unittest.main()
