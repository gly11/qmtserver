# qmtserver

qmtserver 是一个面向 MiniQMT / xtquant 的本地 Python 项目。当前阶段提供连接验证入口，后续会扩展为服务端，作为其他平台和 MiniQMT 通信的中间桥梁。

## 特性

- 使用 uv 管理 Python 3.13 环境。
- 使用标准 `src/` 布局，避免本地路径污染导入结果。
- 提供 CLI 连接检查命令，可验证行情连接、交易连接、账号订阅和资金查询。
- 将 MiniQMT 连接逻辑集中在 `qmtserver.miniqmt`，方便后续封装 API 服务。
- 提供本地 HTTP RPC 网关，支持 token 鉴权、只读白名单、交易保护和审计日志。

## 项目结构

```text
qmtserver/
├── docs/                 # 设计文档和后续接口说明
├── examples/             # 后续示例脚本
├── src/qmtserver/        # Python 源码
├── tests/                # 自动化测试
├── .env.example          # 本地配置示例
├── pyproject.toml        # 项目元数据、CLI、构建配置
└── uv.lock               # uv 锁文件
```

## 环境

- Python 3.13
- uv
- MiniQMT 客户端已启动并登录
- 下载好的 `xtquant` 包已复制到当前 uv 虚拟环境的 `site-packages` 中

如果以后删除并重建 `.venv`，需要把下载好的 `xtquant` 包重新复制到：

```text
.venv\Lib\site-packages\xtquant
```

## 初始化

```powershell
uv sync
```

## 验证连接

先启动并登录 MiniQMT，再运行：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata"
```

也可以使用模块方式：

```powershell
uv run python -m qmtserver check --userdata "D:\path\to\MiniQMT\userdata"
```

如果要同时验证交易账号订阅和资金查询：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata" --account-id "你的资金账号"
```

常用参数：

- `--userdata`：MiniQMT 安装目录下的 `userdata` 目录，交易连接需要它。
- `--account-id`：资金账号；传入后会尝试 `subscribe` 和 `query_stock_asset`。
- `--account-type`：账号类型，默认 `STOCK`。
- `--quote-code`：用于验证行情接口的证券代码，默认 `000001.SZ`。
- `--skip-quote`：只验证交易连接。
- `--json`：输出完整 JSON，便于后续服务端或脚本消费。

连接成功时命令退出码为 `0`；失败时退出码为 `1`，终端会打印失败原因。

## 启动只读 RPC 网关

Milestone 1 提供本地 HTTP 只读 RPC 网关：

```powershell
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata" --account-id "你的资金账号"
```

默认监听：

```text
http://127.0.0.1:8000
```

常用接口：

```text
GET  /v1/health
GET  /v1/qmt/status
POST /v1/qmt/connect
POST /v1/qmt/reconnect
POST /v1/qmt/disconnect
GET  /v1/metrics
GET  /v1/rpc/methods
POST /v1/rpc
WS   /v1/ws/events
```

旧的无版本路径暂时保留；新代码建议使用 `/v1`。

RPC 请求示例：

```json
{
  "target": "xtdata",
  "method": "get_full_tick",
  "args": [["000001.SZ"]],
  "kwargs": {}
}
```

交易账号查询示例：

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

第一版只开放只读白名单方法。下单、撤单类方法默认不开放。

### 安全配置

默认只监听 `127.0.0.1`。如果设置了 `QMT_API_TOKEN`，除 `/health` 外的 `/qmt/*` 和 `/rpc*` 接口都需要：

```http
Authorization: Bearer <token>
```

相关环境变量：

```env
QMT_API_TOKEN=
QMT_REQUIRE_TOKEN=false
QMT_ENABLE_TRADING=false
QMT_TRADING_DRY_RUN=true
QMT_MAX_ORDER_VOLUME=100000
QMT_MAX_ORDER_AMOUNT=1000000
QMT_ALLOWED_ACCOUNTS=
QMT_AUDIT_LOG=true
QMT_AUDIT_LOG_ARGS=true
QMT_WS_HEARTBEAT_SECONDS=15
QMT_WS_CLIENT_QUEUE_SIZE=1000
QMT_LOG_LEVEL=INFO
QMT_LOG_DIR=logs
QMT_LOG_JSON=false
```

`QMT_ENABLE_TRADING=false` 是第一层保护，`QMT_TRADING_DRY_RUN=true` 是第二层保护。只有显式开启交易并关闭 dry-run 后，交易类 RPC 才会调用 xtquant。

WebSocket 事件流：

```text
ws://127.0.0.1:8000/ws/events
```

配置 token 后可使用 `Authorization: Bearer <token>`，也可以在本地调试时使用 `?token=<token>`。

## Python 客户端 SDK

其他 Python 项目可以不直接依赖 xtquant，通过 qmtserver 客户端访问本地服务：

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.health())
print(client.status())
print(client.rpc("xtdata", "get_full_tick", [["000001.SZ"]]))
print(client.xtdata.get_full_tick(["000001.SZ"]))
```

事件订阅：

```python
for event in client.events():
    print(event)
```

示例见 [client_rpc.py](examples/client_rpc.py) 和 [client_events.py](examples/client_events.py)。

## 运维

服务会为 HTTP 请求生成或透传 `X-Request-ID`，并提供 `/metrics` JSON 指标。日志默认写入 `logs/qmtserver.log`，支持文件轮转。

Windows 启动脚本：

```powershell
.\scripts\run-server.ps1 -Userdata "C:\国金证券QMT交易端\userdata_mini" -AccountId "资金账号"
.\scripts\check.ps1
```

更多说明见 [operations.md](docs/operations.md) 和 [troubleshooting.md](docs/troubleshooting.md)。

## 开发

开发路线：

- [Documentation Index](docs/README.md)
- [API Reference](docs/api.md)
- [Error Codes](docs/errors.md)
- [Python SDK](docs/sdk.md)
- [Development Roadmap](docs/roadmap.md)
- [Milestone 1: Readonly RPC Gateway](docs/milestone-1-readonly-rpc.md)
- [Milestone 2: Connection Lifecycle Management](docs/milestone-2-connection-lifecycle.md)
- [Milestone 3: Security Boundary and Trading Guard](docs/milestone-3-security-trading-guard.md)
- [Milestone 4: Trading RPC](docs/milestone-4-trading-rpc.md)
- [Milestone 5: WebSocket Events](docs/milestone-5-websocket-events.md)
- [Milestone 6: Python Client SDK](docs/milestone-6-python-client-sdk.md)
- [Milestone 7: Observability and Operations](docs/milestone-7-observability-ops.md)
- [Operations](docs/operations.md)
- [Troubleshooting](docs/troubleshooting.md)

运行测试：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

检查导入路径：

```powershell
uv run python -c "import qmtserver, xtquant; print(qmtserver.__file__); print(xtquant.__file__)"
```

## 许可证

尚未选择许可证。准备开源发布前，请先补充 `LICENSE` 文件。
