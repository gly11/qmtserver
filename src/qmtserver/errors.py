from __future__ import annotations


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
