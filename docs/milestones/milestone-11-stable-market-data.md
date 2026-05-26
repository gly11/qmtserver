# Milestone 11: Stable Market Data API

Milestone 11 的目标是新增 whitelist-only 的稳定行情 API，让策略、回测系统和 qmtclient 不再消费
`xtdata` 原始返回形态。

状态：已完成本地实现；真实 Windows + MiniQMT smoke test 尚未在本机执行。

## 目标

完成后应支持：

- `/v1/market/bars/daily` 返回标准 daily bars。
- `/v1/market/bars/intraday` 返回标准 intraday bars。
- `/v1/market/capabilities` 返回 schema versions、supported endpoints、periods 和 adjust modes。
- 行情响应包含 request params、row_count、generated_at、qmtserver version 和 xtquant version。
- 空数据、未连接、无权限、方法不允许、数据源异常和参数非法有稳定语义。
- 本地无 `xtquant` 环境可通过 fake adapter / fixture 完成单元测试。

## 非目标

Milestone 11 暂不做：

- CSV、Parquet 或 Arrow 批量导出。
- 历史下载任务队列。
- snapshot registry。
- 交易日历、股票池、数据质量报告。
- qmtclient 的 DataFrame facade。

## 目录规划

计划新增：

```text
src/qmtserver/market/
├── __init__.py
├── adapter.py
├── errors.py
├── models.py
├── normalizers.py
└── service.py

src/qmtserver/api/routes_market.py
tests/test_api_market.py
tests/test_market_normalizers.py
```

计划修改：

```text
src/qmtserver/api/app.py
src/qmtserver/errors.py
docs/api.md
docs/errors.md
```

## API 草案

```text
GET /v1/market/capabilities
GET /v1/market/bars/daily?symbols=000001.SZ,600000.SH&start=2026-01-01&end=2026-01-31&adjust=none
GET /v1/market/bars/intraday?symbols=000001.SZ&period=1m&start=2026-01-01T09:30:00+08:00&end=2026-01-01T15:00:00+08:00&adjust=none
```

daily bars 响应字段：

```json
{
  "ok": true,
  "data": {
    "bars": [
      {
        "date": "2026-01-02",
        "symbol": "000001.SZ",
        "open": 10.1,
        "high": 10.5,
        "low": 10.0,
        "close": 10.3,
        "volume": 1200000,
        "amount": 12345678.9,
        "meta": {}
      }
    ]
  },
  "error": null,
  "meta": {
    "schema": "market.bars.v1",
    "request": {},
    "row_count": 1,
    "generated_at": "2026-05-26T00:00:00+00:00",
    "qmtserver_version": "0.2.0",
    "xtquant_version": null
  }
}
```

## 任务拆分

1. 新增 market models，定义 bars、request、metadata 和 response shape。
2. 新增 normalizers，用 fixture 覆盖 dict / list / table-like 返回到标准 bars 的转换。
3. 新增 adapter，将 qmtserver 内部方法名映射到允许的 `xtdata` 方法。
4. 新增 market service，负责参数校验、调用 adapter、组装 metadata。
5. 新增 FastAPI routes，并在 `create_app()` 中注册 root 和 `/v1` prefix。
6. 新增 capability endpoint。
7. 扩展错误码和错误文档。
8. 更新 API 文档。
9. 在 Windows + MiniQMT 环境执行 smoke test。

## 测试计划

单元测试：

- normalizer 能转换 daily fixture。
- normalizer 能转换 intraday fixture。
- 空返回转换为 `ok=true`、`bars=[]`、`row_count=0`。
- 参数非法返回稳定 error code。
- target 未连接返回 `TARGET_NOT_CONNECTED`。
- capability endpoint 返回 schema versions、periods 和 adjust modes。

接口测试：

- `GET /v1/market/bars/daily` 使用 fake service 返回标准 schema。
- `GET /v1/market/bars/intraday` 使用 fake service 返回标准 schema。
- `GET /v1/market/capabilities` 不依赖真实 MiniQMT。

提交前验证：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
git diff --check
```

## 验收标准

Milestone 11 完成时必须满足：

1. 策略和回测系统可通过 `/v1/market` 获取 stable daily/intraday bars。
2. 不需要开启 transparent RPC。
3. 返回字段和 metadata 对 qmtclient 稳定。
4. 无 `xtquant` 本地环境可以跑完主质量门禁。
5. Windows + MiniQMT 环境至少完成一个 daily 和一个 intraday smoke test。

当前本地验收：

- 已实现 `/v1/market/capabilities`、`/v1/market/bars/daily` 和
  `/v1/market/bars/intraday`。
- 已实现 `market.bars.v1` metadata、`INVALID_MARKET_REQUEST` 和 `MARKET_DATA_ERROR`。
- 已用 fake adapter / fixture 覆盖无 `xtquant` 环境。
- 本机没有 MiniQMT，未执行真实 Windows smoke test；需要在 Windows 网关机补充验证。

## 风险与应对

- `xtdata` 返回形态不稳定：用 fixture 固定多种输入形态，normalizer 只输出稳定 schema。
- JSON 大响应过慢：Milestone 11 限制同步查询规模，大批量留给 snapshot/export。
- API route 变厚：route 只做 request parsing 和 response assembly，逻辑放 market service。
