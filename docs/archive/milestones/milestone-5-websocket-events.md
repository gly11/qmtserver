# Milestone 5: WebSocket Events

Milestone 5 的目标是提供实时事件通道，让外部平台不必轮询就能获得连接状态、账号状态、委托、成交和错误回报。

状态：已完成。

## 目标

完成后应支持：

- 新增 WebSocket 端点 `/ws/events`。
- 客户端连接后可以接收 qmtserver 事件。
- 支持连接状态变化事件。
- 支持账号状态变化事件。
- 支持委托回报、成交回报、下单错误、撤单错误。
- 客户端断开不影响 MiniQMT 主连接。
- 多个客户端可同时订阅事件。
- 事件格式统一、JSON 可编码。

已落地：

- 新增内存 `EventBus`，支持多订阅者广播和慢客户端队列丢弃旧消息。
- 新增 `WS /ws/events`，支持 bearer header 和 `?token=` 鉴权。
- WebSocket 空闲时按 `QMT_WS_HEARTBEAT_SECONDS` 发送 heartbeat。
- `QmtService` 发布连接、断开和错误事件。
- `MiniQmtCallback` 发布账号状态、委托、成交、下单错误和撤单错误事件。
- 事件统一为 `{type, ts, data, meta}` JSON 结构。

## 非目标

Milestone 5 暂不做：

- 行情高频推送。
- 历史事件持久化。
- 消息队列。
- 复杂订阅过滤表达式。
- 前端页面。

行情订阅可以作为后续增强，先把交易和连接事件通道跑稳。

## 当前基础

依赖：

- Milestone 2 的连接生命周期状态。
- Milestone 3 的 token 鉴权。
- Milestone 4 的交易 RPC 和交易审计。

## WebSocket API

```text
WS /ws/events
```

鉴权：

- 如果配置了 `QMT_API_TOKEN`，WebSocket 也需要 token。
- 可支持 query 参数：`?token=...`
- 也可支持 header：`Authorization: Bearer <token>`

## 事件格式

统一格式：

```json
{
  "type": "stock_trade",
  "ts": "2026-05-25T21:00:00+08:00",
  "data": {},
  "meta": {
    "source": "xtquant",
    "sequence": 1
  }
}
```

事件类型：

```text
service_started
service_stopped
qmt_connected
qmt_disconnected
qmt_error
account_status
stock_order
stock_trade
order_error
cancel_error
heartbeat
```

## EventBus 设计

建议新增：

```text
src/qmtserver/events/
├── __init__.py
├── bus.py
└── models.py
```

职责：

- `EventBus` 管理客户端队列。
- `publish(event)` 广播事件。
- `subscribe()` 返回异步队列。
- 客户端断开时自动注销。

第一版可以使用内存队列：

```python
asyncio.Queue
```

暂不引入 Redis 或消息队列。

## xtquant 回调接入

当前 `MiniQmtCallback` 只记录 events list。Milestone 5 应将其升级为可发布事件：

- `on_connected` -> `qmt_connected`
- `on_disconnected` -> `qmt_disconnected`
- `on_account_status` -> `account_status`
- `on_stock_order` -> `stock_order`
- `on_stock_trade` -> `stock_trade`
- `on_order_error` -> `order_error`
- `on_cancel_error` -> `cancel_error`

注意：xtquant 回调可能来自非 asyncio 线程，事件发布需要线程安全。

## 心跳

服务端每隔固定时间发送 heartbeat：

```json
{
  "type": "heartbeat",
  "ts": "...",
  "data": {
    "service": "qmtserver"
  }
}
```

配置：

```env
QMT_WS_HEARTBEAT_SECONDS=15
QMT_WS_CLIENT_QUEUE_SIZE=1000
```

## 测试计划

单元测试：

- EventBus 可以 broadcast 给多个订阅者。
- 客户端取消订阅后不再接收事件。
- 事件模型可 JSON 编码。
- 回调方法会发布正确事件类型。

接口测试：

- WebSocket 可以连接。
- 连接后收到 heartbeat 或测试事件。
- 多个客户端同时收到事件。
- token 开启时，无 token 连接失败。
- 客户端断开不影响服务。

真实环境手动测试：

```powershell
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "你的资金账号"
```

连接：

```text
ws://127.0.0.1:8000/v1/ws/events
```

观察连接、断开、账号状态或交易回报事件。

## 验收标准

Milestone 5 完成时必须满足：

1. `/ws/events` 可连接。
2. WebSocket 支持 token 鉴权。
3. EventBus 支持多客户端广播。
4. 连接状态和交易回调能进入事件通道。
5. 客户端断开不影响 qmtserver。
6. 心跳事件可用。
7. 自动化测试通过。

## 实际提交

代码、测试和文档随 Milestone 5 完成提交。

## 风险与应对

- 回调线程和 asyncio 冲突：使用线程安全发布入口。
- 慢客户端堆积：每个客户端队列设置最大长度。
- 高频行情压垮 WebSocket：本阶段不推行情高频数据。
- token 泄露：不要通过日志记录 query token。
