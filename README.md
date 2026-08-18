# RigManifest

**Define your radio configuration once. Compile it for every rig.**

RigManifest is an open-source configuration-management application for programmable amateur radios.

Traditional radio-programming software starts with the destination radio:

> Edit memories 1–100 for this particular device.

RigManifest starts with operator intent:

> Include my local repeaters, NOAA weather, common simplex channels, and selected receive-only frequencies.

That intent is compiled for each radio according to its capabilities.

```text
Channel Library
      +
Profiles / Intent
      +
Radio Capabilities
      ↓
RigManifest Compiler
      ↓
Radio-specific plan
      ↓
CHIRP CSV
      ↓
CHIRP
      ↓
Radio
```

## Why

CHIRP is generally good at programming radios.

The frustrating part is everything before that:

- deciding what belongs in each radio
- keeping multiple radios consistent
- handling different memory capacities
- adapting labels
- dealing with different receive/transmit ranges
- managing banks or the lack of them
- maintaining home, travel, emergency, and other reusable profiles
- understanding why two radios end up with different configurations

RigManifest focuses on that layer.

## Initial architecture

```text
Python Core
├── compiler
├── domain model
├── CHIRP integration
├── CSV import/export
└── CLI

        ↕

Svelte + TypeScript

        ↓

Tauri desktop shell
```

The UI is deliberately separate from the compiler.

## Initial target radios

- Yaesu VX-6R
- Quansheng UV-K5
- Retevis RT95
- Alervites AT2 later

## Initial CLI direction

```bash
rigmanifest compile home --target yaesu-vx6r
rigmanifest compile home --target quansheng-uvk5
rigmanifest compile home --target retevis-rt95
```

## Development

The first executable slice currently includes:

- immutable typed domain models
- deterministic profile compilation
- structured diagnostics and omissions
- a conservative USA Yaesu VX-6R capability definition
- CHIRP-compatible CSV export
- the `home` in-memory fixture
- a Typer CLI
- a versioned newline-delimited JSON sidecar boundary for the future desktop UI

Set up the Python project and run its tests:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest
```

Exercise the first CLI path:

```bash
rigmanifest compile home --target yaesu-vx6r --output home-yaesu-vx6r.csv
```

The sample profile intentionally includes a receive-only NOAA channel. The
current VX-6R capability overlay omits it with an error because CHIRP's VX-6R
driver does not expose a safe transmit-disable representation. The CSV is
still written for the three safe memories, and the command exits with status
1 so the safety degradation cannot be missed.

See `docs/first-slice-plan.md` for the architecture decisions and delivery
sequence.

## License

RigManifest is intended to be released under GPLv3-compatible terms.

CHIRP is an intentional upstream dependency.

## Status

Early first-slice implementation.

Read `AGENTS.md` and the `docs/` directory before implementation.
