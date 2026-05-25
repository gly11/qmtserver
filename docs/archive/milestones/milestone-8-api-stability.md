# Milestone 8: API Stability and Compatibility

Milestone 8 的目标是把已经能跑的 HTTP RPC、WebSocket 和 Python SDK 固化成稳定契约，降低后续扩展时破坏外部调用方的风险。

状态：已完成。

## 目标

完成后应支持：

- API 版本边界清晰，例如 `/v1`。
- HTTP、RPC、WebSocket、SDK 的错误结构一致。
- 错误码集中定义和文档化。
- OpenAPI 文档能准确表达主要接口。
- SDK 能识别服务端版本和兼容性。
- 契约测试覆盖核心接口响应结构。

已落地：

- 新增 `/v1` HTTP 和 WebSocket 路由，同时保留旧路径。
- RPC `meta` 增加 `request_id` 和 `version`。
- 错误码集中定义在 `qmtserver.errors.ERROR_CODES`。
- SDK 默认调用 `/v1`，可通过 `api_version=None` 使用旧路径。
- SDK 错误对象保留 `code`、`message`、`request_id` 和原始响应。
- 新增 `docs/api.md`、`docs/errors.md`、`docs/sdk.md`。

## 非目标

Milestone 8 暂不做：

- 重写现有 `/rpc` 协议。
- 引入 gRPC / Protobuf。
- 引入数据库。
- 支持多版本长期并行维护。
- 对外发布 PyPI 包。

## 当前基础

已具备：

- `/health`、`/qmt/*`、`/rpc*`、`/ws/events`、`/metrics`。
- Python SDK。
- 结构化错误码雏形。
- OpenAPI 由 FastAPI 自动生成。

## API 版本策略

建议新增 `/v1` 路由前缀，同时保留现有无版本端点作为兼容入口。

第一版：

```text
GET  /v1/health
GET  /v1/qmt/status
POST /v1/qmt/connect
POST /v1/qmt/reconnect
POST /v1/qmt/disconnect
GET  /v1/rpc/methods
POST /v1/rpc
GET  /v1/metrics
WS   /v1/ws/events
```

兼容规则：

- `/v1/*` 是推荐入口。
- 旧路径短期保留，不立刻删除。
- SDK 默认使用 `/v1`，但允许关闭版本前缀。

## 错误契约

统一错误结构：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TRADING_DISABLED",
    "message": "Trading RPC methods are disabled"
  },
  "meta": {
    "request_id": "...",
    "version": "v1"
  }
}
```

需要整理的错误码：

```text
UNAUTHORIZED
METHOD_NOT_ALLOWED
METHOD_NOT_FOUND
TARGET_NOT_FOUND
TARGET_NOT_CONNECTED
TRADING_DISABLED
TRADING_VALIDATION_ERROR
ACCOUNT_NOT_ALLOWED
ORDER_LIMIT_EXCEEDED
RPC_ERROR
QMT_SERVER_ERROR
```

## SDK 兼容性

SDK 增加：

- `client.version()` 或 `client.health()` 读取服务端版本。
- `QmtClient(..., api_version="v1")`。
- 服务端不支持期望版本时抛明确异常。
- SDK 错误对象保留 `code`、`message`、`request_id`、`response`。

## 文档

新增或更新：

```text
docs/api.md
docs/errors.md
docs/sdk.md
```

README 只保留常用入口，详细契约放入 `docs/`。

## 测试计划

单元测试：

- `/v1` 路由可用。
- 旧路由仍可用。
- 错误响应结构稳定。
- SDK 默认调用 `/v1`。
- SDK 可读取服务端版本。
- 错误码文档和代码枚举一致。

接口测试：

- `GET /v1/health`。
- `POST /v1/rpc` 成功和失败响应。
- `GET /v1/rpc/methods` 返回 method specs。
- `WS /v1/ws/events` 可连接。

## 验收标准

Milestone 8 完成时必须满足：

1. `/v1` API 可用。
2. 旧 API 不破坏。
3. 错误码集中定义并文档化。
4. SDK 默认使用稳定版本入口。
5. OpenAPI/文档包含主要接口。
6. 自动化测试通过。

## 实际提交

代码、测试和文档随 Milestone 8 完成提交。

## 风险与应对

- 版本路径引入重复路由：用共享 router 或统一注册函数避免逻辑分叉。
- SDK 兼容性过度复杂：只支持当前 `v1`，不做多版本矩阵。
- 错误结构变动影响旧调用方：旧路径保持当前行为，`/v1` 固化新契约。
