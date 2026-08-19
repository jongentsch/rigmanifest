from __future__ import annotations

import json
from io import StringIO

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
    assert result["schema_version"] == 3
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
    assert result["schema_version"] == 3
    assert result["profiles"] == [
        {
            "id": "home",
            "name": "Home",
            "frequency_set_ids": ["home-essentials", "us-noaa-weather"],
        }
    ]
    assert result["radio_models"][0]["id"] == "yaesu-vx6r"
    assert result["radio_models"][0]["factory_frequency_sets"] == [
        {
            "frequency_set_id": "us-noaa-weather",
            "frequency_set_name": "US NOAA Weather Broadcasts",
            "interface_label": "WX CH",
            "frequency_editing": "unknown",
            "chirp_editing": "unsupported",
        }
    ]
    assert len(result["frequency_definitions"]) == 13
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
    assert calling["tone"] == {
        "mode": "none",
        "encode_hz": None,
        "decode_hz": None,
        "dtcs_code": None,
        "dtcs_polarity": "NN",
    }
    assert "notes" in calling


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
