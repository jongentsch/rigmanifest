from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_release_versions_are_synchronized() -> None:
    with (ROOT / "pyproject.toml").open("rb") as source:
        python_version = tomllib.load(source)["project"]["version"]
    package_version = json.loads(
        (ROOT / "desktop" / "package.json").read_text(encoding="utf-8")
    )["version"]
    tauri_version = json.loads(
        (ROOT / "desktop" / "src-tauri" / "tauri.conf.json").read_text(
            encoding="utf-8"
        )
    )["version"]
    cargo_manifest = (ROOT / "desktop" / "src-tauri" / "Cargo.toml").read_text(
        encoding="utf-8"
    )
    cargo_version = re.search(
        r'^version\s*=\s*"([^"]+)"', cargo_manifest, re.MULTILINE
    )

    assert cargo_version is not None
    assert {
        python_version,
        package_version,
        tauri_version,
        cargo_version.group(1),
    } == {"0.1.3"}
