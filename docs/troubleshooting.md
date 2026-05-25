# Troubleshooting

## xtquant import 失败

确认 `xtquant` 位于当前虚拟环境：

```powershell
uv run python -c "import xtquant; print(xtquant.__file__)"
```

如果 `.venv` 被重建，需要重新把下载好的 `xtquant` 复制到 `.venv\Lib\site-packages\xtquant`。

## MiniQMT 未连接

先启动并登录 MiniQMT，再运行：

```powershell
uv run qmtserver check --userdata "C:\国金证券QMT交易端\userdata_mini" --account-id "资金账号"
```

## userdata 路径错误

确认传入的是 MiniQMT 的 `userdata_mini` 或 `userdata` 目录，不是安装根目录。

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
ws://127.0.0.1:8000/ws/events?token=<QMT_API_TOKEN>
```

## trader 未连接

检查 `/qmt/status` 的 `trader.connected`、`account_subscribed` 和 `last_error` 字段。常见原因是 MiniQMT 未登录、账号不匹配、`userdata` 路径错误或交易端口未就绪。

## WebSocket 收不到事件

先确认 `/ws/events` 能收到 heartbeat；交易回报事件需要 trader 成功连接并触发对应 xtquant 回调。
