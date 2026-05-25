# Contributing

## 本地开发

```powershell
uv sync
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

## 代码风格

- 源码放在 `src/qmtserver`。
- 测试放在 `tests`。
- 与 MiniQMT 直接交互的逻辑优先集中在 `qmtserver.miniqmt`。
- 后续服务端入口可以单独放在 `qmtserver.server` 或 `qmtserver.api`。
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

分支名建议使用：

```text
feature/<short-topic>
fix/<short-topic>
docs/<short-topic>
```

## 注意事项

`xtquant` 来自本地下载包，当前不从 PyPI 安装。重建 `.venv` 后，需要重新复制到 `.venv\Lib\site-packages\xtquant`。
