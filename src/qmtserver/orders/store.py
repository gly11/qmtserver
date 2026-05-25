from __future__ import annotations

from collections import deque
from typing import Any

from qmtserver.orders.models import StoredRecord


class OrderStore:
    def __init__(self, *, max_records: int = 1000) -> None:
        self.max_records = max_records
        self._orders: deque[StoredRecord] = deque(maxlen=max_records)
        self._trades: deque[StoredRecord] = deque(maxlen=max_records)
        self._errors: deque[StoredRecord] = deque(maxlen=max_records)

    def record_order(self, data: dict[str, Any]) -> StoredRecord:
        record = StoredRecord("stock_order", data)
        self._orders.append(record)
        return record

    def record_trade(self, data: dict[str, Any]) -> StoredRecord:
        record = StoredRecord("stock_trade", data)
        self._trades.append(record)
        return record

    def record_error(self, event_type: str, data: dict[str, Any]) -> StoredRecord:
        record = StoredRecord(event_type, data)
        self._errors.append(record)
        return record

    def orders(self, limit: int | None = None) -> list[dict[str, Any]]:
        return _tail(self._orders, limit)

    def trades(self, limit: int | None = None) -> list[dict[str, Any]]:
        return _tail(self._trades, limit)

    def errors(self, limit: int | None = None) -> list[dict[str, Any]]:
        return _tail(self._errors, limit)

    def get_order(self, order_id: str) -> dict[str, Any] | None:
        for record in reversed(self._orders):
            data = record.data
            if str(data.get("order_id", data.get("order_id_str", ""))) == order_id:
                return record.to_dict()
        return None


def _tail(records: deque[StoredRecord], limit: int | None) -> list[dict[str, Any]]:
    items = list(records)
    if limit is not None:
        items = items[-limit:]
    return [item.to_dict() for item in items]
