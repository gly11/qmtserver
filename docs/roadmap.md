# Development Roadmap

qmtserver 的长期目标是成为一个本地 MiniQMT 网关服务。外部平台、策略系统或自动化工具
不需要直接安装和适配 `xtquant`，只需要通过 qmtserver 访问 Windows 上运行的 MiniQMT。

```text
外部平台 / 策略系统 / 自动化工具
        |
HTTP RPC / WebSocket / SDK
        |
qmtserver
        |
xtquant
        |
MiniQMT
```

## 当前能力

当前 `0.1.0` 已经完成安全远程网关 MVP，具备以下基础能力：

- CLI 连接检查：验证行情连接、交易连接、账号订阅和资金查询。
- 本地 FastAPI 服务：提供 `/v1` HTTP API、RPC 网关和健康检查。
- RPC 白名单：只开放显式登记的方法，避免直接暴露任意 `xtquant` 调用。
- 交易保护：交易开关、dry-run、账号/代码/限额校验、确认文本和审计日志。
- WebSocket 事件：推送连接状态、委托回报、成交回报和错误事件。
- 订单/成交/事件缓存：提供最近订单、成交和事件查询接口。
- Python 客户端 SDK：支持 HTTP RPC、动态代理、事件订阅和常用查询。
- 运维基础：日志轮转、请求 ID、错误码、指标端点和 Windows 启动脚本。

## 技术路线

- HTTP JSON：默认控制面和普通查询协议。
- WebSocket：实时事件推送，例如委托回报、成交回报、连接状态变化。
- Python SDK：面向其他 Python 项目和自动化脚本的客户端入口。
- Arrow：作为未来大批量表格数据或行情数据的高性能可选输出格式。
- gRPC + Protobuf：需要强类型多语言客户端或更正式 RPC 契约时再引入。

## 后续方向

这些方向不急于一次性完成，建议根据真实使用反馈逐步推进：

- 透明 RPC：默认关闭，用于白名单外 `xtquant` API 探索和远程策略开发。
- 远程运行体验：网关机启动、防火墙、远程诊断和 SDK 重连体验。
- 策略测试工具：fake client、JSON fixture 和事件回放。
- 发布与安装：PyPI 发布、TestPyPI 验证、可信发布流程。
- Windows 守护：计划任务、NSSM、MiniQMT 进程检测和自动重启。
- 客户端拆包：稳定后将跨平台客户端拆成独立 `qmtclient` 包。
- 多平台接入层：REST 风格业务接口、Webhook、第三方平台示例。
- 数据输出优化：Arrow、大批量行情数据分页/压缩/缓存。
- 协议增强：在确有需求时引入 gRPC + Protobuf。
- 持久化：订单、成交、审计和事件的可选 SQLite/文件存储。

## 版本节奏

```text
0.1.0  已完成  安全远程网关 MVP
0.2.0  计划中  透明 RPC 实验模式
1.0.0  远期    稳定版本
```

详细发布节奏见 [Release Plan](release-plan.md)。

## 历史计划

早期阶段的详细 milestone 计划已归档到
[Archived Milestone Plans](archive/milestones/README.md)。这些文档保留用于追溯设计演进，
不再作为正式使用文档的主要入口。
