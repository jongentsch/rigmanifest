# Architecture

## Goals

The architecture should:

- keep Python as the configuration/compiler engine
- avoid Python-native GUI frameworks
- make the compiler usable from both desktop UI and CLI
- support CHIRP integration naturally
- allow a future hosted/client-side UI without rewriting compiler semantics
- avoid premature distributed-system complexity

## Project scope

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
- image-backed CHIRP radio capability model
- compiler
- diagnostics
- CHIRP adapters
- CHIRP image import/export, with CSV retained as generic interchange
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
- signed update checks, installation, and restart behavior

## Process boundary

The desktop uses one-request newline-delimited JSON messages over a local Python
sidecar's stdin/stdout. Tauri launches the process without opening a network port.
Debug builds resolve the repository's Python environment. Windows release builds
instead launch a PyInstaller-frozen sidecar registered through Tauri's
`externalBin` bundle configuration, so the installed application has no external
Python or CHIRP runtime dependency.

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
default advisory-plan context, and radio-image metadata in a versioned SQLite
database. Exact imported and compiled IMG files live under
`radios/<radio-id>/`; the database tracks their relative paths, types, timestamps,
sizes, and hashes. Workspace backups copy that directory beside the backup database.
Installed builds
use the platform application-data directory. A marker makes the Windows portable
bundle use its adjacent `data` directory; the Linux AppImage derives the same layout
from the AppImage runtime's absolute source path. The Rust shell owns this path
selection and delegates schema migration, validation, atomic writes, and backup to
the Python persistence boundary. On first open only, legacy webview local-storage
records are supplied as an import candidate and cleared after the database confirms
the migration.

The Library page exposes a native save dialog for a consistent SQLite backup.
Frontend saves are serialized so quick successive edits cannot arrive out of order.

Persistence does not leak database rows into compiler APIs.

An image-backed radio is detected and loaded by CHIRP. RigManifest never parses or
writes its binary layout. It translates image memories into reusable definitions,
translates populated banks into user sets, and creates a profile that groups those
sets. Compilation applies normalized memories and bank mappings through the loaded
driver, then asks CHIRP to save a new image without overwriting the source.

The canonical domain objects should remain independently serializable/testable.

Frequency definitions are target-independent and accept any positive integer-Hz
frequency. Target receive/transmit range and CHIRP driver validation happen during
compilation, never while authoring the shared catalog.

## Updates

The Tauri updater reads a static `latest.json` manifest from the latest public GitHub
Release and verifies every installable artifact against the public updater key embedded
in the application. The corresponding encrypted private key exists only in the release
environment and the repository owner's external backup.

Updater artifact generation is enabled only by the release-specific Tauri configuration.
Normal local package commands are unsigned and never discover or load backup keys. The
tagged-release workflow selects the release configuration and supplies the signing key
through GitHub Actions secrets.

Installed Windows and AppImage distributions use Tauri's native updater. Windows
portable and Debian distributions use the same version check but never invoke the
installer; they direct the user to the release instead. Before an in-app installation,
the Rust shell asks the Python persistence boundary for a consistent SQLite backup in
the active workspace's `backups` directory. Update checks never change compiler or
catalog semantics.

## Hosted possibility

A future hosted version is possible, but it is not a current requirement.

If pursued, the same Svelte UI and compiler semantics should be reusable.

Do not distort the desktop architecture today to solve hypothetical cloud concerns.
