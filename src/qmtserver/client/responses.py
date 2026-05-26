from __future__ import annotations

from typing import Any

import httpx

from qmtserver.client.errors import QmtRpcError


def response_json(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    value = response.json()
    if isinstance(value, dict):
        return value
    return {"data": value}


def http_error_detail(
    response: dict[str, Any],
    default_code: str,
    default_message: str,
) -> tuple[str, str]:
    detail = response.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("code", default_code)), str(detail.get("message", default_message))
    error = response.get("error")
    if isinstance(error, dict):
        return str(error.get("code", default_code)), str(error.get("message", default_message))
    return default_code, default_message


def response_request_id(response: dict[str, Any]) -> str | None:
    meta = response.get("meta")
    if isinstance(meta, dict):
        request_id = meta.get("request_id")
        return str(request_id) if request_id is not None else None
    return None


def response_list(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data", [])
    return data if isinstance(data, list) else []


def response_named_item(
    response: dict[str, Any],
    name: str,
    *,
    target: str,
    method: str,
) -> dict[str, Any]:
    data = response_named_data(response, target=target, method=method)
    item = data.get(name)
    return item if isinstance(item, dict) else {}


def response_named_list(
    response: dict[str, Any],
    name: str,
    *,
    target: str,
    method: str,
) -> list[dict[str, Any]]:
    data = response_named_data(response, target=target, method=method)
    items = data.get(name)
    return items if isinstance(items, list) else []


def response_named_data(
    response: dict[str, Any],
    *,
    target: str,
    method: str,
) -> dict[str, Any]:
    if not response.get("ok", False):
        error = response.get("error") or {}
        raise QmtRpcError(
            code=str(error.get("code", "RPC_ERROR")),
            message=str(error.get("message", "Request failed")),
            target=target,
            method=method,
            response=response,
            request_id=response_request_id(response),
        )
    data = response.get("data")
    return data if isinstance(data, dict) else {}
