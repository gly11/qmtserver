# Development Roadmap

qmtserver 的长期目标是成为一个本地 MiniQMT 网关服务。外部平台、策略系统或自动化工具不需要直接安装和适配 `xtquant`，只需要通过 qmtserver 访问 MiniQMT。

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

## 技术路线

第一阶段优先使用 FastAPI + Uvicorn + JSON。它开发快、易调试、容易被其他平台调用，适合先把服务骨架跑稳。

后续增强路径：

- HTTP JSON：默认控制面和普通查询协议。
- WebSocket：实时事件推送，例如委托回报、成交回报、连接状态变化。
- Arrow：大批量表格数据或行情数据的高性能可选输出格式。
- gRPC + Protobuf：需要强类型多语言客户端或更正式 RPC 契约时再引入。

## Milestone 0: 项目基础

目标：项目具备可维护的开源 Python 项目结构。

状态：已完成。

范围：

- uv + Python 3.13。
- `src/qmtserver` 标准源码布局。
- `tests/`、`docs/`、`examples/`。
- CLI `check`。
- `xtquant` 安装到 `.venv\Lib\site-packages\xtquant`。
- Git 初始化。
- MiniQMT 行情、交易、账号订阅、资金查询验证通过。

验收：

```powershell
uv run python -m unittest discover
uv run qmtserver check --userdata "..." --account-id "..."
```

## Milestone 1: 只读 RPC 网关

目标：启动一个 HTTP 服务，通过统一 `/rpc` 转发白名单内的只读 `xtquant` API。

状态：已完成。

详细计划见 [Milestone 1: Readonly RPC](milestone-1-readonly-rpc.md)。

预期能力：

- `uv run qmtserver serve` 启动本地服务。
- `GET /health` 返回服务健康状态。
- `GET /qmt/status` 返回 MiniQMT 连接状态。
- `GET /rpc/methods` 返回当前允许调用的方法。
- `POST /rpc` 调用白名单只读方法。
- 所有响应都能 JSON 序列化。
- 非白名单方法被拒绝。
- 下单、撤单类方法默认不可调用。

## Milestone 2: 连接生命周期管理

目标：服务端能长期稳定运行，而不是只做一次性调用。

状态：已完成。

详细计划见 [Milestone 2: Connection Lifecycle Management](milestone-2-connection-lifecycle.md)。

范围：

- 完善 `QmtService` 生命周期状态。
- 启动时按配置自动连接 MiniQMT。
- 支持手动 reconnect、disconnect、shutdown。
- 维护 quote、trader、account 订阅状态。
- 记录最近一次错误和最近一次成功调用时间。

验收：

- MiniQMT 重启后可以重新连接。
- 单次 xtquant 调用失败不会导致服务崩溃。
- `/qmt/status` 能清楚展示连接状态和最近错误。

## Milestone 3: 安全边界与交易保护

目标：为未来开放交易接口建立安全边界。

状态：已完成。

详细计划见 [Milestone 3: Security Boundary and Trading Guard](milestone-3-security-trading-guard.md)。

范围：

- 支持 `QMT_API_TOKEN`。
- 支持 `Authorization: Bearer <token>`。
- 支持 `QMT_ENABLE_TRADING=false`。
- RPC 方法分级：`readonly`、`trading`、`admin`。
- 下单和撤单默认拒绝。
- 增加调用审计日志。

验收：

- 没有 token 时无法访问受保护接口。
- `QMT_ENABLE_TRADING=false` 时交易方法一定失败。
- 所有 RPC 调用都有方法名、参数摘要、耗时和结果日志。

## Milestone 4: 交易 RPC

目标：在保护机制下开放真实下单和撤单。

状态：已完成。

详细计划见 [Milestone 4: Trading RPC](milestone-4-trading-rpc.md)。

范围：

- 白名单加入 `order_stock`、`order_stock_async`。
- 白名单加入 `cancel_order_stock`、`cancel_order_stock_async`。
- 增加 `StockAccount`、买卖方向、价格类型等参数转换。
- 增加交易前校验。
- 增加 dry-run 模式。

验收：

- dry-run 下不会真实下单。
- 真实下单必须显式开启 `QMT_ENABLE_TRADING=true`。
- 所有交易请求有审计日志。

## Milestone 5: WebSocket 推送

目标：支持实时事件，不再只依赖轮询。

状态：已完成。

详细计划见 [Milestone 5: WebSocket Events](milestone-5-websocket-events.md)。

范围：

- `WS /ws/events`。
- 推送连接状态变化。
- 推送账号状态变化。
- 推送委托回报、成交回报、下单错误、撤单错误。
- 行情订阅推送作为后续增强。

验收：

- 交易相关事件能从 WebSocket 收到。
- 客户端断开不影响 qmtserver 主连接。

## Milestone 6: 客户端 SDK

目标：让其他 Python 项目调用 qmtserver 像调用本地库一样简单。

状态：已完成。

详细计划见 [Milestone 6: Python Client SDK](milestone-6-python-client-sdk.md)。

范围：

- 增加轻量 `qmtserver.client`。
- 支持 token、超时、错误处理。
- 支持通用 RPC 调用。
- 后续支持动态代理。

验收：

```python
client.rpc("xtdata", "get_full_tick", [["000001.SZ"]])
client.rpc("trader", "query_stock_asset", [{"__type__": "StockAccount", "account_id": "..."}])
```

## Milestone 7: 可观测性与运维

目标：服务长期运行时好排查、好监控。

状态：已完成。

详细计划见 [Milestone 7: Observability and Operations](milestone-7-observability-ops.md)。

范围：

- 日志文件轮转。
- 请求 ID。
- 结构化错误码。
- 简单 `/metrics`。
- Windows 启动脚本。
- 可选 Windows 服务或计划任务方案。

验收：

- 出问题能从日志定位。
- 能知道服务是否健康、MiniQMT 是否在线、RPC 调用是否异常。

## Milestone 8: API 稳定化与兼容性

目标：把 HTTP RPC、WebSocket 和 SDK 固化成稳定契约，减少后续扩展时破坏调用方。

状态：已完成。

详细计划见 [Milestone 8: API Stability and Compatibility](milestone-8-api-stability.md)。

范围：

- 增加推荐 `/v1` API 入口，并保留旧路径兼容。
- 统一错误码和错误响应结构。
- 补充 API、错误码和 SDK 文档。
- SDK 支持 API version 和服务端兼容性检查。
- 增加契约测试。

验收：

- `/v1` 和旧路径都可用。
- SDK 默认使用稳定版本入口。
- 错误码集中定义并文档化。
- 自动化测试通过。

## Milestone 9: 交易安全增强

目标：在真实交易前进一步降低误触发、误配置和超限交易风险。

状态：已完成。

详细计划见 [Milestone 9: Trading Safety Hardening](milestone-9-trading-safety.md)。

范围：

- 股票代码白名单/黑名单。
- 单日下单数量和金额限制。
- 真实交易二次确认。
- 交易审计单独 logger 或文件。
- SDK 交易错误增强。

验收：

- 真实交易需要通过开关、dry-run、账号、代码、限额和确认文本多重保护。
- dry-run 仍然不触发真实 xtquant 方法。
- 交易审计清晰且脱敏。
- 自动化测试通过。

## Milestone 10: 订单状态与事件闭环

目标：把下单、撤单、委托回报、成交回报和事件订阅串成手动运行时可观察的完整闭环。

状态：计划中。

详细计划见 [Milestone 10: Order State and Event Loop](milestone-10-order-events.md)。

范围：

- 订单、成交、错误和最近事件内存缓存。
- HTTP 查询最近订单、成交和事件。
- WebSocket 事件类型过滤。
- SDK 支持事件过滤和常用订单查询。
- 下单返回值与后续回报关联。

验收：

- 回调事件能进入缓存。
- 客户端可按类型订阅事件。
- SDK 可查询订单/成交/最近事件。
- 自动化测试通过。

## Backlog: 可选后续方向

这些方向暂不作为正式 milestone，等真实使用中出现明确需求再升级：

- Windows 守护与自动重启：计划任务、NSSM、MiniQMT 进程检测。
- 多平台接入层：REST 风格业务接口、Webhook、第三方平台示例。
- 高性能数据输出：Arrow、大批量行情数据优化。
- 强类型多语言协议：gRPC + Protobuf。

## 版本节奏

```text
v0.1  项目基础 + check CLI
v0.2  只读 HTTP RPC 网关
v0.3  连接生命周期管理
v0.4  token + 白名单 + 交易保护
v0.5  交易 RPC
v0.6  WebSocket 推送
v0.7  Python SDK
v0.8  API 稳定化与兼容性
v0.9  交易安全增强
v1.0  订单状态与事件闭环
```

核心原则：先跑稳“稳定连接 + 只读转发 + 白名单 + JSON 响应”，再逐步增加交易、推送、SDK、稳定 API 和订单事件闭环。
