from __future__ import annotations


class QmtServerError(Exception):
    code = "QMT_SERVER_ERROR"


class QmtTargetNotFoundError(QmtServerError):
    code = "TARGET_NOT_FOUND"


class QmtTargetNotConnectedError(QmtServerError):
    code = "TARGET_NOT_CONNECTED"
