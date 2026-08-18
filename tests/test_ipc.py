from __future__ import annotations

import json
from io import StringIO

from rigmanifest.ipc import handle_request
from rigmanifest.sidecar import serve


def test_compile_request_returns_versioned_plan() -> None:
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
    assert result["schema_version"] == 1
    assert result["summary"] == {
        "included": 3,
        "omitted": 1,
        "warnings": 3,
        "errors": 1,
    }
    assert any(
        item["code"] == "TX_DISABLE_NOT_REPRESENTABLE"
        for item in result["diagnostics"]
    )


def test_compile_request_can_export_csv(tmp_path) -> None:
    output = tmp_path / "home.csv"

    response = handle_request(
        {
            "id": 2,
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "output_path": str(output),
            },
        }
    )

    assert "error" not in response
    assert output.read_text(encoding="utf-8").startswith("Location,Name,Frequency")


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
