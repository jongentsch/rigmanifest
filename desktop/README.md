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

## Verification

```bash
pnpm check
pnpm build
cd src-tauri
cargo fmt --check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

Packaging the Python compiler as a distributable Tauri sidecar is deliberately
deferred. The current desktop build is a source-tree development slice.
