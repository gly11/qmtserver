# Market Data Lake Stabilization Plan

本文档规划 qmtserver Market Data Lake 从 `0.7.0` 基线进入稳定化阶段的开发工作。该方向只处理
MiniQMT / `xtquant` 只读行情数据，不连接 trader，也不执行下单、撤单、转账或其他交易命令。

## 目标

将当前“可下载、可缓存、可查询、可导出”的数据湖基线推进为“可重复运行、可诊断、可维护”的
server 端行情数据层。

稳定化后的预期效果：

- 重复下载相同区间时能够可靠命中本地 coverage。
- 部分覆盖时能够明确报告缺口，而不是只给出粗粒度覆盖范围。
- 本地 Parquet 文件、DuckDB 元数据和 export 文件可以被检查、清理和重建。
- query、quality 和 export 行为只读取本地数据，不意外触发 MiniQMT 下载。
- 发布前可以通过 fake tests 和只读 MiniQMT smoke 验证主要路径。

## 当前基线

`0.7.0` 已经具备：

- `qmtserver[data]` optional extra。
- DuckDB schema 初始化。
- 持久化 data download job。
- `xtdata.download_history_data` 后读取标准 bars。
- 按 symbol 写入 Parquet。
- `data_files` 和 `data_coverage` 元数据。
- `/v1/market/data/download`、`coverage`、`bars`、`quality`、`exports` 和 `jobs` API。

当前主要不足：

- coverage 只按 symbol/period/adjust 维护合并后的整体区间，不能表达中间缺口。
- 重复或重叠下载可能产生多个 Parquet 文件，缺少 compaction 和 orphan 检查。
- query 当前按登记文件逐个读取，缺少更强的排序、去重、分页和大结果保护。
- export 有创建、下载、删除，但缺少过期清理、manifest 校验和维护命令。
- DuckDB schema 还没有显式 migration/version 管理。
- 真实 MiniQMT smoke 流程还没有专门覆盖 data lake 的完整闭环。

## 边界

本阶段不做：

- 不新增真实交易接口。
- 不修改 MiniQMT `userdata_mini/datadir` 原始缓存。
- 不把 qmtclient 功能混入 qmtserver。
- 不承诺全量适配所有 `xtquant` 行情 API。
- 不把 transparent RPC 结果直接写入稳定数据湖。

本阶段可以做：

- 只读调用 `xtdata.download_history_data` 和显式适配的 bars reader。
- 维护 qmtserver 自有 `QMT_DATA_DIR` 下的 Parquet、DuckDB 和 exports。
- 增加维护 CLI 或只读维护 API。
- 增加 fake-based 单元测试和真实 MiniQMT readonly smoke 脚本。

## 文件边界

主要代码区域：

- `src/qmtserver/data/schema.sql`：DuckDB schema 和索引。
- `src/qmtserver/data/repository.py`：job、file、coverage 元数据读写。
- `src/qmtserver/data/coverage.py`：coverage 判断和缺口摘要。
- `src/qmtserver/data/jobs.py`：download job 调度、缓存命中和写入流程。
- `src/qmtserver/data/files.py`：Parquet 写入路径、hash、分区策略。
- `src/qmtserver/data/query.py`：本地 Parquet 查询、排序、limit 和截断。
- `src/qmtserver/data/exports.py`：CSV export manifest、下载和删除。
- `src/qmtserver/api/routes_market_data.py`：HTTP API request/response glue。
- `scripts/`：只读 smoke 和维护脚本。

主要测试区域：

- `tests/test_data_backend.py`
- `tests/test_data_coverage.py`
- `tests/test_data_jobs.py`
- `tests/test_data_files.py`
- `tests/test_data_query.py`
- `tests/test_data_exports.py`
- `tests/test_api_market_data.py`

主要文档区域：

- `docs/market-data-lake.md`
- `docs/api.md`
- `docs/operations.md`
- `docs/compatibility.md`
- `docs/release-plan.md`

## 阶段 1：Metadata And Coverage Correctness

状态：已完成。coverage response 已包含合并摘要、file-level `covered_segments` 和 `gaps`；
cached download 会使用 segments 判断中间缺口。

目标：让 coverage 从“粗略整体区间”变成“能判断完整覆盖、部分覆盖和缺口”的可靠元数据。

开发项：

- 增加 coverage segments 概念，用于记录每个 file 的实际覆盖区间。
- 保留当前合并 coverage summary，作为快速摘要。
- coverage 查询返回：
  - `fully_covered`
  - `coverage`
  - `missing_symbols`
  - `gaps`
  - `covered_segments`
- 下载任务在 `force=false` 时只在所有 symbol 的请求区间都完整覆盖时命中缓存。
- 对重叠 coverage 做合并判断，但不因为合并 summary 覆盖首尾就误判中间无缺口。

建议任务：

1. 在 `tests/test_data_coverage.py` 写 failing tests：
   - 两段 coverage 中间缺一天时 `fully_covered=false`。
   - 两段 coverage 连续或重叠时 `fully_covered=true`。
   - 多 symbol 中任一 symbol 缺口时整体 `fully_covered=false`。
2. 修改 `src/qmtserver/data/coverage.py`，实现 segment/gap 判断。
3. 必要时扩展 `src/qmtserver/data/repository.py` 的 `list_files()` 或新增 `list_coverage_segments()`。
4. 更新 `docs/api.md` 的 coverage response 字段说明。
5. 运行：

```powershell
uv run python -m unittest tests.test_data_coverage tests.test_data_jobs tests.test_api_market_data
uv run ruff check .
uv run ty check
git diff --check
```

验收标准：

- coverage 缺口不会被 summary 首尾范围误判为完整覆盖。
- cached download 不会跳过仍有缺口的真实下载。
- API response 仍保持 JSON-friendly。

建议提交：

```text
feat(data): add coverage gap detection
```

## 阶段 2：Storage Maintenance

状态：已完成维护增强。`qmtserver data check` 可检查 missing registered files、orphan
Parquet、orphan exports、Parquet metadata mismatch，并输出本地数据目录健康摘要；
`qmtserver data cleanup` 默认 dry-run，显式 `--delete` 才删除 `QMT_DATA_DIR` 内候选文件，
并支持 `--expired-days` 清理过期 export；`qmtserver data rebuild-index --execute` 可从本地
Parquet 重建 DuckDB file index 和 coverage metadata。

目标：让本地 Parquet 与 DuckDB 元数据可维护，避免长期运行后文件膨胀、孤儿文件和重复文件失控。

开发项：

- 增加 storage manifest 检查能力：
  - DuckDB 中登记但文件不存在。
  - 文件存在但未登记。
  - hash 不匹配。
  - row_count 不匹配。
- 增加 cleanup 能力：
  - 删除 orphan export。
  - 删除 orphan parquet 时必须显式 `--delete`。
  - dry-run 为默认行为。
- 增加 compaction 规划：
  - 同 symbol/kind/period/adjust 下多个重叠文件合并为一个新文件。
  - compaction 默认只生成 plan，执行需要显式参数。
- 增加 metadata rebuild：
  - 从 `QMT_DATA_DIR/raw/bars/.../*.parquet` 扫描并重建 `data_files` / coverage。

建议任务：

1. 创建 `src/qmtserver/data/maintenance.py`，放 storage check、cleanup plan、rebuild plan。
2. 创建 `tests/test_data_maintenance.py`，覆盖 dry-run、orphan detection、missing file detection。
3. 在 CLI 增加维护命令：

```text
qmtserver data check
qmtserver data cleanup --dry-run
qmtserver data rebuild-index --dry-run
```

4. 更新 `docs/operations.md`，说明维护命令不触发 MiniQMT 下载、不连接 trader。

验收标准：

- 默认维护命令只读或 dry-run。
- 删除动作必须显式确认参数。
- 本地文件和 DuckDB 元数据不一致时能给出可读摘要。

建议提交：

```text
feat(data): add storage maintenance checks
```

## 阶段 3：Query And Export Reliability

状态：已完成。`/v1/market/data/bars` 本地查询已支持稳定排序、symbol/period/time 去重、
`limit`/`offset` 分页、`next_offset` 和 query metadata；data export manifest 已记录
`source_file_count`、`deduplicated_row_count` 和 `truncated`。

目标：让本地查询和导出在大数据量、多文件、重叠文件场景下行为稳定。

开发项：

- query 结果按 symbol + 时间稳定排序。
- 对同 symbol 同时间戳重复行做确定性去重。
- 支持 `offset` 或 cursor-style pagination，避免只靠 `limit`。
- response 增加：
  - `source_file_count`
  - `truncated`
  - `deduplicated_row_count`
  - `next_offset` 或 `next_cursor`
- export 使用 query 的同一套过滤、排序和去重逻辑。
- export manifest 记录：
  - request hash
  - row_count
  - source_file_count
  - generated_at
  - expires_at 可选

建议任务：

1. 扩展 `tests/test_data_query.py`：
   - 多文件乱序输入输出仍排序稳定。
   - 重叠文件重复 bar 只返回一行。
   - limit + offset 返回正确窗口。
2. 修改 `src/qmtserver/data/query.py`。
3. 扩展 `tests/test_data_exports.py`，验证 export manifest 记录 query metadata。
4. 修改 `src/qmtserver/data/exports.py`。
5. 更新 `docs/api.md` 和 `docs/operations.md`。

验收标准：

- 查询结果可分页。
- 重叠下载不会导致 API 返回重复 bar。
- export 与 bars query 的过滤、排序、去重语义一致。

建议提交：

```text
feat(data): stabilize local bars query and exports
```

## 阶段 4：Download Job Reliability

状态：已完成基础增强。data download result 已包含 per-symbol `symbol_results`；新增
`GET /v1/market/data/jobs`，可按 status 和 limit 查询 DuckDB 中持久化的 data jobs。

目标：提高 data download job 的可恢复性和可观测性。

开发项：

- job result 增加 per-symbol summary：
  - `status`
  - `downloaded`
  - `cached`
  - `row_count`
  - `file_count`
  - `coverage_start`
  - `coverage_end`
  - `gaps`
- downloader 执行时按 symbol 记录失败，避免一个 symbol 失败后丢失其他 symbol 成功结果。
- 对 running job 增加超时/卡住诊断字段。
- 服务重启后可以列出最近 job，而不是只能按 id 查询。
- 增加 API：

```text
GET /v1/market/data/jobs
```

可选参数：

```text
status=running|succeeded|failed
limit=50
```

建议任务：

1. 扩展 `DataJobRepository`，增加 `list_jobs(status=None, limit=50)`。
2. 在 `tests/test_data_jobs.py` 增加 job list 和 per-symbol summary tests。
3. 在 `routes_market_data.py` 增加 `GET /v1/market/data/jobs`。
4. 在 `docs/api.md` 增加 job list 文档。

验收标准：

- 服务重启后仍能通过 DuckDB 查询历史 data jobs。
- 多 symbol job 的结果足够定位失败 symbol。
- job API 不暴露本地个人路径，必要时只返回相对路径或脱敏路径。

建议提交：

```text
feat(data): add persistent data job listing
```

## 阶段 5：Readonly Smoke And Compatibility Records

状态：已完成基础脚本。新增 `scripts/smoke_market_data_lake.py`，覆盖 health、data download、
job polling、coverage、bars、quality、export 和 cached second download。脚本只访问
`/v1/market/data/*` 和 `/v1/health`，显式不连接 trader，不执行交易命令。

目标：建立发布前可重复执行的真实 MiniQMT readonly 验证流程。

开发项：

- 新增 smoke 脚本：

```text
scripts/smoke_market_data_lake.py
```

覆盖：

- 启动后检查 `/v1/health`。
- 提交 `/v1/market/data/download`。
- 轮询 `/v1/market/data/jobs/{job_id}`。
- 查询 `/v1/market/data/coverage`。
- 查询 `/v1/market/data/bars`。
- 查询 `/v1/market/data/quality`。
- 创建、下载、删除 export。
- 再提交同一请求，验证 cached result。

脚本约束：

- 显式不连接 trader。
- 不调用 `/v1/trader/*`。
- 不调用任何 order/cancel/transfer 方法。
- 输出只包含脱敏路径、row_count、file_count、coverage 和 cached 状态。

建议任务：

1. 创建 `scripts/smoke_market_data_lake.py`。
2. 创建 `tests/test_smoke_market_data_lake_script.py`，用 fake HTTP server 或 fake client 覆盖流程。
3. 更新 `docs/operations.md` 和 `docs/compatibility.md`。
4. 发布前人工运行：

```powershell
uv sync --extra xtquant --extra data
uv run python scripts\smoke_market_data_lake.py --symbol 000001.SZ --start 2026-01-01 --end 2026-01-31 --require-rows
```

验收标准：

- smoke 能验证 download -> query -> quality -> export -> cached download 闭环。
- 输出明确声明未连接 trader、未执行交易命令。
- compatibility matrix 记录本地 xtquant/MiniQMT smoke 结果。

建议提交：

```text
test(data): add market data lake smoke script
```

## 阶段 6：Documentation And Release Gate

状态：已完成文档收口。`docs/release-plan.md` 已记录 Market Data Lake 稳定化主线和发布门禁；
`docs/operations.md`、`docs/api.md`、`docs/compatibility.md` 和 `docs/market-data-lake.md` 已同步
本阶段新增能力。当前未新增错误码，`docs/errors.md` 暂无变更。

目标：让用户知道如何安全、正确地使用和维护数据湖。

开发项：

- `docs/market-data-lake.md`：补充稳定化后的操作模型。
- `docs/operations.md`：补充数据目录、维护命令、smoke 命令。
- `docs/api.md`：补充新增字段和新增 job list API。
- `docs/errors.md`：补充维护、coverage、export 相关错误码。
- `docs/release-plan.md`：把 Market Data Lake stabilization 加入下一阶段发布门禁。

发布前质量门禁：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts\check_code_health.py --enforce
git diff --check
uv build
uv tool run twine check dist\qmtserver-<version>.tar.gz dist\qmtserver-<version>-py3-none-any.whl
```

真实 MiniQMT 只读门禁：

```powershell
uv run python scripts\smoke_market_data_lake.py --symbol 000001.SZ --require-rows
```

如果真实 MiniQMT smoke 失败，可以继续合并代码，但发布说明必须写明失败原因和未验证项。

建议提交：

```text
docs(data): document market data lake stabilization
```

## 推荐执行顺序

优先级最高：

1. 阶段 1：Metadata And Coverage Correctness。
2. 阶段 5：Readonly Smoke And Compatibility Records。

原因：coverage 正确性决定缓存命中是否可信；smoke 决定真实 MiniQMT 路径是否可信。这两项完成后，
后续 storage maintenance、query/export 和 job list 的风险都更低。

建议不要一次性实现全部阶段。每个阶段单独提交，完成后运行对应测试和完整质量门禁。
