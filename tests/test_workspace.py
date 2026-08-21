from __future__ import annotations

import json
import sqlite3

import pytest

from rigmanifest.ipc import catalog_to_dict
from rigmanifest.workspace import SQLiteWorkspace, default_workspace_state


def _radio(name: str = "Test radio") -> dict[str, object]:
    return {
        "id": "radio-1",
        "name": name,
        "radioModelId": "chirp:Yaesu_VX-6",
        "driverReference": "Yaesu_VX-6",
        "manufacturer": "Yaesu",
        "model": "VX-6",
        "imageFilename": "source.img",
        "memoryStart": 1,
        "mapSetsToBanks": True,
        "notes": "",
    }


def test_workspace_initializes_and_round_trips_state(tmp_path) -> None:
    database = tmp_path / "workspace.sqlite3"
    workspace = SQLiteWorkspace(database)

    initial = workspace.load()
    assert initial["radios"] == []
    assert initial["migrated_legacy"] is False

    state = default_workspace_state()
    state["radios"] = [_radio("Desk radio")]
    state["profiles"] = [
        {
            "id": "weather",
            "name": "Weather",
            "description": "Receive-only weather profile",
            "frequency_set_ids": ["us-noaa-weather"],
            "frequency_definition_ids": [],
            "frequency_plan_id": "kansas-repeater-council",
        }
    ]
    workspace.save(state)

    reloaded = workspace.load()
    assert reloaded["radios"][0]["name"] == "Desk radio"
    assert reloaded["profiles"][0]["frequency_plan_id"] == "kansas-repeater-council"

    with sqlite3.connect(database) as connection:
        assert connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone() == (4,)


def test_workspace_releases_database_file_after_operations(tmp_path) -> None:
    database = tmp_path / "workspace.sqlite3"
    workspace = SQLiteWorkspace(database)

    workspace.load()
    workspace.radio_image_versions("unused-radio")
    database.unlink()

    assert not database.exists()


def test_first_open_imports_legacy_state_only_once(tmp_path) -> None:
    workspace = SQLiteWorkspace(tmp_path / "workspace.sqlite3")
    legacy = default_workspace_state()
    legacy["radios"] = [_radio("Migrated radio")]

    first = workspace.load(legacy)
    replacement = default_workspace_state()
    replacement["radios"] = [_radio("Ignored later legacy")]
    second = workspace.load(replacement)

    assert first["migrated_legacy"] is True
    assert second["migrated_legacy"] is False
    assert second["radios"][0]["name"] == "Migrated radio"


def test_schema_one_workspace_migrates_plan_preferences_into_profiles(tmp_path) -> None:
    database = tmp_path / "workspace.sqlite3"
    state = default_workspace_state()
    catalog = catalog_to_dict()
    state["user_catalog"] = {
        "frequencyDefinitions": [
            item
            for item in catalog["frequency_definitions"]
            if item["origin"] == "user"
        ],
        "frequencySets": [
            item for item in catalog["frequency_sets"] if item["origin"] == "user"
        ],
    }
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        connection.execute("INSERT INTO schema_migrations(version) VALUES (1)")
        connection.execute(
            "CREATE TABLE workspace_state (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)"
        )
        rows = {
            "user_catalog": state["user_catalog"],
            "radios": state["radios"],
            "profile_plan_ids": {"home": "kansas-repeater-council"},
        }
        connection.executemany(
            "INSERT INTO workspace_state(key, value_json) VALUES (?, ?)",
            [(key, json.dumps(value)) for key, value in rows.items()],
        )

    migrated = SQLiteWorkspace(database).load()

    assert migrated["profiles"][0]["id"] == "home"
    assert migrated["profiles"][0]["frequency_plan_id"] == (
        "kansas-repeater-council"
    )
    assert migrated["default_frequency_plan_id"] == "arrl-us-national"
    with sqlite3.connect(database) as connection:
        keys = {
            row[0] for row in connection.execute("SELECT key FROM workspace_state")
        }
    assert "profile_plan_ids" not in keys
    assert {"profiles", "default_frequency_plan_id"} <= keys


def test_backup_is_a_readable_independent_database(tmp_path) -> None:
    source = SQLiteWorkspace(tmp_path / "workspace.sqlite3")
    state = default_workspace_state()
    state["radios"] = [_radio("Backed up")]
    source.save(state)
    source.store_radio_image(
        "radio-1",
        b"radio-image",
        original_filename="source.img",
        driver_reference="Yaesu_VX-6",
    )

    backup_path = tmp_path / "backups" / "rigmanifest.sqlite3"
    assert source.backup(backup_path) == backup_path
    assert SQLiteWorkspace(backup_path).load()["radios"][0]["name"] == "Backed up"
    assert SQLiteWorkspace(backup_path).radio_image("radio-1") == b"radio-image"
    versions = SQLiteWorkspace(backup_path).radio_image_versions("radio-1")
    assert len(versions) == 1
    assert versions[0].path.parent == backup_path.parent / "radios" / "radio-1"
    assert versions[0].path.read_bytes() == b"radio-image"
    with sqlite3.connect(backup_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(radio_image_versions)")
        }
    assert "image_blob" not in columns

    with pytest.raises(ValueError, match="must differ"):
        source.backup(source.path)


def test_removing_a_radio_removes_its_tracked_image_directory(tmp_path) -> None:
    workspace = SQLiteWorkspace(tmp_path / "workspace.sqlite3")
    state = default_workspace_state()
    state["radios"] = [_radio()]
    workspace.save(state)
    version = workspace.store_radio_image(
        "radio-1",
        b"radio-image",
        original_filename="source.img",
        driver_reference="Yaesu_VX-6",
    )

    workspace.save(default_workspace_state())

    assert not version.path.parent.exists()
    assert workspace.radio_image_versions("radio-1") == ()


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
        {"radios": ["not-an-object"]},
        {"profiles": ["not-an-object"]},
        {"default_frequency_plan_id": "missing"},
    ],
)
def test_invalid_workspace_state_is_rejected(tmp_path, change) -> None:
    state = {**default_workspace_state(), **change}
    with pytest.raises(ValueError):
        SQLiteWorkspace(tmp_path / "workspace.sqlite3").save(state)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"radio_id": ""}, "metadata"),
        ({"image": b""}, "metadata"),
        ({"original_filename": ""}, "metadata"),
        ({"driver_reference": ""}, "metadata"),
        ({"kind": "backup"}, "kind"),
    ],
)
def test_radio_image_metadata_is_validated(tmp_path, overrides, message) -> None:
    arguments = {
        "radio_id": "radio-1",
        "image": b"image",
        "original_filename": "source.img",
        "driver_reference": "Yaesu_VX-6",
        "kind": "source",
        **overrides,
    }
    with pytest.raises(ValueError, match=message):
        SQLiteWorkspace(tmp_path / "workspace.sqlite3").store_radio_image(**arguments)


def test_missing_and_unknown_radio_images_are_reported(tmp_path) -> None:
    workspace = SQLiteWorkspace(tmp_path / "workspace.sqlite3")

    with pytest.raises(ValueError, match="does not have"):
        workspace.radio_image_path("missing")
    with pytest.raises(ValueError, match="unknown"):
        workspace.radio_image_version("missing")

    version = workspace.store_radio_image(
        "radio / unsafe",
        b"image",
        original_filename="source.img",
        driver_reference="Yaesu_VX-6",
    )
    version.path.unlink()
    with pytest.raises(ValueError, match="is missing"):
        workspace.radio_image_path("radio / unsafe")


def test_blank_unsafe_radio_id_gets_a_safe_directory(tmp_path) -> None:
    version = SQLiteWorkspace(tmp_path / "workspace.sqlite3").store_radio_image(
        "...",
        b"image",
        original_filename="source.img",
        driver_reference="Yaesu_VX-6",
    )

    assert version.path.parent.name.startswith("radio-")
