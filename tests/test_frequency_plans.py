from __future__ import annotations

import pytest

from rigmanifest.frequency_plans import (
    ARRL_US_NATIONAL,
    AuthorityTier,
    FrequencyPlan,
    FrequencyPlanSegment,
    PlanUse,
    KANSAS_REPEATER_COUNCIL,
    SOUTHERN_NEVADA_REPEATER_COUNCIL,
)


def test_two_meter_offset_suggestions_match_specific_output_segments() -> None:
    low = ARRL_US_NATIONAL.matching_segment(146_910_000)
    high = ARRL_US_NATIONAL.matching_segment(147_300_000)
    simplex = ARRL_US_NATIONAL.matching_segment(146_520_000)

    assert low is not None and low.suggested_offset_hz == -600_000
    assert high is not None and high.suggested_offset_hz == 600_000
    assert simplex is not None and simplex.use is PlanUse.SIMPLEX
    assert simplex.suggested_offset_hz is None
    assert ARRL_US_NATIONAL.matching_segment(145_800_000) is None


def test_raster_uses_its_anchor_and_is_advisory() -> None:
    segment = ARRL_US_NATIONAL.matching_segment(927_137_500)

    assert segment is not None
    assert segment.raster_anchor_hz == 927_125_000
    assert segment.is_on_raster(927_137_500) is True
    assert segment.is_on_raster(927_138_000) is False
    assert ARRL_US_NATIONAL.advisory is True
    assert ARRL_US_NATIONAL.authority_tier is AuthorityTier.NATIONAL_RECOMMENDATION


def test_segment_without_raster_returns_unknown_rather_than_invalid() -> None:
    segment = ARRL_US_NATIONAL.matching_segment(146_910_000)

    assert segment is not None
    assert segment.is_on_raster(146_910_000) is None


def test_regional_plans_preserve_conflicting_seventy_centimeter_conventions() -> None:
    kansas = KANSAS_REPEATER_COUNCIL.matching_segment(444_500_000)
    nevada = SOUTHERN_NEVADA_REPEATER_COUNCIL.matching_segment(447_500_000)

    assert kansas is not None and kansas.suggested_offset_hz == 5_000_000
    assert kansas.is_on_raster(444_500_000) is True
    assert nevada is not None and nevada.suggested_offset_hz == -5_000_000
    assert nevada.is_on_raster(447_500_000) is True
    assert kansas.id != nevada.id


def test_southern_nevada_treats_exactly_147_mhz_as_the_sign_boundary() -> None:
    boundary = SOUTHERN_NEVADA_REPEATER_COUNCIL.matching_segment(147_000_000)
    above = SOUTHERN_NEVADA_REPEATER_COUNCIL.matching_segment(147_020_000)

    assert boundary is not None and boundary.suggested_offset_hz == -600_000
    assert above is not None and above.suggested_offset_hz == 600_000


@pytest.mark.parametrize(
    "segment",
    [
        FrequencyPlanSegment("id", "Name", 10, 20, PlanUse.SIMPLEX),
    ],
)
def test_frequency_plan_rejects_duplicate_segment_ids(
    segment: FrequencyPlanSegment,
) -> None:
    with pytest.raises(ValueError, match="duplicate segment"):
        FrequencyPlan(
            "plan",
            "Plan",
            "Somewhere",
            AuthorityTier.REGIONAL_COORDINATOR,
            "2026-08-19",
            "Source",
            "https://example.com",
            (segment, segment),
        )


def test_frequency_plan_requires_source_metadata() -> None:
    with pytest.raises(ValueError, match="metadata"):
        FrequencyPlan(
            "",
            "Plan",
            "Somewhere",
            AuthorityTier.NATIONAL_RECOMMENDATION,
            "2026-08-19",
            "Source",
            "https://example.com",
            (),
        )


@pytest.mark.parametrize(
    "arguments",
    [
        ("", "Name", 10, 20, PlanUse.SIMPLEX),
        ("id", "Name", 0, 20, PlanUse.SIMPLEX),
        ("id", "Name", 20, 10, PlanUse.SIMPLEX),
        ("id", "Name", 10, 20, PlanUse.SIMPLEX, None, 10, None),
        ("id", "Name", 10, 20, PlanUse.SIMPLEX, None, 10, 0),
    ],
)
def test_invalid_frequency_plan_segments_are_rejected(
    arguments: tuple[object, ...],
) -> None:
    with pytest.raises(ValueError):
        FrequencyPlanSegment(*arguments)  # type: ignore[arg-type]
