# Python SDK

`qmtserver.client.QmtClient` 默认调用 `/v1` API。

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.version())
print(client.status())
print(client.rpc("xtdata", "get_full_tick", [["000001.SZ"]]))
print(client.xtdata.get_full_tick(["000001.SZ"]))
```

## Version Prefix

默认：

```python
QmtClient("http://127.0.0.1:8000")
```

会调用：

```text
http://127.0.0.1:8000/v1/...
```

如果需要兼容旧路径：

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

## Events

```python
for event in client.events():
    print(event)
```

默认连接：

```text
ws://127.0.0.1:8000/v1/ws/events
```

过滤事件：

```python
for event in client.events(types=["stock_order", "stock_trade"]):
    print(event)
```

查询缓存：

```python
client.orders(limit=20)
client.order("123456")
client.trades(limit=20)
client.recent_events(types=["stock_trade"], limit=20)
```
