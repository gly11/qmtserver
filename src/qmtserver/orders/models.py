from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class StoredRecord:
    type: str
    data: dict[str, Any]
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "ts": self.ts,
            "data": self.data,
        }
