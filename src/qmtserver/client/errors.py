from __future__ import annotations

from typing import Any


class QmtClientError(Exception):
    """Base error raised by the qmtserver client SDK."""


class QmtConnectionError(QmtClientError):
    """Raised when qmtserver cannot be reached."""


class QmtHttpError(QmtClientError):
    def __init__(self, status_code: int, message: str, response: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class QmtAuthError(QmtHttpError):
    """Raised when qmtserver rejects authentication."""


class QmtRpcError(QmtClientError):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        target: str,
        method: str,
        response: dict[str, Any],
    ) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.target = target
        self.method = method
        self.response = response
