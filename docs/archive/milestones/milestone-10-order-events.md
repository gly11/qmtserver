# Milestone 10: Order State and Event Loop

Milestone 10 的目标是把下单、撤单、委托回报、成交回报和事件订阅串成完整闭环，让手动运行时也能清楚看到交易后发生了什么。

状态：已完成。

## 目标

完成后应支持：

- 订单状态内存缓存。
- 最近事件缓存。
- 查询最近订单、成交和事件。
- WebSocket 事件过滤。
- SDK 事件回调或过滤订阅。
- 下单返回值与后续回报能关联。

已落地：

- 新增 `OrderStore` 进程内存缓存，记录最近委托、成交和错误。
- `EventBus` 维护最近事件缓存。
- 新增 `/v1/orders`、`/v1/orders/{order_id}`、`/v1/trades`、`/v1/events/recent`，旧路径也保留。
- WebSocket 支持 `types=stock_order,stock_trade` 过滤，heartbeat 不受过滤影响。
- SDK 支持 `events(types=...)`、`orders()`、`order()`、`trades()`、`recent_events()`。
- `MiniQmtCallback` 将委托、成交、下单错误和撤单错误写入缓存并发布事件。

## 非目标

Milestone 10 暂不做：

- 数据库持久化订单。
- 高可用事件队列。
- 行情高频推送。
- 前端 UI。
- 完整策略状态机。

## 当前基础

已具备：

- 交易 RPC。
- WebSocket `/ws/events`。
- `MiniQmtCallback` 可以发布委托、成交和错误事件。
- Python SDK 可迭代消费事件。

## 订单状态缓存

建议新增：

```text
src/qmtserver/orders/
├── __init__.py
├── store.py
└── models.py
```

第一版使用内存缓存：

- 最近 N 条订单。
- 最近 N 条成交。
- 最近 N 条错误。
- 按 order_id 或 xtquant 返回 id 查询。

配置：

```env
QMT_ORDER_CACHE_SIZE=1000
QMT_EVENT_CACHE_SIZE=1000
```

## API

建议新增：

```text
GET /v1/orders
GET /v1/orders/{order_id}
GET /v1/trades
GET /v1/events/recent
```

如果 M8 尚未实现 `/v1`，则先以无版本路径实现，M8 时统一挂载。

## WebSocket 过滤

支持 query 参数：

```text
WS /ws/events?types=stock_order,stock_trade,order_error
```

过滤规则：

- 空值表示接收全部事件。
- 多个类型逗号分隔。
- heartbeat 默认仍发送，避免客户端误判断线。

## SDK

建议增强：

```python
for event in client.events(types=["stock_order", "stock_trade"]):
    ...

client.on_event("stock_trade", callback)
client.orders()
client.trades()
client.recent_events()
```

回调式订阅可以作为轻量同步实现，复杂 async 版本后续再做。

## 测试计划

单元测试：

- OrderStore 记录和查询订单。
- 最近事件缓存按容量裁剪。
- 回调事件能写入订单缓存。
- WebSocket types 过滤。
- heartbeat 不被过滤掉。
- SDK events(types=...) 构造正确 URL。

接口测试：

- 下单 dry-run 后返回可追踪字段。
- fake callback 发布 order/trade 后，`/orders` 或 `/trades` 可查询。
- 多客户端过滤互不影响。

## 验收标准

Milestone 10 完成时必须满足：

1. 委托、成交、错误事件进入内存缓存。
2. 可通过 HTTP 查询最近订单、成交和事件。
3. WebSocket 支持事件类型过滤。
4. SDK 支持事件过滤和常用查询。
5. 自动化测试通过。

## 实际提交

代码、测试和文档随 Milestone 10 完成提交。

## 风险与应对

- xtquant 回调字段不稳定：序列化层保持宽松，未知字段保留 JSON 友好形式。
- 内存缓存不是持久化：文档明确重启后清空。
- 事件过滤遗漏 heartbeat：heartbeat 默认不受过滤影响。
