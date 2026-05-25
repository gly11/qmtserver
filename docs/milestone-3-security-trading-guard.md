# Milestone 3: Security Boundary and Trading Guard

Milestone 3 的目标是给 qmtserver 建立安全边界，为后续开放真实交易能力做准备。这个阶段仍不开放真实下单和撤单；重点是鉴权、方法分级、交易保护开关和审计日志。

状态：已完成。

## 目标

完成后应支持：

- 通过 `QMT_API_TOKEN` 启用 API token 鉴权。
- 支持 `Authorization: Bearer <token>`。
- `/health` 保持无需鉴权，方便本机健康检查。
- `/qmt/*` 和 `/rpc*` 在配置 token 后必须鉴权。
- RPC 方法分级：`readonly`、`trading`、`admin`。
- `QMT_ENABLE_TRADING=false` 时所有 trading 方法都被拒绝。
- 即使 future milestone 将交易方法加入白名单，默认也不会真实开放。
- RPC 调用记录审计日志：target、method、level、参数摘要、耗时、结果。
- 不在日志中写入 token、完整账号敏感信息或大体量行情响应。

已落地：

- `QMT_API_TOKEN` / `QMT_REQUIRE_TOKEN` 控制 bearer token 鉴权。
- `/health` 保持开放，`/qmt/*` 和 `/rpc*` 在 token 配置后受保护。
- RPC registry 升级为 `RpcMethodSpec`，记录 `readonly` / `trading` / `admin` 等级。
- `order_stock`、`order_stock_async`、`cancel_order_stock`、`cancel_order_stock_async` 作为 disabled trading spec 预留。
- `QMT_ENABLE_TRADING=false` 时 trading 方法返回 `TRADING_DISABLED`。
- `qmtserver.audit` 记录 RPC 调用摘要、等级、结果和耗时。

## 非目标

Milestone 3 暂不做：

- 真实下单和撤单 API。
- WebSocket 推送。
- 多用户权限系统。
- OAuth、JWT、RBAC。
- 数据库持久化审计日志。
- 限流和 IP 白名单。

这些内容可以放在后续交易、推送和运维阶段。

## 当前基础

Milestone 1/2 已经提供：

- FastAPI 服务。
- 只读 RPC 白名单。
- `QmtService` 生命周期管理。
- 稳定 target 错误码。
- `.env` 配置入口。

Milestone 3 应在这些基础上增加安全层，而不是重写 RPC 和服务层。

## 配置

保留：

```env
QMT_ENABLE_TRADING=false
QMT_API_TOKEN=
```

建议新增：

```env
QMT_REQUIRE_TOKEN=false
QMT_AUDIT_LOG=true
QMT_AUDIT_LOG_ARGS=true
```

语义：

- `QMT_API_TOKEN` 为空时，默认不启用鉴权。
- `QMT_REQUIRE_TOKEN=true` 但 `QMT_API_TOKEN` 为空时，服务启动应给出明确错误。
- `QMT_ENABLE_TRADING=false` 是默认值，必须保持。
- `QMT_AUDIT_LOG=true` 时记录 RPC 调用摘要。
- `QMT_AUDIT_LOG_ARGS=false` 时只记录方法名和结果，不记录参数摘要。

## API 鉴权设计

鉴权规则：

```text
GET  /health       不需要 token
GET  /qmt/status   需要 token，如果 token 已配置
POST /qmt/connect  需要 token，如果 token 已配置
POST /qmt/reconnect 需要 token，如果 token 已配置
POST /qmt/disconnect 需要 token，如果 token 已配置
GET  /rpc/methods  需要 token，如果 token 已配置
POST /rpc          需要 token，如果 token 已配置
```

请求格式：

```http
Authorization: Bearer <token>
```

错误响应：

```json
{
  "detail": {
    "code": "UNAUTHORIZED",
    "message": "Missing or invalid bearer token"
  }
}
```

## RPC 方法分级

建议把现有 `READONLY_METHODS` 扩展为带元数据的 registry：

```python
@dataclass(frozen=True)
class RpcMethodSpec:
    target: str
    method: str
    level: RpcMethodLevel
```

等级：

```text
readonly
trading
admin
```

第一阶段 registry 中仍只开放 readonly 方法。可以在 registry 中预留 trading 方法集合，但不要加入允许调用列表。

建议错误码：

```text
METHOD_NOT_ALLOWED
TRADING_DISABLED
UNAUTHORIZED
```

## 交易保护

规则：

- 任何 `level=trading` 的 RPC 方法，必须检查 `settings.enable_trading`。
- `QMT_ENABLE_TRADING=false` 时返回：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TRADING_DISABLED",
    "message": "Trading RPC methods are disabled"
  }
}
```

- 交易方法开放前也需要保留白名单校验。
- 后续 Milestone 4 加入 `order_stock` / `cancel_order_stock` 时，必须先经过这个保护层。

## 审计日志

Milestone 3 使用标准库 `logging`，不引入数据库。

建议 logger：

```text
qmtserver.audit
```

每次 RPC 调用记录：

- timestamp
- target
- method
- level
- ok
- error code
- elapsed_ms
- args_summary

参数摘要规则：

- 只记录类型、长度、键名和短字符串。
- 不记录 token。
- 不记录完整大数组、大 DataFrame、大行情响应。
- 账号字段可以做脱敏，例如 `123****789`。

示例日志：

```text
INFO qmtserver.audit rpc target=trader method=query_stock_asset level=readonly ok=true elapsed_ms=12.3 args=[StockAccount(account_id=123****789)]
```

## 目录调整

新增：

```text
src/qmtserver/
├── security.py       # Bearer token 校验
├── audit.py          # RPC 审计日志
```

调整：

```text
src/qmtserver/rpc/registry.py     # 从 set 白名单升级为 method spec
src/qmtserver/rpc/dispatcher.py   # 增加 level 检查和审计日志
src/qmtserver/api/dependencies.py # 增加 auth dependency
```

## 测试计划

单元测试：

- token 为空时不要求鉴权。
- token 配置后，无 Authorization 返回 401。
- token 配置后，错误 token 返回 401。
- token 配置后，正确 bearer token 通过。
- `/health` 无 token 仍可访问。
- registry 返回方法等级。
- `QMT_ENABLE_TRADING=false` 时 trading 方法返回 `TRADING_DISABLED`。
- readonly 方法不受 trading 开关影响。
- 审计日志会记录方法名、等级、耗时和结果。
- 审计日志不会记录 token。

接口测试：

- `GET /qmt/status` 在 token 开启时需要鉴权。
- `GET /rpc/methods` 在 token 开启时需要鉴权。
- `POST /rpc` 在 token 开启时需要鉴权。
- `POST /rpc` 调用 trading spec 时，默认返回 `TRADING_DISABLED`。

真实环境手动测试：

```powershell
$env:QMT_API_TOKEN="dev-token"
uv run qmtserver serve --userdata "C:\国金证券QMT交易端\userdata_mini"
```

验证：

```text
GET /health                         -> 200
GET /qmt/status without token        -> 401
GET /qmt/status with bearer token    -> 200
POST /rpc without token              -> 401
POST /rpc with bearer token          -> 200 or RPC-level error
```

## 验收标准

Milestone 3 完成时必须满足：

1. `uv run qmtserver check ...` 继续可用。
2. `uv run qmtserver serve` 继续可用。
3. `/health` 在 token 开启时仍不要求鉴权。
4. `/qmt/*` 在 token 开启时要求 bearer token。
5. `/rpc*` 在 token 开启时要求 bearer token。
6. RPC registry 支持 `readonly`、`trading`、`admin` 等级。
7. `QMT_ENABLE_TRADING=false` 时 trading 方法返回 `TRADING_DISABLED`。
8. RPC 调用产生审计日志。
9. 日志不泄露 token。
10. 自动化测试通过。

## 实际提交

代码和测试随 Milestone 3 完成提交，文档同步记录完成状态。

## 风险与应对

- 本地服务误暴露到局域网：默认 host 保持 `127.0.0.1`。
- token 被写入日志：审计日志只记录认证结果，不记录 header。
- 交易方法提前开放：registry 分级和 trading guard 必须先于 Milestone 4 合入。
- 测试误触发真实交易：Milestone 3 不调用真实下单方法，测试全部使用 fake target。
