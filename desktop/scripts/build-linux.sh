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
linux_dist="$repository_root/dist/linux"
release_build=false

if [[ "${1:-}" == "--release" ]]; then
    release_build=true
elif [[ $# -gt 0 ]]; then
    echo "Usage: $0 [--release]" >&2
    exit 2
fi

if [[ "$release_build" == true \
    && ( -z "${TAURI_SIGNING_PRIVATE_KEY:-}" \
      || -z "${TAURI_SIGNING_PRIVATE_KEY_PASSWORD:-}" ) ]]; then
    echo "Signed release builds require the Tauri signing environment variables." >&2
    exit 1
fi

if [[ ! -x "$python" ]]; then
    echo "Python environment not found at $python. Run the repository setup steps first." >&2
    exit 1
fi

target_triple="$(rustc --print host-tuple)"
if [[ -z "$target_triple" ]]; then
    echo "rustc did not return a host target triple." >&2
    exit 1
fi

mkdir -p "$sidecar_dist" "$sidecar_work" "$binary_directory" "$linux_dist"

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

smoke_response="$(printf '%s\n' '{"id":"portable-smoke","method":"catalog"}' | "$tauri_sidecar" --once)"
printf '%s' "$smoke_response" | "$python" -c '
import json
import sys

payload = json.load(sys.stdin)
if payload.get("id") != "portable-smoke" or not payload.get("result", {}).get("schema_version"):
    raise SystemExit(f"Frozen sidecar smoke test returned an invalid response: {payload!r}")
'

tauri_config="src-tauri/tauri.portable.conf.json"
if [[ "$release_build" == true ]]; then
    tauri_config="src-tauri/tauri.release.conf.json"
fi

(
    cd "$desktop_root"
    pnpm tauri build --config "$tauri_config" --bundles deb,appimage
)

version="$("$python" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["version"])' "$desktop_root/src-tauri/tauri.conf.json")"
deb_package="$(find "$desktop_root/src-tauri/target/release/bundle/deb" -maxdepth 1 -type f -name '*.deb' -print -quit)"
appimage_package="$(find "$desktop_root/src-tauri/target/release/bundle/appimage" -maxdepth 1 -type f -name '*.AppImage' -print -quit)"
appimage_signature="${appimage_package}.sig"

if [[ -z "$deb_package" || -z "$appimage_package" ]]; then
    echo "Tauri did not produce both Debian and AppImage packages." >&2
    exit 1
fi

if [[ "$release_build" == true && ! -f "$appimage_signature" ]]; then
    echo "Tauri did not produce the AppImage updater signature." >&2
    exit 1
fi

cp "$deb_package" "$linux_dist/RigManifest_${version}_amd64.deb"
cp "$appimage_package" "$linux_dist/RigManifest_${version}_x86_64.AppImage"
if [[ "$release_build" == true ]]; then
    cp "$appimage_signature" "$linux_dist/RigManifest_${version}_x86_64.AppImage.sig"
else
    rm -f "${deb_package}.sig" "$appimage_signature"
    rm -f "$linux_dist/RigManifest_${version}_x86_64.AppImage.sig"
fi

echo "Linux packages ready in $linux_dist"
