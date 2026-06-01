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

当前已经初始化配置、可选依赖检测、DuckDB schema 和持久化 data download job。Parquet 写入、
覆盖范围规划和本地查询 API 会在后续阶段逐步接入。

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
QMT_SNAPSHOT_DIR=data/snapshots
```

`QMT_DATA_DIR` 用于后续标准化行情文件和元数据库。`QMT_SNAPSHOT_DIR` 继续用于一次性
snapshot/export 文件。

## API

提交持久化 data download job：

```text
POST /v1/market/data/download
```

查询 job 状态：

```text
GET /v1/market/data/jobs/{job_id}
```

该 worker 当前只触发 `xtdata.download_history_data` 补齐 MiniQMT 行情缓存，并把 job 状态写入
DuckDB。标准化 Parquet 文件写入会在后续阶段接入。

## 后续阶段

1. Parquet Writer
   从稳定 market adapter 读取 daily/intraday bars，写入分区 Parquet 文件。

2. Coverage Planner
   查询本地已有覆盖范围，只下载缺失区间，并支持 `force=true` 强制重建。

3. Local Query API
   从本地 Parquet/DuckDB 查询 bars，返回稳定 JSON schema；大结果建议走 export。

4. Export From Data Lake
   从本地数据湖生成 CSV 或 Parquet export，逐步复用现有 snapshot manifest 设计。

5. Quality And Maintenance
   增加缺失交易日、重复行、OHLC 异常、成交量异常检查，以及清理和压缩策略。
