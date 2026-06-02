# Error Codes

qmtserver 的错误码集中定义在 `qmtserver.errors.ERROR_CODES`。客户端应优先判断 `error.code`，不要依赖完整错误文本。

| Code | Meaning |
| --- | --- |
| `UNAUTHORIZED` | Authentication failed or bearer token is missing. |
| `METHOD_NOT_ALLOWED` | RPC method is not enabled in the allowlist. |
| `METHOD_NOT_FOUND` | Target object does not expose the requested method. |
| `TARGET_NOT_FOUND` | RPC target name is unknown. |
| `TARGET_NOT_CONNECTED` | RPC target exists but is not currently connected. |
| `TRADING_DISABLED` | Trading RPC methods are disabled by configuration. |
| `TRADING_VALIDATION_ERROR` | Trading request failed validation. |
| `ACCOUNT_NOT_ALLOWED` | Trading account is not in the allowed account set. |
| `SYMBOL_NOT_ALLOWED` | Trading symbol is not allowed by safety settings. |
| `ORDER_LIMIT_EXCEEDED` | Order volume or amount exceeded configured limits. |
| `ORDER_NOT_FOUND` | Requested order is not in the in-memory order cache. |
| `DAILY_LIMIT_EXCEEDED` | Daily process-level trading limit would be exceeded. |
| `TRADE_CONFIRMATION_REQUIRED` | Real trading requires an explicit confirmation. |
| `TRANSPARENT_TARGET_NOT_ALLOWED` | Transparent RPC target is not allowed. |
| `TRANSPARENT_METHOD_DENIED` | Transparent RPC method name is denied. |
| `TRANSPARENT_TRADER_DENIED` | Transparent RPC for trader is disabled. |
| `TRANSPARENT_TRADING_DENIED` | Transparent RPC trading-like method is denied. |
| `INVALID_MARKET_REQUEST` | Market data request parameters are invalid. |
| `MARKET_DATA_ERROR` | Market data source returned an unexpected error. |
| `INVALID_SUBSCRIPTION_REQUEST` | Market subscription parameters are invalid. |
| `MARKET_SUBSCRIPTION_ERROR` | Market subscription failed unexpectedly. |
| `MARKET_SUBSCRIPTION_NOT_FOUND` | Requested market subscription was not found. |
| `MARKET_SUBSCRIPTION_UNSUPPORTED` | Market subscription behavior is unsupported. |
| `INVALID_SNAPSHOT_REQUEST` | Snapshot request parameters are invalid. |
| `SNAPSHOT_NOT_FOUND` | Requested snapshot or snapshot file was not found. |
| `JOB_NOT_FOUND` | Requested job is not in the in-memory job registry. |
| `JOB_NOT_READY` | Requested job result is not ready. |
| `JOB_NOT_CANCELLABLE` | Requested job cannot be cancelled. |
| `DATA_BACKEND_UNAVAILABLE` | Optional data lake dependencies are not installed or enabled. |
| `DATA_EXPORT_UNAVAILABLE` | Data lake export service is not available. |
| `TRADER_ACCOUNT_REQUIRED` | Readonly trader query requires an account id. |
| `RPC_ERROR` | Client-side wrapper for an RPC error response. |
| `QMT_SERVER_ERROR` | Generic qmtserver error. |

## HTTP Authentication Error

FastAPI authentication failures use `detail`:

```json
{
  "detail": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid bearer token"
  }
}
```

## RPC Error

RPC failures use the stable response envelope:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "METHOD_NOT_ALLOWED",
    "message": "RPC method is not allowed: trader.unknown"
  },
  "meta": {}
}
```

## Market Data Error

Market data endpoints use the same stable envelope shape as RPC endpoints:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "INVALID_MARKET_REQUEST",
    "message": "symbols must include at least one symbol"
  },
  "meta": {
    "schema": "market.bars.v1",
    "request": {},
    "row_count": 0,
    "generated_at": "2026-05-26T00:00:00+00:00",
    "qmtserver_version": "0.8.0",
    "xtquant_version": null
  }
}
```
