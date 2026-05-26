# Development Roadmap

qmtserver 的目标是让一台已登录 MiniQMT 的 Windows 电脑成为受控网关。其他机器通过
HTTP RPC、WebSocket 或独立客户端项目 qmtclient 访问它，而不直接安装或适配 `xtquant`。

```text
remote tools / strategies / qmtclient
        |
HTTP RPC / WebSocket
        |
qmtserver
        |
xtquant
        |
MiniQMT
```

## 0.1.0: 已完成

`0.1.0` 是安全远程网关 MVP，已经包含：

- CLI 连接检查。
- `/v1` HTTP API。
- RPC 方法白名单。
- token 鉴权。
- 交易保护、dry-run、账号/代码/限额校验、确认文本和审计日志。
- WebSocket 事件。
- 订单、成交和事件内存缓存。
- 内置 Python 兼容客户端。
- 日志、指标、request ID 和 Windows 启动脚本。

## 0.2.0: 已完成

`0.2.0` 聚焦透明 RPC 实验模式。该模式默认关闭，用于在明确授权后探索白名单外的公开
`xtquant` 方法。

详细设计和使用说明见 [Transparent RPC](transparent-rpc.md)。

## 1.0.0: 远期稳定版

`1.0.0` 代表 qmtserver 的服务端 API、错误码、WebSocket 事件结构、交易保护语义和运维文档
进入稳定承诺期。

## 边界

- qmtclient 已拆为独立项目；客户端 SDK 规划在 qmtclient 中维护。
- qmtserver 只规划服务端能力、MiniQMT 连接、RPC 安全边界、交易保护和运维。
- 没有明确版本计划的想法暂不写入路线图。

详细发布节奏见 [Release Plan](release-plan.md)。

## 历史计划

早期 milestone 文档已归档到 [Archived Milestone Plans](archive/milestones/README.md)。这些文档仅用于追溯设计演进。
