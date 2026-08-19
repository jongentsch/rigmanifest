from __future__ import annotations

from rigmanifest.fixtures import BUILTIN_CATALOG
from rigmanifest.models import CatalogOrigin, Mode, TransmitBehavior


def test_service_presets_are_sourced_read_only_sets() -> None:
    expected_counts = {
        "us-frs": 22,
        "us-gmrs": 30,
        "us-murs": 5,
        "us-cbrs": 40,
        "us-aviation-guard": 2,
        "us-60m-discrete": 8,
    }

    for set_id, count in expected_counts.items():
        frequency_set = BUILTIN_CATALOG.frequency_set(set_id)
        assert frequency_set.origin is CatalogOrigin.PRESET
        assert frequency_set.read_only
        assert len(frequency_set.members) == count
        assert frequency_set.jurisdiction
        assert frequency_set.source_label
        assert frequency_set.source_url
        assert frequency_set.reviewed_at == "2026-08-19"
        assert all(member.channel_designator for member in frequency_set.members)


def test_frs_and_gmrs_share_canonical_frequency_definitions() -> None:
    frs_ids = {
        member.frequency_definition_id
        for member in BUILTIN_CATALOG.frequency_set("us-frs").members
    }
    gmrs_ids = {
        member.frequency_definition_id
        for member in BUILTIN_CATALOG.frequency_set("us-gmrs").members
    }

    assert frs_ids < gmrs_ids
    assert len(gmrs_ids - frs_ids) == 8


def test_part_95_and_aviation_presets_do_not_enable_transmission() -> None:
    for set_id in ("us-frs", "us-gmrs", "us-murs", "us-cbrs", "us-aviation-guard"):
        for member in BUILTIN_CATALOG.frequency_set(set_id).members:
            definition = BUILTIN_CATALOG.definition(member.frequency_definition_id)
            assert definition.transmit_behavior is TransmitBehavior.DISABLED


def test_sixty_meter_discrete_frequencies_preserve_carrier_semantics() -> None:
    frequency_set = BUILTIN_CATALOG.frequency_set("us-60m-discrete")
    definitions = [
        BUILTIN_CATALOG.definition(member.frequency_definition_id)
        for member in frequency_set.ordered_members
    ]

    assert [item.mode for item in definitions[:2]] == [Mode.USB, Mode.CW]
    assert definitions[1].receive_frequency_hz - definitions[0].receive_frequency_hz == 1_500
    assert all(item.transmit_behavior is TransmitBehavior.SAME for item in definitions)


def test_cbrs_irregular_channel_order_matches_the_regulatory_table() -> None:
    members = BUILTIN_CATALOG.frequency_set("us-cbrs").ordered_members
    frequencies = [
        BUILTIN_CATALOG.definition(member.frequency_definition_id).receive_frequency_hz
        for member in members
    ]

    assert frequencies[22:25] == [27_255_000, 27_235_000, 27_245_000]
