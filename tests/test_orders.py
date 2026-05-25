from __future__ import annotations

import unittest

from qmtserver.miniqmt import MiniQmtCallback
from qmtserver.orders import OrderStore


class OrderStoreTests(unittest.TestCase):
    def test_records_and_queries_orders(self) -> None:
        store = OrderStore(max_records=2)
        store.record_order({"order_id": 1, "stock_code": "000001.SZ"})
        store.record_order({"order_id": 2, "stock_code": "600000.SH"})

        order = store.get_order("1")
        assert order is not None
        self.assertEqual(len(store.orders()), 2)
        self.assertEqual(order["data"]["stock_code"], "000001.SZ")

    def test_cache_drops_oldest_records(self) -> None:
        store = OrderStore(max_records=1)
        store.record_order({"order_id": 1})
        store.record_order({"order_id": 2})

        self.assertIsNone(store.get_order("1"))
        order = store.get_order("2")
        assert order is not None
        self.assertEqual(order["data"]["order_id"], 2)

    def test_callback_records_orders_trades_and_errors(self) -> None:
        store = OrderStore(max_records=10)
        callback = MiniQmtCallback(order_store=store)

        callback.on_stock_order({"order_id": 1})
        callback.on_stock_trade({"trade_id": 2})
        callback.on_order_error({"order_id": 1, "error": "bad order"})

        self.assertEqual(store.orders()[0]["data"], {"order_id": 1})
        self.assertEqual(store.trades()[0]["data"], {"trade_id": 2})
        self.assertEqual(store.errors()[0]["type"], "order_error")


if __name__ == "__main__":
    unittest.main()
