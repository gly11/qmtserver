# Operations

qmtserver 默认面向本机运行，建议保持 `QMT_HOST=127.0.0.1`，先启动并登录 MiniQMT，再启动服务。

## 连接检查

先启动并登录 MiniQMT，再运行：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini"
```

如果要同时验证交易账号订阅和资金查询：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
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
.\scripts\run-dev.ps1 -Userdata "D:\path\to\MiniQMT\userdata_mini" -AccountId "资金账号"
```

常规运行：

```powershell
.\scripts\run-server.ps1 -Userdata "D:\path\to\MiniQMT\userdata_mini" -AccountId "资金账号"
```

也可以直接运行：

```powershell
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
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
GET /v1/market/capabilities
GET /v1/rpc/methods
WS  /v1/ws/events
```

## Snapshot 数据目录

Snapshot/export 文件默认写入 `data/snapshots/`，可通过环境变量调整：

```env
QMT_SNAPSHOT_DIR=data/snapshots
```

该目录用于保存 CSV 数据文件和对应的 `*.manifest.json`。manifest 不记录本机绝对路径、账号、
token 或 MiniQMT userdata 路径；如需备份或清理 snapshot，优先以 manifest 为单位处理同名
数据文件。

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
