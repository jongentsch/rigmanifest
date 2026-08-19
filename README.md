# RigManifest

[![CI](https://github.com/jongentsch/rigmanifest/actions/workflows/ci.yml/badge.svg)](https://github.com/jongentsch/rigmanifest/actions/workflows/ci.yml)

**Define your radio configuration once. Compile it for every rig.**

RigManifest is an open-source configuration-management application for programmable amateur radios.

> **RigManifest is an easy-to-use configuration-management frontend for CHIRP,
> built around reusable RF intent rather than individual radio-memory spreadsheets.**

CHIRP supplies the radio-driver knowledge and target validation. RigManifest supplies
the frequency library, reusable sets, profiles, radio inventory, compilation policy,
and explanations needed to maintain multiple radios coherently.

Traditional radio-programming software starts with the destination radio:

> Edit memories 1–100 for this particular device.

RigManifest starts with operator intent:

> Include my local repeaters set, the NOAA preset set, and my common simplex set.

That intent is compiled for each radio according to its capabilities.

```text
Shared Frequency Catalog
      +
Frequency Sets
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

CHIRP is the hardware engine and is generally good at programming radios.

The frustrating part is everything before that:

- deciding what belongs in each radio
- keeping multiple radios consistent
- handling different memory capacities
- adapting labels
- dealing with different receive/transmit ranges
- managing banks or the lack of them
- maintaining home, travel, emergency, and other reusable frequency sets
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

- immutable typed frequency-definition, set, radio-model, and plan models
- deterministic profile compilation
- structured diagnostics and omissions
- a pinned, headless CHIRP dependency and capability adapter
- a USA Yaesu VX-6R target composed from CHIRP facts and sourced overlays
- CHIRP-compatible CSV export
- sourced read-only US FRS, GMRS, MURS, Citizens Band, aviation-guard, and
  regulated 60-meter discrete-frequency sets
- the `home` in-memory fixture
- a Typer CLI
- a versioned newline-delimited JSON sidecar boundary
- a minimal Svelte 5 + Tauri 2 desktop UI for compiling, reviewing diagnostics,
  and exporting CHIRP CSV files
- a dark-first Modern Workshop interface with persistent Dark, Light, and
  System appearance modes
- versioned SQLite persistence for user-owned frequency definitions, sets,
  reusable profiles, radio instances, and advisory plan context, with first-run
  local-storage migration and native database backups
- Dockerized Playwright coverage for compile/export behavior, appearance
  modes, accessibility, and visual regressions

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

Run the desktop app after completing the Python setup and installing the
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/):

```bash
cd desktop
pnpm install
pnpm tauri dev
```

Run the deterministic renderer-level UI suite in Docker:

```bash
cd desktop
docker compose -f compose.ui-tests.yaml build
docker compose -f compose.ui-tests.yaml run --rm ui-tests
```

The test image includes its own pinned Chromium runtime, so no host browser
setup is required. See `desktop/README.md` for test scope and snapshot updates.

The desktop shell calls the same Python compiler through the JSON sidecar. In
this first source-based slice it expects the repository's `.venv` by default;
set `RIGMANIFEST_PYTHON` to use another Python executable.

The sample profile selects a user-owned `Home essentials` set and the read-only
`US NOAA Weather Broadcasts` preset. The VX-6R radio model references the NOAA
set as its factory `WX CH` set, so those definitions are reported separately
and do not consume programmable memories or appear in the CHIRP CSV. Current
CHIRP editing support for that factory set is explicitly recorded as unsupported.

User-owned catalog records, radio instances, reusable profiles, and the default
compile-time plan context are
stored in a versioned SQLite database under the platform application-data
directory. A first run imports the earlier webview local-storage records once;
the Library page can write a consistent native SQLite backup. Every compile
request still sends the user catalog partition through the Python validation
boundary and combines it with the immutable built-in preset partition.

A compile selection is one radio plus zero or more profiles, additional sets, and
additional individual frequency definitions. Profiles may themselves reference
many sets and many individual definitions. Profile and compile-wide band plans add
sourced warnings only; they never block compilation or remove a compatible memory.

Frequency definitions are not restricted to the bands supported by the current radio
inventory. A user may keep HF, VHF, UHF, or receive-only definitions in the shared
catalog; compilation omits anything the selected target cannot safely represent and
reports the reason.

See `docs/first-slice-plan.md` for the architecture decisions and delivery
sequence.

## License

RigManifest is licensed under the GNU General Public License v3.0.

CHIRP is an intentional upstream dependency.

## Status

Early first-slice implementation.

Read `AGENTS.md` and the `docs/` directory before implementation.
