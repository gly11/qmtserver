from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any

from qmtserver.config import Settings

_CONFIGURED_LOGGERS: set[str] = set()


class Metrics:
    def __init__(self) -> None:
        self.started_at = monotonic()
        self._lock = Lock()
        self.rpc_total = 0
        self.rpc_success = 0
        self.rpc_error = 0
        self.rpc_elapsed_total_ms = 0.0

    def record_rpc(self, *, ok: bool, elapsed_ms: float) -> None:
        with self._lock:
            self.rpc_total += 1
            if ok:
                self.rpc_success += 1
            else:
                self.rpc_error += 1
            self.rpc_elapsed_total_ms += elapsed_ms

    def snapshot(self, *, service: Any, event_bus: Any) -> dict[str, Any]:
        with self._lock:
            rpc_total = self.rpc_total
            rpc_success = self.rpc_success
            rpc_error = self.rpc_error
            elapsed_total = self.rpc_elapsed_total_ms

        status = _service_status(service)
        return {
            "ok": True,
            "uptime_seconds": round(monotonic() - self.started_at, 3),
            "rpc": {
                "total": rpc_total,
                "success": rpc_success,
                "error": rpc_error,
                "avg_elapsed_ms": round(elapsed_total / rpc_total, 3) if rpc_total else 0.0,
            },
            "qmt": {
                "quote_connected": bool(status.get("quote", {}).get("connected")),
                "trader_connected": bool(status.get("trader", {}).get("connected")),
                "lifecycle_state": status.get("lifecycle", {}).get("state"),
            },
            "websocket": {
                "clients": getattr(event_bus, "subscriber_count", 0),
                "events_published": getattr(event_bus, "events_published", 0),
            },
        }


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, self.datefmt),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            payload["request_id"] = request_id
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(settings: Settings) -> None:
    logger = logging.getLogger("qmtserver")
    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    if logger.name in _CONFIGURED_LOGGERS:
        return

    settings.log_dir.mkdir(parents=True, exist_ok=True)
    formatter: logging.Formatter
    if settings.log_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
        )

    handler = RotatingFileHandler(
        Path(settings.log_dir) / "qmtserver.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    _CONFIGURED_LOGGERS.add(logger.name)


def _service_status(service: Any) -> dict[str, Any]:
    try:
        value = service.status()
    except Exception as exc:
        return {"lifecycle": {"state": "unknown"}, "error": f"{type(exc).__name__}: {exc}"}
    return value if isinstance(value, dict) else {}
