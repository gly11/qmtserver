# API Reference

qmtserver 推荐使用 `/v1` 入口。旧的无版本路径会暂时保留，方便已有脚本继续运行。

## Stable v1 Endpoints

```text
GET  /v1/health
GET  /v1/qmt/status
POST /v1/qmt/connect
POST /v1/qmt/reconnect
POST /v1/qmt/disconnect
GET  /v1/trader/account-status
GET  /v1/trader/asset
GET  /v1/trader/positions
GET  /v1/trader/orders
GET  /v1/trader/trades
GET  /v1/market/capabilities
GET  /v1/market/bars/daily
GET  /v1/market/bars/intraday
POST /v1/market/subscriptions
GET  /v1/market/subscriptions
GET  /v1/market/subscriptions/{subscription_id}
GET  /v1/market/subscriptions/{subscription_id}/diagnostics
DELETE /v1/market/subscriptions/{subscription_id}
GET  /v1/market/quotes/latest
POST /v1/snapshots
GET  /v1/snapshots
GET  /v1/snapshots/{snapshot_id}/manifest
GET  /v1/snapshots/{snapshot_id}/download
POST /v1/jobs/history-download
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/result
POST /v1/jobs/{job_id}/cancel
GET  /v1/diagnostics
GET  /v1/reference/calendar
GET  /v1/reference/universe
GET  /v1/reference/instruments
GET  /v1/market/bars/daily/quality
GET  /v1/snapshots/{snapshot_id}/quality
GET  /v1/rpc/methods
POST /v1/rpc
GET  /v1/metrics
GET  /v1/orders
GET  /v1/orders/{order_id}
GET  /v1/trades
GET  /v1/events/recent
WS   /v1/ws/events
```

## Trader Readonly API

`/v1/trader` exposes stable readonly account query endpoints. These endpoints do not require
`QMT_ENABLE_TRADING=true` and do not place or cancel orders. They require the trader target to be
connected. Account-specific endpoints resolve `account_id` from the query string first, then from
`QMT_ACCOUNT_ID`.

```text
GET /v1/trader/account-status
GET /v1/trader/asset?account_id=10001&account_type=STOCK
GET /v1/trader/positions?account_id=10001
GET /v1/trader/orders?account_id=10001&cancelable_only=true
GET /v1/trader/trades?account_id=10001
```

All trader readonly responses use the `trader.readonly.v1` schema and the standard qmtserver
envelope:

```json
{
  "ok": true,
  "data": {
    "asset": {
      "account_id": "10001",
      "cash": 1000.0,
      "frozen_cash": 0.0,
      "market_value": 2000.0,
      "total_asset": 3000.0,
      "fetch_balance": 1000.0,
      "extra": {}
    }
  },
  "error": null,
  "meta": {
    "schema": "trader.readonly.v1",
    "qmtserver_version": "0.6.0",
    "xtquant_version": null,
    "account_id": "***",
    "account_type": "STOCK"
  }
}
```

Missing account configuration returns `TRADER_ACCOUNT_REQUIRED`. A disconnected trader target
returns `TARGET_NOT_CONNECTED`.

## Market Data API

`/v1/market` 是策略和回测系统优先使用的稳定行情入口。它只调用 qmtserver 明确适配的
whitelist-only 行情方法，不依赖 transparent RPC，也不直接暴露 `xtdata` 原始返回形态。

### GET /v1/market/capabilities

返回当前稳定行情 API 的 schema versions、supported endpoints、periods、adjust modes 和内部
数据源方法。

### GET /v1/market/bars/daily

示例：

```text
GET /v1/market/bars/daily?symbols=000001.SZ,600000.SH&start=2026-01-01&end=2026-01-31&adjust=none
```

响应字段固定为：

```json
{
  "ok": true,
  "data": {
    "bars": [
      {
        "date": "2026-01-02",
        "symbol": "000001.SZ",
        "open": 10.1,
        "high": 10.5,
        "low": 10.0,
        "close": 10.3,
        "volume": 1200000,
        "amount": 12345678.9,
        "meta": {}
      }
    ]
  },
  "error": null,
  "meta": {
    "schema": "market.bars.v1",
    "request": {
      "symbols": ["000001.SZ"],
      "start": "2026-01-01",
      "end": "2026-01-31",
      "adjust": "none"
    },
    "row_count": 1,
    "generated_at": "2026-05-26T00:00:00+00:00",
    "qmtserver_version": "0.6.0",
    "xtquant_version": null
  }
}
```

### GET /v1/market/bars/intraday

示例：

```text
GET /v1/market/bars/intraday?symbols=000001.SZ&period=1m&start=2026-01-01T09:30:00+08:00&end=2026-01-01T15:00:00+08:00&adjust=none
```

intraday bar 字段固定为 `timestamp`、`symbol`、`period`、`open`、`high`、`low`、`close`、
`volume`、`amount` 和 `meta`。

空数据不是错误：服务返回 `ok=true`、`bars=[]` 和 `row_count=0`。参数非法返回
`INVALID_MARKET_REQUEST`，行情源异常返回 `MARKET_DATA_ERROR`，行情 target 未连接返回
`TARGET_NOT_CONNECTED`。

### Realtime Market Subscriptions

Realtime subscriptions are readonly market-data APIs. They call qmtserver's explicit
`xtdata.subscribe_quote` adapter and publish normalized WebSocket events; they do not place, cancel,
or modify orders.
After the upstream subscription is accepted, qmtserver also emits a best-effort initial
`market_quote` from `xtdata.get_full_tick` so after-hours smoke can verify the event path.

```text
POST /v1/market/subscriptions
GET /v1/market/subscriptions
GET /v1/market/subscriptions/{subscription_id}
GET /v1/market/subscriptions/{subscription_id}/diagnostics
DELETE /v1/market/subscriptions/{subscription_id}
GET /v1/market/quotes/latest?symbols=000001.SZ,600000.SH
```

Create request:

```json
{
  "symbols": ["000001.SZ"],
  "period": "tick"
}
```

Create response:

```json
{
  "ok": true,
  "data": {
    "schema": "market.subscription.v1",
    "subscription_id": "sub_...",
    "symbols": ["000001.SZ"],
    "period": "tick",
    "status": "active",
    "created_at": "2026-05-27T09:30:00+00:00",
    "updated_at": "2026-05-27T09:30:00+00:00",
    "upstream_id": [1],
    "last_error": null
  },
  "error": null
}
```

Invalid requests return `INVALID_SUBSCRIPTION_REQUEST`. Missing quote connectivity returns
`TARGET_NOT_CONNECTED` for request paths that cannot reach the quote target. If upstream subscription
creation fails after local state is created, qmtserver marks the subscription `degraded` and records
`last_error` / `degraded_reason` in diagnostics. If the local `xtquant` package cannot unsubscribe
reliably, qmtserver marks the local subscription `stopped` and ignores later callbacks for that
`subscription_id`.
Stopped subscriptions do not update latest quote cache or subscription diagnostics.

Latest quote cache:

```json
{
  "ok": true,
  "data": {
    "schema": "market.latest_quotes.v1",
    "quotes": [
      {
        "symbol": "000001.SZ",
        "quote": {
          "schema": "market.quote.v1",
          "symbol": "000001.SZ",
          "last_price": 10.25
        },
        "quote_source": "callback",
        "updated_at": "2026-05-28T05:30:00+00:00",
        "subscription_id": "sub_...",
        "event_seq": 2
      }
    ],
    "missing_symbols": ["600000.SH"]
  },
  "error": null
}
```

Subscription diagnostics:

```json
{
  "ok": true,
  "data": {
    "schema": "market.subscription_diagnostics.v1",
    "subscription_id": "sub_...",
    "status": "active",
    "active_symbols": ["000001.SZ"],
    "callback_count": 1,
    "initial_quote_count": 1,
    "last_quote_at": "2026-05-28T05:30:00+00:00",
    "last_initial_quote_at": "2026-05-28T05:29:58+00:00",
    "last_callback_at": "2026-05-28T05:30:00+00:00",
    "last_quote_source": "callback",
    "last_event_seq": 2,
    "seconds_since_last_quote": 1.25,
    "seconds_since_last_callback": 1.25,
    "is_callback_active": true,
    "callback_stale_after_seconds": 30,
    "last_error": null
  },
  "error": null
}
```

## Snapshot API

`/v1/snapshots` 用于回测批量数据准备。大批量数据不通过普通 JSON response 返回，而是写入
服务端 snapshot 文件，并通过 manifest 描述参数、schema、格式、hash、覆盖区间和版本信息。
首个稳定导出格式是 CSV。

CSV 文件字段跟随 snapshot kind：

- `daily_bars`：`date`、`symbol`、`open`、`high`、`low`、`close`、`volume`、`amount`、`meta`
- `intraday_bars`：`timestamp`、`symbol`、`period`、`open`、`high`、`low`、`close`、`volume`、
  `amount`、`meta`

`meta` 在 CSV 中序列化为 JSON 字符串。

## Recent Events

`GET /v1/events/recent` returns the in-memory recent event cache. It is useful after a WebSocket
reconnect, but it is not persistent storage. Use latest quote cache for current market state.

Examples:

```text
GET /v1/events/recent?types=market_quote&symbol=000001.SZ
GET /v1/events/recent?types=market_quote&symbols=000001.SZ,600000.SH&limit=20
```

The `types` filter accepts comma-separated event types. `symbol` or `symbols` filters events whose
`data.symbol` matches one of the requested symbols.

### POST /v1/snapshots

创建或复用 snapshot：

```json
{
  "kind": "daily_bars",
  "symbols": ["000001.SZ"],
  "start": "2026-01-01",
  "end": "2026-01-31",
  "adjust": "none",
  "format": "csv"
}
```

如果相同参数已经生成过 snapshot，服务返回同一个 manifest，并在 `data.cached` 中标记缓存命中。
缓存命中基于 canonical request 的 `request_hash`，包含 kind、symbols、start、end、adjust、
format，以及 intraday 请求的 period。

### GET /v1/snapshots

列出当前 snapshot registry 中的 manifest 摘要。

### GET /v1/snapshots/{snapshot_id}/manifest

返回指定 snapshot manifest。

### GET /v1/snapshots/{snapshot_id}/download

下载 snapshot 数据文件。当前仅承诺 CSV。

### GET /v1/snapshots/{snapshot_id}/quality

基于 snapshot CSV 和 manifest request 生成基础数据质量报告。

## Reference and Quality API

Reference endpoints 用于回测前置数据准备。首版提供 weekday-based calendar、股票池和
instrument detail 的稳定响应结构。

```text
GET /v1/reference/calendar?start=2026-01-01&end=2026-01-31
GET /v1/reference/universe?name=all_a
GET /v1/reference/instruments?symbols=000001.SZ,600000.SH
```

数据质量报告只描述数据问题，不提供投资建议或交易决策：

```text
GET /v1/market/bars/daily/quality?symbols=000001.SZ&start=2026-01-01&end=2026-01-31
GET /v1/snapshots/{snapshot_id}/quality
```

质量报告 schema 为 `market.quality.v1`，包含 `missing_dates`、`duplicate_rows`、
`price_anomalies` 和 `volume_anomalies`。

## Jobs and Diagnostics

历史下载类任务使用内存 job registry。服务重启后 job 状态会清空；已生成的 snapshot 文件和
manifest 仍保留在 snapshot 目录中。

### POST /v1/jobs/history-download

创建历史下载 job。首版 job runner 在后台线程中执行，并把成功结果关联到 snapshot manifest。
请求体沿用 snapshot 创建参数。job 会先调用 qmtserver 的 `xtdata.download_history_data` 适配层
逐标的同步下载历史行情，然后再生成或复用 snapshot manifest。该操作只写入 MiniQMT 行情数据
缓存和 qmtserver snapshot 目录，不连接 trader，也不执行交易命令。

### GET /v1/jobs/{job_id}

查询 job 状态。状态包括 `queued`、`running`、`succeeded`、`failed` 和 `cancelled`。

### GET /v1/jobs/{job_id}/result

成功后返回关联的 snapshot manifest。结果未就绪时返回 `JOB_NOT_READY`。

### POST /v1/jobs/{job_id}/cancel

取消尚未运行的 job。running job 的取消是 best effort，首版只保证 queued job 可取消。

### GET /v1/diagnostics

返回 MiniQMT/qmtserver 状态、server clock、qmtserver/xtquant 版本和 sample symbol smoke 信息，
用于排查连接和行情源状态。

## RPC Request

默认模式下 RPC 是白名单 RPC，不是全透明 `xtquant` 代理。白名单外方法会返回
`METHOD_NOT_ALLOWED`。`0.2.0` 增加了默认关闭的透明 RPC 实验模式，见
[Transparent RPC](transparent-rpc.md)。

```json
{
  "target": "xtdata",
  "method": "get_full_tick",
  "args": [["000001.SZ"]],
  "kwargs": {}
}
```

## RPC Examples

只读行情请求：

```json
{
  "target": "xtdata",
  "method": "get_full_tick",
  "args": [["000001.SZ"]],
  "kwargs": {}
}
```

透明 RPC 请求需要显式开启 `QMT_TRANSPARENT_RPC=true`。开启后，允许 target 上的公开白名单外
方法可以继续使用同一个 `/v1/rpc` endpoint：

```json
{
  "target": "xtdata",
  "method": "get_sector_list",
  "args": [],
  "kwargs": {}
}
```

透明调用成功时，响应结构不变，`meta.level` 为 `transparent`。如果 target、方法名或疑似交易
方法不符合透明 RPC 安全规则，响应仍使用标准 RPC error envelope。详细规则见
[Transparent RPC](transparent-rpc.md)。

交易账号查询：

```json
{
  "target": "trader",
  "method": "query_stock_asset",
  "args": [
    {
      "__type__": "StockAccount",
      "account_id": "资金账号",
      "account_type": "STOCK"
    }
  ],
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
ws://127.0.0.1:8000/v1/ws/events?types=market_subscription,market_quote
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

Realtime quote events use the same envelope:

```json
{
  "type": "market_quote",
  "ts": "2026-05-27T09:30:01+00:00",
  "data": {
    "schema": "market.quote.v1",
    "symbol": "000001.SZ",
    "time": "2026-05-27T09:30:01+08:00",
    "last_price": 10.25,
    "volume": 1200,
    "amount": 12300.0,
    "extra": {}
  },
  "meta": {
    "source": "xtdata",
    "sequence": 10,
    "subscription_id": "sub_...",
    "quote_source": "initial"
  }
}
```

`quote_source` is `initial` for the best-effort `get_full_tick` seed and `callback` for live
`subscribe_quote` callbacks.

## Order and Event Cache

第一版订单和事件缓存是进程内存缓存，服务重启后清空。

```text
GET /v1/orders
GET /v1/orders/{order_id}
GET /v1/trades
GET /v1/events/recent?types=stock_order,stock_trade
```
