from __future__ import annotations

from dataclasses import dataclass

API_VERSION = "v1"


class QmtServerError(Exception):
    code = "QMT_SERVER_ERROR"


class QmtTargetNotFoundError(QmtServerError):
    code = "TARGET_NOT_FOUND"


class QmtTargetNotConnectedError(QmtServerError):
    code = "TARGET_NOT_CONNECTED"


class QmtUnauthorizedError(QmtServerError):
    code = "UNAUTHORIZED"


class QmtTradingDisabledError(QmtServerError):
    code = "TRADING_DISABLED"


class QmtTradingValidationError(QmtServerError):
    code = "TRADING_VALIDATION_ERROR"


class QmtAccountNotAllowedError(QmtServerError):
    code = "ACCOUNT_NOT_ALLOWED"


class QmtOrderLimitExceededError(QmtServerError):
    code = "ORDER_LIMIT_EXCEEDED"


class QmtSymbolNotAllowedError(QmtServerError):
    code = "SYMBOL_NOT_ALLOWED"


class QmtDailyLimitExceededError(QmtServerError):
    code = "DAILY_LIMIT_EXCEEDED"


class QmtTradeConfirmationRequiredError(QmtServerError):
    code = "TRADE_CONFIRMATION_REQUIRED"


@dataclass(frozen=True)
class ErrorCode:
    code: str
    description: str


ERROR_CODES: tuple[ErrorCode, ...] = (
    ErrorCode("UNAUTHORIZED", "Authentication failed or bearer token is missing."),
    ErrorCode("METHOD_NOT_ALLOWED", "RPC method is not enabled in the allowlist."),
    ErrorCode("METHOD_NOT_FOUND", "Target object does not expose the requested method."),
    ErrorCode("TARGET_NOT_FOUND", "RPC target name is unknown."),
    ErrorCode("TARGET_NOT_CONNECTED", "RPC target exists but is not currently connected."),
    ErrorCode("TRADING_DISABLED", "Trading RPC methods are disabled by configuration."),
    ErrorCode("TRADING_VALIDATION_ERROR", "Trading request failed validation."),
    ErrorCode("ACCOUNT_NOT_ALLOWED", "Trading account is not in the allowed account set."),
    ErrorCode("SYMBOL_NOT_ALLOWED", "Trading symbol is not allowed by safety settings."),
    ErrorCode("ORDER_LIMIT_EXCEEDED", "Order volume or amount exceeded configured limits."),
    ErrorCode("DAILY_LIMIT_EXCEEDED", "Daily process-level trading limit would be exceeded."),
    ErrorCode("TRADE_CONFIRMATION_REQUIRED", "Real trading requires an explicit confirmation."),
    ErrorCode("RPC_ERROR", "Client-side wrapper for an RPC error response."),
    ErrorCode("QMT_SERVER_ERROR", "Generic qmtserver error."),
)

ERROR_CODE_VALUES = frozenset(item.code for item in ERROR_CODES)
