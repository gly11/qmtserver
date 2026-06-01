from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qmtserver.config import load_settings
from qmtserver.data.backend import (
    DuckDbDataBackend,
    check_data_backend_dependencies,
    create_data_backend,
    schema_sql,
)
from qmtserver.errors import QmtDataBackendUnavailableError


class DataBackendTests(unittest.TestCase):
    def test_data_settings_defaults_to_market_data_lake_paths(self) -> None:
        settings = load_settings(_env_file=None)

        self.assertEqual(settings.data_dir, Path("data/market"))
        self.assertEqual(settings.data_format, "parquet")
        self.assertEqual(settings.data_db, Path("data/market/db/qmtserver.duckdb"))
        self.assertTrue(settings.data_enable_duckdb)

    def test_dependency_check_reports_missing_optional_modules(self) -> None:
        def missing_import(name: str) -> object:
            raise ModuleNotFoundError(name)

        status = check_data_backend_dependencies(import_module=missing_import)

        self.assertFalse(status.available)
        self.assertEqual(status.missing_modules, ("duckdb", "pyarrow"))

    def test_create_data_backend_raises_stable_error_without_optional_modules(self) -> None:
        def missing_import(name: str) -> object:
            raise ModuleNotFoundError(name)

        settings = load_settings(_env_file=None)

        with self.assertRaises(QmtDataBackendUnavailableError) as captured:
            create_data_backend(settings, import_module=missing_import)

        self.assertIn("qmtserver[data]", str(captured.exception))

    def test_schema_contains_initial_metadata_tables(self) -> None:
        sql = schema_sql()

        self.assertIn("CREATE TABLE IF NOT EXISTS data_jobs", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS data_files", sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS data_coverage", sql)

    def test_duckdb_backend_initializes_schema_and_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = load_settings(
                _env_file=None,
                data_dir=Path(tmp) / "market",
                data_db=Path(tmp) / "market" / "db" / "qmtserver.duckdb",
            )
            connector = FakeDuckDbConnector()
            backend = DuckDbDataBackend(settings, connect=connector.connect)

            backend.initialize()

        self.assertEqual(connector.paths, [Path(tmp) / "market" / "db" / "qmtserver.duckdb"])
        self.assertIn("CREATE TABLE IF NOT EXISTS data_jobs", connector.connection.executed[0])


class FakeDuckDbConnector:
    def __init__(self) -> None:
        self.paths: list[Path] = []
        self.connection = FakeDuckDbConnection()

    def connect(self, path: str) -> FakeDuckDbConnection:
        self.paths.append(Path(path))
        return self.connection


class FakeDuckDbConnection:
    def __init__(self) -> None:
        self.executed: list[str] = []

    def execute(self, sql: str, parameters: tuple[object, ...] | None = None) -> None:
        del parameters
        self.executed.append(sql)

    def close(self) -> None:
        return None


if __name__ == "__main__":
    unittest.main()
