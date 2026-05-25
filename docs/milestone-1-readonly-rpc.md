# Milestone 1: Readonly RPC Gateway

Milestone 1 的目标是把 qmtserver 从“命令行连接检查工具”推进到“本地只读 HTTP RPC 网关”。

第一版不追求完整适配所有 `xtquant` API，也不开放真实交易。核心原则是：能转发、可控制、先只读、可观测。

## 目标

完成后应支持：

- 启动本地 HTTP 服务。
- 自动加载配置。
- 查询服务健康状态。
- 查询 MiniQMT 连接状态。
- 查看当前 RPC 白名单。
- 通过统一 `/rpc` 调用只读 xtquant 方法。
- 将 xtquant 返回值统一转换为 JSON。
- 拒绝非白名单方法。
- 默认拒绝下单、撤单等交易方法。

## 非目标

Milestone 1 暂不做：

- WebSocket 推送。
- 真实下单和撤单。
- 全量 xtquant API 透明代理。
- 多账号复杂管理。
- gRPC、Protobuf、Arrow。
- Windows 服务化部署。

## 依赖

建议新增运行依赖：

```text
fastapi
uvicorn[standard]
pydantic-settings
```

新增开发依赖可以后续再引入，目前继续使用标准库 `unittest`。

## 目录调整

计划新增：

```text
src/qmtserver/
├── api/
│   ├── __init__.py
│   ├── app.py
│   ├── routes_health.py
│   ├── routes_qmt.py
│   └── routes_rpc.py
├── rpc/
│   ├── __init__.py
│   ├── dispatcher.py
│   ├── registry.py
│   └── serializers.py
├── services/
│   ├── __init__.py
│   └── qmt_service.py
├── config.py
└── main.py
```

保留：

- `qmtserver.cli`：增加 `serve` 命令。
- `qmtserver.miniqmt`：继续作为 xtquant 底层适配与连接检查工具。

## 配置

`.env` 规划：

```env
QMT_USERDATA=C:\国金证券QMT交易端\userdata_mini
QMT_ACCOUNT_ID=
QMT_ACCOUNT_TYPE=STOCK
QMT_HOST=127.0.0.1
QMT_PORT=8000
QMT_QUOTE_CODE=000001.SZ
QMT_ENABLE_TRADING=false
QMT_API_TOKEN=
```

第一阶段 `QMT_API_TOKEN` 可以先预留，是否强制校验放到 Milestone 3。

## HTTP API

### GET /health

用途：检查 qmtserver 进程是否存活。

响应示例：

```json
{
  "ok": true,
  "service": "qmtserver",
  "version": "0.1.0"
}
```

### GET /qmt/status

用途：检查 MiniQMT 和 xtquant 状态。

响应示例：

```json
{
  "ok": true,
  "xtquant": {
    "ok": true,
    "path": "C:\\Workspace\\qmtserver\\.venv\\Lib\\site-packages\\xtquant"
  },
  "quote": {
    "connected": true
  },
  "trader": {
    "connected": true,
    "account_id": "..."
  },
  "last_error": null
}
```

### GET /rpc/methods

用途：返回当前允许调用的 RPC 方法。

响应示例：

```json
{
  "ok": true,
  "methods": {
    "xtdata": [
      "get_full_tick",
      "get_market_data",
      "get_market_data_ex",
      "get_instrument_detail",
      "get_stock_list_in_sector"
    ],
    "trader": [
      "query_account_infos",
      "query_account_status",
      "query_stock_asset",
      "query_stock_positions",
      "query_stock_orders",
      "query_stock_trades"
    ]
  }
}
```

### POST /rpc

用途：统一只读 RPC 转发。

请求示例：

```json
{
  "target": "xtdata",
  "method": "get_full_tick",
  "args": [["000001.SZ"]],
  "kwargs": {}
}
```

交易查询请求示例：

```json
{
  "target": "trader",
  "method": "query_stock_asset",
  "args": [
    {
      "__type__": "StockAccount",
      "account_id": "你的资金账号",
      "account_type": "STOCK"
    }
  ],
  "kwargs": {}
}
```

响应示例：

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "meta": {
    "target": "xtdata",
    "method": "get_full_tick",
    "elapsed_ms": 12
  }
}
```

错误响应示例：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "METHOD_NOT_ALLOWED",
    "message": "RPC method is not allowed: trader.order_stock"
  },
  "meta": {
    "target": "trader",
    "method": "order_stock",
    "elapsed_ms": 1
  }
}
```

## 第一阶段白名单

`xtdata`：

- `get_full_tick`
- `get_market_data`
- `get_market_data_ex`
- `get_instrument_detail`
- `get_stock_list_in_sector`

`trader`：

- `query_account_infos`
- `query_account_status`
- `query_stock_asset`
- `query_stock_positions`
- `query_stock_orders`
- `query_stock_trades`

交易类方法不进入第一阶段白名单。

## RPC 分发设计

`registry.py` 负责定义白名单：

```python
READONLY_METHODS = {
    "xtdata": {"get_full_tick", "get_market_data"},
    "trader": {"query_stock_asset"},
}
```

`dispatcher.py` 负责：

1. 校验 `target`。
2. 校验 `method` 是否在白名单。
3. 将 JSON 参数转换为 Python / xtquant 对象。
4. 调用实际方法。
5. 捕获异常并返回统一错误。
6. 记录耗时。

`serializers.py` 负责：

- `dict`、`list`、`tuple`、`set`。
- 基础类型。
- `Path`。
- xtquant 自定义对象。
- pandas DataFrame 和 Series，若 pandas 已安装。
- numpy 数组和标量，若 numpy 已安装。

## StockAccount 参数转换

第一阶段只需要支持一种特殊对象：

```json
{
  "__type__": "StockAccount",
  "account_id": "你的资金账号",
  "account_type": "STOCK"
}
```

服务端转换为：

```python
StockAccount(account_id, account_type)
```

其他复杂对象等实际需要时再补。

## CLI 规划

保留：

```powershell
uv run qmtserver check --userdata "..." --account-id "..."
```

新增：

```powershell
uv run qmtserver serve
uv run qmtserver serve --host 127.0.0.1 --port 8000
```

可选参数：

- `--userdata`
- `--account-id`
- `--account-type`
- `--host`
- `--port`
- `--reload`

## 测试计划

单元测试：

- 配置默认值。
- 白名单注册。
- 非白名单拒绝。
- `StockAccount` 参数转换。
- xtquant 对象 JSON 序列化。
- RPC 成功响应格式。
- RPC 错误响应格式。

集成测试：

- `GET /health`。
- `GET /rpc/methods`。
- mock `xtdata.get_full_tick` 后调用 `/rpc`。
- mock `trader.query_stock_asset` 后调用 `/rpc`。

真实环境手动测试：

```powershell
uv run qmtserver serve --userdata "C:\国金证券QMT交易端\userdata_mini" --account-id "你的资金账号"
```

然后调用：

```http
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/qmt/status
GET http://127.0.0.1:8000/rpc/methods
POST http://127.0.0.1:8000/rpc
```

## 验收标准

Milestone 1 完成时必须满足：

1. `uv run qmtserver check ...` 继续可用。
2. `uv run qmtserver serve` 可以启动服务。
3. `GET /health` 返回 `ok=true`。
4. `GET /qmt/status` 能展示 MiniQMT 状态。
5. `GET /rpc/methods` 能展示白名单。
6. `POST /rpc` 可以调用 `xtdata.get_full_tick`。
7. `POST /rpc` 可以调用 `trader.query_stock_asset`。
8. 非白名单方法被拒绝。
9. 下单类方法默认不可调用。
10. 所有响应都可以被 JSON 编码。
11. 自动化测试通过。

## 风险与应对

- xtquant 返回对象复杂：先实现通用对象序列化，遇到 DataFrame / numpy 再做可选支持。
- MiniQMT 未启动：状态接口返回清晰错误，不让服务进程崩溃。
- 交易方法误开放：白名单默认只读，交易方法必须在后续阶段单独加入。
- 长耗时调用阻塞：第一阶段先接受同步调用，后续再引入线程池或异步任务队列。

## 交付物

- FastAPI 服务入口。
- `serve` CLI 命令。
- RPC registry / dispatcher / serializer。
- 只读方法白名单。
- 配置加载。
- 单元测试和接口测试。
- README 更新。
