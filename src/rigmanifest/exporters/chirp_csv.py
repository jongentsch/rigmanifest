"""CHIRP-compatible CSV serialization for already-compiled memories."""

from __future__ import annotations

import csv
from io import StringIO
from pathlib import Path
from typing import TextIO

from chirp import chirp_common

from rigmanifest.chirp_adapter import apply_signaling_to_chirp_memory
from rigmanifest.models import (
    CompiledMemory,
    CompiledRadioPlan,
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
    tone_mode, rtone, ctone, dtcs, polarity, rx_dtcs, cross_mode = _tone_fields(
        memory
    )
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
        polarity,
        rx_dtcs,
        cross_mode,
        memory.mode.value,
        (
            f"{memory.tuning_step_hz / 1_000:.2f}"
            if memory.tuning_step_hz is not None
            else "5.00"
        ),
        memory.scan_skip,
        memory.power_label or "",
        f"RigManifest source: {memory.source_frequency_definition_id}",
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
) -> tuple[str, str, str, str, str, str, str]:
    chirp_memory = chirp_common.Memory()
    apply_signaling_to_chirp_memory(
        chirp_memory,
        memory.transmit_access,
        memory.receive_squelch,
    )
    return (
        chirp_memory.tmode,
        f"{chirp_memory.rtone:.1f}",
        f"{chirp_memory.ctone:.1f}",
        f"{chirp_memory.dtcs:03d}",
        chirp_memory.dtcs_polarity,
        f"{chirp_memory.rx_dtcs:03d}",
        chirp_memory.cross_mode,
    )


def _format_mhz(frequency_hz: int) -> str:
    sign = "-" if frequency_hz < 0 else ""
    absolute_hz = abs(frequency_hz)
    return f"{sign}{absolute_hz // 1_000_000}.{absolute_hz % 1_000_000:06d}"
