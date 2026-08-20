#!/usr/bin/env bash
set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repository_root="$(cd "$script_directory/../.." && pwd)"
desktop_root="$repository_root/desktop"
python="$repository_root/.venv/bin/python"
sidecar_dist="$repository_root/dist/sidecar"
sidecar_work="$repository_root/build/sidecar"
sidecar_source="$repository_root/src/rigmanifest/sidecar.py"
binary_directory="$desktop_root/src-tauri/binaries"
macos_dist="$repository_root/dist/macos"
release_build=false

if [[ "${1:-}" == "--release" ]]; then
    release_build=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--release]" >&2
    exit 2
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "macOS packages must be built on macOS." >&2
    exit 1
fi

if [[ "$release_build" == true \
    && ( -z "${TAURI_SIGNING_PRIVATE_KEY:-}" \
      || -z "${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}" ) ]]; then
    echo "Release builds require the Tauri updater signing environment variables." >&2
    exit 1
fi

if [[ ! -x "$python" ]]; then
    echo "Python environment not found at $python. Run the repository setup steps first." >&2
    exit 1
fi

target_triple="$(rustc --print host-tuple)"
case "$target_triple" in
    aarch64-apple-darwin)
        artifact_architecture="aarch64"
        ;;
    x86_64-apple-darwin)
        artifact_architecture="x64"
        ;;
    *)
        echo "Unsupported macOS build target: $target_triple" >&2
        exit 1
        ;;
esac

mkdir -p "$sidecar_dist" "$sidecar_work" "$binary_directory" "$macos_dist"

"$python" -m PyInstaller \
    --noconfirm \
    --clean \
    --onefile \
    --name rigmanifest-sidecar \
    --paths "$repository_root/src" \
    --collect-submodules chirp.drivers \
    --collect-data chirp \
    --copy-metadata chirp \
    --distpath "$sidecar_dist" \
    --workpath "$sidecar_work" \
    --specpath "$sidecar_work" \
    "$sidecar_source"

tauri_sidecar="$binary_directory/rigmanifest-sidecar-$target_triple"
cp "$sidecar_dist/rigmanifest-sidecar" "$tauri_sidecar"
chmod +x "$tauri_sidecar"

smoke_response="$(printf '%s\n' '{"id":"macos-smoke","method":"chirp_runtime_status","params":{"required_driver_references":["Quansheng_UV-K5_egzumer"]}}' | "$tauri_sidecar" --once)"
printf '%s' "$smoke_response" | "$python" -c '
import json
import sys

payload = json.load(sys.stdin)
result = payload.get("result", {})
if (payload.get("id") != "macos-smoke"
        or result.get("registered_driver_count", 0) < 100
        or not result.get("translations_ready")
        or result.get("missing_driver_references")):
    raise SystemExit(f"Frozen sidecar smoke test returned an invalid response: {payload!r}")
'

tauri_config="src-tauri/tauri.portable.conf.json"
if [[ "$release_build" == true ]]; then
    tauri_config="src-tauri/tauri.release.conf.json"
fi

# Apple Silicon requires a code signature. The '-' identity creates a local ad-hoc
# signature without an Apple account; Gatekeeper will still require user approval.
(
    cd "$desktop_root"
    APPLE_SIGNING_IDENTITY="-" pnpm tauri build \
        --config "$tauri_config" \
        --bundles app,dmg
)

version="$("$python" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$desktop_root/src-tauri/tauri.conf.json")"
bundle_root="$desktop_root/src-tauri/target/release/bundle"
app_bundle="$bundle_root/macos/RigManifest.app"
dmg_package="$(find "$bundle_root/dmg" -maxdepth 1 -type f -name '*.dmg' -print -quit)"
updater_archive="$(find "$bundle_root/macos" -maxdepth 1 -type f -name '*.app.tar.gz' -print -quit)"

if [[ ! -d "$app_bundle" || -z "$dmg_package" ]]; then
    echo "Tauri did not produce both the macOS application and DMG." >&2
    exit 1
fi

codesign --verify --deep --strict "$app_bundle"

dmg_destination="$macos_dist/RigManifest_${version}_${artifact_architecture}_unsigned.dmg"
cp "$dmg_package" "$dmg_destination"

if [[ "$release_build" == true ]]; then
    if [[ -z "$updater_archive" || ! -f "${updater_archive}.sig" ]]; then
        echo "Tauri did not produce the macOS updater archive and signature." >&2
        exit 1
    fi
    updater_destination="$macos_dist/RigManifest_${version}_${artifact_architecture}.app.tar.gz"
    cp "$updater_archive" "$updater_destination"
    cp "${updater_archive}.sig" "${updater_destination}.sig"
else
    rm -f "$macos_dist/RigManifest_${version}_${artifact_architecture}.app.tar.gz" \
        "$macos_dist/RigManifest_${version}_${artifact_architecture}.app.tar.gz.sig"
fi

echo "Unsigned macOS $artifact_architecture packages ready in $macos_dist"
