from __future__ import annotations

from fastapi import APIRouter

from qmtserver import __version__
from qmtserver.errors import API_VERSION

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "qmtserver",
        "version": __version__,
        "api_versions": [API_VERSION],
    }
