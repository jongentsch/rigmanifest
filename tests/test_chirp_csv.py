from __future__ import annotations

import csv
from dataclasses import replace
from io import StringIO

from rigmanifest.compiler import compile_profile
from rigmanifest.exporters.chirp_csv import CHIRP_CSV_HEADER, render_chirp_csv
from rigmanifest.models import (
    CatalogOrigin,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencyRange,
    FrequencySet,
    FrequencySetMember,
    Mode,
    Profile,
    RadioCapabilities,
    RadioModel,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


def test_chirp_csv_uses_canonical_header_and_duplex_semantics() -> None:
    definitions = (
        FrequencyDefinition(
            "same",
            "Same",
            146_520_000,
            TransmitBehavior.SAME,
            tags=frozenset({"all"}),
        ),
        FrequencyDefinition(
            "negative",
            "Negative",
            146_910_000,
            TransmitBehavior.OFFSET,
            offset_hz=-600_000,
            tone=ToneSpec(mode=ToneMode.TONE, encode_hz=100.0),
            tags=frozenset({"all"}),
        ),
        FrequencyDefinition(
            "split",
            "Split",
            145_000_000,
            TransmitBehavior.SPLIT,
            transmit_frequency_hz=147_000_000,
            tags=frozenset({"all"}),
        ),
        FrequencyDefinition(
            "disabled",
            "Disabled",
            162_550_000,
            TransmitBehavior.DISABLED,
            tags=frozenset({"all"}),
        ),
    )
    catalog = FrequencyCatalog(
        definitions,
        (
            FrequencySet(
                "all",
                "All",
                CatalogOrigin.USER,
                tuple(
                    FrequencySetMember(item.id, index)
                    for index, item in enumerate(definitions)
                ),
            ),
        ),
    )
    profile = Profile("all", "All", ("all",))
    target = RadioModel(
        id="csv-target",
        manufacturer="Test",
        model="CSV Target",
        capabilities=RadioCapabilities(
            memory_capacity=10,
            receive_ranges=(FrequencyRange(100_000_000, 500_000_000),),
            transmit_ranges=(FrequencyRange(100_000_000, 500_000_000),),
            supported_modes=frozenset({Mode.FM}),
            supported_tone_modes=frozenset({ToneMode.NONE, ToneMode.TONE}),
            max_label_length=12,
            supported_label_characters=" ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            supports_banks=False,
            supports_transmit_disable=True,
            supports_split=True,
        ),
    )

    plan = compile_profile(catalog, profile, target)
    rendered = render_chirp_csv(plan)
    reader = csv.DictReader(StringIO(rendered))
    rows = {row["Comment"].removeprefix("RigManifest source: "): row for row in reader}

    assert tuple(reader.fieldnames or ()) == CHIRP_CSV_HEADER
    assert rows["same"]["Frequency"] == "146.520000"
    assert rows["same"]["Duplex"] == ""
    assert rows["same"]["Offset"] == "0.000000"
    assert rows["negative"]["Duplex"] == "-"
    assert rows["negative"]["Offset"] == "0.600000"
    assert rows["negative"]["Tone"] == "Tone"
    assert rows["negative"]["rToneFreq"] == "100.0"
    assert rows["split"]["Duplex"] == "split"
    assert rows["split"]["Offset"] == "147.000000"
    assert rows["disabled"]["Duplex"] == "off"


def test_exporter_does_not_reapply_capacity_or_selection() -> None:
    # A rendered plan is serialized as-is; the exporter owns no compiler policy.
    definition = FrequencyDefinition(
        "only",
        "Only",
        146_520_000,
        TransmitBehavior.SAME,
        tags=frozenset({"all"}),
    )
    catalog = FrequencyCatalog(
        (definition,),
        (
            FrequencySet(
                "all",
                "All",
                CatalogOrigin.USER,
                (FrequencySetMember("only", 0),),
            ),
        ),
    )
    profile = Profile("all", "All", ("all",))
    target = RadioModel(
        id="target",
        manufacturer="Test",
        model="Target",
        capabilities=RadioCapabilities(
            memory_capacity=1,
            receive_ranges=(FrequencyRange(100_000_000, 500_000_000),),
            transmit_ranges=(FrequencyRange(100_000_000, 500_000_000),),
            supported_modes=frozenset({Mode.FM}),
            supported_tone_modes=frozenset({ToneMode.NONE}),
            max_label_length=8,
            supported_label_characters=" ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            supports_banks=False,
        ),
    )
    plan = compile_profile(catalog, profile, target)
    manually_numbered = replace(
        plan,
        memories=(replace(plan.memories[0], memory_number=42),),
    )

    rendered = render_chirp_csv(manually_numbered)

    assert rendered.splitlines()[1].startswith("42,")
