"""CHIRP-compatible CSV serialization for already-compiled memories."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TextIO

from rigmanifest.models import (
    CompiledMemory,
    CompiledRadioPlan,
    ToneMode,
    TransmitBehavior,
)


CHIRP_CSV_HEADER = (
    "Location",
    "Name",
    "Frequency",
    "Duplex",
    "Offset",
    "Tone",
    "rToneFreq",
    "cToneFreq",
    "DtcsCode",
    "DtcsPolarity",
    "RxDtcsCode",
    "CrossMode",
    "Mode",
    "TStep",
    "Skip",
    "Power",
    "Comment",
    "URCALL",
    "RPT1CALL",
    "RPT2CALL",
    "DVCODE",
)


def render_chirp_csv(plan: CompiledRadioPlan) -> str:
    """Render a plan using CHIRP's canonical generic CSV columns."""

    output = StringIO(newline="")
    _write(plan, output)
    return output.getvalue()


def write_chirp_csv(plan: CompiledRadioPlan, path: Path) -> None:
    """Write a compiled plan to disk without making compilation decisions."""

    with path.open("w", encoding="utf-8", newline="") as output:
        _write(plan, output)


def _write(plan: CompiledRadioPlan, output: TextIO) -> None:
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(CHIRP_CSV_HEADER)
    for memory in plan.memories:
        writer.writerow(_row(memory))


def _row(memory: CompiledMemory) -> tuple[str, ...]:
    duplex, offset = _duplex_and_offset(memory)
    tone_mode, rtone, ctone, dtcs, rx_dtcs = _tone_fields(memory)
    return (
        str(memory.memory_number),
        memory.target_name,
        _format_mhz(memory.receive_frequency_hz),
        duplex,
        offset,
        tone_mode,
        rtone,
        ctone,
        dtcs,
        memory.tone.dtcs_polarity,
        rx_dtcs,
        "Tone->Tone",
        memory.mode.value,
        "5.00",
        "",
        "",
        f"RigManifest source: {memory.source_channel_id}",
        "",
        "",
        "",
        "",
    )


def _duplex_and_offset(memory: CompiledMemory) -> tuple[str, str]:
    if memory.transmit_behavior is TransmitBehavior.SAME:
        return "", _format_mhz(0)
    if memory.transmit_behavior is TransmitBehavior.DISABLED:
        return "off", _format_mhz(0)
    if memory.transmit_behavior is TransmitBehavior.SPLIT:
        assert memory.transmit_frequency_hz is not None
        return "split", _format_mhz(memory.transmit_frequency_hz)
    assert memory.offset_hz is not None
    duplex = "+" if memory.offset_hz > 0 else "-"
    return duplex, _format_mhz(abs(memory.offset_hz))


def _tone_fields(
    memory: CompiledMemory,
) -> tuple[str, str, str, str, str]:
    tone = memory.tone
    rtone = tone.encode_hz if tone.encode_hz is not None else 88.5
    ctone = tone.decode_hz if tone.decode_hz is not None else rtone
    dtcs = tone.dtcs_code if tone.dtcs_code is not None else 23

    chirp_mode = {
        ToneMode.NONE: "",
        ToneMode.TONE: "Tone",
        ToneMode.TSQL: "TSQL",
        ToneMode.DTCS: "DTCS",
    }[tone.mode]
    return chirp_mode, f"{rtone:.1f}", f"{ctone:.1f}", f"{dtcs:03d}", f"{dtcs:03d}"


def _format_mhz(frequency_hz: int) -> str:
    sign = "-" if frequency_hz < 0 else ""
    absolute_hz = abs(frequency_hz)
    return f"{sign}{absolute_hz // 1_000_000}.{absolute_hz % 1_000_000:06d}"
