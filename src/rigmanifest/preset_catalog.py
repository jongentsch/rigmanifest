"""Sourced, read-only US frequency sets.

Part 95 and aviation entries intentionally disable transmission. A listed frequency
does not establish that a programmable amateur transceiver is certified or that its
operator is authorized for that service.
"""

from __future__ import annotations

from collections.abc import Callable

from rigmanifest.models import (
    CatalogOrigin,
    FrequencyDefinition,
    FrequencySet,
    FrequencySetMember,
    Mode,
    TransmitBehavior,
)


REVIEWED_AT = "2026-08-19"
ECFR_FRS = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-95/subpart-B/section-95.563"
ECFR_GMRS = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-95/subpart-E/section-95.1763"
ECFR_MURS = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-95/subpart-J/section-95.2763"
ECFR_CBRS = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-95/subpart-D/section-95.963"
ECFR_60M = "https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-D/section-97.303"
FAA_GUARD = "https://www.faa.gov/air_traffic/publications/atpubs/aim_html/chap6_section_3.html"


def _receive_only(
    definition_id: str,
    name: str,
    frequency_hz: int,
    *,
    mode: Mode,
    tags: frozenset[str],
    source: str,
) -> FrequencyDefinition:
    return FrequencyDefinition(
        id=definition_id,
        name=name,
        receive_frequency_hz=frequency_hz,
        transmit_behavior=TransmitBehavior.DISABLED,
        origin=CatalogOrigin.PRESET,
        mode=mode,
        tags=tags,
        notes=(
            f"Receive-only safety preset. Source: {source}. Use only service-certified "
            "equipment and the authorization applicable to transmission."
        ),
    )


FRS_FREQUENCIES_HZ = (
    462_562_500, 462_587_500, 462_612_500, 462_637_500, 462_662_500,
    462_687_500, 462_712_500, 467_562_500, 467_587_500, 467_612_500,
    467_637_500, 467_662_500, 467_687_500, 467_712_500, 462_550_000,
    462_575_000, 462_600_000, 462_625_000, 462_650_000, 462_675_000,
    462_700_000, 462_725_000,
)

FRS_GMRS_SHARED_DEFINITIONS = tuple(
    _receive_only(
        f"us-frs-gmrs-{channel}",
        f"FRS/GMRS {channel}",
        frequency_hz,
        mode=Mode.NFM,
        tags=frozenset({"frs", "gmrs", "part-95", "channelized"}),
        source="47 CFR 95.563 and 95.1763",
    )
    for channel, frequency_hz in enumerate(FRS_FREQUENCIES_HZ, start=1)
)

GMRS_REPEATER_INPUT_DEFINITIONS = tuple(
    _receive_only(
        f"us-gmrs-repeater-input-{index}",
        f"GMRS repeater input {frequency_hz / 1_000_000:.4f}",
        frequency_hz,
        mode=Mode.NFM,
        tags=frozenset({"gmrs", "part-95", "repeater-input", "channelized"}),
        source="47 CFR 95.1763(c)",
    )
    for index, frequency_hz in enumerate(
        range(467_550_000, 467_725_001, 25_000), start=1
    )
)

MURS_FREQUENCIES_HZ = (151_820_000, 151_880_000, 151_940_000, 154_570_000, 154_600_000)
MURS_DEFINITIONS = tuple(
    _receive_only(
        f"us-murs-{channel}",
        f"MURS {frequency_hz / 1_000_000:.3f}",
        frequency_hz,
        mode=Mode.NFM,
        tags=frozenset({"murs", "part-95", "channelized"}),
        source="47 CFR 95.2763",
    )
    for channel, frequency_hz in enumerate(MURS_FREQUENCIES_HZ, start=1)
)

CBRS_FREQUENCIES_HZ = (
    26_965_000, 26_975_000, 26_985_000, 27_005_000, 27_015_000,
    27_025_000, 27_035_000, 27_055_000, 27_065_000, 27_075_000,
    27_085_000, 27_105_000, 27_115_000, 27_125_000, 27_135_000,
    27_155_000, 27_165_000, 27_175_000, 27_185_000, 27_205_000,
    27_215_000, 27_225_000, 27_255_000, 27_235_000, 27_245_000,
    27_265_000, 27_275_000, 27_285_000, 27_295_000, 27_305_000,
    27_315_000, 27_325_000, 27_335_000, 27_345_000, 27_355_000,
    27_365_000, 27_375_000, 27_385_000, 27_395_000, 27_405_000,
)
CBRS_DEFINITIONS = tuple(
    _receive_only(
        f"us-cbrs-{channel}",
        f"CB {channel}",
        frequency_hz,
        mode=Mode.AM,
        tags=frozenset({"cbrs", "citizens-band", "part-95", "channelized"}),
        source="47 CFR 95.963",
    )
    for channel, frequency_hz in enumerate(CBRS_FREQUENCIES_HZ, start=1)
)

AVIATION_GUARD_DEFINITIONS = (
    _receive_only(
        "us-aviation-guard-civil",
        "Civil aviation guard",
        121_500_000,
        mode=Mode.AM,
        tags=frozenset({"aviation", "guard", "emergency"}),
        source="FAA AIM 6-3-2",
    ),
    _receive_only(
        "us-aviation-guard-military",
        "Military aviation guard",
        243_000_000,
        mode=Mode.AM,
        tags=frozenset({"aviation", "guard", "emergency"}),
        source="FAA AIM 6-3-2",
    ),
)

SIXTY_METER_CENTERS_HZ = (5_332_000, 5_348_000, 5_373_000, 5_405_000)
SIXTY_METER_DEFINITIONS = tuple(
    definition
    for channel, center_hz in enumerate(SIXTY_METER_CENTERS_HZ, start=1)
    for definition in (
        FrequencyDefinition(
            id=f"us-60m-{channel}-usb",
            name=f"60 m discrete {channel} phone/data carrier",
            receive_frequency_hz=center_hz - 1_500,
            transmit_behavior=TransmitBehavior.SAME,
            origin=CatalogOrigin.PRESET,
            mode=Mode.USB,
            tags=frozenset({"amateur", "60m", "regulated-special-case"}),
            notes=(
                "Phone/data carrier is 1.5 kHz below the discrete center. "
                "The 5351.5-5366.5 kHz contiguous segment is not a channel list. "
                "Source: 47 CFR 97.303(h)."
            ),
        ),
        FrequencyDefinition(
            id=f"us-60m-{channel}-cw",
            name=f"60 m discrete {channel} CW center",
            receive_frequency_hz=center_hz,
            transmit_behavior=TransmitBehavior.SAME,
            origin=CatalogOrigin.PRESET,
            mode=Mode.CW,
            tags=frozenset({"amateur", "60m", "regulated-special-case"}),
            notes=(
                "CW carrier is at the discrete center; occupied bandwidth and sharing "
                "requirements still apply. Source: 47 CFR 97.303(h)."
            ),
        ),
    )
)


def _set(
    set_id: str,
    name: str,
    description: str,
    definitions: tuple[FrequencyDefinition, ...],
    source_label: str,
    source_url: str,
    designator: Callable[[int, FrequencyDefinition], str],
) -> FrequencySet:
    return FrequencySet(
        id=set_id,
        name=name,
        origin=CatalogOrigin.PRESET,
        description=description,
        jurisdiction="United States",
        source_label=source_label,
        source_url=source_url,
        reviewed_at=REVIEWED_AT,
        members=tuple(
            FrequencySetMember(item.id, position, designator(position, item))
            for position, item in enumerate(definitions)
        ),
    )


US_FRS_SET = _set(
    "us-frs", "US FRS", "The 22 FCC-allotted FRS channels, stored receive-only.",
    FRS_GMRS_SHARED_DEFINITIONS, "47 CFR 95.563", ECFR_FRS,
    lambda position, _item: f"FRS {position + 1}",
)

US_GMRS_SET = _set(
    "us-gmrs", "US GMRS", "The 30 FCC-allotted GMRS frequencies, stored receive-only.",
    FRS_GMRS_SHARED_DEFINITIONS + GMRS_REPEATER_INPUT_DEFINITIONS,
    "47 CFR 95.1763", ECFR_GMRS,
    lambda position, _item: (
        f"GMRS {position + 1}" if position < 22 else f"GMRS repeater input {position - 21}"
    ),
)

US_MURS_SET = _set(
    "us-murs", "US MURS", "The five FCC-allotted MURS channels, stored receive-only.",
    MURS_DEFINITIONS, "47 CFR 95.2763", ECFR_MURS,
    lambda position, _item: f"MURS {position + 1}",
)

US_CBRS_SET = _set(
    "us-cbrs", "US Citizens Band", "The 40 FCC-allotted CBRS channels, stored receive-only.",
    CBRS_DEFINITIONS, "47 CFR 95.963", ECFR_CBRS,
    lambda position, _item: f"CB {position + 1}",
)

US_AVIATION_GUARD_SET = _set(
    "us-aviation-guard", "US aviation guard", "Civil and military aviation emergency guard frequencies, receive-only.",
    AVIATION_GUARD_DEFINITIONS, "FAA AIM 6-3-2", FAA_GUARD,
    lambda position, _item: "VHF guard" if position == 0 else "UHF guard",
)

US_60M_DISCRETE_SET = _set(
    "us-60m-discrete", "US amateur 60 m discrete frequencies",
    "Four regulated discrete centers represented separately for USB phone/data carriers and CW. The contiguous 5351.5-5366.5 kHz segment is intentionally not represented as a channel list.",
    SIXTY_METER_DEFINITIONS, "47 CFR 97.303(h)", ECFR_60M,
    lambda position, _item: f"60m {position // 2 + 1} {'USB' if position % 2 == 0 else 'CW'}",
)

SERVICE_PRESET_DEFINITIONS = (
    FRS_GMRS_SHARED_DEFINITIONS
    + GMRS_REPEATER_INPUT_DEFINITIONS
    + MURS_DEFINITIONS
    + CBRS_DEFINITIONS
    + AVIATION_GUARD_DEFINITIONS
    + SIXTY_METER_DEFINITIONS
)
SERVICE_PRESET_SETS = (
    US_FRS_SET, US_GMRS_SET, US_MURS_SET, US_CBRS_SET,
    US_AVIATION_GUARD_SET, US_60M_DISCRETE_SET,
)
