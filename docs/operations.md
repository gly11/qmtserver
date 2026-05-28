# Operations

qmtserver 默认面向本机运行，建议保持 `QMT_HOST=127.0.0.1`，先启动并登录 MiniQMT，再启动服务。

## 连接检查

先启动并登录 MiniQMT，再运行：

```powershell
$userdata = "D:\path\to\MiniQMT\userdata_mini"
$account = "资金账号"
uv run qmtserver check --userdata $userdata
```

如果要同时验证交易账号订阅和资金查询：

```powershell
uv run qmtserver check --userdata $userdata --account-id $account
```

常用参数：

- `--userdata`：MiniQMT / QMT 交易端目录下的 `userdata_mini` 完整路径。
- `--account-id`：资金账号；传入后会尝试 `subscribe` 和 `query_stock_asset`。
- `--account-type`：账号类型，默认 `STOCK`。
- `--quote-code`：用于验证行情接口的证券代码，默认 `000001.SZ`。
- `--skip-quote`：只验证交易连接。
- `--json`：输出完整 JSON，便于脚本消费。

连接成功时命令退出码为 `0`；失败时退出码为 `1`，终端会打印失败原因。

## 启动

开发模式：

```powershell
.\scripts\run-dev.ps1 -Userdata $userdata -AccountId $account
```

常规运行：

```powershell
.\scripts\run-server.ps1 -Userdata $userdata -AccountId $account
```

也可以直接运行：

```powershell
uv run qmtserver serve --userdata $userdata --account-id $account
```

## 检查

```powershell
.\scripts\check.ps1
```

常用端点：

```text
GET /v1/health
GET /v1/metrics
GET /v1/qmt/status
GET /v1/trader/account-status
GET /v1/trader/asset
GET /v1/trader/positions
GET /v1/trader/orders
GET /v1/trader/trades
GET /v1/market/capabilities
POST /v1/market/subscriptions
GET /v1/market/subscriptions
GET /v1/market/quotes/latest
GET /v1/market/subscriptions/{subscription_id}/diagnostics
GET /v1/diagnostics
GET /v1/reference/calendar
GET /v1/rpc/methods
WS  /v1/ws/events
```

实时行情订阅只读 smoke：

```powershell
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ
```

盘中验证 live `subscribe_quote` callback 时使用：

```powershell
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback
```

批量订阅、latest quote cache 和 diagnostics 验证：

```powershell
uv run python scripts\smoke_market_subscription.py --symbols 000001.SZ,600000.SH,510300.SH --require-callback --require-all-symbols --timeout-seconds 60
```

长窗口实时可靠性 smoke：

```powershell
uv run python scripts\smoke_market_subscription.py --symbols 000001.SZ,600000.SH,510300.SH --duration-seconds 180 --min-callbacks 3 --report-intervals
```

验证 stop 后本地隔离：

```powershell
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback --post-stop-listen-seconds 5
```

该脚本显式使用 `connect_trader=False`，不会连接 trader，也不会执行下单、撤单或转账命令。
脚本还会检查 latest quote cache 和 subscription diagnostics，确认服务端能通过 HTTP 返回最近
一次 quote、回调计数、最近 callback 时间和 freshness 秒数。

WebSocket 客户端断线后，可用最近事件缓存补拉短期事件：

```powershell
curl "http://127.0.0.1:8000/v1/events/recent?types=market_quote&symbols=000001.SZ,600000.SH&limit=20"
```

recent events 是短期内存事件回放；当前行情状态优先使用 `/v1/market/quotes/latest`。

如果订阅状态为 `degraded`，先查看
`/v1/market/subscriptions/{subscription_id}/diagnostics` 中的 `degraded_reason`。当前可靠性
基线只记录 degraded 状态，不自动重连或重订阅。

## Snapshot 数据目录

Snapshot/export 文件默认写入 `data/snapshots/`，可通过环境变量调整：

```env
QMT_SNAPSHOT_DIR=data/snapshots
```

该目录用于保存 CSV 数据文件和对应的 `*.manifest.json`。manifest 不记录本机绝对路径、账号、
token 或 MiniQMT userdata 路径；如需备份或清理 snapshot，优先以 manifest 为单位处理同名
数据文件。

每个 snapshot 使用同一个 `snapshot_id` 生成两个文件：

```text
{snapshot_id}.csv
{snapshot_id}.manifest.json
```

CSV 字段按 snapshot kind 固定：

- `daily_bars`：`date,symbol,open,high,low,close,volume,amount,meta`
- `intraday_bars`：`timestamp,symbol,period,open,high,low,close,volume,amount,meta`

其中 `meta` 字段在 CSV 中为 JSON 字符串。manifest 记录 request、request_hash、schema、
format、hash、row_count、symbol_count、coverage_start、coverage_end、generated_at、
qmtserver_version 和 xtquant_version。

## Jobs 与诊断

历史下载 job 使用进程内存 registry，服务重启后 job 状态清空。成功 job 关联的 snapshot 文件和
manifest 会保留在 `QMT_SNAPSHOT_DIR`。

常用诊断入口：

```text
GET /v1/diagnostics
GET /v1/metrics
```

`/v1/diagnostics` 返回 MiniQMT/qmtserver 状态、server clock、版本信息和 sample symbol smoke。
`/v1/metrics` 包含 job status 计数，便于观察 queued、running、succeeded、failed 和 cancelled
分布。

## Reference、质量报告与缓存

Reference endpoints 和 quality endpoints 不写入交易状态，也不产生投资建议。质量报告只做保守
数据检查，包括缺失日期、重复行、价格异常和成交量异常。

批量数据复用优先通过 snapshot registry 完成：相同 snapshot 参数会命中已有 manifest。后续如
增加更细的 market cache，cache key 必须包含 endpoint、symbols、period、start、end、adjust 和
schema version，且不得改变 API schema 或 error code。

## 日志

默认日志目录为 `logs/`，文件为 `logs/qmtserver.log`。相关配置：

```env
QMT_LOG_LEVEL=INFO
QMT_LOG_DIR=logs
QMT_LOG_JSON=false
QMT_LOG_MAX_BYTES=10485760
QMT_LOG_BACKUP_COUNT=10
```

## Windows 长期运行

第一版建议使用 Windows 计划任务或 NSSM 包装 `scripts\run-server.ps1`。计划任务应设置为用户登录后启动，并确保 MiniQMT 已启动登录。
