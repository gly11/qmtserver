# Changelog

## 0.3.0

- 增加稳定 `/v1/market` 行情 API，覆盖 capabilities、daily bars 和 intraday bars。
- 标准化 bars 响应 schema、metadata、空数据和行情错误语义。
- 增加 snapshot/export API，支持 CSV snapshot、manifest、registry、下载和质量报告。
- 增加历史下载 job API，支持 create/status/result/cancel 和 snapshot result。
- 增加 diagnostics endpoint 和 job metrics，便于检查 MiniQMT、行情源和服务端时钟状态。
- 增加交易日历、标的列表、instrument detail 和数据质量标准接口。
- 更新 API、错误码、roadmap、release plan 和 milestone 归档文档。

## 0.2.0

- 增加默认关闭的透明 RPC 实验模式。
- 增加 `QMT_TRANSPARENT_RPC`、`QMT_TRANSPARENT_RPC_TARGETS`、
  `QMT_TRANSPARENT_RPC_ALLOW_TRADER` 和 `QMT_TRANSPARENT_RPC_ALLOW_TRADING` 配置。
- 透明 RPC 默认只允许 `xtdata`，默认拒绝 `trader` 白名单外方法。
- 拒绝私有方法、dunder 方法、非法方法名和疑似交易方法。
- 透明调用保留 token 鉴权、审计日志、metrics 和标准 RPC 响应结构。
- 补充透明 RPC 文档、错误码和测试。

## 0.1.0

- 初始化 uv / Python 3.13 项目。
- 增加 MiniQMT 连接验证 CLI。
- 将项目整理为标准 `src/` 布局。
- 增加只读 HTTP RPC 网关、方法白名单、JSON 序列化和 `serve` 命令。
- 增加 MiniQMT 连接生命周期状态、重连、断开和稳定 RPC target 错误码。
- 增加 bearer token 鉴权、RPC 方法分级、交易保护开关和审计日志。
- 增加受控交易 RPC、dry-run、账号白名单和下单参数限制。
- 增加 WebSocket 事件流、内存 EventBus、生命周期事件和交易回调事件。
- 增加 Python 客户端 SDK、动态 RPC 代理和事件订阅示例。
- 增加 request ID、`/metrics`、RPC 指标、日志轮转配置和 Windows 运维脚本。
- 增加 `/v1` API、集中错误码、SDK 版本前缀和 API/SDK 文档。
- 增加交易代码白/黑名单、日内限制、真实交易确认和独立交易审计。
- 增加订单/成交/事件内存缓存、查询端点、WebSocket 过滤和 SDK 查询助手。
