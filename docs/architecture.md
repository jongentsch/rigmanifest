# Architecture

## Goals

The architecture should:

- keep Python as the configuration/compiler engine
- avoid Python-native GUI frameworks
- make the compiler usable from both desktop UI and CLI
- support CHIRP integration naturally
- allow a future hosted/client-side UI without rewriting compiler semantics
- avoid premature distributed-system complexity

## Proposed stack

### Core

Python 3.12+

Responsibilities:

- canonical domain model
- profile evaluation
- radio capability model
- compiler
- diagnostics
- CHIRP adapters
- CHIRP CSV import/export
- persistence services
- CLI

### Desktop UI

Svelte + TypeScript

Responsibilities:

- channel library management
- radio inventory
- profile editing
- compiler result display
- diagnostics UI
- export workflow

### Desktop wrapper

Tauri

Responsibilities:

- native packaging
- application lifecycle
- launching/communicating with Python backend
- filesystem integration where needed

## Process boundary

The exact Python ↔ Tauri communication mechanism is intentionally undecided.

Preferred qualities:

- local-only
- simple
- debuggable
- no unnecessary network exposure
- easy to invoke in development and packaged builds

Candidates include:

- localhost HTTP API
- stdin/stdout JSON-RPC
- local socket
- Tauri sidecar process communication

Choose the simplest approach that packages reliably.

## Core isolation

The compiler package must not import:

- Svelte code
- Tauri bindings
- frontend state
- desktop-specific UI logic

Likewise, the frontend should never reproduce compiler rules.

## Suggested repository shape

```text
rigmanifest/
├── pyproject.toml
├── src/
│   └── rigmanifest/
│       ├── domain/
│       ├── profiles/
│       ├── capabilities/
│       ├── compiler/
│       ├── diagnostics/
│       ├── chirp/
│       ├── exporters/
│       ├── persistence/
│       └── cli/
├── tests/
├── desktop/
│   ├── src/
│   ├── src-tauri/
│   └── package.json
├── docs/
├── AGENTS.md
└── README.md
```

## Persistence

Use SQLite for the desktop application unless the first vertical slice proves JSON simpler.

Persistence should not leak database rows into compiler APIs.

The canonical domain objects should remain independently serializable/testable.

## Hosted possibility

A future hosted version is possible, but it is not a current requirement.

If pursued, the same Svelte UI and compiler semantics should be reusable.

Do not distort the desktop architecture today to solve hypothetical cloud concerns.
