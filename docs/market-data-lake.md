# Market Data Lake

本文档记录 qmtserver 行情下载与高性能本地缓存的长期设计。该能力面向
MiniQMT / `xtquant` 行情数据，不连接 trader，也不执行下单、撤单或转账命令。

## 目标

qmtserver 的下载能力应由 server 端负责执行。client 端只负责提交下载请求、查询任务状态、
下载导出结果和展示摘要。这样其他平台不需要直接安装 `xtquant` 或访问 MiniQMT
`userdata_mini`。

高性能数据层的目标是：

- 通过 `xtdata.download_history_data` 补齐 MiniQMT 本地行情缓存。
- 通过稳定 adapter 读取并标准化 bars。
- 将标准化行情写入 qmtserver 自己的数据目录。
- 用 DuckDB 记录 job、文件、覆盖范围和质量信息。
- 后续从本地 Parquet/DuckDB 查询和导出，减少重复访问 MiniQMT。

## 目录分层

MiniQMT 的原始缓存通常位于：

```text
...\userdata_mini\datadir
```

这是 `xtquant` 管理的上游缓存，qmtserver 不直接修改该目录。

qmtserver 自己的数据目录默认为：

```text
data/market/
  raw/          # 后续保存标准化 Parquet 行情文件
  db/           # DuckDB 元数据库

data/snapshots/ # 现有 snapshot/export 文件
```

当前已经初始化配置、可选依赖检测、DuckDB schema、持久化 data download job、按 symbol
分区的 Parquet 写入、coverage planner、本地 bars 查询 API、CSV export、质量检查和 export
清理入口，以及本地 storage maintenance 检查、清理和 metadata rebuild 命令。
本地 bars 查询会通过 DuckDB 直接聚合多个 Parquet 文件，并在 SQL 层完成过滤、排序、去重、
计数和分页；响应包含 query profile 和分页/export 建议。
Bulk download entry points can now resolve `universe="all_a"` with an optional exchange filter before
submitting a data job. The canonical request records resolved symbols, symbol count, and a universe
hash so large jobs remain traceable.
Download jobs also plan persistent symbol/date chunks using `chunk_days` and store them in
`data_job_chunks`. The worker executes these chunks one by one, records chunk attempts, row/file
counts, and failure errors, and exposes job-level progress from the persisted chunk table.
`mode="ensure"` and `incremental=true` use coverage gaps to plan only missing chunks, so repeated
large jobs can fill gaps without rewriting the full requested date range.

## 安装

数据湖能力使用可选依赖，不进入默认安装：

```powershell
python -m pip install "qmtserver[data]"
```

源码开发时：

```powershell
uv sync --extra xtquant --extra data
```

如果未安装 `qmtserver[data]`，数据湖后端会返回稳定错误码：

```text
DATA_BACKEND_UNAVAILABLE
```

## 配置

```env
QMT_DATA_DIR=data/market
QMT_DATA_FORMAT=parquet
QMT_DATA_DB=data/market/db/qmtserver.duckdb
QMT_DATA_ENABLE_DUCKDB=true
QMT_DATA_STORAGE_PROFILES=qmt_main=data/qmt_main,archive=D:\qmt_archive
QMT_SNAPSHOT_DIR=data/snapshots
```

`QMT_DATA_DIR` 用于后续标准化行情文件和元数据库。`QMT_SNAPSHOT_DIR` 继续用于一次性
snapshot/export 文件。`QMT_DATA_STORAGE_PROFILES` 可配置额外白名单数据湖目录；client 只传
`storage_profile` id，不传 server 端绝对路径。

## API

提交持久化 data download job：

```text
POST /v1/market/data/download
```

查询 job 状态：

```text
GET /v1/market/data/jobs/{job_id}
```

查询本地覆盖范围：

```text
GET /v1/market/data/coverage
```

查询本地 bars：

```text
GET /v1/market/data/bars
GET /v1/market/data/quality
```

创建和下载 CSV export：

```text
POST /v1/market/data/exports
GET /v1/market/data/exports
GET /v1/market/data/exports/{export_id}
GET /v1/market/data/exports/{export_id}/download
DELETE /v1/market/data/exports/{export_id}
```

该 worker 当前会先检查 DuckDB 中的 coverage。命中完整覆盖且未设置 `force=true` 时，job
直接返回 cached result；未命中时触发 `xtdata.download_history_data` 补齐 MiniQMT 行情缓存，
然后读取标准 bars，按 symbol 写入 Parquet，并把 job 状态、data file 元数据和 coverage 写入
DuckDB。coverage 会同时返回合并摘要、file-level segments 和缺口列表；缓存命中判断使用
segments，避免把中间缺口误判为完整覆盖。`/v1/market/data/bars`、quality 和 export API 只读取
本地 Parquet/DuckDB，不触发新的 MiniQMT 下载。删除 export 只清理本地 CSV 和 manifest，不删除
MiniQMT 缓存或 Parquet 原始数据。

## 后续阶段

1. Storage Maintenance
   已提供 `qmtserver data check`、`qmtserver data cleanup` 和 `qmtserver data rebuild-index`
   的本地维护入口。`data check` 会输出健康摘要、metadata mismatch 和 coverage consistency
   issues；`data cleanup`
   支持显式删除和 export 过期清理；`data rebuild-index --execute` 可从本地 Parquet
   重建 DuckDB 文件索引和 coverage metadata。`data compact` 可按 kind/symbol/period/adjust
   规划小文件合并，`data compact --execute` 会写入 compact Parquet、删除源文件，并联动
   rebuild-index 重建 metadata。
2. Bulk Download Orchestration
   已完成 universe resolution、canonical request metadata、chunk planner 和 persisted chunk
   table、chunk-level execution、progress/failure summary，以及基于 coverage gaps 的 ensure
   模式。下一步需要新增显式 resume/retry 入口和更细的 storage profile 白名单。

详细稳定化计划见 [Market Data Lake Stabilization Plan](market-data-lake-stabilization.md)。
