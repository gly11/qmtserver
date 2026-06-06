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
POST /v1/market/subscriptions/{subscription_id}/recover
GET  /v1/market/quotes/latest
POST /v1/snapshots
GET  /v1/snapshots
GET  /v1/snapshots/{snapshot_id}/manifest
GET  /v1/snapshots/{snapshot_id}/download
POST /v1/market/data/download
GET  /v1/market/data/bars
GET  /v1/market/data/coverage
GET  /v1/market/data/quality
GET  /v1/market/data/jobs
GET  /v1/market/data/jobs/{job_id}
POST /v1/market/data/jobs/{job_id}/retry-failed
POST /v1/market/data/exports
GET  /v1/market/data/exports
GET  /v1/market/data/exports/{export_id}
GET  /v1/market/data/exports/{export_id}/download
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
    "qmtserver_version": "0.8.0",
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
    "qmtserver_version": "0.8.0",
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
POST /v1/market/subscriptions/{subscription_id}/recover
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

Recover manually rebuilds one existing market subscription with the same `symbols` and `period`:

```http
POST /v1/market/subscriptions/{subscription_id}/recover
```

The response uses the normal subscription envelope and keeps the same `subscription_id`. Recovery
resets the subscription diagnostics counters and publishes `market_subscription` plus
`market_subscription_recovered` events. It only calls the market subscription adapter; it does not
connect trader and does not place, cancel, or modify orders. If the upstream subscribe call fails,
qmtserver marks the subscription `degraded` and records the failure in `last_error`.

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

下载 snapshot 数据文件。当前仅承诺 CSV。找不到 manifest 或数据文件时返回 HTTP 404，body
仍使用 qmtserver JSON error envelope。

### GET /v1/snapshots/{snapshot_id}/quality

基于 snapshot CSV 和 manifest request 生成基础数据质量报告。

## Market Data Lake API

`/v1/market/data` 是高性能行情数据缓存和 Market Data Lake 的 server 端入口。当前阶段提供持久化下载 job、
coverage 查询和缓存命中判断：任务写入 DuckDB 元数据，worker 先检查本地覆盖范围；未命中时
触发只读 `xtdata.download_history_data` 补齐 MiniQMT 行情缓存，再读取标准 bars 并按 symbol
写入 qmtserver Parquet 文件。`/v1/market/data/bars` 从本地 Parquet/DuckDB 读取数据，不触发
MiniQMT 下载。

### POST /v1/market/data/download

```json
{
  "kind": "daily_bars",
  "symbols": ["000001.SZ"],
  "start": "2026-01-01",
  "end": "2026-01-31",
  "chunk_days": 31,
  "mode": "ensure",
  "adjust": "none",
  "format": "parquet"
}
```

也可以让 server 解析股票池，而不是由 client 展开几千个 symbol：

```json
{
  "kind": "daily_bars",
  "universe": "all_a",
  "exchange": "SH",
  "start": "2026-01-01",
  "end": "2026-01-31",
  "adjust": "none",
  "format": "parquet"
}
```

`universe="all_a"` 会通过 server 侧 `xtdata.get_stock_list_in_sector` 解析，`exchange`
可选值为 `SH`、`SZ` 或 `BJ`，用于按证券代码后缀过滤。提交给 data job 的 canonical request
会记录 `resolved_symbols`、`symbol_count` 和 `universe_hash`；job result 也会保留
`universe`、`exchange`、`symbol_count` 和 `universe_hash`，方便追溯全市场任务的输入来源。
请求必须包含至少一个显式 symbol，或包含可解析到至少一个 symbol 的 `universe`；不要用
`symbols=[]` 表达全市场。非法 `exchange` 会返回 `INVALID_MARKET_REQUEST`。
可选 `storage_profile` 必须是 server 配置的白名单 id，不能是本机绝对路径；未知 profile 会返回
`INVALID_MARKET_REQUEST`。
`chunk_days` 用于把大区间下载规划成 symbol/date chunks；默认值为 31，最大值为 366。
server 会将规划结果写入 `data_job_chunks` 元数据表，worker 会逐个执行 chunk，并在 job detail
中返回 chunk 级进度和失败明细。
当 `mode="ensure"` 或 `incremental=true` 且未设置 `force=true` 时，server 会先查询本地
coverage，只为 `gaps` 规划下载 chunks；如果已完整覆盖，则返回 cached job，不会触发新的
MiniQMT 下载。

如果未安装 `qmtserver[data]`，返回 `DATA_BACKEND_UNAVAILABLE`。该接口不连接 trader，
也不执行任何交易命令。

当 `force=false` 且本地 coverage 已完整覆盖请求的 symbol/date range 时，job 会直接标记成功，
结果中 `cached=true`、`downloaded=false`，不会调用 `xtdata.download_history_data`。

### GET /v1/market/data/coverage

查询本地 Parquet 数据覆盖范围：

```text
GET /v1/market/data/coverage?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31&adjust=none
```

响应使用 `market.data.coverage.v1`，包含 `fully_covered`、`coverage`、`covered_segments`、
`gaps` 和 `missing_symbols`。`coverage` 是按 symbol/period/adjust 合并后的摘要，
`covered_segments` 来自已登记的本地 data files；缓存命中判断使用 segments 检查中间缺口，
不会只因为 summary 首尾覆盖请求区间就跳过下载。每个 gap 包含 `reason`，例如
`no_matching_coverage` 或 `segment_gap`，用于区分完全没有匹配文件和已有文件中间缺口。

### GET /v1/market/data/bars

从本地 data lake 查询 bars：

```text
GET /v1/market/data/bars?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31&adjust=none&limit=1000&offset=0
```

该接口只读取已登记的本地 Parquet 文件。若没有匹配文件，返回 `ok=true`、`bars=[]`、
`row_count=0`。结果按 symbol 和 bar time 稳定排序，并按 symbol/period/time 去重。
大结果通过 `limit` 和 `offset` 分页；响应包含 `total_row_count`、`source_file_count`、
`deduplicated_row_count`、`truncated`、`next_offset`、`query_profile` 和 `recommendations`。
当前 DuckDB reader 会直接对多个 Parquet 文件执行一次 `read_parquet([...], union_by_name=true)`
聚合查询，在 SQL 层完成过滤、排序、去重、计数和分页，避免逐文件读出后再用 Python 合并。
如果 `truncated=true`，下一页使用 `next_offset`；如果结果集较大，优先使用
`POST /v1/market/data/exports` 生成本地 CSV export。

### GET /v1/market/data/quality

基于本地 data lake bars 返回 `market.quality.v1` 质量报告：

```text
GET /v1/market/data/quality?kind=daily_bars&symbols=000001.SZ&start=2026-01-01&end=2026-01-31
```

该接口复用 qmtserver 的保守质量检查，包括缺失日期、重复行、价格异常和成交量异常。它只读取
本地 Parquet/DuckDB，不触发新的 MiniQMT 下载。

### POST /v1/market/data/exports

从本地 data lake 生成 CSV 或 Parquet export：

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

该接口只读取本地 Parquet/DuckDB，不触发新的 MiniQMT 下载。响应 manifest 使用
`market.data.export.v1`，并记录 `source_file_count`、`deduplicated_row_count` 和 `truncated`，
方便判断 export 是否来自多个本地文件或是否受请求 limit 截断。manifest 的 `download` 字段
包含 `filename`、`format`、`content_length`、`hash` 和 `etag`，供 qmtclient 下载后校验。
`format` 当前支持 `csv` 和 `parquet`。大批量结果建议使用 export，而不是连续拉取很多页 HTTP
bars 响应。

```text
GET /v1/market/data/exports
GET /v1/market/data/exports/{export_id}
GET /v1/market/data/exports/{export_id}/download
DELETE /v1/market/data/exports/{export_id}
```

`DELETE` 只删除 qmtserver 本地 export CSV 和 manifest，不删除 MiniQMT 缓存或 Parquet 原始数据。
`GET /download` 找不到 manifest 或数据文件时返回 HTTP 404，body 仍使用 qmtserver JSON error
envelope，错误码为 `EXPORT_NOT_FOUND`，避免下载客户端把 200 JSON error 保存成 CSV 或 Parquet
文件。
download response 由 Starlette `FileResponse` 提供 `Content-Length`、`ETag`、`Accept-Ranges`
和 HTTP Range 请求支持；client 可结合 manifest 的 `download.hash` 校验文件内容。

### GET /v1/market/data/jobs/{job_id}

查询 data download job 状态。成功结果包含 `file_count`、`row_count` 和写入的 Parquet 文件摘要。
状态会写入 DuckDB 元数据，设计上用于服务重启后的状态查询。成功结果还包含
`symbol_results`，按 symbol 汇总 `downloaded`、`cached`、`failed`、`row_count`、`file_count`、
coverage 起止、gaps 和 error。失败 job 的 `error.code` 会使用 data lake 专用错误码，例如
`DATA_DOWNLOAD_FAILED`，并保留 `result.partial=true` 的 partial result，方便 client 展示已经完成
和失败的 symbol。
响应还包含 `progress` 和 `chunks`。`progress` 汇总 `total_symbols`、`finished_symbols`、
`failed_symbols`、`current_symbol`、`total_chunks`、`finished_chunks`、`failed_chunks`、
`queued_chunks`、`row_count` 和 `file_count`；`chunks` 保留每个 symbol/date chunk 的
`status`、`attempts`、`row_count`、`file_count`、`error_code` 和 `error_message`，用于定位
大任务的失败子区间。

### POST /v1/market/data/jobs/{job_id}/retry-failed

只重跑指定 data download job 中 `status="failed"` 的 chunks。已成功的 chunks 不会重复执行。
如果所有 failed chunks 重试成功，job 会重新标记为 `succeeded`，并返回基于 chunk metadata
汇总的 `result`、`progress` 和 `chunks`。如果仍有 chunk 失败，job 保持 `failed`，并保留
`result.partial=true`。

### GET /v1/market/data/jobs

列出持久化 data download jobs：

```text
GET /v1/market/data/jobs?status=succeeded&limit=50
```

`status` 可选；`limit` 最大限制为 200。该接口只读取 DuckDB job 元数据，不触发 MiniQMT 下载。

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
用于排查连接和行情源状态。响应还包含 `data_lake`：

- `data_lake.health`：本地 data lake 目录健康摘要，包括 registered/orphan/missing/mismatch 和
  coverage consistency 等计数。
- `data_lake.jobs`：持久化 data download job 诊断摘要，包括 failed jobs 和 stale running jobs。
- `data_lake.error`：如果未安装或未启用 data extra，会返回 `DATA_BACKEND_UNAVAILABLE` 等稳定错误码。

该诊断只读取本地 DuckDB/Parquet metadata，不连接 trader，不触发 MiniQMT 下载，也不执行交易命令。

`data.runtime_health` 提供长期运行摘要：

```json
{
  "schema": "runtime.health.v1",
  "status": "degraded",
  "reasons": ["subscription_callback_stale"],
  "quote": {"status": "connected", "connected": true, "enabled": true},
  "trader": {"status": "connected", "connected": true, "enabled": true},
  "subscriptions": {
    "total": 1,
    "active": 1,
    "degraded": 0,
    "stopped": 0,
    "stale_callbacks": 1
  }
}
```

`status` 为 `ok` 或 `degraded`。`degraded` 表示 quote 未连接、订阅 degraded，或活跃订阅的
callback 已过期。该摘要只用于运维健康判断，不改变交易保护规则。

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
