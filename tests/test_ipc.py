from __future__ import annotations

import json
from io import StringIO

import pytest

from rigmanifest.ipc import handle_request
from rigmanifest.sidecar import serve


def test_compile_request_returns_set_based_plan() -> None:
    response = handle_request(
        {
            "id": "request-1",
            "method": "compile",
            "params": {"profile": "home", "target": "yaesu-vx6r"},
        }
    )

    assert response["id"] == "request-1"
    result = response["result"]
    assert isinstance(result, dict)
    assert result["schema_version"] == 5
    assert result["summary"] == {
        "included": 13,
        "programmed": 3,
        "factory_provided": 10,
        "factory_sets": 1,
        "omitted": 0,
        "warnings": 3,
        "errors": 0,
    }
    assert result["profile"]["frequency_set_ids"] == [
        "home-essentials",
        "us-noaa-weather",
    ]
    assert any(
        item["code"] == "FACTORY_SET_AVAILABLE"
        for item in result["diagnostics"]
    )
    assert result["factory_sets"][0]["frequency_set_id"] == "us-noaa-weather"
    assert result["factory_sets"][0]["definition_count"] == 10


def test_catalog_request_returns_shared_definitions_sets_and_radio_relationships() -> None:
    response = handle_request({"id": "catalog", "method": "catalog"})

    result = response["result"]
    assert isinstance(result, dict)
    assert result["schema_version"] == 7
    assert result["profiles"] == [
        {
            "id": "home",
            "name": "Home",
            "description": "Everyday local operating frequencies and weather coverage.",
            "frequency_set_ids": ["home-essentials", "us-noaa-weather"],
            "frequency_definition_ids": [],
            "frequency_plan_id": "arrl-us-national",
        }
    ]
    assert [item["id"] for item in result["radio_models"]] == [
        "quansheng-uv-k5",
        "retevis-rt95",
        "yaesu-vx6r",
    ]
    vx6 = next(item for item in result["radio_models"] if item["id"] == "yaesu-vx6r")
    assert vx6["factory_frequency_sets"] == [
        {
            "frequency_set_id": "us-noaa-weather",
            "frequency_set_name": "US NOAA Weather Broadcasts",
            "interface_label": "WX CH",
            "frequency_editing": "unknown",
            "chirp_editing": "unsupported",
        }
    ]
    assert next(
        item for item in result["radio_models"] if item["id"] == "quansheng-uv-k5"
    )["chirp_driver_reference"] == "Quansheng_UV-K5"
    assert result["frequency_plans"][0]["source_url"] == (
        "https://www.arrl.org/band-plan"
    )
    assert [plan["id"] for plan in result["frequency_plans"]] == [
        "arrl-us-national",
        "kansas-repeater-council",
        "southern-nevada-repeater-council",
    ]
    two_meter = next(
        segment
        for segment in result["frequency_plans"][0]["segments"]
        if segment["id"] == "2m-repeater-output-mid"
    )
    assert two_meter["suggested_offset_hz"] == -600_000
    assert two_meter["raster_spacing_hz"] is None
    assert len(result["frequency_definitions"]) == 98
    assert len(result["frequency_sets"]) == 8
    frs = next(item for item in result["frequency_sets"] if item["id"] == "us-frs")
    assert frs["source_url"].endswith("section-95.563")
    assert frs["reviewed_at"] == "2026-08-19"
    assert {item["origin"] for item in result["frequency_sets"]} == {
        "preset",
        "user",
    }
    calling = next(
        item
        for item in result["frequency_definitions"]
        if item["id"] == "simplex-calling-2m"
    )
    assert calling["transmit_behavior"] == "same"
    assert calling["transmit_frequency_hz"] is None
    assert calling["transmit_access"] == {
        "kind": "none",
        "ctcss_hz": None,
        "dcs_code": None,
        "dcs_polarity": "N",
    }
    assert calling["receive_squelch"] == calling["transmit_access"]
    assert "notes" in calling


def test_workspace_requests_persist_and_backup_state(tmp_path) -> None:
    database = tmp_path / "workspace.sqlite3"
    loaded = handle_request({
        "id": "load",
        "method": "load_workspace",
        "params": {"database_path": str(database), "legacy_state": None},
    })["result"]
    assert loaded["schema_version"] == 2

    loaded["radios"][0]["name"] = "Portable"
    saved = handle_request({
        "id": "save",
        "method": "save_workspace",
        "params": {"database_path": str(database), "state": loaded},
    })
    assert saved["result"]["radios"][0]["name"] == "Portable"

    backup = tmp_path / "backup.sqlite3"
    response = handle_request({
        "id": "backup",
        "method": "backup_workspace",
        "params": {"database_path": str(database), "destination": str(backup)},
    })
    assert response["result"]["path"] == str(backup)
    assert backup.exists()


def test_compile_request_accepts_an_explicit_set_selection(tmp_path) -> None:
    output = tmp_path / "home.csv"

    response = handle_request(
        {
            "id": 2,
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "frequency_set_ids": ["home-essentials"],
                "output_path": str(output),
            },
        }
    )

    assert "error" not in response
    assert response["result"]["summary"]["programmed"] == 3
    assert response["result"]["summary"]["factory_provided"] == 0
    assert output.read_text(encoding="utf-8").startswith("Location,Name,Frequency")


def test_compile_request_composes_profiles_sets_and_direct_definitions() -> None:
    response = handle_request(
        {
            "id": "selection",
            "method": "compile",
            "params": {
                "target": "yaesu-vx6r",
                "profiles": [
                    {
                        "id": "home",
                        "name": "Home",
                        "description": "",
                        "frequency_set_ids": ["home-essentials"],
                        "frequency_definition_ids": [],
                        "frequency_plan_id": "kansas-repeater-council",
                    },
                    {
                        "id": "vacation",
                        "name": "Vacation",
                        "description": "",
                        "frequency_set_ids": ["home-essentials"],
                        "frequency_definition_ids": ["us-noaa-weather-1"],
                        "frequency_plan_id": "southern-nevada-repeater-council",
                    },
                ],
                "additional_frequency_set_ids": [],
                "additional_frequency_definition_ids": ["simplex-calling-2m"],
                "advisory_plan_id": "arrl-us-national",
            },
        }
    )

    assert "error" not in response
    result = response["result"]
    assert [profile["id"] for profile in result["profiles"]] == [
        "home",
        "vacation",
    ]
    assert result["selection"] == {
        "additional_frequency_set_ids": [],
        "additional_frequency_definition_ids": ["simplex-calling-2m"],
        "advisory_plan_id": "arrl-us-national",
    }
    calling = next(
        memory
        for memory in result["memories"]
        if memory["source_frequency_definition_id"] == "simplex-calling-2m"
    )
    assert calling["source_profile_ids"] == ["home", "vacation"]
    assert calling["selected_directly"] is True
    assert any(
        diagnostic["code"] == "PLAN_CONTEXT_CONFLICT"
        for diagnostic in result["diagnostics"]
    )


def test_compile_request_accepts_persisted_user_catalog_records() -> None:
    response = handle_request(
        {
            "id": "user-catalog",
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "frequency_set_ids": ["user-travel"],
                "user_frequency_definitions": [
                    {
                        "id": "user-travel-simplex",
                        "name": "Travel Simplex",
                        "origin": "user",
                        "read_only": False,
                        "receive_frequency_hz": 146_580_000,
                        "transmit_behavior": "same",
                        "transmit_frequency_hz": None,
                        "offset_hz": None,
                        "mode": "FM",
                        "tone": {
                            "mode": "none",
                            "encode_hz": None,
                            "decode_hz": None,
                            "dtcs_code": None,
                            "dtcs_polarity": "NN",
                        },
                        "tags": ["travel"],
                        "priority": "normal",
                        "notes": "User-authored definition",
                    }
                ],
                "user_frequency_sets": [
                    {
                        "id": "user-travel",
                        "name": "Travel",
                        "origin": "user",
                        "read_only": False,
                        "description": "User-authored set",
                        "members": [
                            {
                                "frequency_definition_id": "user-travel-simplex",
                                "position": 0,
                                "channel_designator": None,
                            }
                        ],
                    }
                ],
            },
        }
    )

    assert "error" not in response
    result = response["result"]
    assert result["summary"]["programmed"] == 1
    assert result["memories"][0]["source_frequency_definition_id"] == (
        "user-travel-simplex"
    )
    assert result["memories"][0]["source_frequency_set_ids"] == ["user-travel"]
    assert result["memories"][0]["transmit_access"]["kind"] == "none"
    assert result["memories"][0]["receive_squelch"]["kind"] == "none"


def test_compile_request_accepts_independent_signaling_records() -> None:
    definition = {
        "id": "user-cross",
        "name": "Cross mode",
        "origin": "user",
        "read_only": False,
        "receive_frequency_hz": 146_580_000,
        "transmit_behavior": "same",
        "transmit_frequency_hz": None,
        "offset_hz": None,
        "mode": "FM",
        "transmit_access": {
            "kind": "ctcss",
            "ctcss_hz": 100.0,
            "dcs_code": None,
            "dcs_polarity": "N",
        },
        "receive_squelch": {
            "kind": "dcs",
            "ctcss_hz": None,
            "dcs_code": 23,
            "dcs_polarity": "N",
        },
        "tags": [],
        "priority": "normal",
        "notes": "",
    }
    response = handle_request(
        {
            "id": "independent-signaling",
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "frequency_set_ids": ["user-cross-set"],
                "user_frequency_definitions": [definition],
                "user_frequency_sets": [
                    {
                        "id": "user-cross-set",
                        "name": "Cross",
                        "origin": "user",
                        "read_only": False,
                        "description": "",
                        "members": [
                            {
                                "frequency_definition_id": "user-cross",
                                "position": 0,
                                "channel_designator": None,
                            }
                        ],
                    }
                ],
            },
        }
    )

    assert "error" not in response
    memory = response["result"]["memories"][0]
    assert memory["transmit_access"] == definition["transmit_access"]
    assert memory["receive_squelch"] == definition["receive_squelch"]


def test_user_catalog_cannot_override_preset_ownership() -> None:
    response = handle_request(
        {
            "id": "preset-injection",
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "frequency_set_ids": ["us-noaa-weather"],
                "user_frequency_definitions": [
                    {
                        "id": "fake-preset",
                        "name": "Fake preset",
                        "origin": "preset",
                        "read_only": True,
                    }
                ],
                "user_frequency_sets": [],
            },
        }
    )

    assert response["error"]["code"] == "INVALID_REQUEST"
    assert "must be user-owned" in response["error"]["message"]


def test_sidecar_emits_one_compact_json_response_per_line() -> None:
    input_stream = StringIO(
        '{"id":1,"method":"compile","params":{"profile":"home","target":"bad"}}\n'
        "not-json\n"
    )
    output_stream = StringIO()

    serve(input_stream, output_stream)

    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert responses[0]["id"] == 1
    assert responses[0]["error"]["code"] == "INVALID_REQUEST"
    assert responses[1]["id"] is None
    assert responses[1]["error"]["code"] == "INVALID_JSON"


def test_sidecar_skips_blank_lines_and_rejects_non_object_json() -> None:
    input_stream = StringIO("\n[]\n")
    output_stream = StringIO()

    serve(input_stream, output_stream)

    response = json.loads(output_stream.getvalue())
    assert response["error"]["code"] == "INVALID_JSON"
    assert "JSON object" in response["error"]["message"]


def test_sidecar_once_mode_exits_after_first_response() -> None:
    input_stream = StringIO(
        '{"id":1,"method":"catalog"}\n{"id":2,"method":"catalog"}\n'
    )
    output_stream = StringIO()

    serve(input_stream, output_stream, once=True)

    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    assert [response["id"] for response in responses] == [1]


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "bad", "method": "unknown"},
        {"id": "bad", "method": "compile"},
        {"id": "bad", "method": "compile", "params": {}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "output_path": 1}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "frequency_set_ids": []}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "user_frequency_definitions": []}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "user_frequency_definitions": "bad", "user_frequency_sets": []}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "user_frequency_definitions": [], "user_frequency_sets": "bad"}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "memory_start": True}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "map_sets_to_banks": "yes"}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "memory_start": -1}},
        {"id": "bad", "method": "compile", "params": {"profile": "missing", "target": "yaesu-vx6r"}},
        {"id": "bad", "method": "compile", "params": {"profile": "home", "target": "yaesu-vx6r", "frequency_set_ids": ["missing"]}},
        {"id": "bad", "method": "import_chirp_csv", "params": {"source_path": "missing.csv"}},
        {"id": "bad", "method": "load_workspace"},
        {"id": "bad", "method": "load_workspace", "params": {"database_path": ""}},
        {"id": "bad", "method": "load_workspace", "params": {"database_path": "workspace.sqlite3", "legacy_state": []}},
        {"id": "bad", "method": "save_workspace", "params": {"database_path": "workspace.sqlite3", "state": []}},
        {"id": "bad", "method": "backup_workspace", "params": {"database_path": "workspace.sqlite3", "destination": ""}},
    ],
)
def test_invalid_ipc_shapes_return_safe_errors(payload: dict[str, object]) -> None:
    response = handle_request(payload)

    assert response["error"]["code"] == "INVALID_REQUEST"
