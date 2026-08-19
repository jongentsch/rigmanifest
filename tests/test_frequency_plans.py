from __future__ import annotations

import pytest

from rigmanifest.frequency_plans import (
    ARRL_US_NATIONAL,
    AuthorityTier,
    FrequencyPlan,
    FrequencyPlanSegment,
    PlanUse,
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
