# Milestone 4: Trading RPC

Milestone 4 的目标是在 Milestone 3 的安全边界之上，受控开放真实下单和撤单能力。这个阶段的核心不是“把所有交易 API 都暴露出去”，而是让最小可用交易闭环安全落地：下单、撤单、dry-run、参数校验、交易审计。

## 目标

完成后应支持：

- 通过 RPC 调用受控交易方法。
- 默认 dry-run 或 trading disabled 不会真实下单。
- 显式开启 `QMT_ENABLE_TRADING=true` 后才允许真实交易。
- 支持同步下单、异步下单、同步撤单、异步撤单。
- 下单前进行基础参数校验。
- 支持单笔最大数量、单笔最大金额等保护阈值。
- 所有交易请求必须进入审计日志。

## 非目标

Milestone 4 暂不做：

- 策略引擎。
- 自动风控系统。
- 订单状态 WebSocket 推送。
- 多账号权限隔离。
- 复杂组合交易。
- 期货、期权、融资融券全部细分适配。

## 当前基础

依赖 Milestone 3 已完成：

- Bearer token 鉴权。
- RPC 方法分级。
- `QMT_ENABLE_TRADING` 保护。
- RPC 审计日志。

Milestone 4 只应在这些保护层之上加入 trading 方法。

## RPC 方法

第一版开放：

```text
trader.order_stock
trader.order_stock_async
trader.cancel_order_stock
trader.cancel_order_stock_async
```

方法等级：

```text
level = trading
```

## 请求模型

建议继续使用统一 `/rpc`，但给 trading 方法提供更严格的参数转换和校验。

下单示例：

```json
{
  "target": "trader",
  "method": "order_stock",
  "args": [
    {
      "__type__": "StockAccount",
      "account_id": "你的资金账号",
      "account_type": "STOCK"
    },
    "000001.SZ",
    23,
    100,
    5,
    10.5,
    "qmtserver",
    "manual-test"
  ],
  "kwargs": {}
}
```

撤单示例：

```json
{
  "target": "trader",
  "method": "cancel_order_stock",
  "args": [
    {
      "__type__": "StockAccount",
      "account_id": "你的资金账号",
      "account_type": "STOCK"
    },
    0,
    123456
  ],
  "kwargs": {}
}
```

## 配置

新增：

```env
QMT_TRADING_DRY_RUN=true
QMT_MAX_ORDER_VOLUME=100000
QMT_MAX_ORDER_AMOUNT=1000000
QMT_ALLOWED_ACCOUNTS=
```

语义：

- `QMT_ENABLE_TRADING=false`：所有 trading 方法拒绝。
- `QMT_TRADING_DRY_RUN=true`：返回模拟结果，不调用 xtquant 真实交易方法。
- `QMT_ALLOWED_ACCOUNTS`：逗号分隔账号白名单，空值表示只允许 `QMT_ACCOUNT_ID`。
- `QMT_MAX_ORDER_VOLUME`：单笔最大数量。
- `QMT_MAX_ORDER_AMOUNT`：单笔最大金额，按 `price * volume` 粗略校验。

## 交易前校验

第一版至少校验：

- account 必须是 `StockAccount`。
- account_id 必须匹配允许账号。
- stock_code 必须是非空字符串。
- order_type 必须在允许集合内。
- order_volume 必须为正整数。
- price 必须非负。
- price * volume 不能超过配置阈值。
- trading disabled 时返回 `TRADING_DISABLED`。
- dry-run 时不触发真实 xtquant 方法。

建议错误码：

```text
TRADING_DISABLED
TRADING_DRY_RUN
TRADING_VALIDATION_ERROR
ACCOUNT_NOT_ALLOWED
ORDER_LIMIT_EXCEEDED
```

## Dry-run 响应

```json
{
  "ok": true,
  "data": {
    "dry_run": true,
    "target": "trader",
    "method": "order_stock",
    "validated": true
  },
  "error": null,
  "meta": {
    "target": "trader",
    "method": "order_stock",
    "level": "trading",
    "elapsed_ms": 1.2
  }
}
```

## 审计日志

交易日志必须比普通 RPC 更严格：

- 记录 account_id 脱敏值。
- 记录 stock_code。
- 记录 order_type。
- 记录 volume、price。
- 记录 dry_run。
- 记录是否真实调用 xtquant。
- 记录返回 order_id 或错误码。

不记录 token。

## 测试计划

单元测试：

- trading disabled 拒绝交易方法。
- dry-run 不调用 fake trader。
- dry-run 返回模拟响应。
- 非允许账号被拒绝。
- 数量超限被拒绝。
- 金额超限被拒绝。
- 合法交易在 `enable_trading=true` 且 `dry_run=false` 时调用 fake trader。
- 交易审计日志包含方法名但不包含 token。

接口测试：

- `POST /rpc` 调用 trading 方法，在默认配置下返回 `TRADING_DISABLED`。
- `POST /rpc` 调用 trading 方法，在 dry-run 下返回 dry-run 响应。
- `GET /rpc/methods` 可以标明方法等级，或新增详细 methods endpoint。

真实环境手动测试：

先 dry-run：

```powershell
$env:QMT_ENABLE_TRADING="true"
$env:QMT_TRADING_DRY_RUN="true"
uv run qmtserver serve --userdata "C:\国金证券QMT交易端\userdata_mini" --account-id "你的资金账号"
```

确认不会真实下单。

真实下单只允许在用户明确确认后测试。

## 验收标准

Milestone 4 完成时必须满足：

1. 默认配置下无法真实下单。
2. `QMT_ENABLE_TRADING=false` 时 trading 方法返回 `TRADING_DISABLED`。
3. `QMT_TRADING_DRY_RUN=true` 时不会调用 xtquant 交易方法。
4. 参数校验覆盖账号、代码、数量、价格、金额。
5. 超过限制的订单被拒绝。
6. 合法交易路径有 fake trader 测试覆盖。
7. 交易审计日志存在且不泄露 token。
8. 自动化测试通过。

## 建议提交顺序

```text
feat(trading): add trading guard settings
feat(rpc): register trading methods
feat(trading): validate order requests
feat(trading): add dry-run execution
test(trading): cover guarded trading rpc
docs(milestone): document trading rpc completion
```

## 风险与应对

- 误触发真实交易：默认 disabled + dry-run 双保险。
- 参数顺序错导致错误下单：为交易方法增加明确参数解析器，不直接信任裸 args。
- 账号误用：默认只允许 `QMT_ACCOUNT_ID`。
- 审计泄露敏感信息：账号脱敏，token 永不记录。
