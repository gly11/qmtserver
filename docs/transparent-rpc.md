# Transparent RPC

透明 RPC 是 `0.2.0` 引入的高级模式。它的目标是让 qmtserver 在显式开启后，
可以转发白名单外的公开 `xtquant` 方法，方便在没有 MiniQMT 的电脑上探索新 API、
开发策略和做兼容性验证。

默认配置仍然是安全白名单 RPC；透明 RPC 必须显式开启。

## 版本目标

`0.2.0` 只做一件事：增加默认关闭、可审计、受限 target 的透明 RPC 实验模式。

完成后应满足：

- 默认配置下行为与 `0.1.x` 一致，白名单外方法继续返回 `METHOD_NOT_ALLOWED`。
- 显式开启后，可以透明调用允许 target 上的公开方法。
- 透明调用不会绕过 token、审计日志、JSON 序列化和现有交易保护。
- 文档清楚说明风险、适用场景和推荐网络边界。

## 使用场景

适合：

- 远程策略开发机临时尝试新的 `xtdata` 查询方法。
- 验证不同 `xtquant` 版本的返回结构。
- 在正式加入白名单前快速探索只读 API。
- 为后续稳定白名单方法收集真实调用样例。

不适合：

- 公网裸露服务。
- 让不可信用户任意探索 `xtquant`。
- 绕过 qmtserver 的交易保护。
- 作为长期稳定业务 API 替代白名单 RPC。

## 非目标

- 不做 Python 对象级透明代理；RPC 参数和返回值仍必须能 JSON 表达。
- 不做自动 API 文档生成或签名推断。
- 不默认开放 `trader` 的白名单外方法。
- 不允许透明模式绕过现有交易保护。
- 不改变现有 `/v1/rpc` 响应 envelope。
- 不在 `0.2.0` 引入 Arrow、gRPC、GUI、持久化或 qmtclient 拆包。

## 配置设计

配置：

```env
QMT_TRANSPARENT_RPC=false
QMT_TRANSPARENT_RPC_TARGETS=xtdata
QMT_TRANSPARENT_RPC_ALLOW_TRADER=false
QMT_TRANSPARENT_RPC_ALLOW_TRADING=false
```

含义：

- `QMT_TRANSPARENT_RPC`：总开关，默认关闭。
- `QMT_TRANSPARENT_RPC_TARGETS`：允许透明调用的 target 列表，逗号分隔，默认 `xtdata`。
- `QMT_TRANSPARENT_RPC_ALLOW_TRADER`：是否允许透明调用 `trader` 白名单外方法，默认关闭。
- `QMT_TRANSPARENT_RPC_ALLOW_TRADING`：保留配置，默认关闭。`0.2.0` 不开放真实透明交易；
  即使开启，也不能绕过 `QMT_ENABLE_TRADING` 和现有交易校验。

`Settings` 中新增：

```python
transparent_rpc: bool = False
transparent_rpc_targets: str = "xtdata"
transparent_rpc_allow_trader: bool = False
transparent_rpc_allow_trading: bool = False
```

并增加 helper：

```python
def transparent_rpc_allowed_targets(self) -> set[str]:
    ...
```

## 安全规则

透明 RPC 必须遵守以下规则：

1. 未开启 `QMT_TRANSPARENT_RPC` 时，白名单外方法一律拒绝。
2. `call.target` 必须在 `transparent_rpc_allowed_targets()` 中。
3. `trader` 只有在 `QMT_TRANSPARENT_RPC_ALLOW_TRADER=true` 时才允许进入透明路径。
4. 方法名不能以 `_` 开头，不能包含 `__` dunder 形式。
5. 方法名必须是合法标识符，避免路径、属性链或魔术访问。
6. handler 必须 callable。
7. 透明调用使用 `transparent` 级别审计和返回 `meta.level`。
8. 疑似交易方法默认拒绝。`QMT_TRANSPARENT_RPC_ALLOW_TRADING` 是保留开关，`0.2.0` 不提供绕过现有交易校验的透明交易能力。
9. token 鉴权、请求 ID、metrics、审计日志继续生效。
10. 返回值必须经过 `to_jsonable()`，不可返回任意 Python 对象。

疑似交易方法第一版可用保守规则识别：

```text
order
cancel
trade
buy
sell
position_adjust
```

如果方法命中上述关键词，并且没有显式允许透明交易，应返回稳定错误码。

## 错误码

新增或复用以下错误码：

```text
METHOD_NOT_ALLOWED              透明模式未开启
TRANSPARENT_TARGET_NOT_ALLOWED  target 不在允许列表
TRANSPARENT_METHOD_DENIED       私有/dunder/非法方法名
TRANSPARENT_TRADER_DENIED       trader 透明调用未开启
TRANSPARENT_TRADING_DENIED      疑似交易方法被透明模式拒绝
METHOD_NOT_FOUND                target 上不存在 callable method
```

为减少客户端破坏，可以保留外层响应结构不变：

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "TRANSPARENT_METHOD_DENIED",
    "message": "transparent RPC method is denied"
  },
  "meta": {
    "target": "xtdata",
    "method": "_private",
    "level": "transparent",
    "elapsed_ms": 1.2
  }
}
```

## 调用流程

白名单内方法继续走现有路径：

```text
命中 registry
  -> 分级校验
  -> 参数转换
  -> 调用 xtquant
  -> JSON 序列化
  -> 审计和 metrics
```

白名单外方法在透明模式下走新路径：

```text
未命中 registry
  -> 检查 QMT_TRANSPARENT_RPC
  -> 检查 target 是否允许
  -> 检查 trader 额外开关
  -> 检查方法名安全性
  -> 检查疑似交易方法
  -> get_target(target)
  -> getattr(target, method)
  -> 检查 callable
  -> convert_input(args/kwargs)
  -> 调用 handler
  -> to_jsonable(result)
  -> response meta level=transparent
  -> 审计和 metrics
```

## 实现结果

### Step 1: 配置和文档

已完成：

- 在 `Settings` 增加透明 RPC 配置。
- 在 `.env.example` 增加默认关闭配置。
- 更新 `docs/api.md`、`docs/release-plan.md` 和 `docs/transparent-rpc.md`。

验收：

- `load_settings()` 默认关闭透明 RPC。
- CSV target 解析覆盖空值、单值和多值。

### Step 2: 策略判断模块

已新增模块：

```text
src/qmtserver/rpc/transparent.py
```

职责：

- 判断 target 是否允许。
- 判断 method 名称是否安全。
- 判断是否疑似交易方法。
- 生成透明调用的 `RpcMethodSpec` 或轻量 spec。

核心 API：

```python
def transparent_method_decision(
    settings: Settings,
    target: str,
    method: str,
) -> TransparentMethodDecision:
    ...
```

验收：

- 默认关闭返回 `None`。
- 非允许 target 返回 `None` 或抛稳定错误。
- `_private`、`__dunder__`、`a.b`、空方法名被拒绝。

### Step 3: Dispatcher 集成

已改造 `RpcDispatcher.dispatch()` 中 `spec is None` 分支：

```text
spec = get_method_spec(...)
if spec is None:
    decision = transparent_method_decision(...)
    if spec is None:
        return METHOD_NOT_ALLOWED
```

透明 spec 的 `level` 已扩展为：

```python
RpcMethodLevel = Literal["readonly", "trading", "admin", "transparent"]
```

也可以将透明调用映射为 `readonly`，但 `meta.level=transparent` 更利于审计和排障。

验收：

- 白名单方法行为不变。
- 透明方法返回 `meta.level == "transparent"`。
- 审计日志能看到 target、method、level、ok、error 和 elapsed。

### Step 4: 交易保护

第一版不透明开放真实交易。

规则：

- `QMT_TRANSPARENT_RPC_ALLOW_TRADING=false` 时，疑似交易方法直接拒绝。
- `0.2.0` 不开放真实透明交易；该配置即使开启，也只能进入现有 `trading` 分支并接受
  `QMT_ENABLE_TRADING`、`prepare_trading_call()` 等保护。
- 不能通过透明 RPC 调用绕过 `QMT_ENABLE_TRADING=false`。

验收：

- `order_stock` 即使通过透明路径判断，也不能绕过交易开关。
- `cancel_order_stock`、`order_stock_async`、包含 `trade`/`buy`/`sell` 的未知方法被保守拒绝。

### Step 5: 可观测性

- audit 日志增加透明调用可识别字段，最少通过 `level=transparent` 表达。
- metrics 暂可复用现有 RPC 计数和耗时。
- 后续如有需要再增加 transparent-specific metrics。

验收：

- 成功透明调用有 audit 日志。
- 被拒绝透明调用也有 audit 日志和错误码。

### Step 6: 测试

新增或扩展测试：

```text
tests/test_rpc_transparent.py
tests/test_config.py
tests/test_api_rpc.py
tests/test_rpc_registry.py
```

测试矩阵：

- 默认关闭时未知方法返回 `METHOD_NOT_ALLOWED`。
- 开启后允许 `xtdata` 公开方法。
- target 不在 allowlist 时拒绝。
- `_private` 方法拒绝。
- `__dunder__` 方法拒绝。
- 非 callable 属性返回 `METHOD_NOT_FOUND` 或稳定错误。
- `trader` 默认拒绝。
- 开启 trader 但疑似交易方法仍拒绝。
- token 鉴权继续保护 `/v1/rpc`。
- 响应仍 JSON friendly。
- audit/metrics 不因透明 spec 为 `None` 崩溃。

## API 示例

开启：

```powershell
$env:QMT_TRANSPARENT_RPC="true"
$env:QMT_TRANSPARENT_RPC_TARGETS="xtdata"
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini"
```

调用白名单外的公开 `xtdata` 方法：

```json
{
  "target": "xtdata",
  "method": "get_sector_list",
  "args": [],
  "kwargs": {}
}
```

响应：

```json
{
  "ok": true,
  "data": [],
  "error": null,
  "meta": {
    "target": "xtdata",
    "method": "get_sector_list",
    "level": "transparent",
    "version": "v1",
    "elapsed_ms": 1.2
  }
}
```

## 发布门禁

`0.2.0` 发布前必须通过：

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv run python scripts/check_code_health.py --enforce
git diff --check
uv build
uv tool run twine check dist\qmtserver-0.2.0.tar.gz dist\qmtserver-0.2.0-py3-none-any.whl
```

建议人工验证：

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "资金账号"
uv run qmtserver serve --userdata "D:\path\to\MiniQMT\userdata_mini"
```

并从另一台机器或本机另一个终端验证：

- `/v1/health`
- 白名单 RPC
- 透明 RPC 成功路径
- 透明 RPC 拒绝路径

## 风险

透明 RPC 会扩大远程调用面，必须作为高级功能看待：

- 可能暴露未来 `xtquant` 新增的敏感方法。
- 可能调用未经过 qmtserver 测试覆盖的方法。
- 参数签名变化会在运行时才暴露为 RPC 错误。
- 返回结构变化可能不会报错，但会影响策略逻辑。
- 如果 token 泄露，攻击者可能远程访问 MiniQMT 网关。
- 如果开放 `trader`，误调用风险明显高于只读行情查询。

建议只在可信局域网、VPN、Tailscale、ZeroTier 或 SSH tunnel 内使用。
