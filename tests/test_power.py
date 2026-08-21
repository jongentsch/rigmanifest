from types import SimpleNamespace

import pytest
from chirp import chirp_common

from rigmanifest.chirp_version import CHIRP_COMMIT
from rigmanifest.models import PowerIntentMode, PowerTier
from rigmanifest.power import (
    POWER_CAPABILITY_SCHEMA_VERSION,
    ObservedMemoryPower,
    RadioPowerCapability,
    failed_power_inspection,
    inspect_radio_power,
    power_intent_from_observed,
    power_intent_to_dict,
    power_levels_from_features,
    power_tier_for_native_level,
)


class _Radio:
    def __init__(self, levels, memories=()):
        self._features = SimpleNamespace(
            valid_power_levels=levels,
            memory_bounds=(1, len(memories)),
        )
        self._memories = tuple(memories)

    def get_features(self):
        return self._features

    def get_memory(self, number):
        return self._memories[number - 1]


def _memory(*, power=None, empty=False, immutable=()):
    return SimpleNamespace(power=power, empty=empty, immutable=immutable)


def test_power_capability_round_trips_and_binds_to_an_image() -> None:
    level = chirp_common.PowerLevel("High", watts=5)
    capability = inspect_radio_power(
        _Radio([level], [_memory(power=level, immutable=("power",))])
    ).bound_to(
        source_image_version_id="source-1",
        source_sha256="abc",
        driver_reference="Vendor_Model",
    )

    restored = RadioPowerCapability.from_dict(capability.to_dict())

    assert restored == capability
    assert restored.status == "fixed"
    assert restored.is_current
    assert restored.levels[0].normalized_tier is PowerTier.MAXIMUM
    assert restored.observed_memories == (
        ObservedMemoryPower(
            memory_number=1,
            native_label="High",
            nominal_dbm=float(level),
            normalized_tier=PowerTier.MAXIMUM,
            immutable=True,
        ),
    )


def test_power_capability_supports_missing_and_rejects_invalid_snapshots() -> None:
    missing = RadioPowerCapability.missing(driver_reference="Vendor_Model")
    assert missing.status == "missing"
    assert missing.driver_reference == "Vendor_Model"

    with pytest.raises(ValueError, match="unknown"):
        RadioPowerCapability(
            status="future",
            source_image_version_id=None,
            source_sha256=None,
            driver_reference=None,
        )
    with pytest.raises(ValueError, match="positive"):
        RadioPowerCapability(
            status="missing",
            source_image_version_id=None,
            source_sha256=None,
            driver_reference=None,
            capability_schema_version=0,
        )
    with pytest.raises(ValueError, match="error message"):
        RadioPowerCapability(
            status="error",
            source_image_version_id=None,
            source_sha256=None,
            driver_reference=None,
        )
    with pytest.raises(ValueError, match="arrays"):
        RadioPowerCapability.from_dict({"status": "missing", "levels": {}})


def test_power_capability_currentness_tracks_chirp_and_schema_versions() -> None:
    common = {
        "status": "missing",
        "source_image_version_id": None,
        "source_sha256": None,
        "driver_reference": None,
    }
    assert not RadioPowerCapability(**common, chirp_revision="older").is_current
    assert not RadioPowerCapability(
        **common,
        chirp_revision=CHIRP_COMMIT,
        capability_schema_version=POWER_CAPABILITY_SCHEMA_VERSION + 1,
    ).is_current


def test_power_inspection_detects_ranked_levels_and_skips_unusable_memories() -> None:
    high = chirp_common.PowerLevel("HI", watts=5)
    low = chirp_common.PowerLevel("LO", watts=1)
    capability = inspect_radio_power(
        _Radio(
            [high, low],
            [
                _memory(empty=True),
                _memory(power=float("nan")),
                _memory(power=low),
            ],
        )
    )

    assert capability.status == "detected"
    assert [level.native_label for level in capability.levels] == ["HI", "LO"]
    assert [level.normalized_tier for level in capability.levels] == [
        PowerTier.MAXIMUM,
        PowerTier.MINIMUM,
    ]
    assert [memory.memory_number for memory in capability.observed_memories] == [3]

    default_only = inspect_radio_power(
        _Radio([], [_memory(power=None), _memory(power=-1)])
    )
    assert default_only.status == "driver_default_only"
    assert default_only.observed_memories == ()


def test_power_level_normalization_ignores_invalid_driver_choices() -> None:
    class _InvalidLevel:
        def __float__(self):
            return float("nan")

        def __str__(self):
            return "invalid"

    assert power_levels_from_features(SimpleNamespace()) == ()
    assert power_levels_from_features(
        SimpleNamespace(valid_power_levels=[_InvalidLevel()])
    ) == ()


def test_native_level_matching_is_scoped_to_one_capability_snapshot() -> None:
    low = chirp_common.PowerLevel("Low", watts=1)
    high = chirp_common.PowerLevel("High", watts=5)
    levels = power_levels_from_features(
        SimpleNamespace(valid_power_levels=[low, high])
    )

    assert power_tier_for_native_level(high, levels) is PowerTier.MAXIMUM
    assert power_tier_for_native_level(
        chirp_common.PowerLevel("Different label", watts=1.1), levels
    ) is PowerTier.MINIMUM
    assert power_tier_for_native_level(low, ()) is None


def test_observed_power_becomes_relative_only_for_a_real_selector_range() -> None:
    relative = power_intent_from_observed(
        native_label="HI",
        nominal_dbm=37,
        normalized_tier=PowerTier.MAXIMUM,
        driver_reference="Vendor_Model",
        level_count=2,
    )
    fixed = power_intent_from_observed(
        native_label="5W",
        nominal_dbm=37,
        normalized_tier=PowerTier.MAXIMUM,
        driver_reference="Vendor_Fixed",
        level_count=1,
    )

    assert relative.mode is PowerIntentMode.RELATIVE
    assert relative.tier is PowerTier.MAXIMUM
    assert fixed.mode is PowerIntentMode.NOMINAL
    assert fixed.nominal_dbm == 37
    assert power_intent_to_dict(relative)["imported_label"] == "HI"


def test_failed_inspection_uses_a_safe_nonblank_message() -> None:
    failed = failed_power_inspection(
        "   ",
        source_image_version_id="source-1",
        source_sha256="abc",
        driver_reference="Vendor_Model",
    )

    assert failed.status == "error"
    assert failed.error == "CHIRP could not inspect this radio image"
