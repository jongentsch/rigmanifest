from __future__ import annotations

import sqlite3

import pytest

from rigmanifest.workspace import SQLiteWorkspace, default_workspace_state


def test_workspace_initializes_and_round_trips_state(tmp_path) -> None:
    database = tmp_path / "workspace.sqlite3"
    workspace = SQLiteWorkspace(database)

    initial = workspace.load()
    assert initial["radios"][0]["radioModelId"] == "yaesu-vx6r"
    assert initial["migrated_legacy"] is False

    state = default_workspace_state()
    state["radios"][0]["name"] = "Desk radio"
    state["profile_plan_ids"]["home"] = "kansas-repeater-council"
    workspace.save(state)

    reloaded = workspace.load()
    assert reloaded["radios"][0]["name"] == "Desk radio"
    assert reloaded["profile_plan_ids"]["home"] == "kansas-repeater-council"

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT version FROM schema_migrations").fetchone() == (1,)


def test_first_open_imports_legacy_state_only_once(tmp_path) -> None:
    workspace = SQLiteWorkspace(tmp_path / "workspace.sqlite3")
    legacy = default_workspace_state()
    legacy["radios"][0]["name"] = "Migrated radio"

    first = workspace.load(legacy)
    replacement = default_workspace_state()
    replacement["radios"][0]["name"] = "Ignored later legacy"
    second = workspace.load(replacement)

    assert first["migrated_legacy"] is True
    assert second["migrated_legacy"] is False
    assert second["radios"][0]["name"] == "Migrated radio"


def test_backup_is_a_readable_independent_database(tmp_path) -> None:
    source = SQLiteWorkspace(tmp_path / "workspace.sqlite3")
    state = default_workspace_state()
    state["radios"][0]["name"] = "Backed up"
    source.save(state)

    backup_path = tmp_path / "backups" / "rigmanifest.sqlite3"
    assert source.backup(backup_path) == backup_path
    assert SQLiteWorkspace(backup_path).load()["radios"][0]["name"] == "Backed up"

    with pytest.raises(ValueError, match="must differ"):
        source.backup(source.path)


def test_corrupt_or_future_workspace_database_is_rejected(tmp_path) -> None:
    corrupt_path = tmp_path / "corrupt.sqlite3"
    corrupt = SQLiteWorkspace(corrupt_path)
    corrupt.load()
    with sqlite3.connect(corrupt_path) as connection:
        connection.execute(
            "UPDATE workspace_state SET value_json = 'not-json' WHERE key = 'radios'"
        )
    with pytest.raises(ValueError, match="contains invalid state"):
        corrupt.load()

    future_path = tmp_path / "future.sqlite3"
    with sqlite3.connect(future_path) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (999)")
    with pytest.raises(ValueError, match="newer than supported"):
        SQLiteWorkspace(future_path).load()


@pytest.mark.parametrize(
    "change",
    [
        {"user_catalog": None},
        {"user_catalog": {"frequencyDefinitions": None, "frequencySets": []}},
        {"user_catalog": {"frequencyDefinitions": ["not-an-object"], "frequencySets": []}},
        {"radios": []},
        {"radios": ["not-an-object"]},
        {"profile_plan_ids": {"home": 3}},
    ],
)
def test_invalid_workspace_state_is_rejected(tmp_path, change) -> None:
    state = {**default_workspace_state(), **change}
    with pytest.raises(ValueError):
        SQLiteWorkspace(tmp_path / "workspace.sqlite3").save(state)
