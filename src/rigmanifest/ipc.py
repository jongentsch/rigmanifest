"""JSON-serializable application boundary shared with the desktop sidecar."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from rigmanifest.capabilities import BUILTIN_TARGETS
from rigmanifest.compiler import compile_profile
from rigmanifest.exporters.chirp_csv import write_chirp_csv
from rigmanifest.fixtures import BUILTIN_PROFILES, HOME_CHANNELS
from rigmanifest.models import CompiledRadioPlan


class RequestError(ValueError):
    """An invalid request that can be safely reported to an IPC caller."""


def compile_builtin(
    profile_id: str,
    target_id: str,
    *,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Compile built-in data and return the stable application DTO."""

    profile = BUILTIN_PROFILES.get(profile_id.casefold())
    if profile is None:
        raise RequestError(f"unknown profile: {profile_id}")
    target = BUILTIN_TARGETS.get(target_id.casefold())
    if target is None:
        raise RequestError(f"unknown target: {target_id}")

    plan = compile_profile(HOME_CHANNELS, profile, target)
    if output_path is not None:
        write_chirp_csv(plan, output_path)

    result = plan_to_dict(plan)
    result["csv_path"] = str(output_path) if output_path is not None else None
    return result


def plan_to_dict(plan: CompiledRadioPlan) -> dict[str, Any]:
    """Convert a compiled plan into an explicit, versionable wire shape."""

    return {
        "schema_version": 1,
        "compiler_version": plan.compiler_version,
        "profile": {"id": plan.profile.id, "name": plan.profile.name},
        "target": {
            "id": plan.target.id,
            "manufacturer": plan.target.manufacturer,
            "model": plan.target.model,
        },
        "summary": {
            "included": len(plan.memories),
            "omitted": len(plan.omitted_channels),
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
                "source_channel_id": memory.source_channel_id,
                "memory_number": memory.memory_number,
                "target_name": memory.target_name,
                "receive_frequency_hz": memory.receive_frequency_hz,
                "transmit_behavior": memory.transmit_behavior.value,
                "transmit_frequency_hz": memory.transmit_frequency_hz,
                "offset_hz": memory.offset_hz,
                "mode": memory.mode.value,
                "tone": {
                    "mode": memory.tone.mode.value,
                    "encode_hz": memory.tone.encode_hz,
                    "decode_hz": memory.tone.decode_hz,
                    "dtcs_code": memory.tone.dtcs_code,
                    "dtcs_polarity": memory.tone.dtcs_polarity,
                },
                "bank_assignments": list(memory.bank_assignments),
                "applied_transformations": [
                    code.value for code in memory.applied_transformations
                ],
            }
            for memory in plan.memories
        ],
        "omitted_channels": [
            {"channel_id": item.channel_id, "reason": item.reason.value}
            for item in plan.omitted_channels
        ],
        "diagnostics": [
            {
                "code": item.code.value,
                "severity": item.severity.value,
                "channel_id": item.channel_id,
                "message": item.message,
                "details": dict(item.details),
            }
            for item in plan.diagnostics
        ],
    }


def handle_request(request: Mapping[str, object]) -> dict[str, object]:
    """Handle one version-1 sidecar request without reading global state."""

    request_id = request.get("id")
    try:
        if request.get("method") != "compile":
            raise RequestError("unsupported method")
        params = request.get("params")
        if not isinstance(params, Mapping):
            raise RequestError("params must be an object")

        profile = params.get("profile")
        target = params.get("target")
        output = params.get("output_path")
        if not isinstance(profile, str) or not isinstance(target, str):
            raise RequestError("profile and target must be strings")
        if output is not None and not isinstance(output, str):
            raise RequestError("output_path must be a string or null")

        result = compile_builtin(
            profile,
            target,
            output_path=Path(output) if output is not None else None,
        )
        return {"id": request_id, "result": result}
    except RequestError as error:
        return {
            "id": request_id,
            "error": {"code": "INVALID_REQUEST", "message": str(error)},
        }
