# Built-in Client Compatibility

qmtserver 仍保留 `qmtserver.client.QmtClient`，用于随服务端一起验证 `/v1` API 契约。

新的策略项目建议使用独立客户端包 qmtclient。qmtserver 文档只说明内置兼容客户端的基础行为。

## Basic Usage

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.version())
print(client.status())
print(client.rpc("xtdata", "get_full_tick", [["000001.SZ"]]))
print(client.xtdata.get_full_tick(["000001.SZ"]))
```

## Version Prefix

默认会调用 `/v1`：

```python
QmtClient("http://127.0.0.1:8000")
```

如果需要兼容旧路径，可以关闭版本前缀：

```python
QmtClient("http://127.0.0.1:8000", api_version=None)
```

## Errors

RPC `ok=false` 时抛 `QmtRpcError`，包含：

- `code`
- `message`
- `target`
- `method`
- `request_id`
- `response`

HTTP 401 时抛 `QmtAuthError`。

## Events And Cache

```python
for event in client.events(types=["stock_order", "stock_trade"]):
    print(event)

client.orders(limit=20)
client.order("123456")
client.trades(limit=20)
client.recent_events(types=["stock_trade"], limit=20)
```
