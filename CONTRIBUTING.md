# Contributing

## 本地开发

```powershell
uv sync
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts/check_code_health.py
```

默认开发环境可以不安装 `xtquant`。不直连 MiniQMT 的单元测试、ruff 和 ty 门禁应在缺少
`xtquant` 时继续可运行；涉及真实行情、交易连接或 `qmtserver check` 的验证仍需要 Windows、
MiniQMT 和下面的可选依赖。

如果需要在本机直连 MiniQMT 或运行依赖 `xtquant` 的检查，可以安装可选依赖：

```powershell
uv sync --extra xtquant
```

## 代码风格

- 源码放在 `src/qmtserver`。
- 测试放在 `tests`。
- 与 MiniQMT 直接交互的逻辑优先集中在 `qmtserver.miniqmt`。
- 后续服务端入口可以单独放在 `qmtserver.server` 或 `qmtserver.api`。
- 单个 `.py` 文件建议控制在 300 行以内，超过 400 行应评估拆分，超过 500 行通常应拆分。
- 单个函数建议控制在 50 行以内，超过 80 行通常应拆 helper 或领域服务。
- API 路由保持轻薄，业务逻辑放入对应服务、交易、事件、订单或 RPC 模块。
- 自动化 agent 和协作者规范见 `AGENTS.md`。

## Git 提交规范

提交信息使用 Conventional Commits 风格：

```text
type(scope): summary
```

常用 `type`：

- `feat`：新增功能。
- `fix`：修复问题。
- `docs`：文档变更。
- `test`：测试变更。
- `refactor`：不改变行为的重构。
- `style`：仅格式化或样式调整。
- `chore`：依赖、工具、配置等维护任务。
- `ci`：持续集成相关变更。

示例：

```text
feat(cli): add serve command
docs(roadmap): add readonly rpc milestone
chore(tooling): configure ruff and ty
```

提交前请运行：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
git diff --check
```

代码健康报告：

```powershell
uv run python scripts/check_code_health.py
```

分支名建议使用：

```text
feature/<short-topic>
fix/<short-topic>
docs/<short-topic>
```

## 注意事项

服务端运行环境限定为 Windows。`xtquant` 可以通过 `uv sync --extra xtquant` 安装 PyPI 版本，也可以从迅投下载页获取新版后覆盖到 `.venv\Lib\site-packages\xtquant`。不要把 `xtquant` 目录提交到项目根目录。
