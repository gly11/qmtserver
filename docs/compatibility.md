# Compatibility Matrix

qmtserver adapts `xtquant` behind stable HTTP and WebSocket contracts. This matrix records observed
local behavior so upgrades can be retested deliberately.

The local package and MiniQMT behavior are authoritative for release verification. Upstream docs are
useful background but are not enough by themselves.

## Environment Records

Add one row per verified environment:

| Date | Python | qmtserver | xtquant source/version | MiniQMT userdata | Smoke scope | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-05-27 | CPython 3.13 | 0.4.0 | `xtquant_250516` from local venv | `userdata_mini` | connection, market bars, readonly trader queries | Baseline before realtime subscription work |
| 2026-05-27 | CPython 3.13.13 | unreleased realtime subscription work | `xtquant_250516` from local venv | `userdata_mini` | quote connection, subscription create, subscription stop, WebSocket lifecycle event | After-hours smoke at 17:27 local time. No live `market_quote` observed before initial quote seed support; rerun after seed support and during active market data. No trader or trading commands used. |
| 2026-05-27 | CPython 3.13.13 | unreleased realtime subscription work | `xtquant_250516` from local venv | `userdata_mini` | quote connection, subscription create, initial `market_quote`, subscription stop | After-hours smoke at 17:59 local time verified the initial `get_full_tick` seed path. Live callback delivery still needs active-market smoke. No trader or trading commands used. |

Do not record account IDs, tokens, private paths, or other local secrets.

## Adaptation Matrix

| qmtserver surface | upstream function | observed signature | tests | real smoke | status |
| --- | --- | --- | --- | --- | --- |
| `GET /v1/market/bars/daily` | `xtdata.get_market_data_ex` | `field_list`, `stock_list`, `period`, `start_time`, `end_time`, `count`, `dividend_type`, `fill_data` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `GET /v1/market/bars/intraday` | `xtdata.get_market_data_ex` | Same as daily bars, with intraday `period` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `GET /v1/trader/*` readonly queries | `XtQuantTrader.query_*` readonly methods | Account-specific methods accept `StockAccount`; orders accept `cancelable_only` | `tests/test_trader_service.py`, `tests/test_api_trader.py` | Required before trader-query release; no real trading | stable |
| `POST /v1/market/subscriptions` | `xtdata.subscribe_quote` | `subscribe_quote(stock_code, period='1d', start_time='', end_time='', count=0, callback=None)` | `tests/test_market_adapter.py`, `tests/test_market_normalizers.py` | After-hours readonly smoke passed for initial quote seed; active-market callback smoke pending | release candidate |
| `DELETE /v1/market/subscriptions/{subscription_id}` | `xtdata.unsubscribe_quote` | `unsubscribe_quote(seq)` | `tests/test_market_adapter.py` | After-hours readonly smoke passed | release candidate |

## Realtime Subscription Observations

Fill this section during the realtime subscription milestone.

### `xtdata.subscribe_quote`

qmtserver surface:
`POST /v1/market/subscriptions`

upstream:
`xtdata.subscribe_quote`

local xtquant version:
`xtquant_250516`.

observed signature:
`subscribe_quote(stock_code, period='1d', start_time='', end_time='', count=0, callback=None)`.

input conversion:
qmtserver accepts a non-empty list of stock symbols and a stable period string. The adapter converts
these to the local upstream signature after validation.

initial quote:
After upstream subscription setup, qmtserver performs a best-effort `xtdata.get_full_tick(symbols)`
call and publishes normalized `market_quote` events. Failure to fetch the initial quote does not fail
the subscription. WebSocket event `meta.quote_source` is `initial` for this seed path and `callback`
for live `subscribe_quote` callbacks.

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
Current: `tests/test_market_adapter.py`, `tests/test_market_normalizers.py`, and
`tests/test_market_subscriptions.py`. Planned: `tests/test_api_market_subscriptions.py`.

real smoke:
Readonly after-hours smoke with initial quote seed support: quote connection succeeded,
subscription create returned `active`, WebSocket received `market_quote` with schema
`market.quote.v1`, and stop returned `stopped`. Rerun during active market data before treating live
callback delivery as real-smoke verified. No trader or trading commands were used.

trading safety:
Readonly market data only.

### Unsubscribe Behavior

upstream:
`xtdata.unsubscribe_quote`.

observed signature:
`unsubscribe_quote(seq)`.

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
