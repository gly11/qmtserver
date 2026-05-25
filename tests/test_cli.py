from __future__ import annotations

import io
import os
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

    def test_serve_applies_cli_overrides(self) -> None:
        clean_env = {key: value for key, value in os.environ.items() if not key.startswith("QMT_")}
        with (
            patch.dict(os.environ, clean_env, clear=True),
            patch("uvicorn.run") as run,
        ):
            exit_code = main(
                [
                    "serve",
                    "--userdata",
                    "userdata_mini",
                    "--account-id",
                    "10001",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "9001",
                ]
            )

        self.assertEqual(exit_code, 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.kwargs["host"], "0.0.0.0")
        self.assertEqual(run.call_args.kwargs["port"], 9001)


if __name__ == "__main__":
    unittest.main()
