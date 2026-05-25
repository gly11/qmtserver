from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qmtserver.client.client import QmtClient


class RpcTargetProxy:
    def __init__(self, client: QmtClient, target: str) -> None:
        self._client = client
        self._target = target

    def __getattr__(self, method: str) -> RpcMethodProxy:
        if method.startswith("_"):
            raise AttributeError(method)
        return RpcMethodProxy(self._client, self._target, method)


class RpcMethodProxy:
    def __init__(self, client: QmtClient, target: str, method: str) -> None:
        self._client = client
        self._target = target
        self._method = method

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._client.rpc(self._target, self._method, list(args), kwargs)
