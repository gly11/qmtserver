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

## 0.3.x: Stable Market Data Track

`0.3.x` 是稳定行情数据主线，目标是让策略和回测系统不再依赖 `/v1/rpc` 与 `xtdata` 原始返回
形态，而是消费 qmtserver 自己承诺的稳定行情数据契约。该主线按 phase 推进；是否拆成多个
patch/minor 版本由完成度和发布风险决定，不提前把每个 phase 绑定到固定版本号。

详细开发计划见 [Active Milestone Plans](milestones/README.md)。

### Phase 1: 标准行情查询

- 新增 whitelist-only 的 `/v1/market` 行情 API，不依赖 transparent RPC。
- 新增标准化 daily bars endpoint，输出固定字段：`date`、`symbol`、`open`、`high`、`low`、
  `close`、`volume`、`amount`、`meta`。
- 新增标准化 intraday bars endpoint，输出固定字段：`timestamp`、`symbol`、`period`、`open`、
  `high`、`low`、`close`、`volume`、`amount`、`meta`。
- 行情响应 metadata 包含 request params、row_count、generated_at、qmtserver version 和
  xtquant version。
- 明确空数据、未连接、无权限、方法不允许、数据源异常和参数非法的稳定语义。
- 新增 capability endpoint，返回 supported methods、schema versions、periods 和 adjust modes，
  供 qmtclient 与策略系统自动适配。
- 使用 fake adapter / fixture 覆盖无 `xtquant` 开发环境；真实 MiniQMT 只作为 Windows 集成验收。

非目标：

- 不做 CSV、Parquet 或 Arrow 批量导出。
- 不做历史下载任务队列。
- 不做服务端持久化缓存或 snapshot registry。
- 不做交易日历、股票池或数据质量报告。

验收标准：

- 策略和回测系统可通过 `/v1/market` 获取稳定 daily/intraday bars，不需要调用 transparent RPC。
- 同一请求参数下，返回字段、metadata 和 error code 对 qmtclient 保持稳定。
- 本地无 `xtquant` 环境可以运行单元测试、ruff、format 和 ty 门禁。
- Windows + MiniQMT 环境完成至少一个 daily bars 和一个 intraday bars smoke test。

### Phase 2: Snapshot、导出与 Manifest

目标是支持回测批量数据准备。大批量历史数据不通过普通 JSON 同步返回，而是生成可追溯
snapshot，并通过 manifest 描述数据完整性。

- 新增 snapshot/export API，支持 CSV 作为首个稳定导出格式。
- 设计 snapshot manifest，包含 request params、schema version、format、hash、row_count、
  symbol_count、coverage_start、coverage_end、generated_at 和版本信息。
- 新增 snapshot registry，可列出已有 snapshot，并按参数 hash 命中已有结果。
- 为后续 Parquet / Arrow 预留格式字段，但不在首版强制支持。

非目标：

- 不把 snapshot 存储做成多用户数据库系统。
- 不在 qmtserver 内实现回测计算。
- 不让 client 端重复解释 `xtdata` 原始形态。

验收标准：

- 回测系统可基于 manifest 判断数据来源、覆盖区间和完整性。
- 相同参数重复请求可以复用已有 snapshot。
- 大数据下载不要求通过 JSON response 承载。

### Phase 3: 历史下载 Job API 与诊断

目标是把耗时的 `xtdata.download_history_data` 类操作任务化，避免同步阻塞 API 请求，并增强
运行诊断能力。

- 新增 job create/status/result/cancel API。
- job 状态至少包含 queued、running、succeeded、failed、cancelled。
- job result 关联 snapshot manifest。
- 新增 diagnostics endpoint，返回 MiniQMT 连接、quote 状态、server clock、qmtserver/xtquant
  version 和 sample symbol smoke 结果。
- metrics 增加 request count、latency、error count 和 job status 统计。

非目标：

- 不默认并发运行大量下载任务。
- 不绕过行情与交易 API 的安全分区。

验收标准：

- 历史下载不会阻塞普通 health/status/market 请求。
- job 失败时有稳定 error code 和可追溯错误信息。
- diagnostics 能用于判断 MiniQMT 连接、行情源和示例标的是否可用。

### Phase 4: 数据准备与质量增强

目标是完善回测前置数据准备和数据质量可观测性。

- 新增交易日历、标的列表和 instrument detail 的标准接口。
- 新增数据质量报告，覆盖缺失日期、重复行、异常价格和异常成交量提示。
- 完善缓存策略，避免重复下载和重复标准化。

非目标：

- 不提供投资建议。
- 不把 qmtserver 变成策略执行框架。

验收标准：

- 回测前可以通过 qmtserver 获取交易日历、股票池和 instrument detail。
- snapshot 或 bars 查询可生成基础质量报告。
- 数据质量报告只描述数据问题，不做交易决策。

## 1.0.0: 远期稳定版

`1.0.0` 代表 qmtserver 的服务端 API、错误码、WebSocket 事件结构、交易保护语义和运维文档
进入稳定承诺期。

进入 `1.0.0` 前至少需要完成稳定行情 API、snapshot/export、job API、诊断能力、错误码文档、
schema version 文档和 qmtclient 兼容验证。

## 边界

- qmtclient 已拆为独立项目；客户端 SDK 规划在 qmtclient 中维护。
- qmtserver 负责稳定服务端契约、MiniQMT 连接、`xtquant` 适配、行情 schema 标准化、RPC 安全
  边界、交易保护、snapshot manifest 和运维诊断。
- qmtclient 负责 Python 友好的 facade、类型模型、DataFrame 转换、job polling helper 和本地
  fixture；策略和回测系统应消费 qmtserver 稳定 schema，不直接依赖 `xtdata` 原始形态。
- 没有明确版本计划的想法暂不写入路线图。

详细发布节奏见 [Release Plan](release-plan.md)。

## 历史计划

早期 milestone 文档已归档到 [Archived Milestone Plans](archive/milestones/README.md)。这些文档仅用于追溯设计演进。
