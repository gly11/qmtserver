# Changelog

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
