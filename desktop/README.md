# RigManifest Desktop

This is the Svelte 5 + TypeScript interface and Tauri 2 shell for RigManifest.
The Rust command layer launches a Python JSON sidecar, keeping all compilation
and radio-capability semantics in the Python core. Development builds use the
repository environment; release builds use a frozen, installer-shipped sidecar.

## Development

Set up the Python environment from the repository root first. Then:

```bash
pnpm install
pnpm check
pnpm tauri dev
```

The desktop app uses `<repository>/.venv/Scripts/python.exe` on Windows and
`<repository>/.venv/bin/python` elsewhere. Set `RIGMANIFEST_PYTHON` to override
that executable.

The Appearance control in the sidebar supports Dark, Light, and System modes.
Dark is the first-run default, and the selected preference persists between
launches.

User catalog records, radio instances, reusable profiles, and advisory plan context persist in
`rigmanifest.sqlite3`. Installed builds use the platform application-data directory;
portable builds use a `data` directory beside the application. Existing webview
local-storage records are imported once on first open. Use **Back up workspace**
on the Frequency Library page to create a consistent SQLite copy.
`RIGMANIFEST_DATABASE` can override the database path for isolated native smoke tests.

## Desktop distribution bundles

After completing the development setup, build the sidecar and NSIS installer:

```powershell
pnpm bundle:windows
```

`scripts/build-portable.ps1` freezes RigManifest, the Python runtime, and the
pinned CHIRP package into a target-triple-suffixed sidecar, smoke-tests its JSON
catalog response, and then runs the Tauri release build. It produces both a
self-contained installer under `src-tauri/target/release/bundle/nsis` and a
portable ZIP under the repository's `dist/portable` directory. The ZIP contains
the app, sidecar, license, portable marker, instructions, and `data` directory.
The workspace database stays in that directory rather than platform app data.
Destination machines do not need Python, CHIRP, Node, or this repository.

To build and smoke-test only the frozen sidecar:

```powershell
pnpm sidecar:windows
```

On Linux x64, build a Debian package and AppImage:

```bash
pnpm bundle:linux
```

The build freezes a native Linux sidecar and writes consistently named packages
under `dist/linux`. The Debian package uses the normal platform application-data
directory. AppImage sets its absolute source path at runtime; RigManifest uses
that location to keep its workspace in a sibling `data` directory. After
downloading an AppImage, make it executable with `chmod +x RigManifest_*.AppImage`.

On macOS, build a native application bundle and DMG for the host architecture:

```bash
pnpm bundle:macos
```

The macOS build freezes a native sidecar, smoke-tests it, and ad-hoc signs the
application with the `-` identity. This does not use an Apple account and does not
notarize the application. A downloaded build requires one-time approval in macOS
**System Settings > Privacy & Security** before it can launch.

Tagged releases build Windows, Linux, Apple Silicon, and Intel macOS packages on
native runners and publish the distributions, updater signatures, `latest.json`, and
`SHA256SUMS.txt` in one GitHub Release.

## Application updates

RigManifest checks the latest public GitHub Release at startup at most once every
24 hours unless the user disables automatic checks in Settings. Installed Windows,
macOS, and AppImage builds can download and install a signature-verified update after
user approval. Portable Windows and Debian builds are notification-only because
replacing those distributions safely is outside Tauri's native updater path. Every
in-app installation creates a consistent workspace backup first.

Tauri updater signatures are distinct from Windows Authenticode signing. Release
builds require these GitHub Actions secrets:

- `TAURI_SIGNING_PRIVATE_KEY`
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`

Ordinary `bundle:windows`, `bundle:linux`, and `bundle:macos` builds never read updater
signing files and do not create updater signatures. Only the tagged-release workflow
calls the explicit `bundle:windows:release`, `bundle:linux:release`, and
`bundle:macos:release` commands. Those commands fail closed when either GitHub Actions
secret is unavailable; they never generate or rotate keys. Never commit the backup
files. Losing the key or password prevents future releases from updating existing
installations.

## Verification

```bash
pnpm check
pnpm build
docker compose -f compose.ui-tests.yaml build
docker compose -f compose.ui-tests.yaml run --rm ui-tests
cd src-tauri
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

The Playwright suite runs the Svelte renderer in the pinned Chromium build from
`mcr.microsoft.com/playwright:v1.62.0-noble`. A deterministic UI-test adapter
stands in for the Tauri command and save-dialog boundary. The suite covers the
compiled multi-profile selection, profile/catalog persistence and backup contract, export flow,
update preferences, Dark/Light/System behavior, Axe accessibility, and Dark and Light visual snapshots.

Refresh the checked-in Linux snapshots only after intentionally reviewing a UI
change:

```bash
docker compose -f compose.ui-tests.yaml run --rm ui-tests pnpm test:ui:update
```

These tests cover the renderer and its contract with the desktop boundary;
they do not replace native Tauri/WebDriver smoke tests for windowing or dialogs.
The platform build scripts and tagged-release workflow exercise the frozen Python
sidecars and build the native packages. Push and pull-request CI runs the test
suites without spending time on distribution packaging.
