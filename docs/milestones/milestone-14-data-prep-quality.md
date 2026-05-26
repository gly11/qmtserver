# Milestone 14: Data Preparation and Quality

Milestone 14 的目标是完善回测前置数据准备，并提供基础数据质量报告。

状态：已完成本地实现；真实 Windows + MiniQMT reference/quality smoke test 尚未在本机执行。

## 目标

完成后应支持：

- 标准交易日历接口。
- 标准股票池 / 标的列表接口。
- 标准 instrument detail 接口。
- bars 或 snapshot 的基础数据质量报告。
- 缓存策略，避免重复下载和重复标准化。

## 非目标

Milestone 14 暂不做：

- 投资建议。
- 策略信号。
- 组合构建。
- 多数据源仲裁。

## 目录规划

计划新增：

```text
src/qmtserver/data_quality/
├── __init__.py
├── checks.py
├── models.py
└── service.py

src/qmtserver/api/routes_reference.py
tests/test_data_quality.py
tests/test_api_reference.py
```

计划修改：

```text
src/qmtserver/market/service.py
src/qmtserver/snapshots/manifest.py
src/qmtserver/api/app.py
docs/api.md
docs/operations.md
```

## API 草案

```text
GET /v1/reference/calendar?start=2026-01-01&end=2026-01-31
GET /v1/reference/universe?name=all_a
GET /v1/reference/instruments?symbols=000001.SZ,600000.SH
GET /v1/market/bars/daily/quality?symbols=000001.SZ&start=2026-01-01&end=2026-01-31
GET /v1/snapshots/{snapshot_id}/quality
```

数据质量报告至少包含：

```json
{
  "ok": true,
  "data": {
    "missing_dates": [],
    "duplicate_rows": [],
    "price_anomalies": [],
    "volume_anomalies": []
  },
  "error": null,
  "meta": {
    "schema": "market.quality.v1",
    "row_count": 0,
    "generated_at": "2026-05-26T00:00:00+00:00"
  }
}
```

## 任务拆分

1. 新增 reference endpoints，优先覆盖 calendar、universe、instrument detail。
2. 新增 quality models。
3. 新增缺失日期检查。
4. 新增重复行检查。
5. 新增价格异常检查。
6. 新增成交量异常检查。
7. 将 quality report 接入 bars 和 snapshot。
8. 明确缓存 key 和缓存失效策略。
9. 更新 API 和 operations 文档。

## 测试计划

单元测试：

- 缺失日期能被识别。
- 重复 symbol/date 或 symbol/timestamp 能被识别。
- 负价格、零价格或 high/low 关系异常能被识别。
- 负成交量或异常成交量能被识别。

接口测试：

- reference endpoints 返回稳定 schema。
- bars quality endpoint 返回质量报告。
- snapshot quality endpoint 从 manifest 关联数据生成报告。

## 验收标准

Milestone 14 完成时必须满足：

1. 回测前可以通过 qmtserver 获取交易日历、股票池和 instrument detail。
2. bars 查询或 snapshot 可生成基础质量报告。
3. 数据质量报告只描述数据问题，不做交易决策。
4. 缓存不会改变返回 schema 或错误语义。

当前本地验收：

- 已实现 `GET /v1/reference/calendar`、`GET /v1/reference/universe` 和
  `GET /v1/reference/instruments`。
- 已实现 `GET /v1/market/bars/daily/quality` 和 `GET /v1/snapshots/{snapshot_id}/quality`。
- 已实现缺失日期、重复行、价格异常和成交量异常的保守检查。
- 批量数据复用继续依赖 snapshot registry；新增缓存策略已在 operations 文档中约束 cache key。
- 本机没有 MiniQMT，未执行真实 Windows reference/quality smoke test；需要在 Windows 网关机
  补充验证。

## 风险与应对

- 交易日历来源不一致：metadata 记录数据来源和生成时间。
- 异常规则误报：首版只做保守检查，并把结果标为 warnings。
- 缓存污染：缓存 key 必须包含 endpoint、symbols、period、start、end、adjust 和 schema version。
