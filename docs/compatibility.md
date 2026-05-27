# Compatibility Matrix

qmtserver adapts `xtquant` behind stable HTTP and WebSocket contracts. This matrix records observed
local behavior so upgrades can be retested deliberately.

The local package and MiniQMT behavior are authoritative for release verification. Upstream docs are
useful background but are not enough by themselves.

## Environment Records

Add one row per verified environment:

| Date | Python | qmtserver | xtquant source/version | MiniQMT userdata | Smoke scope | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-27 | CPython 3.13 | 0.4.0 | local downloaded package, exact version to record | `userdata_mini` | connection, market bars, readonly trader queries | Baseline before realtime subscription work |

Do not record account IDs, tokens, private paths, or other local secrets.

## Adaptation Matrix

| qmtserver surface | upstream function | observed signature | tests | real smoke | status |
| --- | --- | --- | --- | --- | --- |
| `GET /v1/market/bars/daily` | `xtdata.get_market_data_ex` | `field_list`, `stock_list`, `period`, `start_time`, `end_time`, `count`, `dividend_type`, `fill_data` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `GET /v1/market/bars/intraday` | `xtdata.get_market_data_ex` | Same as daily bars, with intraday `period` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `GET /v1/trader/*` readonly queries | `XtQuantTrader.query_*` readonly methods | Account-specific methods accept `StockAccount`; orders accept `cancelable_only` | `tests/test_trader_service.py`, `tests/test_api_trader.py` | Required before trader-query release; no real trading | stable |
| `POST /v1/market/subscriptions` | `xtdata.subscribe_quote` | To be observed locally | Planned fake tests | Planned readonly smoke | planned |
| `DELETE /v1/market/subscriptions/{subscription_id}` | upstream unsubscribe function, if available | To be observed locally | Planned fake tests | Planned readonly smoke | planned |

## Realtime Subscription Observations

Fill this section during the realtime subscription milestone.

### `xtdata.subscribe_quote`

qmtserver surface:
`POST /v1/market/subscriptions`

upstream:
`xtdata.subscribe_quote`

local xtquant version:
To be recorded from the installed package.

observed signature:
To be recorded with `inspect.signature` when available.

input conversion:
qmtserver accepts a non-empty list of stock symbols and a stable period string. The adapter converts
these to the local upstream signature after validation.

callback payload:
To be recorded from readonly MiniQMT smoke. Record shape, not private data.

output normalization:
Callbacks normalize to `market.quote.v1` and publish `market_quote` events. Raw upstream objects must
not be exposed.

error mapping:
Disconnected quote target maps to `TARGET_NOT_CONNECTED`. Invalid request parameters map to
`INVALID_SUBSCRIPTION_REQUEST`. Upstream subscription failures map to `MARKET_SUBSCRIPTION_ERROR` or
`MARKET_SUBSCRIPTION_UNSUPPORTED`.

unit tests:
Planned: `tests/test_market_subscription_adapter.py`, `tests/test_market_subscriptions.py`, and
`tests/test_api_market_subscriptions.py`.

real smoke:
Planned readonly smoke with MiniQMT started and logged in. No trading commands.

trading safety:
Readonly market data only.

### Unsubscribe Behavior

upstream:
To be recorded after local inspection. Possible names include `unsubscribe_quote` or another
function exposed by the local `xtdata` package.

expected qmtserver behavior:
If a real upstream unsubscribe exists, call it. If it does not exist or fails, mark the local
subscription `stopped` and ignore later callbacks for that local subscription.

## Upgrade Checklist

When changing `xtquant`, MiniQMT, or Python versions:

1. Run the normal unit test suite.
2. Re-check relevant upstream signatures.
3. Run readonly MiniQMT smoke for affected surfaces.
4. Update this matrix with date, version, and observed differences.
5. Do not expand stable API behavior solely through transparent RPC.
