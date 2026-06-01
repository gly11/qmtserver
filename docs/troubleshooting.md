# Troubleshooting

## xtquant import 失败

确认 `xtquant` 位于当前虚拟环境：

```powershell
uv run python -c "import xtquant; print(xtquant.__file__)"
```

如果 `.venv` 被重建，需要重新把下载好的 `xtquant` 复制到 `.venv\Lib\site-packages\xtquant`。

也可以安装 PyPI 版本：

```powershell
uv sync --extra xtquant
```

## MiniQMT 未连接

先启动并登录 MiniQMT，再运行：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
```

## userdata 路径错误

确认传入的是 MiniQMT / QMT 交易端目录下的 `userdata_mini` 完整路径，不是安装根目录。

## 端口被占用

换端口启动：

```powershell
uv run qmtserver serve --port 8001
```

## token 鉴权失败

确认请求带有：

```http
Authorization: Bearer <QMT_API_TOKEN>
```

WebSocket 本地调试也可以使用：

```text
ws://127.0.0.1:8000/v1/ws/events?token=<QMT_API_TOKEN>
```

## trader 未连接

检查 `/qmt/status` 的 `trader.connected`、`account_subscribed` 和 `last_error` 字段。常见原因是 MiniQMT 未登录、账号不匹配、`userdata_mini` 路径错误或交易端口未就绪。

优先运行 trader 只读诊断：

```powershell
$userdata = "D:\path\to\MiniQMT\userdata_mini"
$account = "资金账号"
uv run qmtserver diagnose trader --userdata $userdata --account-id $account
```

诊断会按步骤输出：

- `xtquant_import`：当前 Python 环境是否能导入 `xtquant`。
- `userdata_path`：传入的 `userdata_mini` 是否存在。
- `trader_classes`：`XtQuantTrader` 和 `StockAccount` 是否能加载。
- `trader_start`：trader 对象是否能启动。
- `trader_connect`：`connect()` 返回码。
- `query_account_status`：是否能读取账号状态。
- `account_subscribe` 和 `query_stock_asset`：配置账号后的只读账号检查。

`connect_result=-1` 通常表示 MiniQMT 未启动、未登录、userdata 与当前运行实例不匹配、trader
session 状态异常或 timeout 太短。可以依次确认：

- MiniQMT 已启动并完成登录。
- `--userdata` 指向正在运行的 MiniQMT 目录下的 `userdata_mini`。
- `--account-id` 和 `--account-type` 与 MiniQMT 内账号一致。
- 尝试传入新的 `--session-id` 或增大 `--timeout-ms`。
- 确认本地 `xtquant` 版本与 MiniQMT 版本兼容。

该诊断只做连接和只读查询，不执行下单、撤单或转账。

## WebSocket 收不到事件

先确认 `/v1/ws/events` 能收到 heartbeat；交易回报事件需要 trader 成功连接并触发对应 xtquant 回调。

## history job 没有结果

先检查 job 状态：

```text
GET /v1/jobs/{job_id}
```

如果状态仍是 `queued` 或 `running`，结果接口会返回 `JOB_NOT_READY`。如果状态是 `failed`，
查看 job 的 `error.code` 和 `error.message`，再结合 `/v1/diagnostics` 判断 MiniQMT 和行情源是否可用。
