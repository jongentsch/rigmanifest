# First Codex Prompt

Read `AGENTS.md` and every file in `docs/`.

This repository is **RigManifest**.

Do not implement the full project yet.

First review the proposed architecture and MVP for contradictions, missing abstractions, unnecessary complexity, or decisions that should be deferred.

Then propose a concrete implementation plan for the first vertical slice using these already-decided constraints:

- GPLv3-compatible open source
- Python core
- Svelte + TypeScript frontend
- Tauri desktop wrapper
- CHIRP as an intentional upstream dependency
- CHIRP CSV as the first programming/output boundary
- compiler logic must remain independent of UI and persistence

The first vertical slice should:

1. Create a small in-memory channel library fixture.
2. Define a `Home` profile.
3. Define or derive a minimal Yaesu VX-6R capability model.
4. Compile `Home` into a target-specific plan.
5. Return structured diagnostics.
6. Export CHIRP-compatible CSV.
7. Add unit tests for:
   - frequency compatibility
   - receive-only semantics
   - label truncation
   - capacity handling
   - deterministic ordering
   - diagnostics
   - CSV export
8. Add a CLI command:
   `rigmanifest compile home --target yaesu-vx6r`
9. Add the smallest useful Svelte/Tauri UI that can invoke this compile flow and display diagnostics.
10. Only after the above works, add the Quansheng UV-K5 and prove that the same `Home` intent compiles differently.

Before coding, recommend and justify:

- Python package layout
- Python model/validation approach
- test framework
- CLI framework
- Python ↔ Tauri IPC mechanism
- persistence choice for the next phase
- whether CHIRP should initially be vendored, installed as a dependency, or consumed through a clearly isolated adapter

Do not:
- add direct radio programming
- implement clone protocols
- add DMR
- add online services
- add account/auth systems
- add licensing/activation
- build a plugin framework
- over-generalize the domain model for hypothetical future radios

Optimize for a clean, testable compiler and a thin desktop shell.
