# Milestone 7: Observability and Operations

Milestone 7 的目标是让 qmtserver 具备长期运行所需的可观测性和基础运维能力。这个阶段关注日志、指标、运行手册、Windows 启动方式和故障排查。

## 目标

完成后应支持：

- 结构化应用日志。
- 请求 ID。
- RPC 调用指标。
- 简单 `/metrics`。
- 日志文件轮转。
- Windows 启动脚本。
- 运行手册和故障排查文档。
- 可选 Windows 计划任务或服务方案。

## 非目标

Milestone 7 暂不做：

- Prometheus 完整生态适配。
- 分布式 tracing。
- 云部署。
- 多实例高可用。
- 数据库存储指标。

## 当前基础

依赖前序 milestone：

- HTTP 服务。
- 生命周期状态。
- 鉴权。
- RPC 审计日志。
- WebSocket 事件。
- Python client。

## 日志设计

建议 logger：

```text
qmtserver
qmtserver.audit
qmtserver.access
qmtserver.events
```

配置：

```env
QMT_LOG_LEVEL=INFO
QMT_LOG_DIR=logs
QMT_LOG_JSON=false
QMT_LOG_MAX_BYTES=10485760
QMT_LOG_BACKUP_COUNT=10
```

日志内容：

- timestamp
- level
- logger
- request_id
- event
- message
- error code
- elapsed_ms

## 请求 ID

HTTP 请求：

- 接收 `X-Request-ID`。
- 没有则生成 UUID。
- 响应头返回 `X-Request-ID`。
- 日志中携带 request_id。

WebSocket：

- 每个连接生成 connection_id。
- 每个事件包含 sequence。

## Metrics

新增：

```text
GET /metrics
```

第一版返回 JSON：

```json
{
  "ok": true,
  "uptime_seconds": 1234,
  "rpc": {
    "total": 100,
    "success": 95,
    "error": 5,
    "avg_elapsed_ms": 8.3
  },
  "qmt": {
    "quote_connected": true,
    "trader_connected": true
  },
  "websocket": {
    "clients": 2,
    "events_published": 120
  }
}
```

暂不使用 Prometheus 文本格式，后续可以增加 `/metrics/prometheus`。

## 运行脚本

建议新增：

```text
scripts/
├── run-dev.ps1
├── run-server.ps1
└── check.ps1
```

脚本职责：

- 加载 `.env`。
- 启动 `uv run qmtserver serve`。
- 检查健康状态。
- 输出常用排查信息。

## Windows 运行方式

Milestone 7 提供文档，不强制实现服务安装。

可选方案：

- Windows 计划任务。
- NSSM。
- PowerShell 后台任务。

文档应包含：

- 如何启动。
- 如何停止。
- 如何查看日志。
- MiniQMT 未启动时如何处理。
- 端口占用如何处理。

## 故障排查文档

新增：

```text
docs/operations.md
docs/troubleshooting.md
```

覆盖：

- `xtquant` import 失败。
- MiniQMT 未登录。
- `userdata_mini` 路径错误。
- 端口被占用。
- token 鉴权失败。
- trader 未连接。
- WebSocket 收不到事件。

## 测试计划

单元测试：

- request ID middleware。
- metrics counter。
- 日志配置默认值。
- 日志脱敏。
- metrics endpoint 返回结构。

接口测试：

- `GET /metrics`。
- `X-Request-ID` 透传。
- 请求日志携带 request_id。

脚本检查：

- PowerShell 脚本语法基本可解析。
- README / operations 文档包含启动命令。

## 验收标准

Milestone 7 完成时必须满足：

1. 有结构化日志配置。
2. HTTP 请求带 request ID。
3. `/metrics` 返回服务、RPC、QMT、WebSocket 基础指标。
4. 日志支持文件轮转。
5. Windows 启动脚本存在。
6. operations / troubleshooting 文档存在。
7. 常见故障有明确处理步骤。
8. 自动化测试通过。

## 建议提交顺序

```text
feat(observability): add request id middleware
feat(metrics): collect rpc and service metrics
feat(logging): add rotating log configuration
chore(scripts): add windows run scripts
docs(ops): add operations and troubleshooting guides
test(observability): cover metrics and request ids
```

## 风险与应对

- 日志泄露敏感信息：沿用审计脱敏规则。
- 指标影响性能：只记录内存计数器和轻量耗时。
- Windows 脚本不可移植：脚本放 `scripts/`，核心服务仍保持 Python CLI。
- 运维文档过期：每次变更启动方式时同步更新 docs。
