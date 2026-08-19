# Architecture

## Goals

The architecture should:

- keep Python as the configuration/compiler engine
- avoid Python-native GUI frameworks
- make the compiler usable from both desktop UI and CLI
- support CHIRP integration naturally
- allow a future hosted/client-side UI without rewriting compiler semantics
- avoid premature distributed-system complexity

## Product boundary

RigManifest is the intent and configuration-management frontend for CHIRP. The core
must make reusable definitions, set selection, multi-radio maintenance, and compiler
diagnostics approachable. It should delegate normalized hardware facts, target-memory
validation, image formats, and eventual device communication to the pinned CHIRP
dependency wherever CHIRP already provides them.

This boundary is not merely an export choice: it is the organizing principle for the
application. New radio-specific logic belongs upstream in CHIRP or in a narrowly
sourced overlay when CHIRP cannot express the fact. New user-intent and maintenance
workflows belong in RigManifest.

## Proposed stack

### Core

Python 3.12+

Responsibilities:

- canonical frequency catalog and set model
- set/profile evaluation
- CHIRP-backed radio capability model with explicit sourced overlays
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

The desktop persists user-owned catalog records, radio instances, reusable profiles,
and default advisory-plan context in a versioned SQLite database under the platform
application-data directory. The Rust shell owns the database path and delegates
schema migration, validation, atomic writes, and backup to the Python persistence
boundary. On first open only, legacy webview local-storage records are supplied as
an import candidate and cleared after the database confirms the migration.

The Library page exposes a native save dialog for a consistent SQLite backup.
Frontend saves are serialized so quick successive edits cannot arrive out of order.

Persistence does not leak database rows into compiler APIs.

The canonical domain objects should remain independently serializable/testable.

Frequency definitions are target-independent and accept any positive integer-Hz
frequency. Target receive/transmit range and CHIRP driver validation happen during
compilation, never while authoring the shared catalog.

## Hosted possibility

A future hosted version is possible, but it is not a current requirement.

If pursued, the same Svelte UI and compiler semantics should be reusable.

Do not distort the desktop architecture today to solve hypothetical cloud concerns.
