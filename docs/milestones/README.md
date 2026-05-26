# Active Milestone Plans

这些文档用于指导 qmtserver 当前和后续阶段的具体开发。已完成的早期计划归档在
[`docs/archive/milestones`](../archive/milestones/README.md)。

当前主线是 `0.3.x: Stable Market Data Track`，目标是让策略和回测系统消费 qmtserver 的稳定
行情数据契约，而不是直接依赖 `/v1/rpc` 或 `xtdata` 原始返回形态。

## Milestones

- [Milestone 11: Stable Market Data API](milestone-11-stable-market-data.md)
- [Milestone 12: Snapshot Export and Manifest](milestone-12-snapshot-export.md)
- [Milestone 13: History Jobs and Diagnostics](milestone-13-history-jobs-diagnostics.md)
- [Milestone 14: Data Preparation and Quality](milestone-14-data-prep-quality.md)

## 执行原则

- 每个 milestone 都应能独立验收，不要求一次性完成整条主线。
- API route 保持薄层，业务逻辑放到 service、adapter、schema、serialization 或 job/snapshot 模块。
- 新 public behavior 必须有单元测试或接口测试。
- 无 `xtquant` 的本地开发环境必须能运行主质量门禁；真实 MiniQMT 连接作为 Windows 集成验收。
- 大批量数据不要通过普通 JSON response 承载，优先落为 snapshot 和 manifest。

