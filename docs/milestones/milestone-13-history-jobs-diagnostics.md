# Milestone 13: History Jobs and Diagnostics

Milestone 13 的目标是把耗时的历史下载操作任务化，并提供更强的运行诊断能力。

状态：已完成本地实现；真实 Windows + MiniQMT 历史下载 smoke test 尚未在本机执行。

## 目标

完成后应支持：

- 创建历史下载 job。
- 查询 job 状态。
- 获取 job result，并关联 snapshot manifest。
- 取消尚未完成的 job。
- diagnostics endpoint 返回连接、版本、时钟和 sample symbol smoke 信息。
- metrics 增加 job 状态统计。

## 非目标

Milestone 13 暂不做：

- 多进程任务调度。
- 分布式队列。
- 长期任务数据库。
- 高并发下载调度。

## 目录规划

计划新增：

```text
src/qmtserver/jobs/
├── __init__.py
├── models.py
├── registry.py
├── runner.py
└── service.py

src/qmtserver/api/routes_jobs.py
src/qmtserver/api/routes_diagnostics.py
tests/test_jobs.py
tests/test_api_jobs.py
tests/test_api_diagnostics.py
```

计划修改：

```text
src/qmtserver/api/app.py
src/qmtserver/observability.py
docs/api.md
docs/operations.md
docs/troubleshooting.md
```

## API 草案

```text
POST /v1/jobs/history-download
GET  /v1/jobs/{job_id}
GET  /v1/jobs/{job_id}/result
POST /v1/jobs/{job_id}/cancel
GET  /v1/diagnostics
```

job 状态：

```text
queued
running
succeeded
failed
cancelled
```

## 任务拆分

1. 新增 job model，定义 status、timestamps、request、result 和 error。
2. 新增内存 job registry。
3. 新增 runner，使用后台线程或 asyncio task 执行单个 job。
4. 新增 history-download job service，调用 `xtdata.download_history_data` 或等价 adapter。
5. job succeeded 后创建或引用 snapshot manifest。
6. 新增 jobs API routes。
7. 新增 diagnostics service 和 route。
8. 扩展 metrics，记录 job status count。
9. 更新 operations 和 troubleshooting。

## 测试计划

单元测试：

- job 初始状态为 queued。
- runner 执行成功后状态为 succeeded。
- runner 捕获异常后状态为 failed，并记录 error code。
- cancel 可取消 queued job。
- diagnostics 在无真实 MiniQMT 时返回稳定结构。

接口测试：

- `POST /v1/jobs/history-download` 返回 job id。
- `GET /v1/jobs/{job_id}` 返回状态。
- `GET /v1/jobs/{job_id}/result` 在 succeeded 后返回 manifest 引用。
- `POST /v1/jobs/{job_id}/cancel` 对 queued job 生效。
- `GET /v1/diagnostics` 返回 qmt、clock、version 和 sample sections。

## 验收标准

Milestone 13 完成时必须满足：

1. 历史下载不会阻塞 health/status/market 请求。
2. job 失败有稳定 error code 和可追溯错误信息。
3. diagnostics 能判断 MiniQMT 连接、行情源和示例标的是否可用。
4. metrics 可观察 job 状态分布。

当前本地验收：

- 已实现 `POST /v1/jobs/history-download`、`GET /v1/jobs/{job_id}`、
  `GET /v1/jobs/{job_id}/result` 和 `POST /v1/jobs/{job_id}/cancel`。
- 已实现进程内存 job registry 和后台线程 runner。
- history-download job 成功后关联 snapshot manifest。
- 已实现 `/v1/diagnostics`，返回 qmt、clock、version 和 sample sections。
- `/v1/metrics` 已增加 job status 计数。
- 本机没有 MiniQMT，未执行真实 Windows 历史下载 smoke test；需要在 Windows 网关机补充验证。

## 风险与应对

- 任务取消不可靠：首版只保证 queued 可取消，running 取消作为 best effort。
- 后台线程资源泄露：限制并发数量，服务 shutdown 时清理 runner。
- 下载与 snapshot 耦合过深：job result 只引用 manifest，不直接暴露内部文件路径。
