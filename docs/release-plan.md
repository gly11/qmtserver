# Release Plan

本文档记录 qmtserver 的版本节奏和发布门禁。当前最新已发布版本为 `0.5.0`，主题是 realtime
market subscriptions 和 `xtquant` compatibility baseline。

## 版本节奏

```text
0.1.0  已完成  安全远程网关 MVP
0.2.0  已完成  透明 RPC 实验模式
0.3.0  已完成  稳定行情数据、snapshot、job 和诊断接口
0.4.0  已发布    稳定只读交易查询 API
0.5.0  已发布    实时行情订阅和兼容矩阵基线
1.0.0  远期    稳定版本
```

`qmtclient` 是独立客户端项目；本计划只覆盖 qmtserver。

## 0.1.0

状态：已完成。

`0.1.0` 提供安全优先的远程 MiniQMT 网关：

- CLI 连接检查。
- `/v1` HTTP API。
- 白名单 RPC。
- token 鉴权。
- 交易保护和 dry-run。
- WebSocket 事件。
- 订单、成交和事件内存缓存。
- 日志、指标、request ID 和 Windows 启动脚本。

## 0.2.0

状态：已完成。

`0.2.0` 聚焦默认关闭的透明 RPC 实验模式，没有混入 GUI、多语言 SDK、持久化存储或复杂
部署系统。

范围：

- 增加透明 RPC 配置项。
- 增加透明 RPC 策略判断模块。
- 在 dispatcher 中接入白名单外方法的受控转发。
- 默认只允许 `xtdata`，默认不开放 `trader`。
- 拒绝私有方法、dunder 方法和疑似交易方法。
- 保持 token、审计、metrics 和 JSON envelope 不变。
- 增加透明 RPC 单元测试和文档。

详细设计和使用说明见 [Transparent RPC](transparent-rpc.md)。

## 0.3.0

状态：已完成。

`0.3.0` 聚焦稳定行情数据契约，让策略、研究和回测系统优先消费 qmtserver 的显式 API，
不再依赖 transparent RPC 或 `xtdata` 原始返回形态。

范围：

- 增加 `/v1/market/capabilities`、daily bars 和 intraday bars。
- 统一 bars schema、metadata、空数据和错误语义。
- 增加 CSV snapshot/export、manifest、registry、download 和质量报告。
- 增加历史下载 job create/status/result/cancel。
- 增加 diagnostics、job metrics、交易日历、标的列表和 instrument detail。
- 补充 API、错误码、roadmap、release plan 和 milestone 归档文档。

发布限制：

- 本地开发环境可以完成单元测试、lint、format、type 和 diff 检查。
- 真实 Windows + MiniQMT smoke 需要在具备 `xtquant`、MiniQMT userdata 和账号权限的网关机上补做。

## 0.4.0

状态：已发布。

`0.4.0` 聚焦稳定只读交易查询 API，让外部系统在不走 transparent RPC 的情况下查询账号状态、
资产、持仓、当日委托和当日成交。

范围：

- 增加 `/v1/trader/account-status`、asset、positions、orders 和 trades。
- 统一只读交易查询响应 envelope 和 `trader.readonly.v1` schema。
- 增加账号解析、账号 allowlist 过滤和 `TRADER_ACCOUNT_REQUIRED` 错误码。
- 增加内置客户端只读 trader helper。
- 补充 API、SDK、错误码、roadmap 和 xtquant adapter 文档。

发布限制：

- 本地开发环境可以完成单元测试、lint、format、type、code health、build、twine check 和 diff
  检查。
- 真实 Windows + MiniQMT smoke 应在具备 `xtquant`、MiniQMT userdata 和账号权限的网关机上补做。
- 只读交易查询 smoke 不应执行真实下单或撤单。

## 0.5.0

状态：已发布。

`0.5.0` 聚焦实时行情订阅和 WebSocket quote event，使远程客户端可以通过 qmtserver 管理
MiniQMT 行情订阅，而不直接依赖 `xtquant`。

范围：

- 增加 `/v1/market/subscriptions` 创建、列表、详情和停止接口。
- 适配 `xtdata.subscribe_quote`，并记录本地签名、callback 形态和取消订阅行为。
- 标准化 `market.subscription.v1` 和 `market.quote.v1` 事件。
- 复用现有 WebSocket `/v1/ws/events`，支持 `market_quote` 和 `market_subscription` 事件。
- 建立 `docs/compatibility.md`，作为后续 `xtquant` 适配和升级复测基线。

发布记录：

- 普通测试使用 fakes，不依赖真实 MiniQMT。
- 真实 MiniQMT smoke 只做 readonly 行情订阅，不执行下单、撤单、转账或其他交易命令。
- 盘后 smoke 已验证 quote 连接、订阅生命周期和 initial `get_full_tick` quote seed。
- 正式发布 `0.5.0` 前已在活跃行情时段运行
  `uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback`，
  并看到 `received_callback=true` 或 WebSocket 事件 `meta.quote_source=callback`。
- 2026-05-28 13:10 本地时间已完成一次只读活跃行情 smoke，收到 `received_callback=true`
  和 `meta.quote_source=callback`，脚本报告 `trader_connected=false`。
- `v0.5.0` tag 已触发 GitHub Actions 发布工作流，并发布到 PyPI。

## 发布门禁

发布前至少运行：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts\check_code_health.py --enforce
git diff --check
```

如果本地没有 MiniQMT 或账号，允许跳过真实连接验证，但发布说明中必须明确标注。

建议人工验证：

```powershell
$userdata = "D:\path\to\MiniQMT\userdata_mini"
$account = "资金账号"
uv run qmtserver check --userdata $userdata --account-id $account
uv run qmtserver serve --userdata $userdata --account-id $account
```

远程访问发布前建议额外验证：

- 网关机监听地址符合预期。
- token 鉴权开启。
- 远程电脑可访问 `/v1/health`。
- 远程客户端可调用 `status()` 和至少一个只读行情方法。
- `0.5.0` 发布前可运行只读实时订阅 smoke：

```powershell
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback
```

## 发布原则

- 每个 minor 版本只解决一个主要主题。
- 安全边界变化必须单独成版本，并有文档和测试。
- 交易相关能力默认关闭，并保留 dry-run 防护。
- changelog 只记录已经完成的能力。
