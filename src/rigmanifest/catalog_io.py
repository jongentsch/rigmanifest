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
    SignalingKind,
    SignalingSpec,
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
    transmit_access, receive_squelch = _parse_signaling_pair(record)

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
            transmit_access=transmit_access,
            receive_squelch=receive_squelch,
            tags=frozenset(tags),
            priority=Priority[
                (_optional_string(record, "priority") or "normal").upper()
            ],
            notes=_optional_string(record, "notes") or "",
            power_dbm=_optional_number(record, "power_dbm"),
            power_label=_optional_string(record, "power_label"),
            scan_skip=_optional_string(record, "scan_skip") or "",
            tuning_step_hz=_optional_integer(record, "tuning_step_hz"),
        )
    except (KeyError, ValueError) as error:
        raise ValueError(f"invalid user frequency definition: {error}") from error


def _parse_signaling_pair(
    record: Mapping[str, object],
) -> tuple[SignalingSpec, SignalingSpec]:
    transmit_record = record.get("transmit_access")
    receive_record = record.get("receive_squelch")
    if transmit_record is not None or receive_record is not None:
        if not isinstance(transmit_record, Mapping) or not isinstance(
            receive_record, Mapping
        ):
            raise ValueError(
                "transmit_access and receive_squelch must both be objects"
            )
        return _parse_signaling(transmit_record), _parse_signaling(receive_record)

    legacy = record.get("tone", {})
    if not isinstance(legacy, Mapping):
        raise ValueError("legacy frequency definition tone must be an object")
    return _migrate_legacy_tone(legacy)


def _parse_signaling(record: Mapping[str, object]) -> SignalingSpec:
    return SignalingSpec(
        kind=SignalingKind(_optional_string(record, "kind") or "none"),
        ctcss_hz=_optional_number(record, "ctcss_hz"),
        dcs_code=_optional_integer(record, "dcs_code"),
        dcs_polarity=_optional_string(record, "dcs_polarity") or "N",
    )


def _migrate_legacy_tone(
    record: Mapping[str, object],
) -> tuple[SignalingSpec, SignalingSpec]:
    mode = _optional_string(record, "mode") or "none"
    encode_hz = _optional_number(record, "encode_hz")
    decode_hz = _optional_number(record, "decode_hz")
    dcs_code = _optional_integer(record, "dtcs_code")
    polarity = _optional_string(record, "dtcs_polarity") or "NN"
    if polarity not in {"NN", "NR", "RN", "RR"}:
        raise ValueError("legacy DTCS polarity must be NN, NR, RN, or RR")
    if mode == "none":
        return SignalingSpec(), SignalingSpec()
    if mode == "tone":
        return (
            SignalingSpec(kind=SignalingKind.CTCSS, ctcss_hz=encode_hz),
            SignalingSpec(),
        )
    if mode == "tsql":
        return (
            SignalingSpec(kind=SignalingKind.CTCSS, ctcss_hz=encode_hz),
            SignalingSpec(
                kind=SignalingKind.CTCSS,
                ctcss_hz=decode_hz or encode_hz,
            ),
        )
    if mode == "dtcs":
        return (
            SignalingSpec(
                kind=SignalingKind.DCS,
                dcs_code=dcs_code,
                dcs_polarity=polarity[0],
            ),
            SignalingSpec(
                kind=SignalingKind.DCS,
                dcs_code=dcs_code,
                dcs_polarity=polarity[1],
            ),
        )
    raise ValueError(f"unsupported legacy tone mode: {mode}")


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
