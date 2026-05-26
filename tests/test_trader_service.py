from __future__ import annotations

import unittest

from qmtserver.config import load_settings
from qmtserver.errors import QmtAccountNotAllowedError, QmtTraderAccountRequiredError
from qmtserver.trader.service import resolve_stock_account


class TraderServiceAccountTests(unittest.TestCase):
    def test_resolves_default_account_from_settings(self) -> None:
        settings = load_settings(_env_file=None, account_id="10001", account_type="STOCK")

        account = resolve_stock_account(settings, account_id=None, account_type=None)

        self.assertEqual(account.account_id, "10001")
        self.assertEqual(account.account_type, "STOCK")

    def test_explicit_account_overrides_settings_account(self) -> None:
        settings = load_settings(
            _env_file=None,
            account_id="10001",
            account_type="STOCK",
            allowed_accounts="10001,10002",
        )

        account = resolve_stock_account(settings, account_id="10002", account_type="CREDIT")

        self.assertEqual(account.account_id, "10002")
        self.assertEqual(account.account_type, "CREDIT")

    def test_rejects_account_outside_allowlist(self) -> None:
        settings = load_settings(
            _env_file=None,
            account_id="10001",
            allowed_accounts="10001",
        )

        with self.assertRaises(QmtAccountNotAllowedError):
            resolve_stock_account(settings, account_id="10002", account_type="STOCK")

    def test_requires_account_id(self) -> None:
        settings = load_settings(_env_file=None, account_id=None)

        with self.assertRaises(QmtTraderAccountRequiredError):
            resolve_stock_account(settings, account_id=None, account_type=None)


if __name__ == "__main__":
    unittest.main()
