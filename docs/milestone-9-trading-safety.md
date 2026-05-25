# Milestone 9: Trading Safety Hardening

Milestone 9 的目标是在已有交易开关、dry-run、账号白名单和单笔限额基础上，进一步降低真实交易误触发和误配置风险。

## 目标

完成后应支持：

- 股票代码白名单或黑名单。
- 单日下单数量和金额限制。
- 下单二次确认机制。
- 交易审计单独 logger 或单独文件。
- 更明确的真实交易运行模式。
- SDK 对交易错误给出更清晰异常。

## 非目标

Milestone 9 暂不做：

- 完整风控系统。
- 策略引擎。
- 自动止损止盈。
- 多账号权限系统。
- 数据库级审计归档。

## 当前基础

已具备：

- `QMT_ENABLE_TRADING=false` 默认禁用真实交易。
- `QMT_TRADING_DRY_RUN=true` 默认 dry-run。
- `QMT_ALLOWED_ACCOUNTS`。
- `QMT_MAX_ORDER_VOLUME`。
- `QMT_MAX_ORDER_AMOUNT`。
- RPC 审计日志。

## 交易安全配置

建议新增：

```env
QMT_ALLOWED_SYMBOLS=
QMT_BLOCKED_SYMBOLS=
QMT_DAILY_MAX_ORDER_VOLUME=1000000
QMT_DAILY_MAX_ORDER_AMOUNT=5000000
QMT_REQUIRE_TRADE_CONFIRMATION=true
QMT_TRADE_CONFIRMATION_TEXT=I_UNDERSTAND_REAL_TRADING
QMT_TRADE_AUDIT_LOG=true
```

语义：

- `QMT_ALLOWED_SYMBOLS` 非空时，只允许白名单内证券代码。
- `QMT_BLOCKED_SYMBOLS` 永远拒绝。
- 日内限制以服务进程内存计数为第一版实现，不做跨进程持久化。
- 真实交易请求必须携带确认字段，例如 `confirm="I_UNDERSTAND_REAL_TRADING"`。

## 请求增强

交易 RPC 可以继续走 `/rpc`，但建议支持 kwargs 确认：

```json
{
  "target": "trader",
  "method": "order_stock",
  "args": [...],
  "kwargs": {
    "confirm": "I_UNDERSTAND_REAL_TRADING"
  }
}
```

注意：如果 xtquant 原方法不接受 `confirm`，dispatcher 需要在调用真实方法前移除该内部参数。

## 交易审计

建议新增 logger：

```text
qmtserver.trade
```

记录：

- request_id
- account_id 脱敏
- stock_code
- order_type
- volume
- price
- dry_run
- real_call
- result / error_code

不记录 token，不记录完整账号。

## 测试计划

单元测试：

- 股票白名单允许/拒绝。
- 股票黑名单拒绝。
- 日内数量超限拒绝。
- 日内金额超限拒绝。
- 未确认真实交易时拒绝。
- dry-run 不要求真实交易确认。
- 内部 `confirm` 不传给 fake trader。
- trade audit 日志脱敏。

接口测试：

- 默认配置仍无法真实下单。
- `enable_trading=true` + `dry_run=false` + 缺少确认时拒绝。
- 合法确认和限制内订单能进入 fake trader。

## 验收标准

Milestone 9 完成时必须满足：

1. 真实交易需要显式开启、关闭 dry-run、账号允许、代码允许、未超限、确认文本正确。
2. dry-run 仍然安全且易用于手动测试。
3. 交易审计独立清晰。
4. SDK 对交易拒绝错误可读。
5. 自动化测试通过。

## 风险与应对

- 日内限制进程重启后清零：文档明确第一版是进程级保护。
- 确认字段误传 xtquant：dispatcher 调用前剥离内部 kwargs。
- 白名单配置复杂：第一版使用逗号分隔字符串，不引入配置文件格式。
