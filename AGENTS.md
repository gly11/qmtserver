# AGENTS.md

This file defines the working rules for automated agents and collaborators in the qmtserver
repository. Before changing code, read this file, then read `README.md`, `docs/README.md`, and the
relevant source files.

## Project Purpose

qmtserver is a local Windows gateway for MiniQMT / `xtquant`. A Windows machine with MiniQMT runs
qmtserver; other tools, strategy systems, or automation scripts access it through HTTP RPC,
WebSocket events, and client SDKs.

The current `0.3.0` baseline is a safety-first remote gateway MVP:

- connection-check CLI;
- `/v1` HTTP API;
- allowlisted RPC forwarding;
- bearer token authentication;
- trading guards and dry-run behavior;
- WebSocket events;
- in-memory order, trade, and event caches;
- built-in Python client SDK;
- logs, metrics, request IDs, and Windows helper scripts.
- stable market data, snapshot, job, diagnostics, reference, and data quality endpoints.

qmtclient is a separate client project. qmtserver documentation should focus on server API,
runtime, security, trading protection, MiniQMT connectivity, and operational behavior.

## Repository Layout

- Source code lives in `src/qmtserver/`.
- Tests live in `tests/`.
- Architecture, roadmap, release, and operational docs live in `docs/`.
- Example scripts live in `examples/`.
- Helper scripts live in `scripts/`.
- Keep the repository root limited to entry-point docs, configuration, and standard project files.

Do not vendor `xtquant` into the repository root. If needed locally, install the PyPI extra with:

```powershell
uv sync --extra xtquant
```

or place a downloaded package in the virtual environment, not in this repository.

Do not commit `.venv/`, caches, MiniQMT userdata, market data, logs, real account IDs, tokens, or
personal paths.

## Development Commands

Common commands:

```powershell
uv sync
uv sync --extra xtquant
uv run qmtserver check --skip-quote
uv run python -m unittest discover
uv run ruff format .
uv run ruff check .
uv run ty check
```

When checking a real MiniQMT connection:

```powershell
uv run qmtserver check --userdata "D:\path\to\MiniQMT\userdata_mini" --account-id "account-id"
```

## Quality Gate

Before handing off code or preparing a commit, run at least:

```powershell
uv run python -m unittest discover
uv run ruff check .
uv run ruff format --check .
uv run ty check
git diff --check
```

If a real MiniQMT connection check cannot be run because the local machine has no MiniQMT or account
access, say so explicitly in the handoff.

## Coding Style

- Use Python 3.12 or 3.13 for qmtserver.
- Keep the `src/` layout; do not import project source from the repository root.
- Prefer the standard library unless a new dependency has a clear purpose.
- Keep public API responses JSON-friendly.
- Keep `xtquant` object conversion in adapter or serialization layers, not scattered through API
  routes.
- Keep API routes thin: request parsing, dependency injection, and response assembly only.
- Put business logic in service, RPC, trading, event, order, serialization, or audit modules.
- Trading methods such as order and cancel are disabled by default and must require explicit config
  and allowlists.

## xtquant Adapter Rules

- Do not call `xtquant.xtdata`, `XtQuantTrader`, or `xtquant.xttype` directly from API routes,
  client code, or documentation examples that are meant to describe qmtserver behavior.
- Put direct `xtquant` calls behind adapter, service, trading, or serialization modules. Current
  examples are `qmtserver.market.adapter`, `qmtserver.services.qmt_service`, and
  `qmtserver.rpc.serializers`.
- qmtserver public APIs should keep stable JSON-friendly contracts even when `xtquant` signatures or
  return objects are awkward. Convert inputs and outputs at the adapter boundary.
- Treat upstream docs as useful but not sufficient. Verify behavior against the locally installed
  `xtquant` version, especially date formats, period names, adjustment modes, account objects, and
  return shapes.
- Record new or changed `xtquant` adaptations in `docs/xtquant-adapter.md`, including the qmtserver
  endpoint, upstream function, local signature, input conversion, output normalization, error
  mapping, and MiniQMT smoke coverage.
- Every new stable `xtquant` adaptation needs focused unit tests with fakes. Real MiniQMT checks are
  release gates, not substitutes for deterministic tests.
- Transparent RPC is for exploration and advanced debugging only. Do not treat a transparent method
  as stable until it has an explicit qmtserver contract, tests, docs, and safety review.
- Trading-related adaptations require the security and trading rules below, plus failure-path tests.

## Code Size And Structure

- Try to keep individual `.py` files under 300 lines.
- If a `.py` file exceeds 400 lines, actively evaluate whether it should be split by responsibility.
- If a `.py` file exceeds 500 lines, split it unless it is generated code, a constants table, or a
  clearly justified registry.
- Try to keep individual functions under 50 lines.
- If a function exceeds 80 lines, prefer private helpers, domain services, or dedicated models.
- Split large test files by feature when they approach 500 lines, for example
  `test_trading_safety.py` or `test_order_events.py`.
- The RPC dispatcher should coordinate dispatch only; do not pile trading validation,
  serialization, audit, cache, or event logic into it.
- Use early returns or helpers when nesting grows beyond three levels.
- Avoid mixing formatting, refactoring, features, and docs in one change when they can be separated.
- New public behavior needs tests. Trading-related changes must cover failure paths.

## Documentation

- Update `README.md` or the appropriate `docs/` page when adding or changing user-facing behavior.
- Long-term server planning belongs in `docs/roadmap.md`.
- Release cadence and release gates belong in `docs/release-plan.md`.
- API, error, SDK, operation, and troubleshooting details belong in their corresponding docs pages.
- Collaboration rules belong in this file or `CONTRIBUTING.md`.
- Client-side qmtclient planning belongs in the qmtclient project, not in qmtserver.

## Security And Trading Rules

- Never write real account IDs, tokens, passwords, private keys, or personal paths into the
  repository.
- `.env.example` may contain example values only.
- Do not expose arbitrary `xtquant` methods through RPC unless an explicit transparent RPC mode is
  implemented, documented, tested, and disabled by default.
- Trading capability is disabled by default.
- Real trading must require explicit configuration, allowlists, limits, confirmation text, and audit
  logs.
- Do not bypass the RPC allowlist, transparent RPC settings, token authentication, or trading guards.
- Do not make tests depend on real trading. Use fakes or mocks for dangerous paths.

## Git Rules

- Do not revert changes you did not make unless the user explicitly asks.
- Do not commit `.venv/` or local runtime artifacts.
- Keep large files, logs, MiniQMT userdata, and market data ignored.
- Recommended branch names: `codex/<short-topic>`, `feature/<short-topic>`, `fix/<short-topic>`, or
  `docs/<short-topic>`.
- Use Conventional Commits: `type(scope): summary`.
- Use an English lowercase imperative summary, no final period, preferably no longer than 72
  characters.
- Do not mix unrelated formatting, refactoring, feature, and documentation changes in one commit if
  they can reasonably be split.
- Run `git diff --check` before committing.
- Do not create commits unless the user explicitly asks.

Commit types:

- `feat`: user-visible functionality.
- `fix`: bug fixes.
- `docs`: documentation changes.
- `test`: test additions or changes.
- `refactor`: behavior-preserving code restructuring.
- `style`: formatting or non-behavioral style changes.
- `chore`: tooling, dependency, configuration, or maintenance work.
- `ci`: continuous integration changes.

Examples:

```text
feat(cli): add serve command
docs(roadmap): add readonly rpc milestone
chore(tooling): configure ruff and ty
test(cli): cover connectivity check exit codes
```
