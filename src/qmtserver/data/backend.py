from __future__ import annotations

import importlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from qmtserver.config import Settings
from qmtserver.errors import QmtDataBackendUnavailableError

OPTIONAL_MODULES = ("duckdb", "pyarrow")


class DuckDbConnection(Protocol):
    def execute(self, sql: str) -> Any: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class DataBackendDependencyStatus:
    available: bool
    missing_modules: tuple[str, ...]


class DuckDbDataBackend:
    def __init__(
        self,
        settings: Settings,
        *,
        connect: Callable[[str], DuckDbConnection],
    ) -> None:
        self.settings = settings
        self.connect = connect

    @property
    def data_dir(self) -> Path:
        return self.settings.data_dir

    @property
    def database_path(self) -> Path:
        return self.settings.data_db

    def initialize(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connect(str(self.database_path))
        try:
            connection.execute(schema_sql())
        finally:
            connection.close()


def check_data_backend_dependencies(
    *,
    import_module: Callable[[str], object] = importlib.import_module,
) -> DataBackendDependencyStatus:
    missing = []
    for module_name in OPTIONAL_MODULES:
        try:
            import_module(module_name)
        except ModuleNotFoundError:
            missing.append(module_name)
    return DataBackendDependencyStatus(
        available=not missing,
        missing_modules=tuple(missing),
    )


def create_data_backend(
    settings: Settings,
    *,
    import_module: Callable[[str], object] = importlib.import_module,
) -> DuckDbDataBackend:
    if not settings.data_enable_duckdb:
        raise QmtDataBackendUnavailableError("DuckDB data backend is disabled")
    status = check_data_backend_dependencies(import_module=import_module)
    if not status.available:
        missing = ", ".join(status.missing_modules)
        raise QmtDataBackendUnavailableError(
            f"Data backend requires qmtserver[data] optional dependencies; missing: {missing}"
        )
    duckdb: Any = import_module("duckdb")
    return DuckDbDataBackend(settings, connect=duckdb.connect)


def schema_sql() -> str:
    return Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
