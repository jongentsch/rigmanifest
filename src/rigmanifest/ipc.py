"""JSON-serializable application boundary shared with the desktop sidecar."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from rigmanifest.capabilities import BUILTIN_TARGETS
from rigmanifest.catalog_io import catalog_with_user_records
from rigmanifest.chirp_adapter import chirp_memory_validator
from rigmanifest.compiler import compile_profile
from rigmanifest.exporters.chirp_csv import write_chirp_csv
from rigmanifest.frequency_plans import BUILTIN_FREQUENCY_PLANS
from rigmanifest.fixtures import BUILTIN_CATALOG, BUILTIN_PROFILES
from rigmanifest.models import CompilationSettings, CompiledRadioPlan, SignalingSpec


class RequestError(ValueError):
    """An invalid request that can be safely reported to an IPC caller."""


def compile_builtin(
    profile_id: str,
    target_id: str,
    *,
    frequency_set_ids: Sequence[str] | None = None,
    user_frequency_definitions: Sequence[Mapping[str, object]] | None = None,
    user_frequency_sets: Sequence[Mapping[str, object]] | None = None,
    output_path: Path | None = None,
    settings: CompilationSettings | None = None,
) -> dict[str, Any]:
    """Compile built-in catalog data and return the stable application DTO."""

    profile = BUILTIN_PROFILES.get(profile_id.casefold())
    if profile is None:
        raise RequestError(f"unknown profile: {profile_id}")
    target = BUILTIN_TARGETS.get(target_id.casefold())
    if target is None:
        raise RequestError(f"unknown target: {target_id}")
    if frequency_set_ids is not None:
        profile = replace(profile, frequency_set_ids=tuple(frequency_set_ids))

    if (user_frequency_definitions is None) != (user_frequency_sets is None):
        raise RequestError(
            "user_frequency_definitions and user_frequency_sets must be supplied together"
        )
    catalog = BUILTIN_CATALOG
    if user_frequency_definitions is not None and user_frequency_sets is not None:
        try:
            catalog = catalog_with_user_records(
                BUILTIN_CATALOG,
                user_frequency_definitions,
                user_frequency_sets,
            )
        except ValueError as error:
            raise RequestError(str(error)) from error

    try:
        validator = (
            chirp_memory_validator(target.chirp_driver_reference)
            if target.chirp_driver_reference
            else None
        )
        plan = compile_profile(
            catalog,
            profile,
            target,
            settings,
            memory_validator=validator,
        )
    except ValueError as error:
        raise RequestError(str(error)) from error
    if output_path is not None:
        write_chirp_csv(plan, output_path)

    result = plan_to_dict(plan)
    result["csv_path"] = str(output_path) if output_path is not None else None
    return result


def frequency_definitions_to_list() -> list[dict[str, Any]]:
    return [
        {
            "id": definition.id,
            "name": definition.name,
            "origin": definition.origin.value,
            "read_only": definition.read_only,
            "receive_frequency_hz": definition.receive_frequency_hz,
            "transmit_behavior": definition.transmit_behavior.value,
            "transmit_frequency_hz": definition.transmit_frequency_hz,
            "offset_hz": definition.offset_hz,
            "mode": definition.mode.value,
            "transmit_access": _signaling_to_dict(definition.transmit_access),
            "receive_squelch": _signaling_to_dict(definition.receive_squelch),
            "tags": sorted(definition.tags),
            "priority": definition.priority.name.lower(),
            "notes": definition.notes,
        }
        for definition in sorted(BUILTIN_CATALOG.definitions, key=lambda item: item.id)
    ]


def frequency_sets_to_list() -> list[dict[str, Any]]:
    return [
        {
            "id": frequency_set.id,
            "name": frequency_set.name,
            "origin": frequency_set.origin.value,
            "read_only": frequency_set.read_only,
            "description": frequency_set.description,
            "members": [
                {
                    "frequency_definition_id": member.frequency_definition_id,
                    "position": member.position,
                    "channel_designator": member.channel_designator,
                }
                for member in frequency_set.ordered_members
            ],
        }
        for frequency_set in sorted(BUILTIN_CATALOG.sets, key=lambda item: item.id)
    ]


def catalog_to_dict() -> dict[str, Any]:
    """Return shared preset/user catalog data without running compilation."""

    return {
        "schema_version": 5,
        "profiles": [
            {
                "id": profile.id,
                "name": profile.name,
                "frequency_set_ids": list(profile.frequency_set_ids),
            }
            for profile in sorted(BUILTIN_PROFILES.values(), key=lambda item: item.id)
        ],
        "radio_models": [
            {
                "id": target.id,
                "manufacturer": target.manufacturer,
                "model": target.model,
                "memory_capacity": target.capabilities.memory_capacity,
                "memory_start": target.capabilities.memory_start,
                "max_label_length": target.capabilities.max_label_length,
                "supports_banks": target.capabilities.supports_banks,
                "bank_count": target.capabilities.bank_count,
                "chirp_driver_reference": target.chirp_driver_reference,
                "receive_ranges": [
                    [item.lower_hz, item.upper_hz]
                    for item in target.capabilities.receive_ranges
                ],
                "transmit_ranges": [
                    [item.lower_hz, item.upper_hz]
                    for item in target.capabilities.transmit_ranges
                ],
                "supported_modes": sorted(
                    item.value for item in target.capabilities.supported_modes
                ),
                "supported_tone_modes": sorted(
                    item.value for item in target.capabilities.supported_tone_modes
                ),
                "valid_cross_modes": list(target.capabilities.valid_cross_modes),
                "valid_tuning_steps_hz": list(
                    target.capabilities.valid_tuning_steps_hz
                ),
                "valid_ctcss_tones_hz": list(
                    target.capabilities.valid_ctcss_tones_hz
                ),
                "valid_dtcs_codes": list(target.capabilities.valid_dtcs_codes),
                "factory_frequency_sets": [
                    {
                        "frequency_set_id": relation.frequency_set_id,
                        "frequency_set_name": BUILTIN_CATALOG.frequency_set(
                            relation.frequency_set_id
                        ).name,
                        "interface_label": relation.interface_label,
                        "frequency_editing": relation.frequency_editing.value,
                        "chirp_editing": relation.chirp_editing.value,
                    }
                    for relation in target.factory_frequency_sets
                ],
            }
            for target in sorted(BUILTIN_TARGETS.values(), key=lambda item: item.id)
        ],
        "frequency_sets": frequency_sets_to_list(),
        "frequency_definitions": frequency_definitions_to_list(),
        "frequency_plans": [
            {
                "id": plan.id,
                "name": plan.name,
                "jurisdiction": plan.jurisdiction,
                "authority_tier": plan.authority_tier.value,
                "reviewed_at": plan.reviewed_at,
                "source_label": plan.source_label,
                "source_url": plan.source_url,
                "advisory": plan.advisory,
                "segments": [
                    {
                        "id": segment.id,
                        "name": segment.name,
                        "lower_hz": segment.lower_hz,
                        "upper_hz": segment.upper_hz,
                        "use": segment.use.value,
                        "suggested_offset_hz": segment.suggested_offset_hz,
                        "raster_anchor_hz": segment.raster_anchor_hz,
                        "raster_spacing_hz": segment.raster_spacing_hz,
                        "notes": segment.notes,
                    }
                    for segment in plan.segments
                ],
            }
            for plan in sorted(BUILTIN_FREQUENCY_PLANS.values(), key=lambda item: item.id)
        ],
    }


def plan_to_dict(plan: CompiledRadioPlan) -> dict[str, Any]:
    """Convert a compiled plan into an explicit, versionable wire shape."""

    return {
        "schema_version": 4,
        "compiler_version": plan.compiler_version,
        "profile": {
            "id": plan.profile.id,
            "name": plan.profile.name,
            "frequency_set_ids": list(plan.profile.frequency_set_ids),
        },
        "target": {
            "id": plan.target.id,
            "manufacturer": plan.target.manufacturer,
            "model": plan.target.model,
        },
        "summary": {
            "included": len(plan.memories) + plan.factory_definition_count,
            "programmed": len(plan.memories),
            "factory_provided": plan.factory_definition_count,
            "factory_sets": len(plan.factory_sets),
            "omitted": len(plan.omitted_frequency_definitions),
            "warnings": plan.warning_count,
            "errors": plan.error_count,
        },
        "capacity": {
            "capacity": plan.capacity_summary.capacity,
            "compatible_candidates": plan.capacity_summary.compatible_candidates,
            "used": plan.capacity_summary.used,
            "omitted_for_capacity": plan.capacity_summary.omitted_for_capacity,
        },
        "memories": [
            {
                "source_frequency_definition_id": memory.source_frequency_definition_id,
                "source_frequency_set_ids": list(memory.source_frequency_set_ids),
                "memory_number": memory.memory_number,
                "target_name": memory.target_name,
                "receive_frequency_hz": memory.receive_frequency_hz,
                "transmit_behavior": memory.transmit_behavior.value,
                "transmit_frequency_hz": memory.transmit_frequency_hz,
                "offset_hz": memory.offset_hz,
                "mode": memory.mode.value,
                "transmit_access": _signaling_to_dict(memory.transmit_access),
                "receive_squelch": _signaling_to_dict(memory.receive_squelch),
                "bank_assignments": list(memory.bank_assignments),
                "applied_transformations": [
                    code.value for code in memory.applied_transformations
                ],
            }
            for memory in plan.memories
        ],
        "factory_sets": [
            {
                "frequency_set_id": item.frequency_set_id,
                "frequency_set_name": item.frequency_set_name,
                "interface_label": item.interface_label,
                "frequency_definition_ids": list(item.frequency_definition_ids),
                "definition_count": item.definition_count,
                "frequency_editing": item.frequency_editing.value,
                "chirp_editing": item.chirp_editing.value,
            }
            for item in plan.factory_sets
        ],
        "omitted_frequency_definitions": [
            {
                "frequency_definition_id": item.frequency_definition_id,
                "reason": item.reason.value,
            }
            for item in plan.omitted_frequency_definitions
        ],
        "diagnostics": [
            {
                "code": item.code.value,
                "severity": item.severity.value,
                "frequency_definition_id": item.frequency_definition_id,
                "frequency_set_id": item.frequency_set_id,
                "message": item.message,
                "details": dict(item.details),
            }
            for item in plan.diagnostics
        ],
    }


def _signaling_to_dict(signaling: SignalingSpec) -> dict[str, object]:
    return {
        "kind": signaling.kind.value,
        "ctcss_hz": signaling.ctcss_hz,
        "dcs_code": signaling.dcs_code,
        "dcs_polarity": signaling.dcs_polarity,
    }


def handle_request(request: Mapping[str, object]) -> dict[str, object]:
    """Handle one sidecar request without reading frontend state."""

    request_id = request.get("id")
    try:
        method = request.get("method")
        if method == "catalog":
            return {"id": request_id, "result": catalog_to_dict()}
        if method != "compile":
            raise RequestError("unsupported method")
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise RequestError("params must be an object")

        profile = params.get("profile")
        target = params.get("target")
        output = params.get("output_path")
        frequency_sets = params.get("frequency_set_ids")
        user_definitions = params.get("user_frequency_definitions")
        user_sets = params.get("user_frequency_sets")
        memory_start = params.get("memory_start")
        map_sets = params.get("map_sets_to_banks", True)
        use_factory = params.get("use_factory_sets", True)
        if not isinstance(profile, str) or not isinstance(target, str):
            raise RequestError("profile and target must be strings")
        if output is not None and not isinstance(output, str):
            raise RequestError("output_path must be a string or null")
        if frequency_sets is not None and (
            not isinstance(frequency_sets, list)
            or not frequency_sets
            or not all(isinstance(item, str) for item in frequency_sets)
        ):
            raise RequestError("frequency_set_ids must be a non-empty string array")
        if (user_definitions is None) != (user_sets is None):
            raise RequestError(
                "user_frequency_definitions and user_frequency_sets must be supplied together"
            )
        if user_definitions is not None and (
            not isinstance(user_definitions, list)
            or not all(isinstance(item, Mapping) for item in user_definitions)
        ):
            raise RequestError("user_frequency_definitions must be an object array")
        if user_sets is not None and (
            not isinstance(user_sets, list)
            or not all(isinstance(item, Mapping) for item in user_sets)
        ):
            raise RequestError("user_frequency_sets must be an object array")
        if memory_start is not None and (
            isinstance(memory_start, bool) or not isinstance(memory_start, int)
        ):
            raise RequestError("memory_start must be an integer or null")
        if not isinstance(map_sets, bool) or not isinstance(use_factory, bool):
            raise RequestError("radio configuration flags must be booleans")

        try:
            settings = CompilationSettings(
                memory_start=memory_start,
                map_sets_to_banks=map_sets,
                use_factory_sets=use_factory,
            )
        except ValueError as error:
            raise RequestError(str(error)) from error

        result = compile_builtin(
            profile,
            target,
            frequency_set_ids=frequency_sets,
            user_frequency_definitions=user_definitions,
            user_frequency_sets=user_sets,
            output_path=Path(output) if output is not None else None,
            settings=settings,
        )
        return {"id": request_id, "result": result}
    except RequestError as error:
        return {
            "id": request_id,
            "error": {"code": "INVALID_REQUEST", "message": str(error)},
        }
