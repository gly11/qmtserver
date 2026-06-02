from __future__ import annotations

import io
import os
import tempfile
import unittest
from collections.abc import Iterator
from contextlib import contextmanager, redirect_stdout
from pathlib import Path
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

    def test_diagnose_trader_prints_hints_and_returns_failure(self) -> None:
        report = {
            "ok": False,
            "userdata": {"configured": True, "exists": True, "name": "userdata_mini"},
            "account": {"configured": True, "account_id": "123****789", "account_type": "STOCK"},
            "connect_result": -1,
            "steps": [{"name": "trader_connect", "ok": False, "detail": "connect_result=-1"}],
            "hints": ["MiniQMT may not be started or logged in."],
        }

        with patch("qmtserver.cli.build_trader_diagnostics", return_value=report):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "diagnose",
                        "trader",
                        "--userdata",
                        "userdata_mini",
                        "--account-id",
                        "123456789",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertIn("trader diagnostics", output.getvalue())
        self.assertIn("MiniQMT may not be started", output.getvalue())
        self.assertNotIn("123456789", output.getvalue())

    def test_env_use_copies_profile_to_active_env_and_redacts_output(self) -> None:
        with temporary_working_directory() as cwd:
            (cwd / ".env.sim").write_text(
                "QMT_USERDATA=sim_userdata\nQMT_ACCOUNT_ID=123456789\nQMT_API_TOKEN=secret\n",
                encoding="utf-8",
            )
            (cwd / ".env").write_text("QMT_USERDATA=old\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["env", "use", "sim"])

            active = (cwd / ".env").read_text(encoding="utf-8")
            backup = (cwd / ".env.previous").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn("QMT_USERDATA=sim_userdata", active)
        self.assertIn("QMT_USERDATA=old", backup)
        self.assertIn("Switched qmtserver env profile: sim", output.getvalue())
        self.assertIn("account id: <set>", output.getvalue())
        self.assertIn("api token: <set>", output.getvalue())
        self.assertNotIn("123456789", output.getvalue())
        self.assertNotIn("secret", output.getvalue())

    def test_check_profile_uses_profile_userdata_and_account_defaults(self) -> None:
        report = {
            "ok": True,
            "python": {"implementation": "CPython", "version": "3.13.0"},
            "xtquant": {"ok": True, "path": "site-packages/xtquant"},
            "quote": None,
            "trader": {"ok": True, "session_id": 123},
        }
        with temporary_working_directory() as cwd:
            (cwd / ".env.sim").write_text(
                "QMT_USERDATA=sim_userdata\nQMT_ACCOUNT_ID=sim-account\nQMT_TRADER_TIMEOUT_MS=30000\n",
                encoding="utf-8",
            )
            with patch("qmtserver.cli.build_connectivity_report", return_value=report) as build:
                output = io.StringIO()
                with redirect_stdout(output):
                    exit_code = main(["check", "--profile", "sim", "--skip-quote"])

        self.assertEqual(exit_code, 0)
        trader = build.call_args.kwargs["trader"]
        self.assertEqual(trader.userdata, Path("sim_userdata"))
        self.assertEqual(trader.account_id, "sim-account")
        self.assertEqual(trader.timeout_ms, 30000)

    def test_data_check_prints_storage_maintenance_summary(self) -> None:
        service = FakeDataMaintenanceService()

        with patch("qmtserver.cli._build_data_maintenance_service", return_value=service):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["data", "check"])

        self.assertEqual(exit_code, 0)
        self.assertIn("market data lake maintenance", output.getvalue())
        self.assertIn("orphan parquet files: 1", output.getvalue())
        self.assertIn("health: warning", output.getvalue())

    def test_data_cleanup_passes_expired_export_options(self) -> None:
        service = FakeDataMaintenanceService()

        with patch("qmtserver.cli._build_data_maintenance_service", return_value=service):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["data", "cleanup", "--delete", "--expired-days", "7"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(service.cleanup_calls, [{"delete": True, "expired_days": 7}])

    def test_data_rebuild_index_execute_rebuilds_metadata(self) -> None:
        service = FakeDataMaintenanceService()

        with patch("qmtserver.cli._build_data_maintenance_service", return_value=service):
            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = main(["data", "rebuild-index", "--execute"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(service.rebuild_calls, [{"execute": True}])


@contextmanager
def temporary_working_directory() -> Iterator[Path]:
    previous = Path.cwd()
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp)
        os.chdir(cwd)
        try:
            yield cwd
        finally:
            os.chdir(previous)


class FakeDataMaintenanceService:
    def __init__(self) -> None:
        self.cleanup_calls: list[dict[str, object]] = []
        self.rebuild_calls: list[dict[str, object]] = []

    def check(self) -> dict[str, object]:
        return {
            "schema": "market.data.maintenance.v1",
            "registered_file_count": 2,
            "missing_registered_files": [],
            "orphan_parquet_files": [{"path": "data/market/raw/bars/orphan.parquet"}],
            "orphan_export_files": [],
            "metadata_mismatches": [],
            "health": {
                "status": "warning",
                "data_dir_bytes": 7,
            },
        }

    def cleanup(self, *, delete: bool, expired_days: int | None) -> dict[str, object]:
        self.cleanup_calls.append({"delete": delete, "expired_days": expired_days})
        return {
            "schema": "market.data.cleanup.v1",
            "dry_run": not delete,
            "delete_candidates": [],
            "expired_export_files": [],
            "deleted_files": [],
        }

    def rebuild_index(self, *, execute: bool) -> dict[str, object]:
        self.rebuild_calls.append({"execute": execute})
        return {
            "schema": "market.data.rebuild_index.v1",
            "dry_run": not execute,
            "parquet_file_count": 0,
            "parquet_files": [],
            "metadata_error_count": 0,
            "rebuilt_file_count": 0,
        }


if __name__ == "__main__":
    unittest.main()
