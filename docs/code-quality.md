# Code Quality Track

本页记录 qmtserver 的代码健康目标、当前基线和后续优化路线。

## 约束

项目协作规则见 `AGENTS.md`。关键阈值：

- 单个 `.py` 文件尽量控制在 300 行以内。
- 超过 400 行必须评估拆分。
- 超过 500 行通常应拆分。
- 单个函数尽量控制在 50 行以内。
- 超过 80 行应拆成 helper、领域服务或独立模型。

## 检查命令

```powershell
uv run python scripts/check_code_health.py
```

严格模式：

```powershell
uv run python scripts/check_code_health.py --enforce
```

CI 已使用严格模式，提交或 PR 会运行同一套质量门禁。

## 当前基线

截至本计划启动时，最大的源码文件：

```text
263  src/qmtserver/trading.py
255  src/qmtserver/miniqmt.py
254  src/qmtserver/services/qmt_service.py
203  src/qmtserver/client/client.py
193  src/qmtserver/rpc/dispatcher.py
```

最大的测试文件：

```text
459  tests/test_rpc.py
433  tests/test_api.py
185  tests/test_client.py
```

结论：

- 源码没有超过 300 行，暂不需要强制拆分。
- `tests/test_rpc.py` 和 `tests/test_api.py` 已超过 400 行评估线，应优先拆分。
- 后续如果 `trading.py`、`miniqmt.py` 或 `qmt_service.py` 继续增长，应按领域拆分。

## 优化路线

1. 建立代码健康基线和检查脚本。
2. 拆分大测试文件并提取测试夹具。
3. 收紧响应、交易和事件类型边界。
4. 按领域拆分增长较快的源码模块。
5. 用 CI 固化质量门禁。
