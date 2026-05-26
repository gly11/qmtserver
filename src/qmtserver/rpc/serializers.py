from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StockAccountValue:
    account_id: str
    account_type: str = "STOCK"


def convert_input(value: Any) -> Any:
    if isinstance(value, dict):
        value_type = value.get("__type__")
        if value_type == "StockAccount":
            StockAccount = _stock_account_class()
            return StockAccount(value["account_id"], value.get("account_type", "STOCK"))
        return {key: convert_input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [convert_input(item) for item in value]
    return value


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(item) for item in value]

    pandas_value = _try_pandas(value)
    if pandas_value is not None:
        return pandas_value

    numpy_value = _try_numpy(value)
    if numpy_value is not None:
        return numpy_value

    if hasattr(value, "__dict__"):
        return {
            key: to_jsonable(item) for key, item in vars(value).items() if not key.startswith("_")
        }
    return repr(value)


def _try_pandas(value: Any) -> Any:
    module = type(value).__module__
    name = type(value).__name__
    if module.startswith("pandas.") and name == "DataFrame" and hasattr(value, "to_dict"):
        return value.to_dict(orient="split")
    if module.startswith("pandas.") and name == "Series" and hasattr(value, "to_dict"):
        return value.to_dict()
    return None


def _try_numpy(value: Any) -> Any:
    module = type(value).__module__
    if module.startswith("numpy.") and hasattr(value, "tolist"):
        return value.tolist()
    if module.startswith("numpy.") and hasattr(value, "item"):
        return value.item()
    return None


def _stock_account_class() -> type[Any]:
    try:
        module = import_module("xtquant.xttype")
    except ModuleNotFoundError as exc:
        if exc.name is not None and not exc.name.startswith("xtquant"):
            raise
        return StockAccountValue
    return module.StockAccount
