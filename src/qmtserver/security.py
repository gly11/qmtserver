from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status

from qmtserver.config import Settings


def token_required(settings: Settings) -> bool:
    return settings.require_token or bool(settings.api_token)


def verify_bearer_token(authorization: str | None, settings: Settings) -> None:
    if not token_required(settings):
        return
    if not settings.api_token:
        raise _unauthorized()

    prefix = "Bearer "
    if authorization is None or not authorization.startswith(prefix):
        raise _unauthorized()

    token = authorization[len(prefix) :]
    if not secrets.compare_digest(token, settings.api_token):
        raise _unauthorized()


def authenticate_request(request: Request) -> None:
    settings: Settings = request.app.state.settings
    verify_bearer_token(request.headers.get("Authorization"), settings)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": "Missing or invalid bearer token",
        },
    )
