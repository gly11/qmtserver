from __future__ import annotations

from typing import Any

import httpx

from qmtserver.client.errors import QmtAuthError, QmtConnectionError, QmtHttpError, QmtRpcError
from qmtserver.client.events import ConnectFactory, EventStream
from qmtserver.client.proxy import RpcTargetProxy
from qmtserver.client.responses import (
    http_error_detail,
    response_json,
    response_list,
    response_named_item,
    response_named_list,
    response_request_id,
)
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
                request_id=response_request_id(response),
            )
        return response.get("data")

    def orders(self, limit: int | None = None) -> list[dict[str, Any]]:
        params = {"limit": limit} if limit is not None else None
        response = self._request("GET", "/orders", params=params)
        return response_list(response)

    def order(self, order_id: str) -> dict[str, Any]:
        response = self._request("GET", f"/orders/{order_id}")
        data = response.get("data")
        return data if isinstance(data, dict) else {}

    def trades(self, limit: int | None = None) -> list[dict[str, Any]]:
        params = {"limit": limit} if limit is not None else None
        response = self._request("GET", "/trades", params=params)
        return response_list(response)

    def trader_account_status(self) -> list[dict[str, Any]]:
        response = self._request("GET", "/trader/account-status")
        return response_named_list(response, "statuses", target="trader", method="account_status")

    def trader_asset(
        self,
        *,
        account_id: str | None = None,
        account_type: str | None = None,
    ) -> dict[str, Any]:
        response = self._request(
            "GET",
            "/trader/asset",
            params=_account_params(account_id=account_id, account_type=account_type),
        )
        return response_named_item(response, "asset", target="trader", method="asset")

    def trader_positions(
        self,
        *,
        account_id: str | None = None,
        account_type: str | None = None,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/trader/positions",
            params=_account_params(account_id=account_id, account_type=account_type),
        )
        return response_named_list(response, "positions", target="trader", method="positions")

    def trader_orders(
        self,
        *,
        account_id: str | None = None,
        account_type: str | None = None,
        cancelable_only: bool = False,
    ) -> list[dict[str, Any]]:
        params = _account_params(account_id=account_id, account_type=account_type) or {}
        if cancelable_only:
            params["cancelable_only"] = cancelable_only
        response = self._request("GET", "/trader/orders", params=params or None)
        return response_named_list(response, "orders", target="trader", method="orders")

    def trader_trades(
        self,
        *,
        account_id: str | None = None,
        account_type: str | None = None,
    ) -> list[dict[str, Any]]:
        response = self._request(
            "GET",
            "/trader/trades",
            params=_account_params(account_id=account_id, account_type=account_type),
        )
        return response_named_list(response, "trades", target="trader", method="trades")

    def recent_events(
        self,
        *,
        types: list[str] | tuple[str, ...] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if types:
            params["types"] = ",".join(types)
        if limit is not None:
            params["limit"] = limit
        response = self._request("GET", "/events/recent", params=params or None)
        return response_list(response)

    def events(self, *, types: list[str] | tuple[str, ...] | None = None) -> EventStream:
        return EventStream(
            base_url=self.base_url,
            token=self.token,
            timeout=self.timeout,
            api_version=self.api_version,
            types=types,
            connect_factory=self._event_connect_factory,
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._http.request(method, self._api_path(path), **kwargs)
        except httpx.RequestError as exc:
            raise QmtConnectionError(str(exc)) from exc

        response_body = response_json(response)
        request_id = response.headers.get("X-Request-ID")
        if response.status_code == 401:
            code, message = http_error_detail(response_body, "UNAUTHORIZED", "Unauthorized")
            raise QmtAuthError(
                response.status_code,
                message,
                response_body,
                code=code,
                request_id=request_id,
            )
        if response.status_code >= 400:
            code, message = http_error_detail(response_body, "HTTP_ERROR", response.text)
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


def _account_params(
    *,
    account_id: str | None,
    account_type: str | None,
) -> dict[str, Any] | None:
    params: dict[str, Any] = {}
    if account_id is not None:
        params["account_id"] = account_id
    if account_type is not None:
        params["account_type"] = account_type
    return params or None
