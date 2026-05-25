from __future__ import annotations

from typing import Any

import httpx

from qmtserver.client.errors import QmtAuthError, QmtConnectionError, QmtHttpError, QmtRpcError
from qmtserver.client.events import ConnectFactory, EventStream
from qmtserver.client.proxy import RpcTargetProxy
from qmtserver.errors import API_VERSION


class QmtClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        token: str | None = None,
        timeout: float = 10.0,
        api_version: str | None = API_VERSION,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.Client | None = None,
        event_connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.api_version = api_version.strip("/") if api_version else None
        self._event_connect_factory = event_connect_factory
        self._owns_http_client = http_client is None
        self._http = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers=self._headers(),
            transport=transport,
        )
        self.xtdata = RpcTargetProxy(self, "xtdata")
        self.trader = RpcTargetProxy(self, "trader")

    def close(self) -> None:
        if self._owns_http_client:
            self._http.close()

    def __enter__(self) -> QmtClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def version(self) -> dict[str, Any]:
        return self.health()

    def status(self) -> dict[str, Any]:
        return self._request("GET", "/qmt/status")

    def methods(self) -> dict[str, Any]:
        return self._request("GET", "/rpc/methods")

    def rpc(
        self,
        target: str,
        method: str,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> Any:
        response = self._request(
            "POST",
            "/rpc",
            json={
                "target": target,
                "method": method,
                "args": args or [],
                "kwargs": kwargs or {},
            },
        )
        if not response.get("ok", False):
            error = response.get("error") or {}
            raise QmtRpcError(
                code=str(error.get("code", "RPC_ERROR")),
                message=str(error.get("message", "RPC call failed")),
                target=target,
                method=method,
                response=response,
                request_id=_response_request_id(response),
            )
        return response.get("data")

    def events(self) -> EventStream:
        return EventStream(
            base_url=self.base_url,
            token=self.token,
            timeout=self.timeout,
            api_version=self.api_version,
            connect_factory=self._event_connect_factory,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._http.request(method, self._api_path(path), **kwargs)
        except httpx.RequestError as exc:
            raise QmtConnectionError(str(exc)) from exc

        response_body = _response_json(response)
        request_id = response.headers.get("X-Request-ID")
        if response.status_code == 401:
            code, message = _http_error_detail(response_body, "UNAUTHORIZED", "Unauthorized")
            raise QmtAuthError(
                response.status_code,
                message,
                response_body,
                code=code,
                request_id=request_id,
            )
        if response.status_code >= 400:
            code, message = _http_error_detail(response_body, "HTTP_ERROR", response.text)
            raise QmtHttpError(
                response.status_code,
                message,
                response_body,
                code=code,
                request_id=request_id,
            )
        return response_body

    def _headers(self) -> dict[str, str]:
        if self.token is None:
            return {}
        return {"Authorization": f"Bearer {self.token}"}

    def _api_path(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        if self.api_version is None:
            return normalized
        return f"/{self.api_version}{normalized}"


def _response_json(response: httpx.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    value = response.json()
    if isinstance(value, dict):
        return value
    return {"data": value}


def _http_error_detail(
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


def _response_request_id(response: dict[str, Any]) -> str | None:
    meta = response.get("meta")
    if isinstance(meta, dict):
        request_id = meta.get("request_id")
        return str(request_id) if request_id is not None else None
    return None
