from __future__ import annotations

from typing import Any

import httpx

from qmtserver.client.errors import QmtAuthError, QmtConnectionError, QmtHttpError, QmtRpcError
from qmtserver.client.events import ConnectFactory, EventStream
from qmtserver.client.proxy import RpcTargetProxy


class QmtClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        *,
        token: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        http_client: httpx.Client | None = None,
        event_connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
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
            )
        return response.get("data")

    def events(self) -> EventStream:
        return EventStream(
            base_url=self.base_url,
            token=self.token,
            timeout=self.timeout,
            connect_factory=self._event_connect_factory,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.RequestError as exc:
            raise QmtConnectionError(str(exc)) from exc

        if response.status_code == 401:
            raise QmtAuthError(response.status_code, "Unauthorized", _response_json(response))
        if response.status_code >= 400:
            raise QmtHttpError(response.status_code, response.text, _response_json(response))
        return _response_json(response)

    def _headers(self) -> dict[str, str]:
        if self.token is None:
            return {}
        return {"Authorization": f"Bearer {self.token}"}


def _response_json(response: httpx.Response) -> dict[str, Any]:
    value = response.json()
    if isinstance(value, dict):
        return value
    return {"data": value}
