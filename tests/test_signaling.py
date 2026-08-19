from __future__ import annotations

import pytest
from chirp import chirp_common

from rigmanifest.chirp_adapter import (
    apply_signaling_to_chirp_memory,
    signaling_from_chirp_memory,
)
from rigmanifest.models import SignalingKind, SignalingSpec


NONE = SignalingSpec()
TONE_100 = SignalingSpec(kind=SignalingKind.CTCSS, ctcss_hz=100.0)
TONE_123 = SignalingSpec(kind=SignalingKind.CTCSS, ctcss_hz=123.0)
DCS_23_N = SignalingSpec(kind=SignalingKind.DCS, dcs_code=23)
DCS_25_R = SignalingSpec(
    kind=SignalingKind.DCS,
    dcs_code=25,
    dcs_polarity="R",
)


@pytest.mark.parametrize(
    ("transmit", "receive", "tone_mode", "cross_mode"),
    [
        (NONE, NONE, "", "Tone->Tone"),
        (TONE_100, NONE, "Tone", "Tone->Tone"),
        (TONE_100, TONE_100, "TSQL", "Tone->Tone"),
        (TONE_100, TONE_123, "Cross", "Tone->Tone"),
        (DCS_23_N, DCS_23_N, "DTCS", "Tone->Tone"),
        (TONE_100, DCS_25_R, "Cross", "Tone->DTCS"),
        (DCS_25_R, TONE_100, "Cross", "DTCS->Tone"),
        (NONE, TONE_100, "Cross", "->Tone"),
        (NONE, DCS_25_R, "Cross", "->DTCS"),
    ],
)
def test_chirp_signaling_round_trip(
    transmit: SignalingSpec,
    receive: SignalingSpec,
    tone_mode: str,
    cross_mode: str,
) -> None:
    memory = chirp_common.Memory()

    apply_signaling_to_chirp_memory(memory, transmit, receive)

    assert memory.tmode == tone_mode
    assert memory.cross_mode == cross_mode
    assert signaling_from_chirp_memory(memory) == (transmit, receive)


@pytest.mark.parametrize(
    "arguments",
    [
        {"ctcss_hz": 100.0},
        {"kind": SignalingKind.NONE, "dcs_polarity": "R"},
        {"kind": SignalingKind.CTCSS},
        {"kind": SignalingKind.CTCSS, "ctcss_hz": 100.0, "dcs_code": 23},
        {"kind": SignalingKind.DCS},
        {"kind": SignalingKind.DCS, "dcs_code": 23, "ctcss_hz": 100.0},
        {"kind": SignalingKind.DCS, "dcs_code": 23, "dcs_polarity": "X"},
    ],
)
def test_invalid_signaling_is_rejected(arguments: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        SignalingSpec(**arguments)  # type: ignore[arg-type]
