"""Versioned SQLite persistence for the local desktop workspace."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from rigmanifest.catalog_io import catalog_with_user_records
from rigmanifest.fixtures import BUILTIN_CATALOG, BUILTIN_PROFILES


SCHEMA_VERSION = 1


def default_workspace_state() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "user_catalog": {
            "frequencyDefinitions": [],
            "frequencySets": [],
        },
        "radios": [
            {
                "id": "default-vx6r",
                "name": "My VX-6R",
                "radioModelId": "yaesu-vx6r",
                "memoryStart": 1,
                "mapSetsToBanks": True,
                "notes": "",
            }
        ],
        "profile_plan_ids": {
            profile.id: profile.frequency_plan_id
            for profile in BUILTIN_PROFILES.values()
        },
    }


class SQLiteWorkspace:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, legacy_state: Mapping[str, object] | None = None) -> dict[str, Any]:
        with self._connect() as connection:
            self._migrate(connection)
            rows = dict(connection.execute("SELECT key, value_json FROM workspace_state"))
            migrated_legacy = not rows and legacy_state is not None
            state = (
                _validate_state(legacy_state)
                if migrated_legacy
                else _state_from_rows(rows)
            )
            if not rows:
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
        with self._connect() as source, sqlite3.connect(destination) as target:
            self._migrate(source)
            source.commit()
            source.backup(target)
        return destination

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
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
            "INSERT OR IGNORE INTO schema_migrations(version) VALUES (?)",
            (SCHEMA_VERSION,),
        )

    @staticmethod
    def _write(connection: sqlite3.Connection, state: Mapping[str, object]) -> None:
        values = {
            "user_catalog": state["user_catalog"],
            "radios": state["radios"],
            "profile_plan_ids": state["profile_plan_ids"],
        }
        connection.execute("DELETE FROM workspace_state")
        connection.executemany(
            "INSERT INTO workspace_state(key, value_json) VALUES (?, ?)",
            [(key, json.dumps(value, separators=(",", ":"))) for key, value in values.items()],
        )


def _state_from_rows(rows: Mapping[str, str]) -> dict[str, Any]:
    if not rows:
        return default_workspace_state()
    try:
        candidate = {
            "schema_version": SCHEMA_VERSION,
            "user_catalog": json.loads(rows["user_catalog"]),
            "radios": json.loads(rows["radios"]),
            "profile_plan_ids": json.loads(rows["profile_plan_ids"]),
        }
    except (KeyError, json.JSONDecodeError) as error:
        raise ValueError(f"workspace database contains invalid state: {error}") from error
    return _validate_state(candidate)


def _validate_state(state: Mapping[str, object]) -> dict[str, Any]:
    user_catalog = state.get("user_catalog")
    radios = state.get("radios")
    plan_ids = state.get("profile_plan_ids")
    if not isinstance(user_catalog, Mapping):
        raise ValueError("workspace user_catalog must be an object")
    definitions = user_catalog.get("frequencyDefinitions")
    sets = user_catalog.get("frequencySets")
    if not isinstance(definitions, list) or not isinstance(sets, list):
        raise ValueError("workspace user catalog arrays are required")
    if not all(isinstance(item, Mapping) for item in definitions + sets):
        raise ValueError("workspace user catalog records must be objects")
    catalog_with_user_records(BUILTIN_CATALOG, definitions, sets)
    if not isinstance(radios, list) or not radios or not all(_valid_radio(item) for item in radios):
        raise ValueError("workspace radios must be a non-empty valid array")
    if not isinstance(plan_ids, Mapping) or not all(
        isinstance(key, str) and isinstance(value, str) and value
        for key, value in plan_ids.items()
    ):
        raise ValueError("workspace profile plan preferences must be string mappings")
    return {
        "schema_version": SCHEMA_VERSION,
        "user_catalog": {"frequencyDefinitions": definitions, "frequencySets": sets},
        "radios": radios,
        "profile_plan_ids": dict(plan_ids),
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
