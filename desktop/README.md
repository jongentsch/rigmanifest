# RigManifest Desktop

This is the Svelte 5 + TypeScript interface and Tauri 2 shell for RigManifest.
The Rust command layer launches the repository's Python JSON sidecar, keeping
all compilation and radio-capability semantics in the Python core.

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

User catalog records, radio instances, and profile plan preferences persist in
`rigmanifest.sqlite3` under the platform application-data directory. Existing
webview local-storage records are imported once on first open. Use **Back up
workspace** on the Frequency Library page to create a consistent SQLite copy.
`RIGMANIFEST_DATABASE` can override the database path for isolated native smoke
tests.

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
compiled plan, catalog persistence and backup contract, export flow,
Dark/Light/System behavior, Axe accessibility, and Dark and Light visual snapshots.

Refresh the checked-in Linux snapshots only after intentionally reviewing a UI
change:

```bash
docker compose -f compose.ui-tests.yaml run --rm ui-tests pnpm test:ui:update
```

These tests cover the renderer and its contract with the desktop boundary;
they do not replace native Tauri/WebDriver smoke tests for windowing, dialogs,
or the Python sidecar process.

Packaging the Python compiler as a distributable Tauri sidecar is deliberately
deferred. The current desktop build is a source-tree development slice.
