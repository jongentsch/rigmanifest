# AGENTS.md

## Project identity

This repository is **RigManifest**.

RigManifest is an open-source amateur-radio configuration-management application.

The core idea is:

> define the desired operating configuration once, then compile it for each radio according to that radio's capabilities.

RigManifest is the intent, maintenance, and workflow frontend for CHIRP. It provides
an easier way to maintain reusable frequency definitions and sets, select them for
owned radios, and understand how that intent compiles for each target.

RigManifest is not intended to replace CHIRP. CHIRP owns normalized radio-driver
knowledge, target-memory validation, image handling, and eventually the final radio
I/O path. RigManifest owns reusable RF intent, profiles, provenance, compilation
policy, and explainable diagnostics.

## License

RigManifest is intended to be GPLv3-compatible open-source software.

CHIRP is an intentional upstream dependency and source of radio capability information where appropriate.

Do not introduce dependencies with licenses that are incompatible with GPLv3.

## Architecture

The application has three primary layers:

```text
Python Core
├── domain model
├── shared frequency catalog and sets
├── profiles / intent
├── radio capabilities
├── compiler
├── diagnostics
├── CHIRP integration
├── CHIRP CSV import/export
└── CLI
        ↕
local IPC/API boundary
        ↕
Svelte UI
        ↓
Tauri desktop shell
```

The Python core is the product logic.

The Svelte/Tauri layer is presentation and desktop packaging.

Do not put compiler logic, capability logic, selection rules, or CHIRP semantics in the frontend.

## Product principles

1. User intent is the source of truth.
2. Frequency definitions and sets do not belong to a specific radio.
3. Radios are compilation targets with explicit capabilities and constraints.
4. Compilation must explain compromises instead of silently mutating or dropping data.
5. Canonical frequency definitions and sets must remain unchanged by compilation.
6. CHIRP CSV is the first supported output target.
7. Direct radio programming is deferred until the compiler proves useful.
8. CHIRP integration should be embraced rather than reimplemented where practical.
9. Desktop is the primary user experience.
10. Keep the compiler independently testable and usable from the CLI.
11. Prefer deterministic, inspectable behavior over "smart" opaque heuristics.
12. Keep the MVP narrow.

## Read before coding

Read all documents in `docs/` before making architectural decisions:

- `docs/product-vision.md`
- `docs/architecture.md`
- `docs/mvp.md`
- `docs/domain-model.md`
- `docs/compiler-design.md`
- `docs/chirp-integration.md`

## Initial radio targets

Primary:
- Yaesu VX-6R
- Quansheng UV-K5
- Retevis RT95

Secondary:
- Alervites AT2

The first vertical slice may start with the VX-6R and add the UV-K5 second.

## MVP constraints

Do not add these unless explicitly requested:

- direct USB/serial radio programming
- custom radio clone protocols
- DMR
- accounts
- cloud sync
- paid licensing
- subscription infrastructure
- online activation
- repeater-data licensing integrations
- plugin marketplaces
- distributed services
- over-generalized framework code
- large abstractions for hypothetical future radios

## Engineering preferences

- Python 3.12+ unless a concrete compatibility reason suggests otherwise.
- Use typed Python throughout.
- Prefer dataclasses or Pydantic models where they materially help validation and serialization.
- Keep the compiler pure where practical.
- Keep CHIRP adapters isolated from the core domain model.
- Treat capability definitions as data where practical.
- Use structured diagnostic codes and severities.
- Exporters consume compiled plans; they do not make selection decisions.
- Persistence should sit behind a repository/service boundary but remain simple.
- Avoid binding the Python core to Tauri internals.
- The CLI and desktop UI should consume the same core APIs.

## Frontend preferences

- Svelte + TypeScript.
- Tauri for desktop packaging.
- The frontend should render:
  - frequency definitions and sets
  - radio inventory
  - profiles
  - compile results
  - warnings/errors
  - export actions
- Frontend state should not become the source of truth for configuration semantics.

## Testing expectations

At minimum, compiler behavior should be covered for:

- memory capacity
- unsupported receive frequency
- unsupported transmit frequency
- receive-only handling
- label truncation
- unsupported mode
- unsupported tone mode
- set selection
- preset/user definition sharing
- factory frequency-set coverage
- deterministic ranking
- deterministic memory numbering
- group degradation
- capacity omissions
- structured diagnostics
- CHIRP CSV generation

CHIRP adapter behavior should have tests against representative feature mappings.

## First vertical slice

The first meaningful end-to-end path is:

1. Define a small shared frequency catalog with preset and user-owned sets.
2. Define a `Home` profile.
3. Define or derive a minimal Yaesu VX-6R capability model.
4. Compile `Home` for the VX-6R.
5. Return structured diagnostics.
6. Export CHIRP-compatible CSV.
7. Add a CLI command:
   `rigmanifest compile home --target yaesu-vx6r`
8. Add a minimal Svelte screen that invokes the same compiler flow.
9. Add the UV-K5 as a second target and prove the same selected sets compile differently.

Do not expand beyond that slice until it works cleanly.
