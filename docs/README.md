# Documentation

- [xtquant Adapter Guide](xtquant-adapter.md): adapter rules, compatibility checklist, and real
  MiniQMT smoke requirements for stable `xtquant` integrations.

文档按用途拆分：

- [Architecture](architecture.md)：当前架构和后续服务端方向。
- [Installation](installation.md)：Windows、Python 和 `xtquant` 安装说明。
- [Development Roadmap](roadmap.md)：整体开发能力路线。
- [Realtime Market Subscriptions](realtime-subscriptions.md)：实时行情订阅和 WebSocket quote
  event 的设计、验证记录和 smoke 命令。
- [Compatibility Matrix](compatibility.md)：`xtquant` 版本、签名和真实 MiniQMT smoke 记录。
- [Market Data Lake](market-data-lake.md)：行情下载、高性能本地缓存和 DuckDB/Parquet 数据层规划。
- [RFC: Market Data Lake Large Historical Downloads](rfc-market-data-lake-large-downloads.md)：
  全市场多年历史数据下载的 server 端增强规划。
- [Market Data Lake Stabilization Plan](market-data-lake-stabilization.md)：数据湖 coverage、
  storage maintenance、query/export 和 readonly smoke 的稳定化计划。
- [Release Plan](release-plan.md)：版本定位、发布门禁、实时订阅 smoke 和后续节奏。
- [API Reference](api.md)：稳定 HTTP RPC 和 WebSocket 契约。
- [Error Codes](errors.md)：错误码和错误响应结构。
- [Built-in Client](sdk.md)：内置 Python 兼容客户端说明；独立客户端规划在 qmtclient 项目中维护。
- [Transparent RPC](transparent-rpc.md)：`0.2.0` 引入的透明 RPC 模式和风险边界。
- [Code Quality Track](code-quality.md)：代码健康基线、阈值和优化路线。
- [Operations](operations.md)：本机运行、日志和健康检查。
- [Troubleshooting](troubleshooting.md)：常见连接、鉴权和事件问题排查。
- [Archived Milestone Plans](archive/milestones/README.md)：已完成 milestone 详细计划归档。

原则：

- 面向开发者的长期规划放在 `docs/`。
- 面向首次使用者的安装、运行、验证命令放在根目录 `README.md`。
- 面向协作流程和代码规范的内容放在 `CONTRIBUTING.md` 和 `AGENTS.md`。
