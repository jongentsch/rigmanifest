"""JSON-serializable application boundary shared with the desktop sidecar."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from typing import Any, Mapping, Sequence

from chirp import chirp_common

from rigmanifest.capabilities import BUILTIN_TARGETS
from rigmanifest.catalog_io import catalog_with_user_records
from rigmanifest.chirp_import import ChirpCatalogImport, import_chirp_csv
from rigmanifest.chirp_image import (
    ChirpImageImport,
    image_memory_validator,
    import_chirp_image,
    load_chirp_image,
    write_compiled_image,
)
from rigmanifest.chirp_adapter import chirp_memory_validator
from rigmanifest.compiler import compile_profiles
from rigmanifest.exporters.chirp_csv import write_chirp_csv
from rigmanifest.frequency_plans import BUILTIN_FREQUENCY_PLANS
from rigmanifest.fixtures import BUILTIN_CATALOG, BUILTIN_PROFILES
from rigmanifest.models import (
    CompilationSettings,
    CompiledRadioPlan,
    FrequencyDefinition,
    FrequencySet,
    SignalingSpec,
)
from rigmanifest.profile_io import profile_to_dict, profiles_from_records
from rigmanifest.workspace import RadioImageVersion, SQLiteWorkspace


class RequestError(ValueError):
    """An invalid request that can be safely reported to an IPC caller."""


def compile_builtin(
    profile_id: str | None,
    target_id: str,
    *,
    frequency_set_ids: Sequence[str] | None = None,
    profiles: Sequence[Mapping[str, object]] | None = None,
    additional_frequency_set_ids: Sequence[str] = (),
    additional_frequency_definition_ids: Sequence[str] = (),
    advisory_plan_id: str | None = None,
    user_frequency_definitions: Sequence[Mapping[str, object]] | None = None,
    user_frequency_sets: Sequence[Mapping[str, object]] | None = None,
    output_path: Path | None = None,
    settings: CompilationSettings | None = None,
) -> dict[str, Any]:
    """Compile built-in catalog data and return the stable application DTO."""

    target = BUILTIN_TARGETS.get(target_id.casefold())
    if target is None:
        raise RequestError(f"unknown target: {target_id}")
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

    if profiles is None:
        if profile_id is None:
            raise RequestError("a profile or profiles array is required")
        profile = BUILTIN_PROFILES.get(profile_id.casefold())
        if profile is None:
            raise RequestError(f"unknown profile: {profile_id}")
        if frequency_set_ids is not None:
            profile = replace(profile, frequency_set_ids=tuple(frequency_set_ids))
        selected_profiles = (profile,)
    else:
        try:
            selected_profiles = profiles_from_records(profiles, catalog)
        except ValueError as error:
            raise RequestError(str(error)) from error

    try:
        validator = (
            chirp_memory_validator(target.chirp_driver_reference)
            if target.chirp_driver_reference
            else None
        )
        plan = compile_profiles(
            catalog,
            selected_profiles,
            target,
            settings,
            additional_frequency_set_ids=tuple(additional_frequency_set_ids),
            additional_frequency_definition_ids=tuple(
                additional_frequency_definition_ids
            ),
            advisory_plan_id=advisory_plan_id,
            memory_validator=validator,
        )
    except ValueError as error:
        raise RequestError(str(error)) from error
    if output_path is not None:
        write_chirp_csv(plan, output_path)

    result = plan_to_dict(plan)
    result["csv_path"] = str(output_path) if output_path is not None else None
    return result


def compile_radio_image(
    database_path: Path,
    radio_id: str,
    *,
    profiles: Sequence[Mapping[str, object]],
    additional_frequency_set_ids: Sequence[str] = (),
    additional_frequency_definition_ids: Sequence[str] = (),
    advisory_plan_id: str | None = None,
    user_frequency_definitions: Sequence[Mapping[str, object]],
    user_frequency_sets: Sequence[Mapping[str, object]],
    output_path: Path | None = None,
    settings: CompilationSettings | None = None,
) -> dict[str, Any]:
    """Compile reusable intent against the exact CHIRP driver in a stored image."""

    workspace = SQLiteWorkspace(database_path)
    source_path = workspace.radio_image_path(radio_id)
    catalog = catalog_with_user_records(
        BUILTIN_CATALOG,
        user_frequency_definitions,
        user_frequency_sets,
    )
    selected_profiles = profiles_from_records(profiles, catalog)

    imported = import_chirp_image(source_path, radio_id=radio_id)
    radio = load_chirp_image(source_path)
    try:
        plan = compile_profiles(
            catalog,
            selected_profiles,
            imported.target,
            settings,
            additional_frequency_set_ids=tuple(additional_frequency_set_ids),
            additional_frequency_definition_ids=tuple(
                additional_frequency_definition_ids
            ),
            advisory_plan_id=advisory_plan_id,
            memory_validator=image_memory_validator(radio),
        )
    except ValueError as error:
        raise RequestError(str(error)) from error

    image_version: RadioImageVersion | None = None
    if output_path is not None:
        with TemporaryDirectory(prefix="rigmanifest-image-") as directory_name:
            compiled_path = Path(directory_name) / "compiled.img"
            bank_names = {item.id: item.name for item in catalog.sets}
            write_compiled_image(
                plan,
                source_path,
                compiled_path,
                bank_names=bank_names,
            )
            image_version = workspace.store_radio_image(
                radio_id,
                compiled_path.read_bytes(),
                original_filename=output_path.name,
                driver_reference=imported.driver_reference,
                kind="compiled",
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(image_version.path, output_path)

    result = plan_to_dict(plan)
    result["image_path"] = str(output_path) if output_path is not None else None
    result["managed_image_path"] = (
        str(image_version.path) if image_version is not None else None
    )
    result["image_version"] = (
        _radio_image_version_to_dict(image_version)
        if image_version is not None
        else None
    )
    result["csv_path"] = None
    return result


def frequency_definitions_to_list() -> list[dict[str, Any]]:
    return [
        _definition_to_dict(definition)
        for definition in sorted(BUILTIN_CATALOG.definitions, key=lambda item: item.id)
    ]


def frequency_sets_to_list() -> list[dict[str, Any]]:
    return [
        _set_to_dict(frequency_set)
        for frequency_set in sorted(BUILTIN_CATALOG.sets, key=lambda item: item.id)
    ]


def catalog_to_dict() -> dict[str, Any]:
    """Return shared preset/user catalog data without running compilation."""

    return {
        "schema_version": 7,
        "ctcss_tones_hz": [float(tone) for tone in chirp_common.TONES],
        "profiles": [
            profile_to_dict(profile)
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
        "schema_version": 6,
        "compiler_version": plan.compiler_version,
        "profile": {
            "id": plan.profile.id,
            "name": plan.profile.name,
            "frequency_set_ids": list(plan.profile.frequency_set_ids),
        },
        "profiles": [profile_to_dict(profile) for profile in plan.profiles],
        "selection": {
            "additional_frequency_set_ids": list(
                plan.additional_frequency_set_ids
            ),
            "additional_frequency_definition_ids": list(
                plan.additional_frequency_definition_ids
            ),
            "advisory_plan_id": plan.advisory_plan_id,
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
                "source_profile_ids": list(memory.source_profile_ids),
                "selected_directly": memory.selected_directly,
                "memory_number": memory.memory_number,
                "target_name": memory.target_name,
                "receive_frequency_hz": memory.receive_frequency_hz,
                "transmit_behavior": memory.transmit_behavior.value,
                "transmit_frequency_hz": memory.transmit_frequency_hz,
                "offset_hz": memory.offset_hz,
                "mode": memory.mode.value,
                "transmit_access": _signaling_to_dict(memory.transmit_access),
                "receive_squelch": _signaling_to_dict(memory.receive_squelch),
                "power_dbm": memory.power_dbm,
                "power_label": memory.power_label,
                "scan_skip": memory.scan_skip,
                "tuning_step_hz": memory.tuning_step_hz,
                "bank_assignments": list(memory.bank_assignments),
                "applied_transformations": [
                    code.value for code in memory.applied_transformations
                ],
            }
            for memory in plan.memories
        ],
        "banks": [
            {
                "bank_number": bank.bank_number,
                "frequency_set_id": bank.frequency_set_id,
                "name": bank.name,
                "memory_numbers": list(bank.memory_numbers),
            }
            for bank in plan.banks
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


def _definition_to_dict(definition: FrequencyDefinition) -> dict[str, Any]:
    return {
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
        "power_dbm": definition.power_dbm,
        "power_label": definition.power_label,
        "scan_skip": definition.scan_skip,
        "tuning_step_hz": definition.tuning_step_hz,
    }


def _set_to_dict(frequency_set: FrequencySet) -> dict[str, Any]:
    return {
        "id": frequency_set.id,
        "name": frequency_set.name,
        "origin": frequency_set.origin.value,
        "read_only": frequency_set.read_only,
        "description": frequency_set.description,
        "jurisdiction": frequency_set.jurisdiction,
        "source_label": frequency_set.source_label,
        "source_url": frequency_set.source_url,
        "reviewed_at": frequency_set.reviewed_at,
        "members": [
            {
                "frequency_definition_id": member.frequency_definition_id,
                "position": member.position,
                "channel_designator": member.channel_designator,
            }
            for member in frequency_set.ordered_members
        ],
    }


def _import_to_dict(imported: ChirpCatalogImport) -> dict[str, Any]:
    return {
        "source_path": str(imported.source_path),
        "definition_count": imported.definition_count,
        "frequency_definitions": [
            _definition_to_dict(definition)
            for definition in imported.frequency_definitions
        ],
        "frequency_set": _set_to_dict(imported.frequency_set),
    }


def _image_import_to_dict(imported: ChirpImageImport) -> dict[str, Any]:
    target = imported.target
    return {
        "source_path": str(imported.source_path),
        "source_filename": imported.source_path.name,
        "driver_reference": imported.driver_reference,
        "manufacturer": target.manufacturer,
        "model": target.model,
        "definition_count": imported.definition_count,
        "bank_count": imported.bank_count,
        "setting_count": imported.setting_count,
        "memory_start": target.capabilities.memory_start,
        "memory_capacity": target.capabilities.memory_capacity,
        "max_label_length": target.capabilities.max_label_length,
        "frequency_definitions": [
            _definition_to_dict(definition)
            for definition in imported.frequency_definitions
        ],
        "frequency_sets": [
            _set_to_dict(frequency_set) for frequency_set in imported.frequency_sets
        ],
        "profile": profile_to_dict(imported.profile),
    }


def _radio_image_version_to_dict(version: RadioImageVersion) -> dict[str, object]:
    return version.to_dict()


def handle_request(request: Mapping[str, object]) -> dict[str, object]:
    """Handle one sidecar request without reading frontend state."""

    request_id = request.get("id")
    try:
        method = request.get("method")
        if method == "catalog":
            return {"id": request_id, "result": catalog_to_dict()}
        if method in {"load_workspace", "save_workspace", "backup_workspace"}:
            params = request.get("params")
            if not isinstance(params, Mapping):
                raise RequestError("params must be an object")
            database_path = params.get("database_path")
            if not isinstance(database_path, str) or not database_path:
                raise RequestError("database_path must be a non-empty string")
            workspace = SQLiteWorkspace(Path(database_path))
            try:
                if method == "load_workspace":
                    legacy = params.get("legacy_state")
                    if legacy is not None and not isinstance(legacy, Mapping):
                        raise RequestError("legacy_state must be an object or null")
                    return {"id": request_id, "result": workspace.load(legacy)}
                if method == "save_workspace":
                    state = params.get("state")
                    if not isinstance(state, Mapping):
                        raise RequestError("state must be an object")
                    return {"id": request_id, "result": workspace.save(state)}
                destination = params.get("destination")
                if not isinstance(destination, str) or not destination:
                    raise RequestError("destination must be a non-empty string")
                path = workspace.backup(Path(destination))
                return {"id": request_id, "result": {"path": str(path)}}
            except (OSError, sqlite3.Error, ValueError) as error:
                raise RequestError(str(error)) from error
        if method == "import_chirp_csv":
            params = request.get("params")
            if not isinstance(params, Mapping):
                raise RequestError("params must be an object")
            source_path = params.get("source_path")
            if not isinstance(source_path, str) or not source_path:
                raise RequestError("source_path must be a non-empty string")
            try:
                imported = import_chirp_csv(Path(source_path))
            except ValueError as error:
                raise RequestError(str(error)) from error
            return {"id": request_id, "result": _import_to_dict(imported)}
        if method == "import_chirp_image":
            params = request.get("params")
            if not isinstance(params, Mapping):
                raise RequestError("params must be an object")
            source_path = params.get("source_path")
            database_path = params.get("database_path")
            radio_id = params.get("radio_id")
            if not isinstance(source_path, str) or not source_path:
                raise RequestError("source_path must be a non-empty string")
            if not isinstance(database_path, str) or not database_path:
                raise RequestError("database_path must be a non-empty string")
            if not isinstance(radio_id, str) or not radio_id:
                raise RequestError("radio_id must be a non-empty string")
            path = Path(source_path)
            try:
                imported = import_chirp_image(path, radio_id=radio_id)
                version = SQLiteWorkspace(Path(database_path)).store_radio_image(
                    radio_id,
                    path.read_bytes(),
                    original_filename=path.name,
                    driver_reference=imported.driver_reference,
                )
            except (OSError, sqlite3.Error, ValueError) as error:
                raise RequestError(str(error)) from error
            result = _image_import_to_dict(imported)
            result["image_version"] = _radio_image_version_to_dict(version)
            return {"id": request_id, "result": result}
        if method == "list_radio_images":
            params = request.get("params")
            if not isinstance(params, Mapping):
                raise RequestError("params must be an object")
            database_path = params.get("database_path")
            radio_id = params.get("radio_id")
            if not isinstance(database_path, str) or not database_path:
                raise RequestError("database_path must be a non-empty string")
            if not isinstance(radio_id, str) or not radio_id:
                raise RequestError("radio_id must be a non-empty string")
            try:
                versions = SQLiteWorkspace(Path(database_path)).radio_image_versions(
                    radio_id
                )
            except (OSError, sqlite3.Error, ValueError) as error:
                raise RequestError(str(error)) from error
            return {
                "id": request_id,
                "result": {
                    "versions": [
                        _radio_image_version_to_dict(version)
                        for version in versions
                    ]
                },
            }
        if method != "compile":
            raise RequestError("unsupported method")
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise RequestError("params must be an object")

        profile = params.get("profile")
        profile_records = params.get("profiles")
        target = params.get("target")
        radio_id = params.get("radio_id")
        database_path = params.get("database_path")
        output = params.get("output_path")
        frequency_sets = params.get("frequency_set_ids")
        additional_sets = params.get("additional_frequency_set_ids", [])
        additional_definitions = params.get(
            "additional_frequency_definition_ids",
            [],
        )
        advisory_plan = params.get("advisory_plan_id")
        user_definitions = params.get("user_frequency_definitions")
        user_sets = params.get("user_frequency_sets")
        memory_start = params.get("memory_start")
        map_sets = params.get("map_sets_to_banks", True)
        use_factory = params.get("use_factory_sets", True)
        image_backed = radio_id is not None or database_path is not None
        if image_backed:
            if not isinstance(radio_id, str) or not radio_id:
                raise RequestError("radio_id must be a non-empty string")
            if not isinstance(database_path, str) or not database_path:
                raise RequestError("database_path must be a non-empty string")
        elif not isinstance(target, str):
            raise RequestError("target must be a string")
        if profile_records is None and not isinstance(profile, str):
            raise RequestError("profile must be a string when profiles are omitted")
        if profile_records is not None and (
            not isinstance(profile_records, list)
            or not all(isinstance(item, Mapping) for item in profile_records)
        ):
            raise RequestError("profiles must be an object array")
        if output is not None and not isinstance(output, str):
            raise RequestError("output_path must be a string or null")
        if frequency_sets is not None and (
            not isinstance(frequency_sets, list)
            or not frequency_sets
            or not all(isinstance(item, str) for item in frequency_sets)
        ):
            raise RequestError("frequency_set_ids must be a non-empty string array")
        for value, label in (
            (additional_sets, "additional_frequency_set_ids"),
            (additional_definitions, "additional_frequency_definition_ids"),
        ):
            if not isinstance(value, list) or not all(
                isinstance(item, str) and item for item in value
            ):
                raise RequestError(f"{label} must be a string array")
        if advisory_plan is not None and (
            not isinstance(advisory_plan, str) or not advisory_plan
        ):
            raise RequestError("advisory_plan_id must be a non-empty string or null")
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

        if image_backed:
            if profile_records is None:
                raise RequestError("image-backed compilation requires profiles")
            if user_definitions is None or user_sets is None:
                raise RequestError(
                    "image-backed compilation requires the user catalog"
                )
            try:
                result = compile_radio_image(
                    Path(database_path),
                    radio_id,
                    profiles=profile_records,
                    additional_frequency_set_ids=additional_sets,
                    additional_frequency_definition_ids=additional_definitions,
                    advisory_plan_id=advisory_plan,
                    user_frequency_definitions=user_definitions,
                    user_frequency_sets=user_sets,
                    output_path=Path(output) if output is not None else None,
                    settings=settings,
                )
            except (OSError, sqlite3.Error, ValueError) as error:
                raise RequestError(str(error)) from error
        else:
            result = compile_builtin(
                profile if isinstance(profile, str) else None,
                target,
                frequency_set_ids=frequency_sets,
                profiles=profile_records,
                additional_frequency_set_ids=additional_sets,
                additional_frequency_definition_ids=additional_definitions,
                advisory_plan_id=advisory_plan,
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
