# Architecture

qmtserver is a Windows service wrapper around MiniQMT / `xtquant`. It exposes a small, controlled
HTTP and WebSocket surface so other machines can access a logged-in MiniQMT client without importing
`xtquant` locally.

```text
remote tools / strategies / qmtclient
        |
HTTP RPC / WebSocket
        |
qmtserver
        |
xtquant
        |
MiniQMT
```

## Runtime Layers

- `cli`: command-line entry points such as `check` and `serve`.
- `config`: environment and runtime settings.
- `api`: FastAPI routes, request parsing, authentication, and response assembly.
- `services`: MiniQMT connection lifecycle and shared runtime state.
- `rpc`: method registry, dispatch, input conversion, and JSON serialization.
- `trading`: trading validation, dry-run behavior, account/symbol/limit checks, and confirmation.
- `events`: in-process event bus and WebSocket delivery.
- `orders`: in-memory order, trade, and recent event caches.
- `miniqmt`: direct MiniQMT / `xtquant` adapter code.
- `client`: built-in compatibility client used to exercise the `/v1` contract.

## Boundaries

API routes should stay thin. They should parse requests, enforce authentication, call services, and
assemble responses. Business logic belongs in service, RPC, trading, event, order, serialization, or
audit modules.

RPC is not an arbitrary `xtquant` proxy by default. Requests must pass through the method registry or
the explicitly enabled transparent RPC policy. Trading methods must also pass server-side trading
guards.

qmtclient is a separate client project. qmtserver documentation should describe the server API,
runtime, security, and compatibility boundary; client-side SDK planning belongs in qmtclient.

## Persistence

The first server version keeps order, trade, and recent event state in memory. Restarting qmtserver
clears these caches.
