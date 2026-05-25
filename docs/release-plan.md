# Release Plan

本文档记录 qmtserver 的版本节奏和发布门禁。当前已完成版本为 `0.1.0`。

## 版本节奏

```text
0.1.0  已完成  安全远程网关 MVP
0.2.0  计划中  透明 RPC 实验模式
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

状态：计划中。

`0.2.0` 只聚焦默认关闭的透明 RPC 实验模式。不要在同一个版本混入 GUI、多语言 SDK、
持久化存储或复杂部署系统。

详细计划见 [Transparent RPC](transparent-rpc.md)。

## 发布门禁

发布前至少运行：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
git diff --check
```

如果本地没有 MiniQMT 或账号，允许跳过真实连接验证，但发布说明中必须明确标注。

建议人工验证：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
```

远程访问发布前建议额外验证：

- 网关机监听地址符合预期。
- token 鉴权开启。
- 远程电脑可访问 `/v1/health`。
- 远程客户端可调用 `status()` 和至少一个只读行情方法。

## 发布原则

- 每个 minor 版本只解决一个主要主题。
- 安全边界变化必须单独成版本，并有文档和测试。
- 交易相关能力默认关闭，并保留 dry-run 防护。
- changelog 只记录已经完成的能力。
