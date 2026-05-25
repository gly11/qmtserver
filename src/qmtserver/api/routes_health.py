from __future__ import annotations

from fastapi import APIRouter

from qmtserver import __version__

router = APIRouter()


@router.get("/health")
def health() -> dict[str, object]:
    return {
        "ok": True,
        "service": "qmtserver",
        "version": __version__,
    }
