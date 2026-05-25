# qmtserver

qmtserver 是一个面向 MiniQMT / xtquant 的本地 Windows 网关服务。它把只能在
Windows 本机运行的 MiniQMT 能力封装为 HTTP、WebSocket 和 Python SDK，方便其他平台、
策略系统或自动化工具通过网络访问。

## 重要说明

- qmtserver 是非官方开源项目，不隶属于迅投、QMT、MiniQMT 或任何券商。
- 服务端运行环境限定为 Windows + Python 3.13。
- 交易相关接口默认关闭，并且默认 dry-run。
- 本项目不提供投资建议；真实交易风险由使用者自行承担。

## 特性

- CLI 连接检查：验证行情连接、交易连接、账号订阅和资金查询。
- 本地 HTTP RPC 网关：提供 `/v1/rpc` 和白名单方法转发。
- 交易保护：token 鉴权、交易开关、dry-run、账号/代码/限额校验和审计日志。
- WebSocket 事件：推送连接状态、委托回报、成交回报和错误事件。
- Python 客户端 SDK：其他 Python 项目可以不直接依赖 `xtquant`。

## 快速开始

安装项目依赖和 PyPI 版 `xtquant`：

```powershell
uv sync --extra xtquant
```

如果 PyPI 版落后，也可以从迅投知识库下载新版后覆盖安装：

- [xtquant 版本下载](https://dict.thinktrader.net/nativeApi/download_xtquant.html)

先启动并登录 MiniQMT，再检查连接：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
```

启动本地网关：

```powershell
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
```

默认监听：

```text
http://127.0.0.1:8000
```

常用入口：

```text
GET  /v1/health
GET  /v1/qmt/status
GET  /v1/rpc/methods
POST /v1/rpc
WS   /v1/ws/events
```

## Python 客户端

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.health())
print(client.status())
print(client.xtdata.get_full_tick(["000001.SZ"]))
```

## 文档

- [Installation](docs/installation.md)
- [API Reference](docs/api.md)
- [Python SDK](docs/sdk.md)
- [Operations](docs/operations.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development Roadmap](docs/roadmap.md)
- [Documentation Index](docs/README.md)

## 开发

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
```

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
