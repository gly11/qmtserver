# Transparent RPC

透明 RPC 是计划在 `0.2.0` 引入的高级模式。它的目标是让 qmtserver 在显式开启后，
可以转发白名单外的公开 `xtquant` 方法，方便在没有 MiniQMT 的电脑上探索新 API、
开发策略和做兼容性验证。

`0.1.0` 不包含透明 RPC。当前已发布能力仍然是安全白名单 RPC。

## 目标

- 减少 `xtquant` 新增只读 API 时的手动适配成本。
- 支持远程策略开发机直接尝试白名单外的 `xtdata` 查询方法。
- 保持默认安全边界：不开启时行为与 `0.1.0` 完全一致。
- 透明调用也进入审计日志，便于定位远程调用来源和失败原因。

## 非目标

- 不做 Python 对象级透明代理；RPC 参数和返回值仍必须能 JSON 表达。
- 不默认开放 `trader` 的白名单外方法。
- 不允许透明模式绕过现有交易保护。
- 不建议也不支持公网裸暴露 qmtserver。

## 计划配置

```env
QMT_TRANSPARENT_RPC=false
QMT_TRANSPARENT_RPC_TARGETS=xtdata
QMT_TRANSPARENT_RPC_ALLOW_TRADER=false
QMT_TRANSPARENT_RPC_ALLOW_TRADING=false
```

默认配置只表达计划语义；实际配置名以 `0.2.0` 实现为准。

- `QMT_TRANSPARENT_RPC`：总开关，默认关闭。
- `QMT_TRANSPARENT_RPC_TARGETS`：允许透明调用的 target，默认只考虑 `xtdata`。
- `QMT_TRANSPARENT_RPC_ALLOW_TRADER`：是否允许透明调用 `trader` 的白名单外方法。
- `QMT_TRANSPARENT_RPC_ALLOW_TRADING`：是否允许透明调用交易类方法，默认关闭。

## 调用规则

白名单内方法继续走现有路径：

```text
命中 registry -> 分级校验 -> 参数转换 -> 调用 xtquant -> JSON 序列化
```

白名单外方法在透明模式下走计划路径：

```text
未命中 registry
  -> 检查 transparent 总开关
  -> 检查 target 是否允许
  -> 拒绝 _private 和 __dunder__ 方法
  -> trader 需要额外开关
  -> 交易类方法不能绕过交易保护
  -> getattr(target, method)
  -> 参数转换
  -> 调用 xtquant
  -> JSON 序列化
```

如果透明模式未开启，白名单外方法继续返回 `METHOD_NOT_ALLOWED`。

## 风险

透明 RPC 会扩大远程调用面，必须作为高级功能看待：

- 可能暴露未来 `xtquant` 新增的敏感方法。
- 可能调用未经过 qmtserver 测试覆盖的方法。
- 参数签名变化会在运行时才暴露为 RPC 错误。
- 返回结构变化可能不会报错，但会影响策略逻辑。
- 如果 token 泄露，攻击者可能远程访问 MiniQMT 网关。
- 如果开放 `trader`，误调用风险明显高于只读行情查询。

建议只在可信局域网、VPN、Tailscale、ZeroTier 或 SSH tunnel 内使用。

## 验收标准

`0.2.0` 完成时至少满足：

1. 默认模式下白名单外方法仍被拒绝。
2. 开启透明 RPC 后，可以调用允许 target 的公开方法。
3. 私有方法和 dunder 方法被拒绝。
4. `trader` 默认不能透明开放。
5. 交易方法不能绕过现有交易保护。
6. 透明调用有审计日志或可观测字段。
7. token 鉴权对透明调用继续生效。
8. 文档明确标注风险和推荐网络边界。
