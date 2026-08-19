"""Validation and wire conversion for persisted profile records."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rigmanifest.frequency_plans import BUILTIN_FREQUENCY_PLANS
from rigmanifest.models import FrequencyCatalog, Profile


def profiles_from_records(
    records: Sequence[Mapping[str, object]],
    catalog: FrequencyCatalog,
) -> tuple[Profile, ...]:
    profiles = tuple(_parse_profile(record) for record in records)
    ids = [profile.id for profile in profiles]
    if len(ids) != len(set(ids)):
        raise ValueError("profiles contain a duplicate ID")
    for profile in profiles:
        for set_id in profile.frequency_set_ids:
            try:
                catalog.frequency_set(set_id)
            except KeyError as error:
                raise ValueError(
                    f"profile {profile.id} references unknown frequency set: {set_id}"
                ) from error
        for definition_id in profile.frequency_definition_ids:
            try:
                catalog.definition(definition_id)
            except KeyError as error:
                raise ValueError(
                    f"profile {profile.id} references unknown frequency definition: "
                    f"{definition_id}"
                ) from error
        if (
            profile.frequency_plan_id is not None
            and profile.frequency_plan_id not in BUILTIN_FREQUENCY_PLANS
        ):
            raise ValueError(
                f"profile {profile.id} references unknown frequency plan: "
                f"{profile.frequency_plan_id}"
            )
    return profiles


def profile_to_dict(profile: Profile) -> dict[str, object]:
    return {
        "id": profile.id,
        "name": profile.name,
        "description": profile.description,
        "frequency_set_ids": list(profile.frequency_set_ids),
        "frequency_definition_ids": list(profile.frequency_definition_ids),
        "frequency_plan_id": profile.frequency_plan_id,
    }


def _parse_profile(record: Mapping[str, object]) -> Profile:
    set_ids = _string_array(record, "frequency_set_ids")
    definition_ids = _string_array(record, "frequency_definition_ids")
    plan_id = record.get("frequency_plan_id")
    if plan_id is not None and (not isinstance(plan_id, str) or not plan_id):
        raise ValueError("profile frequency_plan_id must be a non-empty string or null")
    description = record.get("description", "")
    if not isinstance(description, str):
        raise ValueError("profile description must be a string")
    try:
        return Profile(
            id=_required_string(record, "id"),
            name=_required_string(record, "name"),
            frequency_set_ids=tuple(set_ids),
            frequency_plan_id=plan_id,
            frequency_definition_ids=tuple(definition_ids),
            description=description,
        )
    except ValueError as error:
        raise ValueError(f"invalid profile: {error}") from error


def _required_string(record: Mapping[str, object], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"profile {key} must be a non-empty string")
    return value


def _string_array(record: Mapping[str, object], key: str) -> list[str]:
    value = record.get(key, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"profile {key} must be a string array")
    return value
