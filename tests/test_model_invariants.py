from __future__ import annotations

from dataclasses import replace

import pytest

from rigmanifest.models import (
    CatalogOrigin,
    CompilationSettings,
    FactoryFrequencySet,
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
    TransmitBehavior,
)


def _definition(**changes: object) -> FrequencyDefinition:
    base = FrequencyDefinition("id", "Name", 146_520_000, TransmitBehavior.SAME)
    return replace(base, **changes)


def _capabilities(**changes: object) -> RadioCapabilities:
    base = RadioCapabilities(
        memory_capacity=10,
        receive_ranges=(FrequencyRange(100, 200),),
        transmit_ranges=(FrequencyRange(100, 200),),
        supported_modes=frozenset({Mode.FM}),
        supported_tone_modes=frozenset({ToneMode.NONE}),
        max_label_length=8,
        supported_label_characters=" ABC",
        supports_banks=False,
    )
    return replace(base, **changes)


@pytest.mark.parametrize("bounds", [(0, 1), (2, 1)])
def test_invalid_frequency_ranges_are_rejected(bounds: tuple[int, int]) -> None:
    with pytest.raises(ValueError):
        FrequencyRange(*bounds)


@pytest.mark.parametrize(
    "changes",
    [
        {"id": ""},
        {"name": ""},
        {"receive_frequency_hz": 0},
        {"transmit_behavior": TransmitBehavior.OFFSET, "offset_hz": None},
        {"transmit_behavior": TransmitBehavior.OFFSET, "offset_hz": 1, "transmit_frequency_hz": 2},
        {"transmit_behavior": TransmitBehavior.SPLIT, "transmit_frequency_hz": None},
        {"transmit_behavior": TransmitBehavior.SPLIT, "transmit_frequency_hz": 2, "offset_hz": 1},
        {"transmit_frequency_hz": 2},
    ],
)
def test_invalid_frequency_definitions_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _definition(**changes)


@pytest.mark.parametrize("arguments", [("", 0), ("id", -1)])
def test_invalid_set_members_are_rejected(arguments: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        FrequencySetMember(*arguments)  # type: ignore[arg-type]


def test_set_and_catalog_identity_invariants_are_enforced() -> None:
    member = FrequencySetMember("id", 0)
    with pytest.raises(ValueError, match="ID and name"):
        FrequencySet("", "Set", CatalogOrigin.USER, ())
    with pytest.raises(ValueError, match="duplicate definition"):
        FrequencySet("set", "Set", CatalogOrigin.USER, (member, replace(member, position=1)))
    with pytest.raises(ValueError, match="duplicate position"):
        FrequencySet("set", "Set", CatalogOrigin.USER, (member, FrequencySetMember("other", 0)))

    definition = _definition()
    frequency_set = FrequencySet("set", "Set", CatalogOrigin.USER, (member,))
    with pytest.raises(ValueError, match="duplicate frequency definition"):
        FrequencyCatalog((definition, definition), ())
    with pytest.raises(ValueError, match="duplicate frequency set"):
        FrequencyCatalog((definition,), (frequency_set, frequency_set))
    with pytest.raises(ValueError, match="unknown definition"):
        FrequencyCatalog((), (frequency_set,))


def test_catalog_lookup_failures_are_key_errors() -> None:
    catalog = FrequencyCatalog((), ())
    with pytest.raises(KeyError):
        catalog.definition("missing")
    with pytest.raises(KeyError):
        catalog.frequency_set("missing")


@pytest.mark.parametrize(
    "arguments",
    [
        ("", "Name", ("set",)),
        ("id", "Name", ("set", "set")),
    ],
)
def test_invalid_profiles_are_rejected(arguments: tuple[object, ...]) -> None:
    with pytest.raises(ValueError):
        Profile(*arguments)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "changes",
    [
        {"memory_capacity": 0},
        {"memory_start": -1},
        {"receive_ranges": ()},
        {"max_label_length": 0},
        {"supports_banks": True, "bank_count": 0},
        {"supports_banks": False, "bank_count": 1},
    ],
)
def test_invalid_radio_capabilities_are_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _capabilities(**changes)


def test_radio_relationship_and_identity_invariants_are_enforced() -> None:
    with pytest.raises(ValueError, match="reference and interface"):
        FactoryFrequencySet("", "WX")
    with pytest.raises(ValueError, match="identity"):
        RadioModel("", "Maker", "Model", _capabilities())
    relation = FactoryFrequencySet("set", "WX")
    with pytest.raises(ValueError, match="duplicate factory"):
        RadioModel(
            "id",
            "Maker",
            "Model",
            _capabilities(),
            (relation, relation),
        )


def test_negative_compilation_start_is_rejected() -> None:
    with pytest.raises(ValueError):
        CompilationSettings(memory_start=-1)
