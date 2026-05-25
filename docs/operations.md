# Operations

qmtserver 默认面向本机运行，建议保持 `QMT_HOST=127.0.0.1`，先启动并登录 MiniQMT，再启动服务。

## 启动

开发模式：

```powershell
.\scripts\run-dev.ps1 -Userdata "C:\国金证券QMT交易端\userdata_mini" -AccountId "资金账号"
```

常规运行：

```powershell
.\scripts\run-server.ps1 -Userdata "C:\国金证券QMT交易端\userdata_mini" -AccountId "资金账号"
```

也可以直接运行：

```powershell
uv run qmtserver serve --userdata "C:\国金证券QMT交易端\userdata_mini" --account-id "资金账号"
```

## 检查

```powershell
.\scripts\check.ps1
```

常用端点：

```text
GET /health
GET /metrics
GET /qmt/status
GET /rpc/methods
WS  /ws/events
```

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
