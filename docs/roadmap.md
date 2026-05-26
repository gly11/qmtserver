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

## 0.3.0: 已完成

`0.3.0` 是稳定行情数据版本，目标是让策略和回测系统不再依赖 `/v1/rpc` 与 `xtdata` 原始返回
形态，而是消费 qmtserver 自己承诺的稳定数据契约。

已完成能力：

- whitelist-only 的 `/v1/market` 行情 API，不依赖 transparent RPC。
- 标准化 daily bars 和 intraday bars，包含固定 OHLCV/amount 字段和 per-row `meta`。
- 行情响应 metadata，包含 request params、row_count、generated_at、qmtserver version 和
  xtquant version。
- 空数据、未连接、无权限、方法不允许、数据源异常和参数非法的稳定错误语义。
- capability endpoint，返回 supported methods、schema versions、periods 和 adjust modes。
- CSV snapshot/export、manifest、registry、download 和 snapshot 质量报告。
- 历史下载 job create/status/result/cancel，job result 可关联 snapshot manifest。
- diagnostics endpoint、job metrics、交易日历、标的列表、instrument detail 和 bars 质量报告。

详细 milestone 计划已归档到 [Archived Milestone Plans](archive/milestones/README.md)。

## 1.0.0: 远期稳定版

`1.0.0` 代表 qmtserver 的服务端 API、错误码、WebSocket 事件结构、交易保护语义和运维文档
进入稳定承诺期。

进入 `1.0.0` 前至少需要完成真实 Windows + MiniQMT 集成 smoke、qmtclient 兼容验证、schema
version 稳定性审查和长期运行诊断验证。

## 边界

- qmtclient 已拆为独立项目；客户端 SDK 规划在 qmtclient 中维护。
- qmtserver 负责稳定服务端契约、MiniQMT 连接、`xtquant` 适配、行情 schema 标准化、RPC 安全
  边界、交易保护、snapshot manifest 和运维诊断。
- qmtclient 负责 Python 友好的 facade、类型模型、DataFrame 转换、job polling helper 和本地
  fixture；策略和回测系统应消费 qmtserver 稳定 schema，不直接依赖 `xtdata` 原始形态。
- 没有明确版本计划的想法暂不写入路线图。

详细发布节奏见 [Release Plan](release-plan.md)。

## 历史计划

已完成 milestone 文档已归档到 [Archived Milestone Plans](archive/milestones/README.md)。这些文档仅用于追溯设计演进。
