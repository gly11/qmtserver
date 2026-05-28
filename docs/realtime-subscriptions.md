# Realtime Market Subscriptions

This document is the working plan for the next qmtserver capability: managed realtime market
subscriptions over the existing HTTP API and WebSocket event channel.

The feature is readonly. It must not call order, cancel, transfer, or other trading methods.

## Goal

Allow a remote client to subscribe to MiniQMT quote updates through qmtserver without importing
`xtquant` or running MiniQMT locally.

Target user flow:

```text
POST /v1/market/subscriptions
WS   /v1/ws/events?types=market_quote,market_subscription
GET  /v1/market/quotes/latest?symbols=000001.SZ
GET  /v1/market/subscriptions/{subscription_id}/diagnostics
GET  /v1/market/subscriptions
DELETE /v1/market/subscriptions/{subscription_id}
```

The public contract is qmtserver JSON, not raw `xtquant` callback payloads.

## Scope

In scope:

- Stable subscription lifecycle models.
- In-memory subscription registry.
- `xtdata.subscribe_quote` adapter boundary.
- Best-effort initial quote seed from `xtdata.get_full_tick`.
- Quote callback normalization to `market.quote.v1`.
- In-memory latest quote cache for subscribed symbols.
- Subscription diagnostics for callback counts, initial quote counts, and last quote metadata.
- Monotonic `event_seq` metadata on `market_quote` WebSocket events.
- WebSocket events for quote updates, subscription status, and subscription errors.
- HTTP APIs for create, list, get, and stop.
- Unit tests with fakes.
- Real MiniQMT readonly smoke before release.
- Compatibility matrix entries for the observed local `xtquant` behavior.

Out of scope:

- Real trading commands or tests.
- Order or cancel APIs.
- Persistent subscription storage.
- Level2, tick-by-tick, or full-depth market data unless a minimal upstream shape is needed for the
  first quote callback.
- qmtclient project changes.
- Transparent RPC expansion.

## Public API Draft

Create:

```http
POST /v1/market/subscriptions
```

```json
{
  "symbols": ["000001.SZ", "600000.SH"],
  "period": "tick"
}
```

Response:

```json
{
  "ok": true,
  "data": {
    "subscription_id": "sub_...",
    "symbols": ["000001.SZ", "600000.SH"],
    "period": "tick",
    "status": "active",
    "upstream_id": 1,
    "last_error": null
  },
  "error": null
}
```

List and get:

```http
GET /v1/market/subscriptions
GET /v1/market/subscriptions/{subscription_id}
```

Stop:

```http
DELETE /v1/market/subscriptions/{subscription_id}
```

If upstream cancellation is unavailable or unreliable, qmtserver still marks the subscription as
`stopped` and drops later callbacks for that local subscription. The exact behavior must be recorded
in [Compatibility Matrix](compatibility.md).

## Event Contract

Subscription lifecycle event:

```json
{
  "type": "market_subscription",
  "data": {
    "schema": "market.subscription.v1",
    "subscription_id": "sub_...",
    "symbols": ["000001.SZ"],
    "period": "tick",
    "status": "active"
  },
  "meta": {
    "source": "qmtserver"
  }
}
```

Quote event:

```json
{
  "type": "market_quote",
  "data": {
    "schema": "market.quote.v1",
    "symbol": "000001.SZ",
    "time": "2026-05-27T09:30:01+08:00",
    "last_price": 10.25,
    "volume": 1200,
    "amount": 12300.0,
    "extra": {}
  },
  "meta": {
    "subscription_id": "sub_...",
    "source": "xtdata",
    "quote_source": "callback",
    "event_seq": 2
  }
}
```

Errors:

```json
{
  "type": "market_subscription_error",
  "data": {
    "schema": "market.subscription.v1",
    "subscription_id": "sub_...",
    "status": "error",
    "error": "quote subscription failed"
  },
  "meta": {
    "source": "qmtserver"
  }
}
```

## Internal Design

Recommended modules:

```text
src/qmtserver/market/subscription_models.py
src/qmtserver/market/subscription_adapter.py
src/qmtserver/market/subscription_service.py
```

Responsibilities:

- Models define stable qmtserver request, state, and event shapes.
- Adapter owns direct `xtdata.subscribe_quote` and unsubscribe calls.
- Adapter may emit one initial `get_full_tick` quote after subscription setup; failures are ignored
  because live callbacks remain the primary stream.
- Service owns local lifecycle, registry state, status transitions, and EventBus publishing.
- Service owns the latest quote cache, per-subscription diagnostics, and quote event sequence.
- EventBus recent cache can be queried by event type and symbol for short reconnect recovery.
- API routes parse HTTP input and assemble responses only.

The first implementation should use the existing in-process `EventBus`. It should not introduce a
database.

## State Model

Subscription statuses:

```text
starting
active
degraded
stopped
error
```

Rules:

- `starting`: local object exists, upstream subscription call is in progress.
- `active`: upstream subscription was accepted.
- `degraded`: quote connection became unavailable after creation.
- `stopped`: user stopped the subscription, or qmtserver intentionally ignores later callbacks.
- `error`: create or runtime failure.

## Error Codes

Add or reuse stable codes:

```text
INVALID_SUBSCRIPTION_REQUEST
MARKET_SUBSCRIPTION_ERROR
MARKET_SUBSCRIPTION_NOT_FOUND
MARKET_SUBSCRIPTION_UNSUPPORTED
TARGET_NOT_CONNECTED
```

## Test Plan

Add focused fake-based tests:

- Creating a subscription stores stable state and publishes `market_subscription`.
- Invalid symbols or periods return `INVALID_SUBSCRIPTION_REQUEST`.
- Disconnected `xtdata` returns `TARGET_NOT_CONNECTED`.
- Callback payloads normalize to `market.quote.v1`.
- Callback and initial quote payloads update `/v1/market/quotes/latest`.
- Subscription diagnostics report `callback_count`, `initial_quote_count`, `last_quote_at`,
  `last_initial_quote_at`, `last_callback_at`, freshness seconds, `is_callback_active`,
  `last_quote_source`, and `last_event_seq`.
- Stopping a subscription marks it `stopped`.
- Stopped subscriptions do not publish later quote callbacks.
- WebSocket filtering can receive `market_quote`.
- EventBus queue behavior remains bounded.

Real MiniQMT smoke is a release gate, not a replacement for deterministic tests.

## Real MiniQMT Smoke

Readonly smoke only:

1. Start and log in to MiniQMT.
2. Start qmtserver with quote connection enabled.
3. Create one subscription for a liquid symbol.
4. Connect to `/v1/ws/events?types=market_subscription,market_quote`.
5. Observe one lifecycle event and at least one quote event while the market data source is active.
6. Query `/v1/market/quotes/latest?symbols=<symbol>` and confirm the cache contains that symbol.
7. Query `/v1/market/subscriptions/{subscription_id}/diagnostics` and confirm the quote counters.
8. Stop the subscription.
9. Optionally listen for a short post-stop window and confirm no `market_quote` events are
   published for the stopped local `subscription_id`.

After-hours smoke can verify the event path through the initial `get_full_tick` quote seed. Treat
live callback delivery as verified only after observing a quote event while market data is active.
Use WebSocket event `meta.quote_source`: `initial` proves the seed path, while `callback` proves the
live `subscribe_quote` callback path.

2026-05-28 13:10 local time readonly smoke received both the initial quote seed and a live callback
quote event with `meta.quote_source=callback`. The smoke script reported `trader_connected=false`,
and no order, cancel, transfer, or other trading command was used.

2026-05-28 13:57 local time readonly batch smoke subscribed to `000001.SZ`, `600000.SH`, and
`510300.SH`. It verified initial quotes for all three symbols, one live callback, latest cache hits
for all requested symbols, `initial_quote_count=3`, `callback_count=1`, and
`trader_connected=false`.

Helper command:

```powershell
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback
uv run python scripts\smoke_market_subscription.py --symbol 000001.SZ --require-callback --post-stop-listen-seconds 5
uv run python scripts\smoke_market_subscription.py --symbols 000001.SZ,600000.SH,510300.SH --require-callback --require-all-symbols --timeout-seconds 60
```

Do not run order, cancel, transfer, or other trading commands during this smoke.
