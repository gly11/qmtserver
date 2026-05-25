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
| `ORDER_LIMIT_EXCEEDED` | Order volume or amount exceeded configured limits. |
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
