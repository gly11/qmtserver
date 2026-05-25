# Milestone 2: Connection Lifecycle Management

Milestone 2 的目标是让 qmtserver 从“能提供只读 RPC 的服务”升级为“可以长期稳定运行的 MiniQMT 网关”。重点不在新增更多 xtquant API，而在连接生命周期、状态可观测、失败恢复和资源清理。

状态：已完成。

## 目标

完成后应支持：

- 服务启动时按配置自动连接，也可以选择延迟连接。
- 显式连接、重连、断开 MiniQMT。
- 状态接口能展示 quote、trader、账号订阅、最近错误、最近成功时间。
- RPC 调用前能判断目标连接是否可用。
- MiniQMT 未启动、重启、断线时，服务进程不崩溃。
- 重复 connect / reconnect 不泄露旧 trader 线程或连接资源。

## 非目标

Milestone 2 暂不做：

- token 鉴权。
- 真实下单、撤单。
- WebSocket 推送。
- 多账号连接池。
- 后台自动无限重连策略。
- Windows 服务化部署。

这些内容分别放到后续安全、交易、推送和运维 milestone 中。

## 当前基础

Milestone 1 已经提供：

- FastAPI 服务入口。
- `qmtserver serve` 命令。
- `GET /health`。
- `GET /qmt/status`。
- `POST /qmt/connect`。
- `GET /rpc/methods`。
- `POST /rpc`。
- `QmtService` 的基础 `connect()` / `shutdown()` / `status()`。

Milestone 2 需要把这些能力变得更可靠、更明确。

## API 设计

保留：

```text
GET  /qmt/status
POST /qmt/connect
```

新增：

```text
POST /qmt/reconnect
POST /qmt/disconnect
```

### GET /qmt/status

响应应包含：

```json
{
  "ok": true,
  "xtquant": {
    "ok": true,
    "path": "..."
  },
  "quote": {
    "connected": true,
    "address": "127.0.0.1:58610",
    "data_dir": "..."
  },
  "trader": {
    "connected": true,
    "session_id": 123456,
    "userdata": "...",
    "account_id": "...",
    "account_type": "STOCK",
    "account_subscribed": true
  },
  "lifecycle": {
    "state": "connected",
    "last_connect_at": "...",
    "last_disconnect_at": null,
    "last_success_at": "...",
    "last_error_at": null,
    "last_error": null
  }
}
```

建议状态枚举：

```text
new
connecting
connected
partial
disconnected
error
```

### POST /qmt/connect

用途：首次连接。若已有连接，应先安全清理旧连接再重新连接，保证幂等。

### POST /qmt/reconnect

用途：强制断开后重新连接。语义上等价于：

```text
disconnect -> connect
```

但响应中应能看出这是一次 reconnect 操作。

### POST /qmt/disconnect

用途：显式释放 quote / trader 连接和线程资源。

成功后：

- quote connected = false
- trader connected = false
- account subscribed = false
- lifecycle state = disconnected

## QmtService 设计

建议将 `QmtService` 拆清楚几个职责：

- 配置：保存 `Settings`。
- 状态：保存连接状态、时间戳、错误信息。
- 生命周期：`connect()`、`reconnect()`、`disconnect()`、`shutdown()`。
- 目标访问：`get_target("xtdata")`、`get_target("trader")`。
- 健康判断：`is_quote_connected()`、`is_trader_connected()`。

建议新增内部数据结构：

```python
@dataclass
class LifecycleState:
    state: str
    last_connect_at: str | None
    last_disconnect_at: str | None
    last_success_at: str | None
    last_error_at: str | None
    last_error: str | None
```

第一版可以继续用 dataclass，不急着引入数据库或持久化。

## RPC 调用前检查

`RpcDispatcher` 调用 `service.get_target(target)` 时应获得明确错误：

- `xtdata` 未连接：`TARGET_NOT_CONNECTED`
- `trader` 未连接：`TARGET_NOT_CONNECTED`
- target 不存在：`TARGET_NOT_FOUND`

Milestone 2 可以把这些错误从普通异常字符串升级为更稳定的错误码。

## 配置项

保留：

```env
QMT_AUTO_CONNECT=true
QMT_USERDATA=
QMT_ACCOUNT_ID=
QMT_ACCOUNT_TYPE=STOCK
QMT_TRADER_TIMEOUT_MS=5000
```

建议新增：

```env
QMT_CONNECT_ON_STARTUP=true
QMT_CONNECT_QUOTE=true
QMT_CONNECT_TRADER=true
```

其中：

- `QMT_CONNECT_QUOTE=false` 时只启动 HTTP 服务，不连行情。
- `QMT_CONNECT_TRADER=false` 时不初始化 trader。
- 若没有 `QMT_USERDATA`，trader 连接应被跳过而不是报错。

## 测试计划

单元测试：

- `connect()` 成功时更新状态。
- `connect()` 失败时记录 `last_error`，服务不抛出到 API 层。
- `disconnect()` 能重置 quote / trader / account 状态。
- `reconnect()` 会先释放旧连接再连接。
- 未配置 `userdata` 时跳过 trader。
- `get_target("trader")` 在未连接时返回稳定错误。

接口测试：

- `GET /qmt/status` 返回 lifecycle 信息。
- `POST /qmt/connect` 返回状态。
- `POST /qmt/reconnect` 返回状态。
- `POST /qmt/disconnect` 返回 disconnected 状态。
- 未连接 trader 时，`POST /rpc` 查询 trader 方法返回稳定错误响应。

真实环境手动测试：

```powershell
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "你的资金账号"
```

验证：

```text
GET  /qmt/status
POST /qmt/disconnect
GET  /qmt/status
POST /qmt/connect
GET  /qmt/status
POST /qmt/reconnect
GET  /qmt/status
```

再手动关闭 MiniQMT，确认：

- 服务进程仍运行。
- `/qmt/status` 有清晰错误。
- `/health` 仍返回 qmtserver 进程健康。

## 验收标准

Milestone 2 完成时必须满足：

1. `uv run qmtserver check ...` 继续可用。
2. `uv run qmtserver serve` 继续可用。
3. `GET /health` 不依赖 MiniQMT 是否在线。
4. `GET /qmt/status` 返回完整 lifecycle 状态。
5. `POST /qmt/connect` 可重复调用且不泄露旧连接。
6. `POST /qmt/reconnect` 可强制重连。
7. `POST /qmt/disconnect` 可释放连接并更新状态。
8. MiniQMT 未启动时服务不崩溃。
9. RPC 调用未连接 target 时返回稳定错误码。
10. 自动化测试通过。

## 建议提交顺序

```text
feat(service): add lifecycle state model
feat(service): add reconnect and disconnect
feat(api): expose qmt lifecycle endpoints
feat(rpc): return stable target connection errors
test(service): cover qmt lifecycle transitions
docs(milestone): document connection lifecycle behavior
```

## 风险与应对

- xtquant trader 线程清理不彻底：每次 connect 前先 shutdown，失败时也清理。
- MiniQMT 启动慢：状态接口显示 `connecting` / `error`，不阻塞 `/health`。
- 重连语义混乱：明确 `connect` 幂等，`reconnect` 强制断开再连。
- 错误码不稳定：集中定义错误类型，不在各处拼字符串。
