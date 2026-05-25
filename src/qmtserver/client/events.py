from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from types import TracebackType
from typing import Any, Protocol, cast
from urllib.parse import urlencode, urlsplit, urlunsplit


class WebSocketLike(Protocol):
    def __enter__(self) -> Any: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> object: ...

    def recv(self, *args: Any, **kwargs: Any) -> str | bytes: ...


ConnectFactory = Callable[..., WebSocketLike]


class EventStream:
    def __init__(
        self,
        *,
        base_url: str,
        token: str | None,
        timeout: float,
        connect_factory: ConnectFactory | None = None,
    ) -> None:
        self.url = build_ws_url(base_url, token)
        self.timeout = timeout
        self._headers = {"Authorization": f"Bearer {token}"} if token else {}
        self._connect_factory = connect_factory or _default_connect

    def __iter__(self) -> Iterator[dict[str, Any]]:
        with self._connect_factory(
            self.url,
            additional_headers=self._headers,
            open_timeout=self.timeout,
        ) as websocket:
            while True:
                yield json.loads(websocket.recv())


def build_ws_url(base_url: str, token: str | None = None) -> str:
    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    query = parsed.query
    if token:
        token_query = urlencode({"token": token})
        query = f"{query}&{token_query}" if query else token_query
    return urlunsplit((scheme, parsed.netloc, "/ws/events", query, ""))


def _default_connect(*args: Any, **kwargs: Any) -> WebSocketLike:
    from websockets.sync.client import connect

    return cast(WebSocketLike, connect(*args, **kwargs))
