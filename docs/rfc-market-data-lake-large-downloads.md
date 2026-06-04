# RFC: Market Data Lake Large Historical Downloads

状态：Draft；Phase 1 已开始落地。

本文规划 qmtserver 为“大规模全市场历史数据下载”提供的 server 端增强。典型目标是：
在已登录 MiniQMT 的 Windows 网关机上，把全市场 `2015-01-01` 至今的日 K 数据下载到
server 可见、可维护、可查询的 Market Data Lake 目录。

本文只描述后续设计和验收标准，不要求一次性实现所有内容。

## 背景

qmtclient 已经实现 client 侧数据下载编排能力，包括：

- `client.market_data.wait_job()`
- `wait_download()`
- `ensure_daily_symbol()`
- `ensure_daily_exchange()`
- `ensure_daily_market()`
- `download_export()`
- `create_export_and_download()`
- `client.snapshots.download()`
- `qmtclient market-data` CLI

qmtclient 的边界是：只负责提交任务、轮询 job、显式下载 export/snapshot 文件；不维护本地
Parquet data lake，不维护 DuckDB metadata，不直接访问 MiniQMT/`xtquant`，也不传任意 server
端绝对路径。

qmtserver 当前已经具备 Market Data Lake 基线：`/v1/market/data/download`、coverage、bars、
quality、exports、jobs、DuckDB metadata、Parquet writer、job chunks、ensure gap-fill 和
maintenance CLI。后续增强应让这些能力在“全市场多年历史数据”场景下更可靠、更可诊断，并保持
只读和安全边界。

## 目标

- 由 qmtserver 负责 MiniQMT/`xtdata` 适配、历史数据下载、Parquet/DuckDB 数据湖、coverage、
  quality、job metadata、export/snapshot 文件。
- 让 qmtclient 继续只做远程请求编排和显式文件下载。
- 支持明确、可追溯的大任务输入，例如 `universe="all_a"` 和 `exchange="SH"`。
- 支持全市场长区间任务的进度、失败明细、可恢复 chunk 和增量补齐。
- 避免 client 指定 server 任意绝对路径；server 使用受控 storage profile。
- 修正下载文件 endpoint 的错误语义，避免 client 把 JSON error 保存为数据文件。

## 非目标

- 不新增真实交易能力。
- 不连接或调用 trader 下单、撤单、转账能力。
- 不绕过 token、RPC allowlist、transparent RPC 设置、交易保护或审计规则。
- 不让 qmtclient 直接访问 MiniQMT `userdata_mini`、`xtquant` 或 qmtserver 本地 data lake 文件。
- 不把任意 `xtquant` 方法透明写入稳定数据湖。
- 不允许 request body 传入任意 server 端绝对输出路径。

## 当前观察

根据当前代码和文档：

- `routes_market_data.py` 已支持 `symbols`、`universe`、`exchange`、`chunk_days`、`mode`、
  `incremental`、`force` 等 download request 字段。
- `qmtserver.data.universe` 已能把 `universe="all_a"` 映射到本地 `沪深A股` sector，并生成
  `resolved_symbols`、`symbol_count`、`universe_hash`。
- `jobs.py` 已能规划 chunks、按 chunk 执行、记录 chunk 状态，并在 job detail 返回 `progress`
  和 `chunks`。
- `coverage.py` 已能返回 `covered_segments`、`gaps` 和 `missing_symbols`。
- `repository.py` 已持久化 `data_jobs`、`data_job_chunks`、`data_files` 和 `data_coverage`。
- `files.py` 负责按 symbol/period/adjust 写 Parquet part 文件。
- `exports.py` 当前只稳定支持 CSV export，manifest 记录 hash、row_count、source file count、
  truncation 等摘要。
- `routes_reference.py` 提供 calendar、universe 和 instruments 参考数据入口。
- Phase 1 已要求 `exports/{id}/download` 和 `snapshots/{id}/download` 在 not found 时返回
  HTTP 404；后续阶段需要继续补充更完整的下载 metadata 和断点续传语义。

这些能力说明 qmtserver 已具备大任务调度层的基础，但仍需要把 API 契约、恢复语义、storage
profile 和下载文件语义进一步固化。

## 边界

### qmtserver 负责

- MiniQMT / `xtdata` 连接和显式 adapter。
- 历史行情下载：`xtdata.download_history_data` 和标准 bars reader。
- qmtserver 自有 Parquet/DuckDB data lake。
- `data_jobs`、`data_job_chunks`、`data_files`、`data_coverage` 元数据。
- coverage、gaps、quality、diagnostics、maintenance。
- export/snapshot manifest、文件生成和下载。
- token 鉴权、API envelope、错误码和 HTTP status。

### qmtclient 负责

- 构造稳定 qmtserver API 请求。
- 轮询 job，展示进度和失败摘要。
- 显式下载 export/snapshot 文件。
- 对下载文件做本地校验，例如 hash、content-length 或 etag。
- 不维护 qmtserver data lake，不直接 import `xtquant`，不传 server 本地绝对路径。

### 路径安全

下载和导出请求不应包含 `C:\...`、`D:\...`、`/mnt/...`、`\\server\share` 等任意 server 端路径。
如果需要选择存储位置，应使用 server 配置的 `storage_profile` id。server 负责把 profile 解析到
白名单目录，并验证最终写入路径仍位于该目录下。

## P0 Server 增强

### P0.1 显式 universe/exchange contract

`POST /v1/market/data/download` 应明确支持：

- `universe`: 例如 `"all_a"`。
- `exchange`: 可选 `"SH"`、`"SZ"`、`"BJ"`。
- `symbols`: 仍支持显式 symbol 列表，但不得用 `symbols=[]` 表示全市场。

server 解析后应记录：

- `resolved_symbols`
- `symbol_count`
- `universe_hash`
- `universe`
- `exchange`

这些字段应写入 job request/result，方便以后复盘任务输入。

### P0.2 下载文件 endpoint 错误语义

以下 endpoint 找不到 manifest 或数据文件时，应返回真实 HTTP 404：

- `GET /v1/market/data/exports/{export_id}/download`
- `GET /v1/snapshots/{snapshot_id}/download`

不应返回 HTTP 200 + JSON error envelope。原因是 qmtclient 的下载函数通常按文件流处理响应；
如果 status 是 200，client 可能把 JSON error 保存成 `.csv`、`.zip` 或 `.parquet` 文件。

建议错误响应：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "SNAPSHOT_NOT_FOUND",
    "message": "data export file not found: export-abc"
  },
  "meta": {
    "request_id": "..."
  }
}
```

HTTP status 必须是 `404`。

### P0.3 大任务进度摘要

job status/result 应增加或稳定以下字段：

- `total_symbols`
- `finished_symbols`
- `failed_symbols`
- `current_symbol`
- `row_count`
- `file_count`
- `started_at`
- `updated_at`

这些字段可以来自 `data_job_chunks` 聚合，也可以由 job runner 写入 job result，但 API response
应稳定，便于 qmtclient 轮询展示。

## P1 Server 增强

### P1.1 symbol/date chunk

全市场下载必须拆成 symbol/date chunk，例如：

- 每个 symbol 一组任务。
- 每个 symbol 按 `chunk_days` 拆成日期片段。
- 每个 chunk 有独立 `status`、`attempts`、`row_count`、`file_count`、`error_code`、
  `error_message`、`chunk_start`、`chunk_end`。

chunk 状态应持久化到 DuckDB。服务重启后至少能跳过 `succeeded` chunk；更理想的是提供
显式 resume/retry API。

### P1.2 ensure / incremental 模式

支持：

- `mode="ensure"`
- 或 `incremental=true`

语义：

- 先查 coverage。
- 如果完整覆盖，返回 cached job。
- 如果存在 gaps，只为 gaps 生成 chunks。
- 不重复写完整 `2015-now` 区间。
- `force=true` 明确表示绕过 coverage cache，重新下载 request 覆盖的完整范围。

### P1.3 restart recovery

服务重启后，server 应能基于 DuckDB metadata 恢复或跳过已完成 chunk：

- `queued` / `running` 且长时间未更新的 chunk 可以标记为 `stale` 或重新入队。
- `succeeded` chunk 不重复执行。
- `failed` chunk 可通过 retry/resume 入口重试。
- 如果没有实现后台队列恢复，至少 `mode="ensure"` 再次提交同一 request 时应基于 coverage
  gaps 跳过已写入的部分。

### P1.4 per-symbol result

job result 应提供 per-symbol 摘要：

- `symbol`
- `downloaded`
- `cached`
- `failed`
- `row_count`
- `file_count`
- `coverage_start`
- `coverage_end`
- `gaps`
- `error`

这样 qmtclient 可以展示“哪些 symbol 完成、哪些失败、哪些本地已缓存”，而不需要解析每个
chunk。

### P1.5 storage profile

引入 `storage_profile`：

- client 只传 profile id，例如 `"qmt_main"`。
- server 在配置中维护 profile 到本地目录的映射。
- server 验证最终路径在 profile root 内。
- job、file、export manifest 记录 `storage_profile`，但不暴露不必要的本机绝对路径。

## P2 后续增强

### P2.1 大 export 格式

在 CSV 之外支持：

- `format="parquet"`
- `format="zip"`
- manifest + 多文件分片

大 export 不应强迫所有数据进入单个 CSV。manifest 应描述分片、格式、hash、row_count、
symbol_count 和 coverage。

### P2.2 下载元数据和断点续传

文件下载 endpoint 建议支持：

- `Content-Length`
- `ETag`
- `Last-Modified`
- manifest 中的 `hash`
- `Range` request
- 断点续传

qmtclient 可据此实现大文件下载恢复和本地校验。

### P2.3 数据湖维护

继续增强：

- 小文件 compaction。
- index rebuild 执行模式。
- orphan files 清理。
- coverage consistency check。
- metadata mismatch 报告。
- data lake health summary。

维护命令默认 dry-run，删除和重写必须显式 `--execute` 或 `--delete`。

## API 草案

### POST /v1/market/data/download

请求：

```json
{
  "kind": "daily_bars",
  "universe": "all_a",
  "exchange": "SH",
  "start": "2015-01-01",
  "end": "2026-06-05",
  "adjust": "none",
  "format": "parquet",
  "mode": "ensure",
  "chunk_days": 31,
  "storage_profile": "qmt_main"
}
```

响应：

```json
{
  "ok": true,
  "data": {
    "job": {
      "job_id": "job-20260605-001",
      "kind": "market_data_download",
      "status": "queued",
      "request": {
        "kind": "daily_bars",
        "universe": "all_a",
        "exchange": "SH",
        "start": "2015-01-01",
        "end": "2026-06-05",
        "mode": "ensure",
        "chunk_days": 31,
        "storage_profile": "qmt_main",
        "resolved_symbols": ["600000.SH", "600004.SH"],
        "symbol_count": 2,
        "universe_hash": "sha256:..."
      },
      "created_at": "2026-06-05T02:00:00+00:00",
      "started_at": null,
      "updated_at": "2026-06-05T02:00:00+00:00"
    }
  },
  "error": null,
  "meta": {
    "request_id": "..."
  }
}
```

### GET /v1/market/data/jobs/{job_id}

响应：

```json
{
  "ok": true,
  "data": {
    "job": {
      "job_id": "job-20260605-001",
      "kind": "market_data_download",
      "status": "running",
      "created_at": "2026-06-05T02:00:00+00:00",
      "started_at": "2026-06-05T02:00:01+00:00",
      "updated_at": "2026-06-05T02:10:00+00:00",
      "progress": {
        "schema": "market.data.job_progress.v1",
        "total_symbols": 5200,
        "finished_symbols": 120,
        "failed_symbols": 2,
        "current_symbol": "600519.SH",
        "total_chunks": 62400,
        "finished_chunks": 1480,
        "failed_chunks": 3,
        "queued_chunks": 60917,
        "running_chunks": 1,
        "row_count": 1860000,
        "file_count": 1480
      },
      "symbol_results": [
        {
          "symbol": "600000.SH",
          "downloaded": true,
          "cached": false,
          "failed": false,
          "row_count": 2600,
          "file_count": 84,
          "coverage_start": "2015-01-01",
          "coverage_end": "2026-06-05",
          "gaps": [],
          "error": null
        },
        {
          "symbol": "600004.SH",
          "downloaded": false,
          "cached": false,
          "failed": true,
          "row_count": 0,
          "file_count": 0,
          "coverage_start": null,
          "coverage_end": null,
          "gaps": [
            {
              "gap_start": "2015-01-01",
              "gap_end": "2026-06-05",
              "reason": "download_failed"
            }
          ],
          "error": {
            "code": "DATA_DOWNLOAD_FAILED",
            "message": "RuntimeError: ..."
          }
        }
      ]
    }
  },
  "error": null,
  "meta": {
    "request_id": "..."
  }
}
```

### GET /v1/market/data/coverage

请求：

```text
GET /v1/market/data/coverage?kind=daily_bars&symbols=600000.SH,600004.SH&start=2015-01-01&end=2026-06-05&adjust=none
```

响应：

```json
{
  "ok": true,
  "data": {
    "coverage": {
      "schema": "market.data.coverage.v1",
      "request": {
        "kind": "daily_bars",
        "symbols": ["600000.SH", "600004.SH"],
        "period": "1d",
        "start": "2015-01-01",
        "end": "2026-06-05",
        "adjust": "none"
      },
      "fully_covered": false,
      "coverage": [
        {
          "symbol": "600000.SH",
          "coverage_start": "2015-01-01",
          "coverage_end": "2026-06-05",
          "row_count": 2600,
          "file_count": 84
        }
      ],
      "covered_segments": [
        {
          "symbol": "600000.SH",
          "coverage_start": "2015-01-01",
          "coverage_end": "2015-01-31",
          "row_count": 21,
          "file_count": 1,
          "file_id": "..."
        }
      ],
      "gaps": [
        {
          "symbol": "600004.SH",
          "gap_start": "2015-01-01",
          "gap_end": "2026-06-05",
          "reason": "no_matching_coverage"
        }
      ],
      "missing_symbols": ["600004.SH"]
    }
  },
  "error": null,
  "meta": {
    "request_id": "..."
  }
}
```

### GET /v1/market/data/exports/{export_id}/download error

```http
HTTP/1.1 404 Not Found
Content-Type: application/json
```

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "SNAPSHOT_NOT_FOUND",
    "message": "data export file not found: export-abc"
  },
  "meta": {
    "request_id": "..."
  }
}
```

### Storage profile 配置示例

`.env` 示例：

```env
QMT_DATA_STORAGE_PROFILES=qmt_main
QMT_DATA_STORAGE_PROFILE_QMT_MAIN_ROOT=D:\qmtserver-data\market
QMT_DATA_STORAGE_PROFILE_QMT_MAIN_DB=D:\qmtserver-data\market\db\qmtserver.duckdb
QMT_DATA_STORAGE_PROFILE_QMT_MAIN_FORMAT=parquet
QMT_DATA_STORAGE_PROFILE_QMT_MAIN_EXPORT_ROOT=D:\qmtserver-data\market\exports
```

请求只传：

```json
{
  "storage_profile": "qmt_main"
}
```

server 负责解析和校验，不接受 client 传入 `output_path`、`data_dir`、`db_path` 等绝对路径字段。

## Rollout Plan

### Phase 1: universe/exchange explicit contract + HTTP file error semantics

开发内容：

- 固化 `universe` / `exchange` request contract。
- 拒绝用空 `symbols` 表示全市场。
- job request/result 持久化 `resolved_symbols`、`symbol_count`、`universe_hash`。
- `exports/{id}/download` 和 `snapshots/{id}/download` 找不到文件时返回 HTTP 404。

验收标准：

- `POST /v1/market/data/download` with `universe="all_a"` records canonical symbols metadata。
- invalid universe/exchange 返回稳定错误。
- missing export/snapshot download 的 HTTP status 是 404，不是 200。

测试建议：

- 用 fake qmt service / fake `xtdata.get_stock_list_in_sector` 测 universe resolution。
- 用 FastAPI `TestClient` 验证 download endpoint status code。
- 用临时目录模拟缺失 manifest 和缺失 data file。

### Phase 2: progress fields + per-symbol result

开发内容：

- job detail 增加 `progress` 摘要字段。
- result 增加 `symbol_results`。
- 每个 symbol 汇总 downloaded/cached/failed、row/file count、coverage、gaps、error。

验收标准：

- qmtclient 只读 job response 即可展示大任务进度。
- chunk 失败不会隐藏其他 symbol 的成功进度。
- cached job 的 progress 不显示 queued chunks。

测试建议：

- 用 fake repository 构造 succeeded/failed/running chunks。
- 单元测试 `progress_from_chunks`。
- service 层测试 partial failure result。

### Phase 3: chunked/resumable jobs + ensure mode

开发内容：

- symbol/date chunk 持久化。
- worker 按 chunk 执行。
- `mode="ensure"` / `incremental=true` 基于 coverage gaps 规划 chunks。
- 重启后跳过已完成 chunk，或至少通过再次提交 ensure request 跳过已覆盖数据。
- 增加 stale running chunk 诊断。

验收标准：

- 全市场请求会拆分为多个 chunk，而不是单个粗粒度 job。
- chunk 失败后，其他 chunk 可继续执行。
- 重新提交同一 ensure request 只为 gaps 生成 chunk。
- 不重复写完整 `2015-now` 区间。

测试建议：

- 用 fake downloader 记录实际 chunk request。
- 用 temporary DuckDB 验证 `data_job_chunks` 状态持久化。
- 用 fake coverage planner 返回 `segment_gap` 和 `no_matching_coverage`。
- 不依赖真实 MiniQMT；真实 MiniQMT 只作为手动 readonly smoke。

### Phase 4: storage profile + export download metadata

开发内容：

- 配置 storage profiles。
- request 支持 `storage_profile` id。
- 禁止 request 传入任意 server 端绝对路径。
- export/snapshot manifest 增加 download metadata：content length、hash、etag、format。
- 为大文件下载准备 range/断点续传契约。

验收标准：

- unknown storage profile 返回稳定错误。
- profile root 之外的路径不会被写入或删除。
- manifest 不暴露敏感本机路径；必要路径只用于 server 内部。
- qmtclient 可根据 manifest 校验下载文件。

测试建议：

- 用临时目录配置 fake profile。
- 测试路径 traversal：`..`、绝对路径、UNC path。
- 测试 manifest 中 hash/content length 与文件一致。

### Phase 5: maintenance/compaction

开发内容：

- 小文件 compaction plan/execute。
- rebuild-index execute。
- orphan files cleanup。
- coverage consistency check。
- data lake health summary。

验收标准：

- 默认维护命令 dry-run。
- 删除或重写必须显式 `--execute` / `--delete`。
- compaction 后 DuckDB metadata 与 Parquet 文件一致。
- orphan/missing/mismatch 能给出可读摘要。

测试建议：

- 用临时目录创建 fake Parquet 文件和 manifest。
- 用 fake metadata reader 避免依赖真实 PyArrow。
- 用 temporary DuckDB 验证 rebuild 后 `data_files` 和 `data_coverage`。
- 手动 readonly smoke 只访问 `/v1/market/data/*` 和 maintenance 命令，不连接 trader。

## 测试策略

默认测试不能依赖真实 MiniQMT：

- API 层使用 FastAPI `TestClient`。
- `xtdata` 通过 fake qmt service / fake adapter 注入。
- job runner 使用 fake downloader、fake bar reader、fake writer。
- DuckDB 使用临时目录和测试数据库。
- 文件系统测试使用 temporary directory。
- 大文件下载测试用小文件模拟 content-length、hash、etag、range。

真实 MiniQMT 只作为手动 readonly smoke：

- 启动并登录 MiniQMT。
- 不连接 trader，或明确 `connect_trader=False`。
- 不调用 `/v1/trader/*`。
- 不执行下单、撤单、转账或其他交易命令。
- 可运行小范围 symbol/date smoke 验证 `download -> coverage -> bars -> quality -> export`。

## 文档落点

- 本 RFC：`docs/rfc-market-data-lake-large-downloads.md`。
- 用户操作：`docs/operations.md`。
- 稳定 API 契约：`docs/api.md`。
- 长期路线：`docs/roadmap.md`。
- 发布门禁：`docs/release-plan.md`。
- 真实 MiniQMT smoke 记录：`docs/compatibility.md`。

## Open Questions

- 是否需要显式 `POST /v1/market/data/jobs/{job_id}/resume` 和
  `POST /v1/market/data/jobs/{job_id}/retry-failed`，还是先依赖再次提交 ensure request？
- `storage_profile` 是否只支持一个 active data lake，还是允许同一 server 同时维护多个 profile？
- 大 export 优先支持单个 Parquet、目录 manifest，还是 zip bundle？
- 是否需要为全市场任务引入最大并发、速率限制和 MiniQMT 下载冷却时间？
- job/chunk 历史保留多久，是否需要自动归档或清理？
