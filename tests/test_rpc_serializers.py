from __future__ import annotations

import unittest
from pathlib import Path

from qmtserver.config import load_settings
from qmtserver.rpc.serializers import convert_input, to_jsonable


class RpcSerializerTests(unittest.TestCase):
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

    def test_settings_import_keeps_dev_dependency_visible(self) -> None:
        self.assertEqual(load_settings().account_type, "STOCK")


if __name__ == "__main__":
    unittest.main()
