from __future__ import annotations

from pathlib import Path

import pytest

from rigmanifest.chirp_import import import_chirp_csv
from rigmanifest.ipc import handle_request
from rigmanifest.models import SignalingKind, TransmitBehavior


HEADER = (
    "Location,Name,Frequency,Duplex,Offset,Tone,rToneFreq,cToneFreq,"
    "DtcsCode,DtcsPolarity,RxDtcsCode,CrossMode,Mode,Comment\n"
)


def _write_csv(path: Path, rows: str) -> Path:
    path.write_text(HEADER + rows, encoding="utf-8")
    return path


def test_import_maps_chirp_memories_to_reusable_definitions_and_one_set(
    tmp_path: Path,
) -> None:
    source = _write_csv(
        tmp_path / "road-trip.csv",
        "1,Local,146.910000,-,0.600000,Tone,100.0,88.5,023,NN,023,Tone->Tone,FM,Home repeater\n"
        "2,Mixed,147.300000,+,0.600000,Cross,100.0,88.5,023,NR,025,Tone->DTCS,FM,Cross mode\n"
        "3,Odd split,145.000000,split,147.000000,,88.5,88.5,023,NN,023,Tone->Tone,NFM,\n"
        "4,Weather,162.550000,off,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,Receive only\n",
    )

    imported = import_chirp_csv(source)

    assert imported.definition_count == 4
    assert imported.frequency_set.name == "Imported road-trip"
    assert [member.position for member in imported.frequency_set.members] == [0, 1, 2, 3]
    negative, mixed, split, disabled = imported.frequency_definitions
    assert negative.transmit_behavior is TransmitBehavior.OFFSET
    assert negative.offset_hz == -600_000
    assert negative.transmit_access.kind is SignalingKind.CTCSS
    assert negative.transmit_access.ctcss_hz == 100.0
    assert negative.receive_squelch.kind is SignalingKind.NONE
    assert "Home repeater" in negative.notes
    assert "CHIRP memory 1" in negative.notes
    assert mixed.offset_hz == 600_000
    assert mixed.transmit_access.kind is SignalingKind.CTCSS
    assert mixed.receive_squelch.kind is SignalingKind.DCS
    assert mixed.receive_squelch.dcs_code == 25
    assert mixed.receive_squelch.dcs_polarity == "R"
    assert split.transmit_behavior is TransmitBehavior.SPLIT
    assert split.transmit_frequency_hz == 147_000_000
    assert disabled.transmit_behavior is TransmitBehavior.DISABLED
    assert disabled.resolved_transmit_frequency_hz is None
    assert all(item.origin.value == "user" for item in imported.frequency_definitions)
    assert all("chirp-import" in item.tags for item in imported.frequency_definitions)


def test_import_uses_a_memory_location_when_name_is_blank(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "blank-name.csv",
        "7,,146.520000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,\n",
    )

    imported = import_chirp_csv(source)

    assert imported.frequency_definitions[0].name == "Memory 7"


@pytest.mark.parametrize(
    ("filename", "rows", "message"),
    [
        ("empty.csv", "", "no frequency memories"),
        (
            "digital.csv",
            "1,Digital,146.520000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,DV,\n",
            "unsupported CHIRP mode",
        ),
    ],
)
def test_import_rejects_unrepresentable_or_empty_csv(
    tmp_path: Path,
    filename: str,
    rows: str,
    message: str,
) -> None:
    source = _write_csv(tmp_path / filename, rows)

    with pytest.raises(ValueError, match=message):
        import_chirp_csv(source)


def test_import_requires_an_existing_csv_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="requires a .csv"):
        import_chirp_csv(tmp_path / "image.img")
    with pytest.raises(ValueError, match="does not exist"):
        import_chirp_csv(tmp_path / "missing.csv")


def test_import_is_available_through_the_sidecar_boundary(tmp_path: Path) -> None:
    source = _write_csv(
        tmp_path / "ipc.csv",
        "1,Calling,146.520000,,0.000000,,88.5,88.5,023,NN,023,Tone->Tone,FM,\n",
    )

    response = handle_request(
        {
            "id": "import",
            "method": "import_chirp_csv",
            "params": {"source_path": str(source)},
        }
    )

    assert "error" not in response
    result = response["result"]
    assert result["definition_count"] == 1
    assert result["frequency_set"]["name"] == "Imported ipc"
    assert result["frequency_definitions"][0]["receive_frequency_hz"] == 146_520_000

    compiled = handle_request(
        {
            "id": "compile-import",
            "method": "compile",
            "params": {
                "profile": "home",
                "target": "yaesu-vx6r",
                "frequency_set_ids": [result["frequency_set"]["id"]],
                "user_frequency_definitions": result["frequency_definitions"],
                "user_frequency_sets": [result["frequency_set"]],
            },
        }
    )
    assert "error" not in compiled
    assert compiled["result"]["summary"]["programmed"] == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"id": "bad", "method": "import_chirp_csv"},
        {"id": "bad", "method": "import_chirp_csv", "params": {}},
    ],
)
def test_import_boundary_rejects_missing_parameters(
    payload: dict[str, object],
) -> None:
    response = handle_request(payload)

    assert response["error"]["code"] == "INVALID_REQUEST"
