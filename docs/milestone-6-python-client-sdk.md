# Milestone 6: Python Client SDK

Milestone 6 的目标是提供一个轻量 Python 客户端，让其他 Python 项目无需安装 xtquant，也能方便调用 qmtserver。

## 目标

完成后应支持：

- `QmtClient` 连接 qmtserver HTTP API。
- 自动处理 base URL、token、超时。
- 提供通用 `rpc()` 方法。
- 提供常用封装：`health()`、`status()`、`methods()`。
- 支持动态代理：`client.xtdata.get_full_tick(...)`。
- 支持 WebSocket 事件订阅客户端。
- 提供清晰异常类型。

## 非目标

Milestone 6 暂不做：

- 独立发布到 PyPI。
- 非 Python 客户端。
- 完整 xtquant 类型系统。
- 自动代码生成。
- GUI 或前端。

## 当前基础

依赖：

- HTTP RPC 网关。
- token 鉴权。
- WebSocket 事件端点。

## 模块设计

建议新增：

```text
src/qmtserver/client/
├── __init__.py
├── client.py
├── errors.py
├── proxy.py
└── events.py
```

## 基础用法

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.health())
print(client.status())
print(client.rpc("xtdata", "get_full_tick", [["000001.SZ"]]))
```

动态代理：

```python
client.xtdata.get_full_tick(["000001.SZ"])
client.trader.query_stock_asset({
    "__type__": "StockAccount",
    "account_id": "10001",
    "account_type": "STOCK",
})
```

事件订阅：

```python
for event in client.events():
    print(event)
```

## HTTP 客户端

建议使用已有 dev 依赖 `httpx`，在 Milestone 6 将其提升为运行依赖或为 client extra：

```toml
[project.optional-dependencies]
client = ["httpx>=0.28.1"]
```

如果希望 qmtserver 自带 client，`httpx` 可以成为普通运行依赖。

## 错误模型

建议异常：

```text
QmtClientError
QmtHttpError
QmtRpcError
QmtAuthError
QmtConnectionError
```

RPC 响应 `ok=false` 时抛 `QmtRpcError`，包含：

- code
- message
- target
- method
- response

## Token 和超时

客户端配置：

```python
QmtClient(
    base_url="http://127.0.0.1:8000",
    token=None,
    timeout=10.0,
)
```

请求时自动添加：

```http
Authorization: Bearer <token>
```

## 测试计划

单元测试：

- client 构造 base_url。
- token header 正确添加。
- `health()` 调用正确 endpoint。
- `rpc()` 正确发送 target/method/args/kwargs。
- `ok=false` 抛 `QmtRpcError`。
- 动态代理生成正确 RPC 调用。
- WebSocket 事件客户端能解析事件。

接口测试：

- 使用 FastAPI TestClient 或 mock transport 覆盖成功/失败响应。
- token 错误时抛认证异常。

示例测试：

```python
client.rpc("xtdata", "get_full_tick", [["000001.SZ"]])
```

## 文档

新增：

```text
examples/client_rpc.py
examples/client_events.py
```

README 增加客户端使用小节。

## 验收标准

Milestone 6 完成时必须满足：

1. 外部 Python 代码可以通过 `QmtClient` 调用 qmtserver。
2. `client.rpc(...)` 可用。
3. `client.xtdata.<method>(...)` 动态代理可用。
4. token、timeout、错误处理可用。
5. WebSocket 事件订阅客户端可用。
6. 示例脚本存在。
7. 自动化测试通过。

## 建议提交顺序

```text
feat(client): add qmt http client
feat(client): add dynamic rpc proxies
feat(client): add websocket event client
test(client): cover rpc client behavior
docs(client): add sdk examples
```

## 风险与应对

- client 与 server 版本漂移：响应格式保持稳定，错误对象包含 code。
- 动态代理隐藏错误：所有 RPC 错误都抛明确异常。
- WebSocket 阻塞：提供迭代式和回调式两种用法可以后续增强。
