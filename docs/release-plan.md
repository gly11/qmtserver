# Release Plan

本文档记录 qmtserver 的版本节奏和发布门禁。当前待发布版本为 `0.8.0`，主题是 Market Data
Lake 稳定化：让 server 端行情数据湖具备更可靠的 coverage、维护、查询、导出、job 追踪和
只读 smoke 流程。

## 版本节奏

```text
0.1.0  已完成  安全远程网关 MVP
0.2.0  已完成  透明 RPC 实验模式
0.3.0  已完成  稳定行情数据、snapshot、job 和诊断接口
0.4.0  已发布    稳定只读交易查询 API
0.5.0  已发布    实时行情订阅和兼容矩阵基线
0.6.0  已发布    只读实盘 smoke、历史下载可靠性和实时稳定性基线
0.7.0  已发布    网关可靠性诊断和 Market Data Lake 基线
0.8.0  待发布    Market Data Lake 稳定化
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

## 0.6.0

状态：已发布。

`0.6.0` 聚焦发布前可复跑的实盘只读验证基线，补强历史数据下载、snapshot/job 验证、reference
字段基线和实时行情长窗口稳定性记录。

范围：

- 增加 `scripts/smoke_trader_readonly.py`，只调用 trader readonly GET 端点，输出脱敏摘要。
- 增加 `scripts/smoke_market_history.py`，覆盖 history download job、daily/intraday bars、
  snapshot manifest 和 daily quality，并支持 `--require-rows`。
- 将 history download job 调整为先逐标的调用同步 `xtdata.download_history_data`，再生成 snapshot。
- 增加 `scripts/smoke_reference.py`，记录 calendar、`all_a` universe 和 instrument detail 字段集合。
- 增强 realtime subscription smoke，支持 `--omit-events`，并记录 180 秒三标的活跃行情稳定性 smoke。

发布记录：

- 普通测试使用 fakes，不依赖真实 MiniQMT。
- 真实 MiniQMT smoke 只做 readonly 行情、reference、history 和 trader 查询验证，不执行下单、
  撤单、转账或其他交易命令。
- 2026-05-28 本地时间已完成 history/download/snapshot 非空行 smoke，`trader_connected=false`。
- 2026-05-28 本地时间已完成 reference/instrument detail smoke，`trader_connected=false`。
- 2026-05-28 本地时间已完成 180 秒三标的 realtime subscription smoke，收到 180 个 callback。
- 只读 trader smoke 脚本已完成；当前本机 trader 连接返回 `connect_result=-1`，需在交易侧连接正常
  后复测，不影响行情/history/reference 只读能力发布。

## 0.7.0

状态：已发布。

`0.7.0` 聚焦两条只读能力：网关运行可靠性诊断，以及 server 端 Market Data Lake 基线。
当 MiniQMT 或订阅状态异常时，服务端应能给出更清晰的诊断、健康摘要和手动恢复入口；当外部
系统需要批量行情数据时，server 端可以负责下载、缓存、查询和导出本地标准化数据。该版本仍不
新增任何真实交易命令。

范围：

- 增加 `qmtserver diagnose trader`，用于分步骤检查 `xtquant` 导入、userdata、trader class、
  trader start、`connect()` 返回码和账号只读查询。
- `/v1/diagnostics` 增加 `data.runtime_health`，汇总 quote、trader、订阅数量、degraded 状态和
  stale callback 状态。
- 增加 `POST /v1/market/subscriptions/{subscription_id}/recover`，手动重建已有行情订阅，复用
  原 symbols、period 和本地 `subscription_id`，并重置该订阅 diagnostics。
- 增加 `qmtserver[data]` extra，引入 DuckDB 和 PyArrow 作为可选高性能数据依赖。
- 增加 `/v1/market/data/download`，将历史行情下载任务持久化到 DuckDB。
- 下载任务会先检查本地 coverage；命中完整覆盖且未设置 `force=true` 时返回 cached result，不
  再触发 `xtdata.download_history_data`。
- 未命中时通过 `xtdata.download_history_data` 补齐 MiniQMT 行情缓存，再读取标准 bars 并按
  symbol/period/adjust 写入 qmtserver Parquet 文件。
- 增加 `/v1/market/data/coverage`、`/v1/market/data/bars`、`/v1/market/data/quality` 和
  `/v1/market/data/exports`，支持本地覆盖范围查询、本地 bars 查询、质量检查、CSV export、
  export 下载和 export 清理。

发布记录：

- 普通测试使用 fakes，不依赖真实 MiniQMT。
- 真实 MiniQMT smoke 只做 readonly 行情、历史数据和 trader 诊断，不执行下单、撤单、转账或
  其他交易命令。
- 2026-06-01 本地时间已完成活跃行情三标的 subscription smoke：quote 连接成功，收到 live
  callback，latest cache 命中全部标的，subscription diagnostics 为 active。
- 2026-06-01 本地时间已完成 manual recover smoke：停止后的订阅可通过 recover 恢复为
  `active`，保留相同 `subscription_id`，diagnostics callback count 重置为 `0`。
- 2026-06-01 本地时间已完成 runtime health smoke：quote connected、trader disabled、一个 active
  subscription 时 `runtime_health.status=ok`。
- 2026-06-01 本地 trader 诊断和 trader readonly smoke 仍返回 `connect_result=-1` /
  `TARGET_NOT_CONNECTED`。该结果说明诊断链路可用，但当前 MiniQMT trader 通道未就绪；如发布说明
  要声明 trader readonly 已通过真实连接，需要在 trader 连接恢复后复测。
- Market Data Lake 的普通测试使用 fakes 和本地临时目录，不依赖真实 MiniQMT；真实数据下载仍应
  使用只读行情路径，不连接 trader，也不执行任何交易命令。

## 0.8.0

状态：待发布。

`0.8.0` 在 `0.7.0` 数据湖基线之上增强稳定性和可维护性：

- coverage response 增加 file-level `covered_segments` 和 `gaps`，cached download 使用 segments
  判断中间缺口。
- 增加 `qmtserver data check`、`cleanup` 和 `rebuild-index` 本地维护入口；cleanup 默认
  dry-run，支持 export 过期清理；`rebuild-index --execute` 可从本地 Parquet 重建 metadata。
- `/v1/market/data/bars` 支持稳定排序、symbol/period/time 去重、`limit`/`offset` 分页和
  query metadata。
- data export manifest 记录 `source_file_count`、`deduplicated_row_count` 和 `truncated`。
- data download result 增加 per-symbol `symbol_results`。
- 增加 `GET /v1/market/data/jobs`，从 DuckDB 查询持久化 data jobs。
- 增加 `scripts/smoke_market_data_lake.py`，覆盖 download、coverage、bars、quality、export 和
  cached download 闭环。

发布记录：

- 已完成普通单元测试、lint、format、type、code health、diff check、build 和 twine check。
- 普通测试使用 fakes 和本地临时目录，不依赖真实 MiniQMT。
- 真实 MiniQMT smoke 只做 readonly 行情数据湖验证，不连接 trader，不执行下单、撤单、转账或
  其他交易命令。

发布限制：

- 如果真实 smoke 未执行或失败，发布说明必须明确标注未验证项。

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
- Market Data Lake 稳定化发布前可运行只读 smoke：

```powershell
uv run python scripts\smoke_market_history.py --symbol 000001.SZ --require-rows
uv run python scripts\smoke_market_data_lake.py --symbol 000001.SZ --require-rows
uv run python scripts\smoke_reference.py --symbols 000001.SZ,600000.SH
uv run python scripts\smoke_market_subscription.py --symbols 000001.SZ,600000.SH,510300.SH --duration-seconds 180 --min-callbacks 30 --require-all-symbols --report-intervals --omit-events
uv run python scripts\smoke_trader_readonly.py
uv run qmtserver diagnose trader
```

如需人工验证 Market Data Lake，请先安装 data extra：

```powershell
uv sync --extra xtquant --extra data
```

然后启动 qmtserver，并只调用 `/v1/market/data/*` 行情数据接口。该验证不需要连接 trader，也不应
执行任何交易命令。

## 发布原则

- 每个 minor 版本只解决一个主要主题。
- 安全边界变化必须单独成版本，并有文档和测试。
- 交易相关能力默认关闭，并保留 dry-run 防护。
- changelog 只记录已经完成的能力。
