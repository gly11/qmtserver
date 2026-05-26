# xtquant Adapter Guide

qmtserver exposes stable HTTP, WebSocket, and client contracts on top of MiniQMT / `xtquant`.
`xtquant` is the upstream integration boundary, not the public qmtserver contract. Adapter work must
therefore be explicit, tested, and checked against the locally installed package.

## Sources

Use sources in this order:

1. The locally installed `xtquant` package, because it is the version users actually run.
2. The bundled local docs under `.venv/Lib/site-packages/xtquant/doc/`.
3. Official or curated online docs for background and parameter explanations.
4. Real MiniQMT smoke tests for release verification.

Document the observed local `xtquant` version when an adaptation depends on version-specific
behavior. For example, the `0.3.0` market data work was verified against `xtquant_250516`.

## Boundary Rules

- API routes should parse requests and assemble responses only.
- Adapters and services should own direct `xtquant` calls.
- qmtserver should accept stable, user-friendly inputs where possible, then convert to upstream
  formats at the adapter boundary.
- qmtserver should return JSON-friendly dictionaries, lists, strings, numbers, booleans, and nulls.
  Do not leak raw `xtquant` objects through stable endpoints.
- Keep upstream errors inside the qmtserver error envelope. Prefer stable qmtserver error codes over
  raw exception text.
- Do not add a transparent RPC method to the stable API surface without creating an explicit
  adaptation entry, tests, and docs.

## Adaptation Checklist

For each new or changed adaptation, record:

- qmtserver endpoint or RPC method.
- Upstream module and function.
- Observed local signature.
- Required input conversion.
- Output normalization rules.
- Error mapping.
- Unit tests.
- Real MiniQMT smoke coverage.
- Trading safety review, if the method can place, cancel, transfer, or otherwise alter account
  state.

Template:

```text
qmtserver surface:
upstream:
local xtquant version:
observed signature:
input conversion:
output normalization:
error mapping:
unit tests:
real smoke:
trading safety:
notes:
```

## Known Adaptations

### Market Bars

qmtserver surface:
`GET /v1/market/bars/daily`, `GET /v1/market/bars/intraday`, snapshot and history job paths that
reuse market bars.

upstream:
`xtquant.xtdata.get_market_data_ex`.

observed signature:
`get_market_data_ex(field_list=[], stock_list=[], period='1d', start_time='', end_time='', count=-1,
dividend_type='none', fill_data=True)`.

input conversion:
qmtserver accepts ISO dates and datetimes. The adapter converts them before calling `xtdata`:

- `2026-05-25` becomes `20260525`.
- `2026-05-26T09:30:00+08:00` becomes `20260526093000`.
- Already compact strings are passed through.

output normalization:
Daily bars normalize to `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`, `amount`, and
`meta`. Intraday bars normalize to `timestamp`, `symbol`, `period`, `open`, `high`, `low`, `close`,
`volume`, `amount`, and `meta`.

error mapping:
Connection failures map to `TARGET_NOT_CONNECTED`. Invalid qmtserver request parameters map to
`INVALID_MARKET_REQUEST`. Unexpected upstream failures map to `MARKET_DATA_ERROR`.

unit tests:
`tests/test_market_adapter.py`, `tests/test_api_market.py`, `tests/test_api_snapshots.py`, and
`tests/test_api_jobs.py`.

real smoke:
Verify daily bars, intraday bars, snapshot creation, snapshot quality, and history jobs against a
logged-in MiniQMT before release.

## Real MiniQMT Smoke Gate

Before release, run the normal quality gate, then run a real MiniQMT check on a Windows machine with
MiniQMT started and logged in:

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --json
```

For market-data releases, also verify the service layer with `connect_trader=false` if no safe test
account is configured. At minimum cover:

- `/v1/health`
- `/v1/qmt/status`
- `/v1/diagnostics`
- `/v1/market/capabilities`
- `/v1/market/bars/daily`
- `/v1/market/bars/intraday`
- `/v1/rpc` with `xtdata.get_full_tick`
- `/v1/snapshots`
- `/v1/jobs/history-download`

Record any skipped real-account checks in the handoff.

## Trading Adaptations

Trading methods are a separate risk class. They must keep all existing protections:

- `QMT_ENABLE_TRADING=false` by default.
- `QMT_TRADING_DRY_RUN=true` by default.
- Account allowlists.
- Symbol allowlists or blocklists where relevant.
- Per-order and daily limits.
- Confirmation text for real trading.
- Audit logs with masked account IDs.
- Unit tests for rejection paths.

Do not use real trading as a routine smoke test. Use fakes, dry-run behavior, and explicit manual
checks unless the user specifically asks for a real trading test and accepts the risk.
