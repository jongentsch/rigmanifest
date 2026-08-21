"""Restart-safe startup enrichment for image-derived radio power data."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from rigmanifest.chirp_image import load_chirp_image
from rigmanifest.models import PowerIntent, PowerIntentMode
from rigmanifest.power import (
    failed_power_inspection,
    inspect_radio_power,
    power_intent_from_observed,
    power_intent_to_dict,
)
from rigmanifest.workspace import SQLiteWorkspace


def backfill_radio_power_capabilities(
    workspace: SQLiteWorkspace,
    state: Mapping[str, Any],
    *,
    force_radio_id: str | None = None,
) -> dict[str, Any]:
    """Inspect current source images and migrate legacy power records safely."""

    migrated_legacy = bool(state.get("migrated_legacy", False))
    definitions = [
        dict(item)
        for item in state["user_catalog"]["frequencyDefinitions"]
    ]
    definitions_by_id = {str(item.get("id")): item for item in definitions}
    catalog_changed = False

    for radio in state["radios"]:
        radio_id = str(radio["id"])
        version = workspace.latest_source_image_version(radio_id)
        if version is None:
            continue
        capability = workspace.radio_power_capability(radio_id)
        must_inspect = (
            radio_id == force_radio_id
            or capability is None
            or capability.source_image_version_id != version.id
            or capability.source_sha256 != version.sha256
            or not capability.is_current
            or capability.status == "error"
        )
        if must_inspect:
            try:
                inspection = inspect_radio_power(load_chirp_image(version.path))
                capability = inspection.bound_to(
                    source_image_version_id=version.id,
                    source_sha256=version.sha256,
                    driver_reference=version.driver_reference,
                )
            except Exception as error:  # One bad user image must not block startup.
                capability = failed_power_inspection(
                    str(error),
                    source_image_version_id=version.id,
                    source_sha256=version.sha256,
                    driver_reference=version.driver_reference,
                )
            workspace.store_radio_power_capability(capability)

        if capability.status not in {"detected", "fixed", "driver_default_only"}:
            continue
        for observed in capability.observed_memories:
            definition = definitions_by_id.get(
                f"user-radio-{radio_id}-memory-{observed.memory_number}"
            )
            if definition is None or "power_intent" in definition:
                continue
            if not _legacy_power_matches(
                definition,
                observed.native_label,
                observed.nominal_dbm,
            ):
                continue
            intent = power_intent_from_observed(
                native_label=observed.native_label,
                nominal_dbm=observed.nominal_dbm,
                normalized_tier=observed.normalized_tier,
                driver_reference=capability.driver_reference,
                level_count=len(capability.levels),
            )
            definition["power_intent"] = power_intent_to_dict(intent)
            catalog_changed = True

    for definition in definitions:
        if "power_intent" in definition:
            continue
        legacy_dbm = definition.get("power_dbm")
        legacy_label = definition.get("power_label")
        intent = (
            PowerIntent(
                mode=PowerIntentMode.NOMINAL,
                nominal_dbm=float(legacy_dbm),
                imported_label=(
                    str(legacy_label) if legacy_label is not None else None
                ),
                imported_dbm=float(legacy_dbm),
            )
            if isinstance(legacy_dbm, (int, float))
            and not isinstance(legacy_dbm, bool)
            else PowerIntent()
        )
        definition["power_intent"] = power_intent_to_dict(intent)
        catalog_changed = True

    if catalog_changed:
        user_catalog = {
            **state["user_catalog"],
            "frequencyDefinitions": definitions,
        }
        workspace.save({**state, "user_catalog": user_catalog})

    refreshed = workspace.load()
    refreshed["migrated_legacy"] = migrated_legacy
    return refreshed


def _legacy_power_matches(
    definition: Mapping[str, object],
    native_label: str,
    nominal_dbm: float,
) -> bool:
    value = definition.get("power_dbm")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    label = definition.get("power_label")
    return math.isclose(float(value), nominal_dbm, abs_tol=0.05) and (
        label is None or str(label) == native_label
    )
