# Milestone 12: Snapshot Export and Manifest

Milestone 12 的目标是支持回测批量数据准备。大批量历史数据不通过普通 JSON 同步返回，而是生成
可追溯 snapshot，并通过 manifest 描述数据完整性。

状态：已完成本地实现；真实 Windows + MiniQMT 大样本导出尚未在本机执行。

## 目标

完成后应支持：

- 创建 daily/intraday snapshot。
- 使用 manifest 描述 snapshot 参数、schema、格式、hash、覆盖区间和版本信息。
- 列出已有 snapshot。
- 按参数 hash 命中已有 snapshot。
- 下载 CSV 格式结果。

## 非目标

Milestone 12 暂不做：

- Parquet / Arrow 稳定支持。
- 多用户权限模型。
- 数据库化 snapshot registry。
- 长任务队列和取消机制。

## 目录规划

计划新增：

```text
src/qmtserver/snapshots/
├── __init__.py
├── manifest.py
├── registry.py
├── service.py
└── writers.py

src/qmtserver/api/routes_snapshots.py
tests/test_snapshots_manifest.py
tests/test_api_snapshots.py
```

计划修改：

```text
src/qmtserver/api/app.py
src/qmtserver/config.py
docs/api.md
docs/operations.md
```

## API 草案

```text
POST /v1/snapshots
GET  /v1/snapshots
GET  /v1/snapshots/{snapshot_id}/manifest
GET  /v1/snapshots/{snapshot_id}/download
```

创建请求示例：

```json
{
  "kind": "daily_bars",
  "symbols": ["000001.SZ"],
  "start": "2026-01-01",
  "end": "2026-01-31",
  "adjust": "none",
  "format": "csv"
}
```

manifest 必须包含：

```json
{
  "snapshot_id": "daily_bars-...",
  "schema": "market.bars.v1",
  "format": "csv",
  "request": {},
  "hash": "sha256:...",
  "row_count": 100,
  "symbol_count": 1,
  "coverage_start": "2026-01-01",
  "coverage_end": "2026-01-31",
  "generated_at": "2026-05-26T00:00:00+00:00",
  "qmtserver_version": "0.2.0",
  "xtquant_version": null
}
```

## 任务拆分

1. 新增 snapshot 配置项，例如 `QMT_SNAPSHOT_DIR`。
2. 新增 request canonicalization，生成稳定参数 hash。
3. 新增 manifest model 和 hash 计算。
4. 新增 CSV writer。
5. 新增 registry，支持 list / get / find_by_request_hash。
6. 新增 snapshot service，复用 Milestone 11 market service 获取数据。
7. 新增 API routes。
8. 更新 operations 文档，说明 snapshot 目录、清理和备份。

## 测试计划

单元测试：

- 相同参数生成相同 request hash。
- manifest hash 可复算。
- CSV writer 输出稳定列顺序。
- registry 能列出 snapshot 并按参数命中。

接口测试：

- `POST /v1/snapshots` 创建 CSV snapshot。
- `GET /v1/snapshots` 返回 registry 列表。
- `GET /v1/snapshots/{id}/manifest` 返回 manifest。
- `GET /v1/snapshots/{id}/download` 返回文件响应。

## 验收标准

Milestone 12 完成时必须满足：

1. 回测系统可通过 manifest 判断数据来源、覆盖区间和完整性。
2. 相同参数重复请求可以复用已有 snapshot。
3. 大数据下载不通过普通 JSON response 承载。
4. snapshot 文件不泄露账号、token 或个人路径。

当前本地验收：

- 已实现 `POST /v1/snapshots`、`GET /v1/snapshots`、
  `GET /v1/snapshots/{snapshot_id}/manifest` 和
  `GET /v1/snapshots/{snapshot_id}/download`。
- 已实现 request hash、CSV writer、manifest JSON 和 snapshot registry。
- 已实现同参数 snapshot 复用。
- 默认 snapshot 目录为 `data/snapshots/`，该目录已由仓库忽略规则覆盖。
- 本机没有 MiniQMT，未执行真实 Windows 大样本导出；需要在 Windows 网关机补充验证。

## 风险与应对

- snapshot 文件过大：只承诺本地文件输出，不做内存聚合下载。
- registry 损坏：manifest 采用独立 JSON 文件，registry 可从目录重建。
- 格式承诺过早：首版只稳定 CSV，Parquet / Arrow 作为后续增强。
