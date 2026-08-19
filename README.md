# RigManifest

[![CI](https://github.com/jongentsch/rigmanifest/actions/workflows/ci.yml/badge.svg)](https://github.com/jongentsch/rigmanifest/actions/workflows/ci.yml)
[![Latest release](https://img.shields.io/github/v/release/jongentsch/rigmanifest)](https://github.com/jongentsch/rigmanifest/releases/latest)
[![GPLv3](https://img.shields.io/badge/license-GPLv3-blue.svg)](LICENSE)

**Build a reusable frequency library, describe what you want on a radio, and let
RigManifest and CHIRP turn that intent into a radio-specific image.**

![RigManifest compiled memory plan](docs/images/compile-plan.png)

RigManifest is a desktop configuration manager for programmable radios. It keeps
frequency definitions independent of any one radio, combines them into reusable
sets and profiles, and compiles those selections against the exact CHIRP driver and
capabilities detected from a radio image.

The result is a new CHIRP image with compatible memories and bank assignments, plus
an explanation of every rename, omission, warning, or degraded mapping. The source
image is never overwritten.

## Why RigManifest?

Traditional radio-programming tools begin with memory rows for one device.
RigManifest begins with operator intent:

- “Home” can combine local repeaters, calling frequencies, and NOAA.
- “Canada trip” can reuse some of the same sets and add trip-specific definitions.
- The same profile can compile differently for an HT, mobile, or non-bank radio.
- Band-plan guidance is visible but advisory; it never blocks compilation.
- Radio-specific limits come from CHIRP instead of a parallel hand-maintained model.

```text
Frequency definitions -> Sets -> Profiles --+
                                              +-> Compile -> New CHIRP IMG
CHIRP radio image -> Driver + capabilities --+              + diagnostics
```

## Download

Get the latest build from [GitHub Releases](https://github.com/jongentsch/rigmanifest/releases/latest):

| Platform | Package | Workspace behavior |
| --- | --- | --- |
| Windows x64 | Installer | Uses the normal per-user application-data directory |
| Windows x64 | Portable ZIP | Keeps the workspace in `data/` beside the application |
| Linux x86_64 | AppImage | Keeps the workspace in `data/` beside the AppImage |
| Debian/Ubuntu x86_64 | `.deb` package | Uses the normal per-user application-data directory |

macOS packages are not currently produced. The release bundles include the Python
runtime, RigManifest core, and pinned CHIRP dependency; users do not need a separate
development environment.

> RigManifest is early-release software. Keep the original image downloaded from
> your radio and verify a generated image in CHIRP before uploading it to hardware.

## Quick start

1. Download the radio with CHIRP and save its `.img` file.
2. Open **My radios**, choose **Add radio from IMG**, and select that image.
3. Review the imported frequency definitions, bank-backed sets, and profile.
4. Build or refine reusable sets in **Frequency library**.
5. Combine sets and individual definitions into profiles such as Home, Travel, or
   Emergency.
6. Open **Compile & export**, choose one radio and any combination of profiles, sets,
   and individual definitions, then compile.
7. Review diagnostics and export a new CHIRP image. Open it in CHIRP to upload it to
   the radio.

RigManifest does not currently clone directly to or from a radio. CHIRP remains the
hardware communication layer.

See the [Getting Started guide](docs/getting-started.md) for a complete first-run
walkthrough.

## The model

- A **frequency definition** describes target-independent RF intent: receive and
  transmit behavior, signaling, mode, step, label, and notes. It is not a radio
  channel or memory location.
- A **frequency set** is an ordered, reusable group of definitions. Imported radio
  banks become sets; built-in service presets are read-only sets.
- A **profile** combines any number of sets and individual definitions for a place,
  trip, or operating role.
- A **radio** begins with a CHIRP image. That image identifies the exact driver,
  available memories, banks, settings, and supported values.
- A **compile** combines one radio with zero or more profiles, extra sets, and extra
  definitions. Compatible intent becomes memories and bank mappings; incompatibilities
  are reported instead of silently coerced.

The [Concepts guide](docs/concepts.md) explains these boundaries and the relationship
between RigManifest and CHIRP.

## Documentation

- [Getting Started](docs/getting-started.md) — install, import a radio, compile, and export
- [User Guide](docs/user-guide.md) — page-by-page workflows with screenshots
- [Core Concepts](docs/concepts.md) — definitions, sets, profiles, banks, and images
- [Product Vision](docs/product-vision.md) — the problem and long-term direction
- [Architecture](docs/architecture.md) — desktop, compiler, persistence, and updater boundaries
- [CHIRP Integration](docs/chirp-integration.md) — driver, image, validation, and export strategy
- [Domain Model](docs/domain-model.md) — canonical entities and invariants
- [Compiler Design](docs/compiler-design.md) — deterministic selection and diagnostics
- [US Amateur Frequency Practices](docs/us-amateur-frequency-practices.md) — sourced advisory-plan notes
- [Desktop Development](desktop/README.md) — packaging, UI testing, and release details

## Development

Requirements: Python 3.12+, Node.js, pnpm, Rust, and the
[Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python -m pytest

cd desktop
pnpm install
pnpm check
pnpm tauri dev
```

Run the deterministic browser suite in Docker:

```bash
cd desktop
docker compose -f compose.ui-tests.yaml build
docker compose -f compose.ui-tests.yaml run --rm ui-tests
```

CI runs Python tests with branch coverage, frontend checks/builds, Dockerized
Playwright accessibility and visual tests, and Rust formatting, Clippy, and tests.
Native packages are built only for version tags.

## Project status

RigManifest is usable but still evolving. The current focus is reliable image-backed
radio inventory, maintainable frequency intent, bank-aware compilation, explainable
diagnostics, and safe public releases. Issues and focused pull requests are welcome.

CHIRP is an intentional upstream dependency and remains the authority for radio
drivers, image formats, target-memory validation, and device communication.

## License

RigManifest is licensed under the [GNU General Public License v3.0](LICENSE).
