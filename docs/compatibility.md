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
| 2026-05-28 | CPython 3.13.13 | 0.5.0 | `xtquant_250516` from local venv | `userdata_mini` | quote connection, subscription create, initial `market_quote`, live callback `market_quote`, subscription stop | Active-market readonly smoke at 13:10 local time verified `meta.quote_source=callback` with `trader_connected=false`. No trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | quote connection, subscription create, initial `market_quote`, live callback `market_quote`, latest quote cache, subscription diagnostics, subscription stop | Active-market readonly smoke at 13:46 local time verified event sequence, latest cache hit, `callback_count=1`, and `trader_connected=false`. No trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | batch subscription, three initial `market_quote` events, one live callback, latest quote cache, subscription diagnostics, subscription stop | Active-market readonly smoke at 13:57 local time for `000001.SZ`, `600000.SH`, and `510300.SH` verified latest cache hits for all symbols, `initial_quote_count=3`, `callback_count=1`, and `trader_connected=false`. No trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | 20-second batch subscription smoke, latest quote cache, subscription diagnostics, callback report, subscription stop | Active-market readonly smoke at 14:08 local time for `000001.SZ`, `600000.SH`, and `510300.SH` collected 21 callbacks, latest cache hits for all symbols, `callback_count=21`, and `trader_connected=false`. No trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | history download job, daily bars, intraday bars, snapshot manifest, daily quality | Active-market readonly smoke used `download_history_data` before reads and verified non-empty rows for `000001.SZ`: 579 daily rows and 222 intraday rows. `trader_connected=false`; no trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | reference calendar, `all_a` universe, instrument detail field baseline | Active-market readonly smoke for `000001.SZ` and `600000.SH` returned 5208 universe symbols and observed stable instrument detail fields including `InstrumentID`, `InstrumentName`, `ExchangeID`, `PriceTick`, `UpStopPrice`, and `DownStopPrice`. `trader_connected=false`; no trader or trading commands used. |
| 2026-05-28 | CPython 3.13.13 | 0.6.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | 180-second realtime subscription stability smoke | Active-market readonly smoke for `000001.SZ`, `600000.SH`, and `510300.SH` collected 180 callbacks in 180 seconds, with 60 callbacks per symbol, latest cache hits for all symbols, active diagnostics, and stopped status. `trader_connected=false`; no trader or trading commands used. |
| 2026-06-01 | CPython 3.13.13 | 0.7.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | batch subscription, live callback, latest quote cache, subscription diagnostics, manual recover, runtime health | Active-market readonly smoke for `000001.SZ`, `600000.SH`, and `510300.SH` verified quote connection, active subscription, live callback, latest cache hits for all symbols, active diagnostics, stopped status, manual recover to `active`, diagnostics reset, and `runtime_health.status=ok`. `trader_connected=false`; no trader or trading commands used. |
| 2026-06-01 | CPython 3.13.13 | 0.7.0 release candidate | `xtquant_250516` from local venv | `userdata_mini` | trader diagnostics and trader readonly smoke | `qmtserver diagnose trader` and `scripts/smoke_trader_readonly.py` both reached `xtquant` import, userdata path, class loading, and trader start, but `connect()` returned `-1`. Explicitly testing the quote-observed MiniQMT userdata path returned the same result. No order, cancel, transfer, or other trading command was used. |

Do not record account IDs, tokens, private paths, or other local secrets.

## Adaptation Matrix

| qmtserver surface | upstream function | observed signature | tests | real smoke | status |
| --- | --- | --- | --- | --- | --- |
| `GET /v1/market/bars/daily` | `xtdata.get_market_data_ex` | `field_list`, `stock_list`, `period`, `start_time`, `end_time`, `count`, `dividend_type`, `fill_data` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `GET /v1/market/bars/intraday` | `xtdata.get_market_data_ex` | Same as daily bars, with intraday `period` | `tests/test_market_adapter.py`, `tests/test_api_market.py` | Required before market-data release | stable |
| `POST /v1/jobs/history-download` | `xtdata.download_history_data` then `xtdata.get_market_data_ex` | Per-symbol synchronous `download_history_data(stock_code, period, start_time, end_time, incrementally=None)` before snapshot creation | `tests/test_market_adapter.py`, `tests/test_jobs.py`, `tests/test_api_jobs.py` | Active-market readonly smoke passed with non-empty daily and intraday rows | development verified |
| `GET /v1/reference/universe` | `xtdata.get_stock_list_in_sector` | `all_a` maps to local sector name `沪深A股`; other names pass through | `tests/test_api_reference.py` | Active-market readonly smoke passed for `all_a` | development verified |
| `GET /v1/reference/instruments` | `xtdata.get_instrument_detail` | `get_instrument_detail(symbol)` returns a dict with local instrument metadata fields | `tests/test_api_reference.py` | Active-market readonly smoke recorded observed fields for two symbols | development verified |
| `GET /v1/trader/*` readonly queries | `XtQuantTrader.query_*` readonly methods | Account-specific methods accept `StockAccount`; orders accept `cancelable_only` | `tests/test_trader_service.py`, `tests/test_api_trader.py` | Required before trader-query release; no real trading | stable |
| `scripts/smoke_trader_readonly.py` | qmtserver smoke helper | Connects trader only and checks readonly `GET /v1/trader/*` summaries without raw rows | `tests/test_smoke_trader_readonly_script.py` | Pending rerun; 2026-05-28 local attempt returned `connect_result=-1` before readonly queries could pass | development |
| `POST /v1/market/subscriptions` | `xtdata.subscribe_quote` | `subscribe_quote(stock_code, period='1d', start_time='', end_time='', count=0, callback=None)` | `tests/test_market_adapter.py`, `tests/test_market_normalizers.py` | Active-market readonly smoke passed for initial quote seed and live callback quote event | released in 0.5.0 |
| `DELETE /v1/market/subscriptions/{subscription_id}` | `xtdata.unsubscribe_quote` | `unsubscribe_quote(seq)` | `tests/test_market_adapter.py` | After-hours readonly smoke passed | released in 0.5.0 |
| `GET /v1/market/quotes/latest` | qmtserver in-memory cache | Updated from normalized `market.quote.v1` events | `tests/test_market_subscriptions.py`, `tests/test_api_market.py` | Active-market readonly smoke passed for latest quote cache hit | development verified |
| `GET /v1/market/subscriptions/{subscription_id}/diagnostics` | qmtserver in-memory diagnostics | Counts initial quotes, callback quotes, last source, and last event sequence | `tests/test_market_subscriptions.py`, `tests/test_api_market.py` | Active-market readonly smoke passed for callback and initial quote counters | development verified |
| `POST /v1/market/subscriptions/{subscription_id}/recover` | qmtserver subscription service and `xtdata.subscribe_quote` | Reuses the same local subscription, symbols, and period; resets diagnostics; publishes `market_subscription_recovered` | `tests/test_market_subscriptions.py`, `tests/test_api_market.py` | 2026-06-01 active-market readonly smoke passed for stopped-to-active recovery | development verified |
| `GET /v1/diagnostics` runtime health | qmtserver status and subscription diagnostics | Summarizes quote, trader, and subscription health under `runtime.health.v1` | `tests/test_api_diagnostics.py` | 2026-06-01 readonly smoke passed with quote connected, trader disabled, one active subscription, and `status=ok` | development verified |
| `scripts/smoke_market_subscription.py --symbols` | qmtserver smoke helper | Creates one multi-symbol readonly subscription and checks events, latest cache, and diagnostics | `tests/test_smoke_market_subscription_script.py` | Active-market readonly batch smoke passed with three symbols | development verified |
| `scripts/smoke_market_subscription.py --duration-seconds` | qmtserver smoke helper | Collects callback counts and per-symbol callback report over a bounded window | `tests/test_smoke_market_subscription_script.py` | Active-market readonly 20-second batch smoke passed | development verified |
| `scripts/smoke_market_subscription.py --omit-events` | qmtserver smoke helper | Suppresses full event arrays in printed long-window smoke output while preserving event counts | `tests/test_smoke_market_subscription_script.py` | Used after 180-second active-market smoke to keep future output concise | development verified |
| `scripts/smoke_market_data_lake.py` | qmtserver smoke helper | Checks `/v1/health` and `/v1/market/data/*` download, coverage, bars, quality, export, and cached download paths with `connect_trader=False` | `tests/test_smoke_market_data_lake_script.py` | Pending real MiniQMT readonly smoke | development |

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
`market.quote.v1`, and stop returned `stopped`. Active-market smoke on 2026-05-28 at 13:10 local
time also received a WebSocket `market_quote` event with `meta.quote_source=callback`. The smoke
script used `connect_trader=False`; no trader or trading commands were used.

0.6.0 release-candidate active-market smoke on 2026-05-28 at 13:46 local time verified `event_seq`, latest
quote cache lookup, and subscription diagnostics in the same readonly script. The script reported
`trader_connected=false`.

Batch active-market smoke on 2026-05-28 at 13:57 local time used one subscription for three symbols.
It received initial quotes for all requested symbols, one live callback, latest cache hits for all
requested symbols, and diagnostics counters for both initial and callback quote sources.

Long-window active-market smoke on 2026-05-28 at 14:08 local time used a 20-second window with the
same three symbols. It collected 21 callback events, latest cache hits for every requested symbol,
and active callback diagnostics.

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
