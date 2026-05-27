# qmtserver

[![PyPI](https://img.shields.io/pypi/v/qmtserver?style=flat-square)](https://pypi.org/project/qmtserver/)
[![Python](https://img.shields.io/pypi/pyversions/qmtserver?style=flat-square)](https://pypi.org/project/qmtserver/)
[![License](https://img.shields.io/pypi/l/qmtserver?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/gly11/qmtserver/ci.yml?branch=main&style=flat-square&label=ci)](https://github.com/gly11/qmtserver/actions/workflows/ci.yml)
[![Ask Zread](https://img.shields.io/badge/Ask_Zread-_.svg?style=flat-square&color=00b0aa&labelColor=000000&logo=data%3Aimage%2Fsvg%2Bxml%3Bbase64%2CPHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTQuOTYxNTYgMS42MDAxSDIuMjQxNTZDMS44ODgxIDEuNjAwMSAxLjYwMTU2IDEuODg2NjQgMS42MDE1NiAyLjI0MDFWNC45NjAxQzEuNjAxNTYgNS4zMTM1NiAxLjg4ODEgNS42MDAxIDIuMjQxNTYgNS42MDAxSDQuOTYxNTZDNS4zMTUwMiA1LjYwMDEgNS42MDE1NiA1LjMxMzU2IDUuNjAxNTYgNC45NjAxVjIuMjQwMUM1LjYwMTU2IDEuODg2NjQgNS4zMTUwMiAxLjYwMDEgNC45NjE1NiAxLjYwMDFaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00Ljk2MTU2IDEwLjM5OTlIMi4yNDE1NkMxLjg4ODEgMTAuMzk5OSAxLjYwMTU2IDEwLjY4NjQgMS42MDE1NiAxMS4wMzk5VjEzLjc1OTlDMS42MDE1NiAxNC4xMTM0IDEuODg4MSAxNC4zOTk5IDIuMjQxNTYgMTQuMzk5OUg0Ljk2MTU2QzUuMzE1MDIgMTQuMzk5OSA1LjYwMTU2IDE0LjExMzQgNS42MDE1NiAxMy43NTk5VjExLjAzOTlDNS42MDE1NiAxMC42ODY0IDUuMzE1MDIgMTAuMzk5OSA0Ljk2MTU2IDEwLjM5OTlaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik0xMy43NTg0IDEuNjAwMUgxMS4wMzg0QzEwLjY4NSAxLjYwMDEgMTAuMzk4NCAxLjg4NjY0IDEwLjM5ODQgMi4yNDAxVjQuOTYwMUMxMC4zOTg0IDUuMzEzNTYgMTAuNjg1IDUuNjAwMSAxMS4wMzg0IDUuNjAwMUgxMy43NTg0QzE0LjExMTkgNS42MDAxIDE0LjM5ODQgNS4zMTM1NiAxNC4zOTg0IDQuOTYwMVYyLjI0MDFDMTQuMzk4NCAxLjg4NjY0IDE0LjExMTkgMS42MDAxIDEzLjc1ODQgMS42MDAxWiIgZmlsbD0iI2ZmZiIvPgo8cGF0aCBkPSJNNCAxMkwxMiA0TDQgMTJaIiBmaWxsPSIjZmZmIi8%2BCjxwYXRoIGQ9Ik00IDEyTDEyIDQiIHN0cm9rZT0iI2ZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIvPgo8L3N2Zz4K&logoColor=ffffff)](https://zread.ai/gly11/qmtserver)

qmtserver 是一个面向 MiniQMT / xtquant 的本地 Windows 网关服务。它把 MiniQMT 能力封装为
HTTP RPC 和 WebSocket，方便其他机器通过网络访问。

## 重要说明

- qmtserver 是非官方开源项目，不隶属于迅投、QMT、MiniQMT 或任何券商。
- 服务端运行环境限定为 Windows + Python 3.12/3.13。
- 交易相关接口默认关闭，并且默认 dry-run。
- 本项目不提供投资建议；真实交易风险由使用者自行承担。

## 特性

- CLI 连接检查：验证行情连接、交易连接、账号订阅和资金查询。
- 本地 HTTP RPC 网关：提供 `/v1/rpc` 和白名单方法转发。
- 稳定行情 API：提供 capabilities、daily bars、intraday bars 和标准 metadata。
- 稳定只读交易查询：提供 account status、asset、positions、orders 和 trades。
- Snapshot 与历史任务：支持 CSV snapshot、manifest、下载任务和运行诊断。
- 数据准备接口：提供交易日历、标的列表、instrument detail 和数据质量报告。
- 透明 RPC 实验模式：显式开启后可受控探索白名单外的公开 `xtquant` 方法。
- 交易保护：token 鉴权、交易开关、dry-run、账号/代码/限额校验和审计日志。
- WebSocket 事件：推送连接状态、委托回报、成交回报和错误事件。
- 内置 Python 兼容客户端：用于验证 `/v1` API；独立客户端请使用 qmtclient。

当前版本节奏见 [Release Plan](docs/release-plan.md)。

## 快速开始

### PyPI 安装

普通使用不需要 clone 仓库，可以直接从 PyPI 安装 qmtserver 和 PyPI 版 `xtquant`：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install "qmtserver[xtquant]"
```

### 源码安装

需要本地开发或运行仓库内测试时，先 clone 项目并进入项目目录：

```powershell
git clone https://github.com/gly11/qmtserver.git
cd qmtserver
uv sync --extra xtquant
```

`uv sync --extra xtquant` 会安装项目依赖和 PyPI 版 `xtquant`。

如果 PyPI 版落后，也可以从迅投知识库下载新版后覆盖安装：

- [xtquant 版本下载](https://dict.thinktrader.net/nativeApi/download_xtquant.html)

先启动并登录 MiniQMT，再检查连接：

```powershell
$userdata = "D:\path\to\MiniQMT\userdata_mini"
$account = "资金账号"
uv run qmtserver check --userdata $userdata --account-id $account
```

启动本地网关：

```powershell
uv run qmtserver serve --userdata $userdata --account-id $account
```

默认监听：

```text
http://127.0.0.1:8000
```

常用入口：

```text
GET  /v1/health
GET  /v1/qmt/status
GET  /v1/trader/account-status
GET  /v1/trader/asset
GET  /v1/trader/positions
GET  /v1/trader/orders
GET  /v1/trader/trades
GET  /v1/market/capabilities
GET  /v1/market/bars/daily
GET  /v1/market/bars/intraday
POST /v1/snapshots
POST /v1/jobs/history-download
GET  /v1/diagnostics
GET  /v1/reference/calendar
GET  /v1/market/bars/daily/quality
GET  /v1/snapshots/{snapshot_id}/quality
GET  /v1/rpc/methods
POST /v1/rpc
WS   /v1/ws/events
```

## 内置兼容客户端

```python
from qmtserver.client import QmtClient

client = QmtClient("http://127.0.0.1:8000", token="dev-token")
print(client.health())
print(client.status())
print(client.xtdata.get_full_tick(["000001.SZ"]))
print(client.trader_asset(account_id="资金账号"))
```

新的策略项目建议使用独立包 qmtclient；本仓库内置客户端主要用于服务端兼容性验证。

## 文档

- [Installation](docs/installation.md)
- [API Reference](docs/api.md)
- [Built-in Client](docs/sdk.md)
- [Operations](docs/operations.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Development Roadmap](docs/roadmap.md)
- [Release Plan](docs/release-plan.md)
- [Transparent RPC](docs/transparent-rpc.md)
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
