"""Versioned SQLite persistence for the local desktop workspace."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from rigmanifest.catalog_io import catalog_with_user_records
from rigmanifest.fixtures import BUILTIN_CATALOG, BUILTIN_PROFILES
from rigmanifest.frequency_plans import BUILTIN_FREQUENCY_PLANS
from rigmanifest.profile_io import profile_to_dict, profiles_from_records


SCHEMA_VERSION = 3


@dataclass(frozen=True, slots=True)
class RadioImageVersion:
    id: str
    radio_id: str
    kind: str
    path: Path
    filename: str
    driver_reference: str
    byte_size: int
    sha256: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "radio_id": self.radio_id,
            "kind": self.kind,
            "path": str(self.path),
            "filename": self.filename,
            "driver_reference": self.driver_reference,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "created_at": self.created_at,
        }


def default_workspace_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "user_catalog": {
            "frequencyDefinitions": [],
            "frequencySets": [],
        },
        "radios": [],
        "profiles": [],
        "default_frequency_plan_id": "arrl-us-national",
    }


class SQLiteWorkspace:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, legacy_state: Mapping[str, object] | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            self._migrate(connection)
            rows = dict(connection.execute("SELECT key, value_json FROM workspace_state"))
            needs_rewrite = bool(rows) and (
                "profiles" not in rows or "default_frequency_plan_id" not in rows
            )
            migrated_legacy = not rows and legacy_state is not None
            state = (
                _validate_state(legacy_state)
                if migrated_legacy
                else _state_from_rows(rows)
            )
            if not rows or needs_rewrite:
                self._write(connection, state)
            return {**state, "migrated_legacy": migrated_legacy}

    def save(self, state: Mapping[str, object]) -> dict[str, Any]:
        validated = _validate_state(state)
        with self._connect() as connection:
            self._migrate(connection)
            self._write(connection, validated)
        return validated

    def backup(self, destination: Path) -> Path:
        if destination.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from the workspace database")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination_workspace = SQLiteWorkspace(destination)
        with self._connect() as source, destination_workspace._connect() as target:
            self._migrate(source)
            source.commit()
            source.backup(target)
        backup_radios = destination.parent / "radios"
        if (
            self.radios_directory.is_dir()
            and backup_radios.resolve() != self.radios_directory.resolve()
        ):
            shutil.copytree(
                self.radios_directory,
                backup_radios,
                dirs_exist_ok=True,
            )
        return destination

    @property
    def radios_directory(self) -> Path:
        return self.path.parent / "radios"

    def store_radio_image(
        self,
        radio_id: str,
        image: bytes,
        *,
        original_filename: str,
        driver_reference: str,
        kind: str = "source",
    ) -> RadioImageVersion:
        """Store an immutable image version on disk and track it in SQLite."""

        if not radio_id or not image or not original_filename or not driver_reference:
            raise ValueError("radio image metadata must not be blank")
        if kind not in {"source", "compiled"}:
            raise ValueError("radio image kind must be source or compiled")
        version_id = str(uuid4())
        stored_filename = f"{kind}-{version_id}.img"
        relative_path = Path("radios") / _safe_segment(radio_id) / stored_filename
        absolute_path = self.path.parent / relative_path
        _atomic_write(absolute_path, image)
        try:
            with self._connect() as connection:
                self._migrate(connection)
                connection.execute(
                    "INSERT INTO radio_image_versions("
                    "id, radio_id, kind, relative_path, display_filename, "
                    "driver_reference, byte_size, sha256"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        version_id,
                        radio_id,
                        kind,
                        relative_path.as_posix(),
                        Path(original_filename).name,
                        driver_reference,
                        len(image),
                        hashlib.sha256(image).hexdigest(),
                    ),
                )
        except Exception:
            absolute_path.unlink(missing_ok=True)
            raise
        return self.radio_image_version(version_id)

    def radio_image(self, radio_id: str) -> bytes:
        return self.radio_image_path(radio_id).read_bytes()

    def radio_image_path(self, radio_id: str) -> Path:
        with self._connect() as connection:
            self._migrate(connection)
            row = connection.execute(
                "SELECT relative_path FROM radio_image_versions "
                "WHERE radio_id = ? AND kind = 'source' "
                "ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (radio_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"radio {radio_id} does not have an imported image")
        path = self.path.parent / Path(row[0])
        if not path.is_file():
            raise ValueError(f"stored source image for radio {radio_id} is missing")
        return path

    def radio_image_version(self, version_id: str) -> RadioImageVersion:
        with self._connect() as connection:
            self._migrate(connection)
            row = connection.execute(
                "SELECT id, radio_id, kind, relative_path, display_filename, "
                "driver_reference, byte_size, sha256, created_at "
                "FROM radio_image_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"unknown radio image version: {version_id}")
        return self._version_from_row(row)

    def radio_image_versions(self, radio_id: str) -> tuple[RadioImageVersion, ...]:
        with self._connect() as connection:
            self._migrate(connection)
            rows = connection.execute(
                "SELECT id, radio_id, kind, relative_path, display_filename, "
                "driver_reference, byte_size, sha256, created_at "
                "FROM radio_image_versions WHERE radio_id = ? "
                "ORDER BY created_at DESC, rowid DESC",
                (radio_id,),
            ).fetchall()
        return tuple(self._version_from_row(row) for row in rows)

    def _version_from_row(self, row: tuple[object, ...]) -> RadioImageVersion:
        return RadioImageVersion(
            id=str(row[0]),
            radio_id=str(row[1]),
            kind=str(row[2]),
            path=self.path.parent / Path(str(row[3])),
            filename=str(row[4]),
            driver_reference=str(row[5]),
            byte_size=int(row[6]),
            sha256=str(row[7]),
            created_at=str(row[8]),
        )

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _migrate(self, connection: sqlite3.Connection) -> None:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        newest_version = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
        if newest_version is not None and newest_version > SCHEMA_VERSION:
            raise ValueError(
                f"workspace schema {newest_version} is newer than supported schema {SCHEMA_VERSION}"
            )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS workspace_state ("
            "key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS radio_image_versions ("
            "id TEXT PRIMARY KEY, "
            "radio_id TEXT NOT NULL, "
            "kind TEXT NOT NULL CHECK(kind IN ('source', 'compiled')), "
            "relative_path TEXT NOT NULL UNIQUE, "
            "display_filename TEXT NOT NULL, "
            "driver_reference TEXT NOT NULL, "
            "byte_size INTEGER NOT NULL, "
            "sha256 TEXT NOT NULL, "
            "created_at TEXT NOT NULL DEFAULT "
            "(strftime('%Y-%m-%dT%H:%M:%fZ', 'now')))"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS radio_image_versions_by_radio "
            "ON radio_image_versions(radio_id, created_at DESC)"
        )
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

    def _write(self, connection: sqlite3.Connection, state: Mapping[str, object]) -> None:
        values = {
            "user_catalog": state["user_catalog"],
            "radios": state["radios"],
            "profiles": state["profiles"],
            "default_frequency_plan_id": state["default_frequency_plan_id"],
        }
        connection.execute("DELETE FROM workspace_state")
        connection.executemany(
            "INSERT INTO workspace_state(key, value_json) VALUES (?, ?)",
            [(key, json.dumps(value, separators=(",", ":"))) for key, value in values.items()],
        )
        radio_ids = [str(item["id"]) for item in state["radios"]]  # type: ignore[index]
        tracked_ids = {
            str(row[0])
            for row in connection.execute("SELECT DISTINCT radio_id FROM radio_image_versions")
        }
        removed_ids = tracked_ids - set(radio_ids)
        if radio_ids:
            placeholders = ",".join("?" for _ in radio_ids)
            connection.execute(
                f"DELETE FROM radio_image_versions WHERE radio_id NOT IN ({placeholders})",
                radio_ids,
            )
        else:
            connection.execute("DELETE FROM radio_image_versions")
        for radio_id in removed_ids:
            directory = self.radios_directory / _safe_segment(radio_id)
            if directory.is_dir():
                shutil.rmtree(directory)


def _state_from_rows(rows: Mapping[str, str]) -> dict[str, Any]:
    if not rows:
        return default_workspace_state()
    try:
        profiles_json = rows.get("profiles")
        if profiles_json is None:
            legacy_plan_ids = json.loads(rows.get("profile_plan_ids", "{}"))
            profiles = [
                {
                    **profile_to_dict(profile),
                    "frequency_plan_id": legacy_plan_ids.get(
                        profile.id,
                        profile.frequency_plan_id,
                    ),
                }
                for profile in BUILTIN_PROFILES.values()
            ]
        else:
            profiles = json.loads(profiles_json)
        default_plan_json = rows.get("default_frequency_plan_id")
        candidate = {
            "schema_version": SCHEMA_VERSION,
            "user_catalog": json.loads(rows["user_catalog"]),
            "radios": json.loads(rows["radios"]),
            "profiles": profiles,
            "default_frequency_plan_id": (
                json.loads(default_plan_json)
                if default_plan_json is not None
                else "arrl-us-national"
            ),
        }
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"workspace database contains invalid state: {error}") from error
    return _validate_state(candidate)


def _validate_state(state: Mapping[str, object]) -> dict[str, Any]:
    user_catalog = state.get("user_catalog")
    radios = state.get("radios")
    profiles = state.get("profiles")
    default_plan_id = state.get("default_frequency_plan_id")
    if not isinstance(user_catalog, Mapping):
        raise ValueError("workspace user_catalog must be an object")
    definitions = user_catalog.get("frequencyDefinitions")
    sets = user_catalog.get("frequencySets")
    if not isinstance(definitions, list) or not isinstance(sets, list):
        raise ValueError("workspace user catalog arrays are required")
    if not all(isinstance(item, Mapping) for item in definitions + sets):
        raise ValueError("workspace user catalog records must be objects")
    catalog = catalog_with_user_records(BUILTIN_CATALOG, definitions, sets)
    if not isinstance(radios, list) or not all(_valid_radio(item) for item in radios):
        raise ValueError("workspace radios must be a valid array")
    if not isinstance(profiles, list) or not all(
        isinstance(item, Mapping) for item in profiles
    ):
        raise ValueError("workspace profiles must be an object array")
    parsed_profiles = profiles_from_records(profiles, catalog)
    if default_plan_id is not None and (
        not isinstance(default_plan_id, str)
        or default_plan_id not in BUILTIN_FREQUENCY_PLANS
    ):
        raise ValueError("workspace default frequency plan must reference a known plan")
    return {
        "schema_version": SCHEMA_VERSION,
        "user_catalog": {"frequencyDefinitions": definitions, "frequencySets": sets},
        "radios": radios,
        "profiles": [profile_to_dict(profile) for profile in parsed_profiles],
        "default_frequency_plan_id": default_plan_id,
    }


def _valid_radio(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    memory_start = value.get("memoryStart")
    return (
        all(isinstance(value.get(key), str) for key in ("id", "name", "radioModelId", "notes"))
        and isinstance(memory_start, int)
        and not isinstance(memory_start, bool)
        and memory_start >= 0
        and isinstance(value.get("mapSetsToBanks"), bool)
    )


def _safe_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", value).strip(".")
    if not cleaned:
        cleaned = "radio"
    if cleaned != value:
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
        cleaned = f"{cleaned}-{digest}"
    return cleaned


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{uuid4().hex}.tmp")
    try:
        temporary.write_bytes(payload)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
