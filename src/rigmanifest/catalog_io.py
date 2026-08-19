"""Validation and conversion for user-owned catalog records at application boundaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rigmanifest.models import (
    CatalogOrigin,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencySet,
    FrequencySetMember,
    Mode,
    Priority,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


def catalog_with_user_records(
    base: FrequencyCatalog,
    definition_records: Sequence[Mapping[str, object]],
    set_records: Sequence[Mapping[str, object]],
) -> FrequencyCatalog:
    """Replace the base user partition with validated user-owned wire records."""

    user_definitions = tuple(_parse_definition(item) for item in definition_records)
    user_sets = tuple(_parse_set(item) for item in set_records)
    preset_definitions = tuple(item for item in base.definitions if item.read_only)
    preset_sets = tuple(item for item in base.sets if item.read_only)
    return FrequencyCatalog(
        definitions=preset_definitions + user_definitions,
        sets=preset_sets + user_sets,
    )


def _parse_definition(record: Mapping[str, object]) -> FrequencyDefinition:
    _require_user_owned(record, "frequency definition")
    tone_record = record.get("tone", {})
    if not isinstance(tone_record, Mapping):
        raise ValueError("frequency definition tone must be an object")

    tags = record.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(item, str) for item in tags):
        raise ValueError("frequency definition tags must be a string array")

    try:
        return FrequencyDefinition(
            id=_required_string(record, "id"),
            name=_required_string(record, "name"),
            origin=CatalogOrigin.USER,
            receive_frequency_hz=_required_integer(record, "receive_frequency_hz"),
            transmit_behavior=TransmitBehavior(
                _required_string(record, "transmit_behavior")
            ),
            transmit_frequency_hz=_optional_integer(record, "transmit_frequency_hz"),
            offset_hz=_optional_integer(record, "offset_hz"),
            mode=Mode(_required_string(record, "mode")),
            tone=ToneSpec(
                mode=ToneMode(_optional_string(tone_record, "mode") or "none"),
                encode_hz=_optional_number(tone_record, "encode_hz"),
                decode_hz=_optional_number(tone_record, "decode_hz"),
                dtcs_code=_optional_integer(tone_record, "dtcs_code"),
                dtcs_polarity=_optional_string(tone_record, "dtcs_polarity") or "NN",
            ),
            tags=frozenset(tags),
            priority=Priority[
                (_optional_string(record, "priority") or "normal").upper()
            ],
            notes=_optional_string(record, "notes") or "",
        )
    except (KeyError, ValueError) as error:
        raise ValueError(f"invalid user frequency definition: {error}") from error


def _parse_set(record: Mapping[str, object]) -> FrequencySet:
    _require_user_owned(record, "frequency set")
    members = record.get("members", [])
    if not isinstance(members, list) or not all(
        isinstance(item, Mapping) for item in members
    ):
        raise ValueError("frequency set members must be an object array")

    try:
        return FrequencySet(
            id=_required_string(record, "id"),
            name=_required_string(record, "name"),
            origin=CatalogOrigin.USER,
            description=_optional_string(record, "description") or "",
            members=tuple(_parse_member(item) for item in members),
        )
    except ValueError as error:
        raise ValueError(f"invalid user frequency set: {error}") from error


def _parse_member(record: Mapping[str, object]) -> FrequencySetMember:
    channel_designator = _optional_string(record, "channel_designator")
    return FrequencySetMember(
        frequency_definition_id=_required_string(
            record, "frequency_definition_id"
        ),
        position=_required_integer(record, "position"),
        channel_designator=channel_designator,
    )


def _require_user_owned(record: Mapping[str, object], label: str) -> None:
    origin = record.get("origin", "user")
    read_only = record.get("read_only", False)
    if origin != "user" or read_only is not False:
        raise ValueError(f"{label} records supplied by the user must be user-owned")


def _required_string(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_string(record: Mapping[str, object], key: str) -> str | None:
    value = record.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string or null")
    return value


def _required_integer(record: Mapping[str, object], key: str) -> int:
    value = record.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _optional_integer(record: Mapping[str, object], key: str) -> int | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer or null")
    return value


def _optional_number(record: Mapping[str, object], key: str) -> float | None:
    value = record.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{key} must be a number or null")
    return float(value)
