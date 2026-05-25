# AGENTS.md

本文件用于约束 qmtserver 项目中的自动化 agent 和协作者行为。改动代码前先读本文件，再读 `README.md`、`docs/README.md` 和相关源码。

## 项目目标

qmtserver 是本地 MiniQMT / xtquant 网关服务。当前已完成连接检查 CLI，后续按 `docs/roadmap.md` 逐步扩展为只读 RPC 网关、交易保护网关、WebSocket 推送和客户端 SDK。

## 目录规范

- 源码放在 `src/qmtserver/`。
- 测试放在 `tests/`。
- 架构、路线、阶段计划放在 `docs/`。
- 示例脚本放在 `examples/`。
- 根目录只放项目入口文档、配置和少量标准文件。
- 不要把 `xtquant` 放回项目根目录；它应安装在 `.venv\Lib\site-packages\xtquant`。
- 不要提交 `.venv/`、缓存目录、MiniQMT 用户数据、行情数据或日志。

## 开发命令

常用命令：

```powershell
uv sync
uv run qmtserver check --skip-quote
uv run python -m unittest discover
uv run ruff format .
uv run ruff check .
uv run ty check
```

连接真实 MiniQMT 时：

```powershell
uv run qmtserver check --userdata "C:\国金证券QMT交易端\userdata_mini" --account-id "资金账号"
```

## 质量门禁

提交或交付前至少运行：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

如果因为本地没有 MiniQMT 或账号无法运行真实连接检查，需要在回复中说明。

## 代码风格

- 使用 Python 3.13。
- 保持 `src/` 布局，不从项目根目录导入源码。
- 优先使用标准库；新增依赖必须有明确用途。
- 对外接口返回 JSON 友好的基础类型。
- xtquant 返回对象转换逻辑集中到适配/序列化层，不要散落在 API 路由里。
- 后续服务端代码按 `api/`、`rpc/`、`services/` 分层。
- 下单、撤单等交易方法默认禁止，必须通过显式配置开关和白名单开放。

## 代码质量与拆分约束

- 单个 `.py` 文件尽量控制在 300 行以内。
- 单个 `.py` 文件超过 400 行时，必须主动评估是否按职责拆分。
- 单个 `.py` 文件超过 500 行时，除非是生成文件、纯常量表或非常明确的集中 registry，否则应拆分。
- 单个函数尽量控制在 50 行以内。
- 单个函数超过 80 行时，应优先拆成私有 helper、领域服务或独立模型。
- 测试文件超过 500 行时，也应按功能拆分，例如 `test_trading_safety.py`、`test_order_events.py`。
- API 路由只做请求解析、依赖注入和响应组装，不承载复杂业务逻辑。
- RPC dispatcher 只负责调度流程，不堆叠交易校验、序列化、审计、缓存等细节。
- 交易校验、订单缓存、事件分发、序列化、审计日志应放在各自领域模块。
- 同一函数内嵌套超过 3 层时，优先用早返回或 helper 降低复杂度。
- 一个改动如果同时涉及格式化、重构、功能和文档，应尽量拆成多个提交。
- 新增公共行为必须有测试；交易相关改动必须覆盖失败路径。

## 文档规范

- 新增功能要同步更新 `README.md` 或 `docs/` 中对应文档。
- 长期规划写入 `docs/roadmap.md`。
- 单阶段详细计划写入独立 milestone 文档。
- 协作规则更新写入本文件或 `CONTRIBUTING.md`。

## 安全约束

- 不要在仓库中写入真实账号、token、密码或个人路径。
- `.env.example` 只能保留示例值。
- 不要绕过 RPC 白名单直接暴露任意 xtquant 方法。
- 交易能力默认关闭；真实下单能力必须有审计日志和显式开关。

## Git 约束

- 不要回滚用户未要求回滚的改动。
- 不要提交 `.venv/` 或本地运行产物。
- 大文件、日志、MiniQMT 数据目录应保持在 `.gitignore` 中。
- 分支名建议使用 `codex/<short-topic>`、`feature/<short-topic>`、`fix/<short-topic>` 或 `docs/<short-topic>`。
- 提交信息使用 Conventional Commits 风格：`type(scope): summary`。
- `summary` 使用英文小写祈使句，不以句号结尾，长度建议不超过 72 个字符。
- 不要把格式化、重构、功能、文档大杂烩塞进同一个提交；能拆就拆。
- 提交前确认 `git diff --check` 没有空白错误。
- 如果没有明确要求，不要替用户创建 commit；只准备好变更并说明验证结果。

提交类型：

- `feat`：新增用户可见功能。
- `fix`：修复 bug。
- `docs`：文档变更。
- `test`：测试新增或调整。
- `refactor`：不改变行为的代码结构调整。
- `style`：仅格式化或非行为风格调整。
- `chore`：工具、依赖、配置、维护任务。
- `ci`：持续集成相关变更。

示例：

```text
feat(cli): add serve command
docs(roadmap): add readonly rpc milestone
chore(tooling): configure ruff and ty
test(cli): cover connectivity check exit codes
```
