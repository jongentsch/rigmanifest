"""Sourced, advisory frequency-plan data for catalog editing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthorityTier(StrEnum):
    NATIONAL_RECOMMENDATION = "national-recommendation"
    REGIONAL_COORDINATOR = "regional-coordinator"


class PlanUse(StrEnum):
    SIMPLEX = "simplex"
    REPEATER_OUTPUT = "repeater-output"


@dataclass(frozen=True, slots=True)
class FrequencyPlanSegment:
    id: str
    name: str
    lower_hz: int
    upper_hz: int
    use: PlanUse
    suggested_offset_hz: int | None = None
    raster_anchor_hz: int | None = None
    raster_spacing_hz: int | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("frequency plan segment identity is required")
        if self.lower_hz <= 0 or self.upper_hz < self.lower_hz:
            raise ValueError("frequency plan segment range is invalid")
        if (self.raster_anchor_hz is None) != (self.raster_spacing_hz is None):
            raise ValueError("frequency raster requires both anchor and spacing")
        if self.raster_spacing_hz is not None and self.raster_spacing_hz <= 0:
            raise ValueError("frequency raster spacing must be positive")

    def contains(self, frequency_hz: int) -> bool:
        return self.lower_hz <= frequency_hz <= self.upper_hz

    def is_on_raster(self, frequency_hz: int) -> bool | None:
        if self.raster_anchor_hz is None or self.raster_spacing_hz is None:
            return None
        return (frequency_hz - self.raster_anchor_hz) % self.raster_spacing_hz == 0


@dataclass(frozen=True, slots=True)
class FrequencyPlan:
    id: str
    name: str
    jurisdiction: str
    authority_tier: AuthorityTier
    reviewed_at: str
    source_label: str
    source_url: str
    segments: tuple[FrequencyPlanSegment, ...]
    advisory: bool = True

    def __post_init__(self) -> None:
        if not all(
            (
                self.id,
                self.name,
                self.jurisdiction,
                self.reviewed_at,
                self.source_label,
                self.source_url,
            )
        ):
            raise ValueError("frequency plan metadata is required")
        object.__setattr__(self, "segments", tuple(self.segments))
        segment_ids = [segment.id for segment in self.segments]
        if len(segment_ids) != len(set(segment_ids)):
            raise ValueError("frequency plan contains a duplicate segment ID")

    def matching_segment(self, frequency_hz: int) -> FrequencyPlanSegment | None:
        return next(
            (segment for segment in self.segments if segment.contains(frequency_hz)),
            None,
        )


ARRL_US_NATIONAL = FrequencyPlan(
    id="arrl-us-national",
    name="ARRL US national band plan",
    jurisdiction="United States",
    authority_tier=AuthorityTier.NATIONAL_RECOMMENDATION,
    reviewed_at="2026-08-19",
    source_label="ARRL Band Plan",
    source_url="https://www.arrl.org/band-plan",
    segments=(
        FrequencyPlanSegment(
            "10m-repeater-output",
            "10 m repeater outputs",
            29_610_000,
            29_700_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-100_000,
        ),
        FrequencyPlanSegment(
            "6m-repeater-output-low",
            "6 m repeater outputs (51 MHz)",
            51_620_000,
            51_980_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-500_000,
            raster_anchor_hz=51_620_000,
            raster_spacing_hz=20_000,
        ),
        FrequencyPlanSegment(
            "6m-repeater-output-mid",
            "6 m repeater outputs (52 MHz)",
            52_500_000,
            52_980_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-500_000,
            raster_anchor_hz=52_500_000,
            raster_spacing_hz=20_000,
            notes="ARRL lists simplex exceptions inside this range; verify locally.",
        ),
        FrequencyPlanSegment(
            "6m-repeater-output-high",
            "6 m repeater outputs (53 MHz)",
            53_500_000,
            53_980_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-500_000,
            raster_anchor_hz=53_500_000,
            raster_spacing_hz=20_000,
            notes="ARRL lists simplex/control exceptions; verify locally.",
        ),
        FrequencyPlanSegment(
            "2m-repeater-output-low",
            "2 m repeater outputs (145 MHz)",
            145_200_000,
            145_500_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-600_000,
            notes="National plan supplies paired ranges; local coordinators set the raster.",
        ),
        FrequencyPlanSegment(
            "2m-simplex-low",
            "2 m simplex",
            146_400_000,
            146_580_000,
            PlanUse.SIMPLEX,
            notes="146.520 MHz is the national FM simplex calling frequency.",
        ),
        FrequencyPlanSegment(
            "2m-repeater-output-mid",
            "2 m repeater outputs (146 MHz)",
            146_610_000,
            146_970_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-600_000,
            notes="National plan supplies paired ranges; local coordinators set the raster.",
        ),
        FrequencyPlanSegment(
            "2m-repeater-output-high",
            "2 m repeater outputs (147 MHz)",
            147_000_000,
            147_390_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=600_000,
            notes="National plan supplies paired ranges; local coordinators set the raster.",
        ),
        FrequencyPlanSegment(
            "2m-simplex-high",
            "2 m simplex",
            147_420_000,
            147_570_000,
            PlanUse.SIMPLEX,
        ),
        FrequencyPlanSegment(
            "1_25m-repeater-output",
            "1.25 m repeater outputs",
            223_850_000,
            224_980_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-1_600_000,
            notes="Local coordinator options exist elsewhere in the band.",
        ),
        FrequencyPlanSegment(
            "33cm-repeater-output-low",
            "33 cm repeater outputs",
            927_000_000,
            927_075_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-25_000_000,
            raster_anchor_hz=927_000_000,
            raster_spacing_hz=12_500,
        ),
        FrequencyPlanSegment(
            "33cm-repeater-output-high",
            "33 cm repeater outputs",
            927_125_000,
            928_000_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-25_000_000,
            raster_anchor_hz=927_125_000,
            raster_spacing_hz=12_500,
        ),
        FrequencyPlanSegment(
            "23cm-repeater-output",
            "23 cm repeater outputs",
            1_282_000_000,
            1_288_000_000,
            PlanUse.REPEATER_OUTPUT,
            suggested_offset_hz=-12_000_000,
            raster_anchor_hz=1_282_000_000,
            raster_spacing_hz=25_000,
        ),
    ),
)


BUILTIN_FREQUENCY_PLANS = {ARRL_US_NATIONAL.id: ARRL_US_NATIONAL}
