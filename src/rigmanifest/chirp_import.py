"""Import CHIRP generic CSV memories into reusable catalog records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from chirp import errors
from chirp.drivers.generic_csv import CSVRadio

from rigmanifest.chirp_adapter import signaling_from_chirp_memory
from rigmanifest.models import (
    CatalogOrigin,
    FrequencyDefinition,
    FrequencySet,
    FrequencySetMember,
    Mode,
    TransmitBehavior,
)


@dataclass(frozen=True, slots=True)
class ChirpCatalogImport:
    source_path: Path
    frequency_definitions: tuple[FrequencyDefinition, ...]
    frequency_set: FrequencySet

    @property
    def definition_count(self) -> int:
        return len(self.frequency_definitions)


def import_chirp_csv(path: Path) -> ChirpCatalogImport:
    """Parse a CHIRP generic CSV file and create a user-owned catalog set."""

    if path.suffix.casefold() != ".csv":
        raise ValueError("CHIRP import currently requires a .csv file")
    if not path.is_file():
        raise ValueError(f"CHIRP CSV file does not exist: {path}")

    try:
        radio = CSVRadio(str(path))
    except errors.InvalidDataError as error:
        raise ValueError("CHIRP CSV contains no frequency memories") from error
    if radio.errors:
        raise ValueError("CHIRP CSV contains errors: " + "; ".join(radio.errors))

    import_id = uuid4().hex[:12]
    set_slug = _slug(path.stem) or "chirp"
    definitions: list[FrequencyDefinition] = []
    members: list[FrequencySetMember] = []
    for memory in radio.memories:
        if memory.empty or not memory.freq:
            continue
        definition = definition_from_chirp_memory(
            memory,
            definition_id=f"user-import-{set_slug}-{import_id}-{memory.number}",
            source_name=path.name,
        )
        definitions.append(definition)
        members.append(FrequencySetMember(definition.id, len(members)))

    if not definitions:
        raise ValueError("CHIRP CSV contains no frequency memories")

    frequency_set = FrequencySet(
        id=f"user-set-import-{set_slug}-{import_id}",
        name=f"Imported {path.stem}",
        origin=CatalogOrigin.USER,
        description=f"Imported from CHIRP CSV {path.name}.",
        members=tuple(members),
    )
    return ChirpCatalogImport(
        source_path=path,
        frequency_definitions=tuple(definitions),
        frequency_set=frequency_set,
    )


def definition_from_chirp_memory(
    memory: object,
    *,
    definition_id: str,
    source_name: str,
) -> FrequencyDefinition:
    duplex = str(getattr(memory, "duplex"))
    raw_offset = int(getattr(memory, "offset"))
    if duplex == "":
        transmit_behavior = TransmitBehavior.SAME
        transmit_frequency_hz = None
        offset_hz = None
    elif duplex in {"+", "-"}:
        transmit_behavior = TransmitBehavior.OFFSET
        transmit_frequency_hz = None
        offset_hz = raw_offset if duplex == "+" else -raw_offset
    elif duplex == "split":
        transmit_behavior = TransmitBehavior.SPLIT
        transmit_frequency_hz = raw_offset
        offset_hz = None
    elif duplex == "off":
        transmit_behavior = TransmitBehavior.DISABLED
        transmit_frequency_hz = None
        offset_hz = None
    else:
        raise ValueError(f"unsupported CHIRP duplex value: {duplex!r}")

    try:
        mode = Mode(str(getattr(memory, "mode")))
    except ValueError as error:
        raise ValueError(
            f"unsupported CHIRP mode at memory {getattr(memory, 'number')}: "
            f"{getattr(memory, 'mode')}"
        ) from error

    transmit_access, receive_squelch = signaling_from_chirp_memory(memory)
    location = int(getattr(memory, "number"))
    name = str(getattr(memory, "name")).strip() or f"Memory {location}"
    comment = str(getattr(memory, "comment", "")).strip()
    power = getattr(memory, "power", None)
    provenance = f"Imported from {source_name}, CHIRP memory {location}."
    notes = f"{comment}\n\n{provenance}" if comment else provenance
    return FrequencyDefinition(
        id=definition_id,
        name=name,
        receive_frequency_hz=int(getattr(memory, "freq")),
        transmit_behavior=transmit_behavior,
        transmit_frequency_hz=transmit_frequency_hz,
        offset_hz=offset_hz,
        mode=mode,
        transmit_access=transmit_access,
        receive_squelch=receive_squelch,
        tags=frozenset({"chirp-import"}),
        notes=notes,
        power_dbm=float(power) if power is not None else None,
        power_label=str(power) if power is not None else None,
        scan_skip=str(getattr(memory, "skip", "")),
        tuning_step_hz=int(round(float(getattr(memory, "tuning_step", 0)) * 1_000))
        or None,
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
