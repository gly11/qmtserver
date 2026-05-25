# Architecture

qmtserver 当前分为三层：

1. CLI 层：`qmtserver.cli`
2. MiniQMT 适配层：`qmtserver.miniqmt`
3. 第三方 SDK：`xtquant`

CLI 只负责参数解析和结果展示，MiniQMT 连接、检查和数据转换逻辑都放在适配层。后续扩展服务端时，可以在适配层之上新增 HTTP、WebSocket、RPC 或消息队列接口。

## 后续方向

- 增加配置加载模块，支持 `.env` 和环境变量。
- 增加服务端模块，封装连接生命周期。
- 增加账号、行情、委托、成交等领域接口。
- 增加结构化日志和健康检查端点。
