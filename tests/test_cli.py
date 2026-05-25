from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from qmtserver.cli import main


class CliTests(unittest.TestCase):
    def test_check_returns_success_when_report_is_ok(self) -> None:
        report = {
            "ok": True,
            "python": {"implementation": "CPython", "version": "3.13.0"},
            "xtquant": {"ok": True, "path": "site-packages/xtquant"},
            "quote": None,
            "trader": None,
        }

        with patch("qmtserver.cli.build_connectivity_report", return_value=report):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["check", "--skip-quote"])

        self.assertEqual(exit_code, 0)
        self.assertIn("result: OK", output.getvalue())

    def test_check_returns_failure_when_report_is_not_ok(self) -> None:
        report = {
            "ok": False,
            "python": {"implementation": "CPython", "version": "3.13.0"},
            "xtquant": {"ok": False, "error": "missing xtquant"},
            "quote": None,
            "trader": None,
        }

        with patch("qmtserver.cli.build_connectivity_report", return_value=report):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["check", "--skip-quote"])

        self.assertEqual(exit_code, 1)
        self.assertIn("xtquant: FAILED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
