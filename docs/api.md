# API Reference

qmtserver 推荐使用 `/v1` 入口。旧的无版本路径会暂时保留，方便已有脚本继续运行。

## Stable v1 Endpoints

```text
GET  /v1/health
GET  /v1/qmt/status
POST /v1/qmt/connect
POST /v1/qmt/reconnect
POST /v1/qmt/disconnect
GET  /v1/rpc/methods
POST /v1/rpc
GET  /v1/metrics
GET  /v1/orders
GET  /v1/orders/{order_id}
GET  /v1/trades
GET  /v1/events/recent
WS   /v1/ws/events
```

## RPC Request

```json
{
  "target": "xtdata",
  "method": "get_full_tick",
  "args": [["000001.SZ"]],
  "kwargs": {}
}
```

## RPC Success

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "target": "xtdata",
    "method": "get_full_tick",
    "request_id": "...",
    "version": "v1",
    "level": "readonly",
    "elapsed_ms": 1.2
  }
}
```

## RPC Error

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TRADING_DISABLED",
    "message": "Trading RPC methods are disabled"
  },
  "meta": {
    "target": "trader",
    "method": "order_stock",
    "request_id": "...",
    "version": "v1",
    "level": "trading",
    "elapsed_ms": 1.2
  }
}
```

## Request ID

HTTP 请求可以传入 `X-Request-ID`。服务会在响应头中回写同一个值；如果没有传入，服务会生成 UUID。

## WebSocket Events

```text
ws://127.0.0.1:8000/v1/ws/events
ws://127.0.0.1:8000/v1/ws/events?types=stock_order,stock_trade
```

事件结构：

```json
{
  "type": "heartbeat",
  "ts": "2026-05-25T21:00:00+08:00",
  "data": {},
  "meta": {
    "source": "qmtserver",
    "sequence": 1
  }
}
```

## Order and Event Cache

第一版订单和事件缓存是进程内存缓存，服务重启后清空。

```text
GET /v1/orders
GET /v1/orders/{order_id}
GET /v1/trades
GET /v1/events/recent?types=stock_order,stock_trade
```
