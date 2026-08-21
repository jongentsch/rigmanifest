"""Normalized power intent and image-derived CHIRP capability snapshots."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from rigmanifest.chirp_version import CHIRP_COMMIT
from rigmanifest.models import (
    PowerIntent,
    PowerIntentMode,
    PowerLevelCapability,
    PowerTier,
)


POWER_CAPABILITY_SCHEMA_VERSION = 1
_TIERS = (
    PowerTier.MINIMUM,
    PowerTier.LOW,
    PowerTier.MEDIUM,
    PowerTier.HIGH,
    PowerTier.MAXIMUM,
)


@dataclass(frozen=True, slots=True)
class ObservedMemoryPower:
    memory_number: int
    native_label: str
    nominal_dbm: float
    normalized_tier: PowerTier | None
    immutable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "memory_number": self.memory_number,
            "native_label": self.native_label,
            "nominal_dbm": self.nominal_dbm,
            "normalized_tier": (
                self.normalized_tier.value
                if self.normalized_tier is not None
                else None
            ),
            "immutable": self.immutable,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> ObservedMemoryPower:
        tier = value.get("normalized_tier")
        return cls(
            memory_number=int(value["memory_number"]),
            native_label=str(value["native_label"]),
            nominal_dbm=float(value["nominal_dbm"]),
            normalized_tier=PowerTier(str(tier)) if tier is not None else None,
            immutable=bool(value.get("immutable", False)),
        )


@dataclass(frozen=True, slots=True)
class RadioPowerCapability:
    """A retryable capability inspection bound to one immutable source image."""

    status: str
    source_image_version_id: str | None
    source_sha256: str | None
    driver_reference: str | None
    chirp_revision: str = CHIRP_COMMIT
    capability_schema_version: int = POWER_CAPABILITY_SCHEMA_VERSION
    levels: tuple[PowerLevelCapability, ...] = ()
    observed_memories: tuple[ObservedMemoryPower, ...] = ()
    inspected_at: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.status not in {
            "detected",
            "fixed",
            "driver_default_only",
            "missing",
            "error",
        }:
            raise ValueError(f"unknown radio power capability status: {self.status}")
        if self.capability_schema_version <= 0:
            raise ValueError("power capability schema version must be positive")
        if self.status == "error" and not self.error:
            raise ValueError("failed power capability requires an error message")

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "source_image_version_id": self.source_image_version_id,
            "source_sha256": self.source_sha256,
            "driver_reference": self.driver_reference,
            "chirp_revision": self.chirp_revision,
            "capability_schema_version": self.capability_schema_version,
            "levels": [power_level_to_dict(level) for level in self.levels],
            "observed_memories": [
                memory.to_dict() for memory in self.observed_memories
            ],
            "inspected_at": self.inspected_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> RadioPowerCapability:
        levels = value.get("levels", [])
        memories = value.get("observed_memories", [])
        if not isinstance(levels, list) or not isinstance(memories, list):
            raise ValueError("invalid stored power capability arrays")
        return cls(
            status=str(value["status"]),
            source_image_version_id=_optional_string(
                value.get("source_image_version_id")
            ),
            source_sha256=_optional_string(value.get("source_sha256")),
            driver_reference=_optional_string(value.get("driver_reference")),
            chirp_revision=str(value.get("chirp_revision", CHIRP_COMMIT)),
            capability_schema_version=int(
                value.get(
                    "capability_schema_version",
                    POWER_CAPABILITY_SCHEMA_VERSION,
                )
            ),
            levels=tuple(
                power_level_from_dict(level)
                for level in levels
                if isinstance(level, Mapping)
            ),
            observed_memories=tuple(
                ObservedMemoryPower.from_dict(memory)
                for memory in memories
                if isinstance(memory, Mapping)
            ),
            inspected_at=_optional_string(value.get("inspected_at")),
            error=_optional_string(value.get("error")),
        )

    @classmethod
    def missing(
        cls,
        *,
        source_image_version_id: str | None = None,
        source_sha256: str | None = None,
        driver_reference: str | None = None,
    ) -> RadioPowerCapability:
        return cls(
            status="missing",
            source_image_version_id=source_image_version_id,
            source_sha256=source_sha256,
            driver_reference=driver_reference,
        )

    def bound_to(
        self,
        *,
        source_image_version_id: str,
        source_sha256: str,
        driver_reference: str,
    ) -> RadioPowerCapability:
        return replace(
            self,
            source_image_version_id=source_image_version_id,
            source_sha256=source_sha256,
            driver_reference=driver_reference,
        )

    @property
    def is_current(self) -> bool:
        return (
            self.chirp_revision == CHIRP_COMMIT
            and self.capability_schema_version == POWER_CAPABILITY_SCHEMA_VERSION
        )


def inspect_radio_power(radio: Any) -> RadioPowerCapability:
    """Inspect only CHIRP's public feature and memory objects."""

    features = radio.get_features()
    levels = power_levels_from_features(features)
    if len(levels) == 1:
        status = "fixed"
    elif levels:
        status = "detected"
    else:
        status = "driver_default_only"

    observed: list[ObservedMemoryPower] = []
    lower, upper = features.memory_bounds
    for number in range(int(lower), int(upper) + 1):
        memory = radio.get_memory(number)
        power = getattr(memory, "power", None)
        if memory.empty or power is None:
            continue
        power_dbm = float(power)
        if not math.isfinite(power_dbm) or power_dbm < 0:
            continue
        observed.append(
            ObservedMemoryPower(
                memory_number=number,
                native_label=str(power),
                nominal_dbm=power_dbm,
                normalized_tier=power_tier_for_native_level(power, levels),
                immutable="power" in getattr(memory, "immutable", ()),
            )
        )

    return RadioPowerCapability(
        status=status,
        source_image_version_id=None,
        source_sha256=None,
        driver_reference=None,
        levels=levels,
        observed_memories=tuple(observed),
        inspected_at=_timestamp(),
    )


def failed_power_inspection(
    message: str,
    *,
    source_image_version_id: str,
    source_sha256: str,
    driver_reference: str,
) -> RadioPowerCapability:
    detail = message.strip() or "CHIRP could not inspect this radio image"
    return RadioPowerCapability(
        status="error",
        source_image_version_id=source_image_version_id,
        source_sha256=source_sha256,
        driver_reference=driver_reference,
        inspected_at=_timestamp(),
        error=detail,
    )


def power_levels_from_features(features: Any) -> tuple[PowerLevelCapability, ...]:
    raw_levels = list(getattr(features, "valid_power_levels", ()))
    indexed: list[tuple[int, str, float]] = []
    for index, level in enumerate(raw_levels):
        nominal_dbm = float(level)
        if not math.isfinite(nominal_dbm) or nominal_dbm < 0:
            continue
        indexed.append((index, str(level), nominal_dbm))
    ranked = sorted(indexed, key=lambda item: (item[2], item[1], item[0]))
    tier_by_index = {
        native_index: _tier_for_rank(rank, len(ranked))
        for rank, (native_index, _label, _dbm) in enumerate(ranked)
    }
    return tuple(
        PowerLevelCapability(
            native_index=index,
            native_label=label,
            nominal_dbm=nominal_dbm,
            normalized_tier=tier_by_index[index],
        )
        for index, label, nominal_dbm in indexed
    )


def power_tier_for_native_level(
    level: Any,
    capabilities: Sequence[PowerLevelCapability],
) -> PowerTier | None:
    """Match within one driver snapshot; labels are not compared across radios."""

    label = str(level)
    nominal_dbm = float(level)
    label_matches = [item for item in capabilities if item.native_label == label]
    if label_matches:
        return min(
            label_matches,
            key=lambda item: abs(item.nominal_dbm - nominal_dbm),
        ).normalized_tier
    if not capabilities:
        return None
    return min(
        capabilities,
        key=lambda item: abs(item.nominal_dbm - nominal_dbm),
    ).normalized_tier


def power_intent_from_observed(
    *,
    native_label: str,
    nominal_dbm: float,
    normalized_tier: PowerTier | None,
    driver_reference: str | None,
    level_count: int,
) -> PowerIntent:
    """Prefer relative intent only when a driver exposes multiple selectors."""

    provenance = {
        "imported_driver_reference": driver_reference,
        "imported_label": native_label,
        "imported_dbm": nominal_dbm,
    }
    if level_count > 1 and normalized_tier is not None:
        return PowerIntent(
            mode=PowerIntentMode.RELATIVE,
            tier=normalized_tier,
            **provenance,
        )
    return PowerIntent(
        mode=PowerIntentMode.NOMINAL,
        nominal_dbm=nominal_dbm,
        **provenance,
    )


def power_intent_to_dict(intent: PowerIntent) -> dict[str, object]:
    return {
        "mode": intent.mode.value,
        "tier": intent.tier.value if intent.tier is not None else None,
        "nominal_dbm": intent.nominal_dbm,
        "imported_driver_reference": intent.imported_driver_reference,
        "imported_label": intent.imported_label,
        "imported_dbm": intent.imported_dbm,
    }


def power_level_to_dict(level: PowerLevelCapability) -> dict[str, object]:
    return {
        "native_index": level.native_index,
        "native_label": level.native_label,
        "nominal_dbm": level.nominal_dbm,
        "normalized_tier": level.normalized_tier.value,
    }


def power_level_from_dict(value: Mapping[str, object]) -> PowerLevelCapability:
    return PowerLevelCapability(
        native_index=int(value["native_index"]),
        native_label=str(value["native_label"]),
        nominal_dbm=float(value["nominal_dbm"]),
        normalized_tier=PowerTier(str(value["normalized_tier"])),
    )


def _tier_for_rank(rank: int, count: int) -> PowerTier:
    if count <= 1:
        return PowerTier.MAXIMUM
    tier_index = round(rank * (len(_TIERS) - 1) / (count - 1))
    return _TIERS[tier_index]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _optional_string(value: object) -> str | None:
    return str(value) if value is not None else None
