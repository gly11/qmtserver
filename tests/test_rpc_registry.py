from __future__ import annotations

import unittest

from qmtserver.rpc import allowed_methods, is_method_allowed, method_specs


class RpcRegistryTests(unittest.TestCase):
    def test_allowed_methods_are_sorted(self) -> None:
        methods = allowed_methods()

        self.assertIn("xtdata", methods)
        self.assertEqual(methods["xtdata"], sorted(methods["xtdata"]))

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


if __name__ == "__main__":
    unittest.main()
