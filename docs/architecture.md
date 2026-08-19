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

- canonical frequency catalog and set model
- set/profile evaluation
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

- frequency definition and set management
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

The desktop uses one-request newline-delimited JSON messages over a local Python
sidecar's stdin/stdout. Tauri launches the process without opening a network port.

Catalog requests return immutable presets plus the starter user partition. Compile
requests include the current user-owned definitions and sets. Python validates that
payload, rejects preset impersonation or broken references, combines it with the
built-in preset partition, and then calls the same compiler used by the CLI.

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

The current vertical slice persists user-owned catalog records and radio instances
in the desktop webview's local storage. This proves the editing and compilation
workflow without allowing frontend state to bypass Python validation.

Move the same records behind SQLite repository interfaces before catalog size,
migrations, backups, or multi-window behavior make local storage inappropriate.

Persistence should not leak database rows into compiler APIs.

The canonical domain objects should remain independently serializable/testable.

## Hosted possibility

A future hosted version is possible, but it is not a current requirement.

If pursued, the same Svelte UI and compiler semantics should be reusable.

Do not distort the desktop architecture today to solve hypothetical cloud concerns.
