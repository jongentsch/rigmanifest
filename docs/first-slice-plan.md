# First Vertical Slice Plan

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
6. Capability definitions carry source notes. CHIRP-derived facts and
   RigManifest safety overlays remain distinguishable.
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
- Persistence: the first UI workflow keeps the user-owned catalog partition in
  local storage and submits it to Python validation for every compile. SQLite
  repository interfaces remain the next durability step.
- CHIRP integration: CSV only. Do not vendor or install CHIRP in the first
  slice. Keep the exporter isolated, then add an optional CHIRP capability
  adapter after the compiler contract is stable.

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
