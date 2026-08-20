# First Vertical Slice Plan

> **Historical document.** This records the decisions and delivery sequence for the
> first executable slice. It is retained for architectural context, not as a list of
> unfinished work. See the current [RigManifest Roadmap](../ROADMAP.md).

## Architecture review

The proposed architecture is coherent: a pure Python compiler owns semantics,
while the CLI and desktop app are adapters. The first slice does not need a
database or a long-running service.

The design documents leave several details intentionally open. This slice
resolves them as follows:

1. Frequency definitions store integer Hz. Capability ranges are inclusive. This avoids
   floating-point comparisons and makes CSV formatting an exporter concern.
2. `TransmitBehavior.DISABLED` is the single source of receive-only intent.
   A second `receive_only` boolean would permit contradictory states.
3. Profiles select ordered frequency-set IDs. Sets reference definitions in one
   shared catalog; user sets may reuse preset definitions without copying them.
4. Ranking is deterministic: mandatory, high, normal, and low priority, followed
   by stable set-selection order and definition ID.
5. Optional incompatible definitions are omitted with warnings. An incompatible
   mandatory definition is an error. A target that cannot safely represent
   transmit-disabled intent always emits an error rather than enabling TX.
6. Capability definitions are extracted from a pinned CHIRP driver. Only facts that
   `RadioFeatures` cannot express remain in sourced RigManifest overlays.
7. Factory frequency availability is modeled as a radio-model-to-preset-set
   relationship. It is never inferred by matching individual frequencies.
8. The VX-6R USA capability uses a conservative capacity of 900 advertised
   user memories. CHIRP exposes locations 1-999; the later capability adapter
   must model address bounds, reserved locations, and usable capacity
   separately before expanding this value.

## Technology choices

- Package layout: `src/rigmanifest`, split by domain, compiler, capabilities,
  exporters, fixtures, and CLI.
- Models: frozen, slotted dataclasses plus enums. Validation is performed at
  construction boundaries; no runtime modeling dependency is needed yet.
- Tests: pytest with small immutable fixtures.
- CLI: Typer, kept as a thin adapter over the same compiler API used elsewhere.
- Desktop IPC: newline-delimited JSON over a Tauri sidecar's stdin/stdout. It
  is local, inspectable, and avoids binding the compiler to HTTP or Tauri.
- Persistence: a versioned SQLite workspace stores the user-owned catalog
  partition, radio instances, reusable profiles, and advisory plan context. It supports a one-time
  legacy local-storage import and native backups, while every compile still submits
  the catalog partition to Python validation.
- CHIRP integration: a pinned headless dependency supplies normalized driver facts
  and final memory validation. CSV remains the first output boundary; direct radio
  programming is still deferred.

## Verified upstream constraints

- CHIRP's canonical CSV header and serialization behavior come from
  `chirp/chirp_common.py` in the official CHIRP repository.
- CHIRP's VX-6R driver reports modes FM/WFM/AM/NFM, a six-character label,
  banks, odd split, locations 1-999, and no `off` duplex representation.
- Yaesu documents wide-band receive, USA transmit ranges of 144-148,
  222-225, and 430-450 MHz, and 900 advertised memory channels.

## Delivery sequence

1. Domain types, shared frequency catalog, diagnostics, and capabilities.
2. A small `Home` set selection and USA VX-6R radio-model definition.
3. Pure deterministic compiler with omissions and transformations.
4. CHIRP CSV exporter.
5. `rigmanifest compile home --target yaesu-vx6r`.
6. Unit tests for compatibility, receive-only safety, label handling,
   capacity, ordering, diagnostics, grouping, and CSV output.
7. Freeze the JSON IPC contract, then add the smallest Svelte/Tauri screen.
8. Add local user-catalog authoring and pass the complete user partition through
   the validated IPC boundary during compilation.
