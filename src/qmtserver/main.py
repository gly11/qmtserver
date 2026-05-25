from __future__ import annotations

from qmtserver.api import create_app

app = create_app()

__all__ = ["app", "create_app"]
