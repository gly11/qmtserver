# qmtserver

qmtserver 是一个面向 MiniQMT / xtquant 的本地 Python 项目。当前阶段提供连接验证入口，后续会扩展为服务端，作为其他平台和 MiniQMT 通信的中间桥梁。

## 特性

- 使用 uv 管理 Python 3.13 环境。
- 使用标准 `src/` 布局，避免本地路径污染导入结果。
- 提供 CLI 连接检查命令，可验证行情连接、交易连接、账号订阅和资金查询。
- 将 MiniQMT 连接逻辑集中在 `qmtserver.miniqmt`，方便后续封装 API 服务。

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
GET  /health
GET  /qmt/status
POST /qmt/connect
GET  /rpc/methods
POST /rpc
```

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

## 开发

开发路线：

- [Documentation Index](docs/README.md)
- [Development Roadmap](docs/roadmap.md)
- [Milestone 1: Readonly RPC Gateway](docs/milestone-1-readonly-rpc.md)

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
