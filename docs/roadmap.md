# Development Roadmap

qmtserver 的目标是让一台已登录 MiniQMT 的 Windows 电脑成为受控网关。其他机器通过
HTTP API、WebSocket 或独立客户端项目 qmtclient 访问它，而不直接安装或适配 `xtquant`。

```text
remote tools / strategies / qmtclient
        |
HTTP API / WebSocket
        |
qmtserver
        |
xtquant adapters
        |
MiniQMT
```

路线图按能力方向维护，不精确绑定版本号。具体已发布版本和发布门禁见
[Release Plan](release-plan.md)。

## Completed Foundation

qmtserver 当前已经具备一个安全优先的本地网关基础：

- CLI MiniQMT 连接检查。
- `/v1` HTTP API。
- allowlisted RPC forwarding。
- 默认关闭的 transparent RPC 探索模式。
- token 鉴权。
- 交易保护、dry-run、账号/代码/限额校验、确认文本和审计日志。
- WebSocket 事件。
- 订单、成交和事件内存缓存。
- 内置 Python 兼容客户端；独立客户端能力由 qmtclient 项目承接。
- 日志、metrics、request ID 和 Windows helper scripts。
- trader 只读诊断、runtime health summary 和手动行情订阅恢复基线。
- 稳定行情 API、daily/intraday bars schema、snapshot/export、history job、diagnostics、
  reference 和 data quality endpoints。
- 稳定只读交易查询 API：account status、asset、positions、orders 和 trades。

## Adapter Direction

qmtserver 后续重点不是“一次性转发全部 xtquant API”，而是把高价值能力逐步适配成稳定、
可测试、可运维的 qmtserver 契约。适配规则见 [xtquant Adapter Guide](xtquant-adapter.md)。

### Readonly Trading Queries

继续完善风险较低、价值较高的只读交易查询：

- 账号状态。
- 资金资产。
- 持仓。
- 当日委托。
- 当日成交。
- 可撤委托。

这些接口应返回稳定 JSON schema，不暴露原始 `xtquant` 对象。账号 ID 必须脱敏进入日志，
真实账号查询需要沿用 token、安全边界和审计规则。

### Market Data Depth

继续扩展行情数据能力，但保持显式 API 优先：

- 历史数据下载和补齐。
- 批量历史数据任务。
- 本地缓存状态和缺失数据诊断。
- 交易日历、标的池和 instrument detail 的更完整字段。
- 可选的 Level2、逐笔、盘口等高阶行情能力。

这些能力需要明确区分“从本地缓存读取”和“触发 MiniQMT 下载”的行为，避免用户误以为所有
接口都是即时、无副作用、无等待的查询。

### Market Data Lake

下一条主线是把历史行情下载升级为 server 端高性能本地数据层。设计目标见
[Market Data Lake](market-data-lake.md)。

- 使用 `qmtserver[data]` extra 引入 DuckDB 和 PyArrow。
- 保持 MiniQMT `userdata_mini/datadir` 为上游缓存，不直接修改。
- 在 `data/market` 下维护 qmtserver 标准化行情文件和 DuckDB 元数据。
- 将 download job、data file、coverage 和 quality 信息持久化。
- 后续从本地 Parquet/DuckDB 查询和导出，减少重复访问 MiniQMT。
- client 只提交任务、查询状态和下载结果，不直接 import `xtquant`。

该方向会分阶段推进：先落配置、依赖和 schema 骨架，再实现持久化 job、Parquet writer、
coverage planner、本地查询 API 和 export。

### Subscriptions And Events

在稳定查询 API 之后，逐步增强订阅和事件：

- `xtdata.subscribe_quote` 适配。
- 实时行情事件标准化。
- 断线重连后的手动恢复和后续自动重订阅策略。
- WebSocket backpressure 和事件缓存策略。
- 订阅生命周期管理 API。

订阅类能力应明确连接、取消订阅、心跳、错误事件和客户端断开后的服务端行为。
下一阶段计划见 [Realtime Market Subscriptions](realtime-subscriptions.md)，并同步维护
[Compatibility Matrix](compatibility.md)。

### Trading Expansion

交易能力继续放在更严格的安全边界内推进：

- 下单和撤单保持默认关闭。
- 真实交易必须显式开启，并继续要求 dry-run 关闭、账号 allowlist、symbol allowlist 或
  blocklist、限额、确认文本和审计日志。
- 融资融券、银证转账、期权、期货或其他账户状态变更接口必须单独评审。
- 普通 CI 和默认 smoke test 不执行真实交易。

交易接口不追求覆盖速度，优先保证误用成本高、日志可追溯、失败语义稳定。

### Compatibility Matrix

建立 `xtquant` 兼容性记录：

- 本地 `xtquant` 版本。
- 关键函数签名。
- 输入格式差异，例如日期和时间格式。
- 返回对象和字段变化。
- 已覆盖的单元测试。
- 已完成的真实 MiniQMT smoke 项。

兼容矩阵应帮助判断升级 `xtquant` 包后哪些适配需要复测，而不是假设上游文档和当前行为总是
一致。
矩阵记录见 [Compatibility Matrix](compatibility.md)。

## Stabilization Goals

qmtserver 进入长期稳定阶段前，需要持续强化：

- trader 连接诊断和失败 hint，尤其是 `connect_result=-1` 的定位路径。
- API schema 和错误码稳定性。
- Windows + MiniQMT 真实 smoke 流程。
- qmtclient 兼容性验证。
- 长时间运行诊断。
- 日志、metrics 和事件追踪。
- 安全配置文档和部署建议。
- 发布流程和回滚说明。

稳定版本代表服务端 API、错误码、WebSocket 事件结构、交易保护语义和运维文档进入承诺期。

## Boundaries

- qmtserver 负责服务端契约、MiniQMT 连接、`xtquant` 适配、行情 schema 标准化、RPC 安全
  边界、交易保护、snapshot manifest 和运维诊断。
- qmtclient 是独立客户端项目；Python 友好的 facade、类型模型、DataFrame 转换、job polling
  helper 和本地 fixture 由 qmtclient 承接。
- Transparent RPC 是探索和调试能力，不等同于稳定 API。
- 没有明确使用场景、测试策略和安全边界的想法暂不进入路线图。

## Historical Plans

已完成 milestone 文档归档在 [Archived Milestone Plans](archive/milestones/README.md)。这些文档
仅用于追溯设计演进，不代表当前路线图仍按固定 milestone 推进。
