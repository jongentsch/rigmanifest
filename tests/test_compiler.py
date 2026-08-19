from __future__ import annotations

from dataclasses import replace

import pytest

from rigmanifest.compiler import compile_profile
from rigmanifest.models import (
    CapabilityStatus,
    CatalogOrigin,
    CompilationSettings,
    DiagnosticCode,
    FactoryFrequencySet,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencyRange,
    FrequencySet,
    FrequencySetMember,
    Mode,
    Priority,
    Profile,
    RadioCapabilities,
    RadioModel,
    Severity,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


def make_capabilities(**changes: object) -> RadioCapabilities:
    target = RadioCapabilities(
        memory_capacity=10,
        memory_start=1,
        receive_ranges=(FrequencyRange(100_000_000, 500_000_000),),
        transmit_ranges=(FrequencyRange(144_000_000, 148_000_000),),
        supported_modes=frozenset({Mode.FM, Mode.NFM}),
        supported_tone_modes=frozenset(
            {ToneMode.NONE, ToneMode.TONE, ToneMode.TSQL}
        ),
        max_label_length=8,
        supported_label_characters=" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
        supports_banks=False,
        supports_transmit_disable=True,
        supports_split=True,
    )
    return replace(target, **changes)


def make_radio(
    *,
    factory_frequency_sets: tuple[FactoryFrequencySet, ...] = (),
    **capability_changes: object,
) -> RadioModel:
    return RadioModel(
        id="test-radio",
        manufacturer="Test",
        model="Test Radio",
        capabilities=make_capabilities(**capability_changes),
        factory_frequency_sets=factory_frequency_sets,
    )


def make_definition(
    definition_id: str,
    *,
    frequency_hz: int = 146_520_000,
    priority: Priority = Priority.NORMAL,
    name: str | None = None,
    origin: CatalogOrigin = CatalogOrigin.USER,
    transmit_behavior: TransmitBehavior = TransmitBehavior.SAME,
    transmit_frequency_hz: int | None = None,
    offset_hz: int | None = None,
    mode: Mode = Mode.FM,
    tone: ToneSpec | None = None,
) -> FrequencyDefinition:
    return FrequencyDefinition(
        id=definition_id,
        name=name or definition_id,
        receive_frequency_hz=frequency_hz,
        transmit_behavior=transmit_behavior,
        origin=origin,
        transmit_frequency_hz=transmit_frequency_hz,
        offset_hz=offset_hz,
        mode=mode,
        tone=tone or ToneSpec(),
        priority=priority,
    )


def make_catalog(
    definitions: tuple[FrequencyDefinition, ...],
    *,
    set_id: str = "selected",
    set_origin: CatalogOrigin = CatalogOrigin.USER,
) -> FrequencyCatalog:
    return FrequencyCatalog(
        definitions=definitions,
        sets=(
            FrequencySet(
                id=set_id,
                name="Selected",
                origin=set_origin,
                members=tuple(
                    FrequencySetMember(item.id, position=index)
                    for index, item in enumerate(definitions)
                ),
            ),
        ),
    )


def selected_profile(set_id: str = "selected") -> Profile:
    return Profile(id="test", name="Test", frequency_set_ids=(set_id,))


@pytest.mark.parametrize(
    ("definition", "expected_code"),
    [
        (
            make_definition("bad-rx", frequency_hz=99_000_000),
            DiagnosticCode.RX_FREQUENCY_UNSUPPORTED,
        ),
        (
            make_definition(
                "bad-tx",
                transmit_behavior=TransmitBehavior.SPLIT,
                transmit_frequency_hz=155_000_000,
            ),
            DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
        ),
    ],
)
def test_unsupported_frequency_is_omitted(
    definition: FrequencyDefinition,
    expected_code: DiagnosticCode,
) -> None:
    catalog = make_catalog((definition,))
    plan = compile_profile(catalog, selected_profile(), make_radio())

    assert plan.memories == ()
    assert plan.omitted_frequency_definitions[0].reason is expected_code
    assert plan.diagnostics[0].severity is Severity.WARNING


def test_mandatory_incompatibility_is_an_error() -> None:
    definition = make_definition(
        "mandatory-rx",
        frequency_hz=99_000_000,
        priority=Priority.MANDATORY,
    )
    plan = compile_profile(
        make_catalog((definition,)),
        selected_profile(),
        make_radio(),
    )

    assert plan.error_count == 1
    assert plan.diagnostics[0].code is DiagnosticCode.RX_FREQUENCY_UNSUPPORTED


def test_receive_only_is_never_silently_made_transmittable() -> None:
    definition = make_definition(
        "weather",
        frequency_hz=162_550_000,
        transmit_behavior=TransmitBehavior.DISABLED,
    )
    catalog = make_catalog((definition,))

    unsupported = compile_profile(
        catalog,
        selected_profile(),
        make_radio(supports_transmit_disable=False),
    )
    supported = compile_profile(catalog, selected_profile(), make_radio())

    assert unsupported.memories == ()
    assert unsupported.diagnostics[0].code is DiagnosticCode.TX_DISABLE_NOT_REPRESENTABLE
    assert unsupported.diagnostics[0].severity is Severity.ERROR
    assert supported.memories[0].transmit_behavior is TransmitBehavior.DISABLED
    assert supported.memories[0].transmit_frequency_hz is None


def test_factory_availability_is_a_set_relationship_not_a_frequency_match() -> None:
    weather = make_definition(
        "weather",
        frequency_hz=162_550_000,
        origin=CatalogOrigin.PRESET,
        transmit_behavior=TransmitBehavior.DISABLED,
    )
    preset = FrequencySet(
        id="noaa",
        name="NOAA",
        origin=CatalogOrigin.PRESET,
        members=(FrequencySetMember(weather.id, position=0, channel_designator="WX1"),),
    )
    user_set = FrequencySet(
        id="my-weather",
        name="My weather",
        origin=CatalogOrigin.USER,
        members=(FrequencySetMember(weather.id, position=0),),
    )
    catalog = FrequencyCatalog((weather,), (preset, user_set))
    radio = make_radio(
        supports_transmit_disable=False,
        factory_frequency_sets=(
            FactoryFrequencySet(
                "noaa",
                "WX CH",
                frequency_editing=CapabilityStatus.UNKNOWN,
                chirp_editing=CapabilityStatus.UNSUPPORTED,
            ),
        ),
    )

    factory_plan = compile_profile(
        catalog,
        selected_profile("noaa"),
        radio,
    )
    user_plan = compile_profile(
        catalog,
        selected_profile("my-weather"),
        radio,
    )

    assert factory_plan.memories == ()
    assert factory_plan.factory_sets[0].frequency_set_id == "noaa"
    assert factory_plan.factory_definition_count == 1
    assert factory_plan.diagnostics[0].code is DiagnosticCode.FACTORY_SET_AVAILABLE
    assert user_plan.factory_sets == ()
    assert user_plan.diagnostics[0].code is DiagnosticCode.TX_DISABLE_NOT_REPRESENTABLE


def test_radio_settings_control_numbering_banks_and_factory_set_use() -> None:
    weather = make_definition(
        "weather",
        frequency_hz=162_550_000,
        origin=CatalogOrigin.PRESET,
        transmit_behavior=TransmitBehavior.DISABLED,
    )
    catalog = make_catalog(
        (weather,),
        set_id="noaa",
        set_origin=CatalogOrigin.PRESET,
    )
    radio = make_radio(
        supports_banks=True,
        bank_count=4,
        factory_frequency_sets=(FactoryFrequencySet("noaa", "WX CH"),),
    )
    settings = CompilationSettings(
        memory_start=40,
        map_sets_to_banks=False,
        use_factory_sets=False,
    )

    plan = compile_profile(catalog, selected_profile("noaa"), radio, settings)

    assert plan.memories[0].memory_number == 40
    assert plan.memories[0].bank_assignments == ()
    assert plan.factory_sets == ()


def test_label_normalization_and_truncation_are_explained() -> None:
    definition = make_definition("long-name", name="Local Repeater")
    catalog = make_catalog((definition,))
    plan = compile_profile(
        catalog,
        selected_profile(),
        make_radio(max_label_length=6),
        CompilationSettings(map_sets_to_banks=False),
    )

    assert plan.memories[0].target_name == "LOCAL"
    assert plan.memories[0].applied_transformations == (
        DiagnosticCode.LABEL_CHARACTERS_NORMALIZED,
        DiagnosticCode.LABEL_TRUNCATED,
    )
    assert {item.code for item in plan.diagnostics} == {
        DiagnosticCode.LABEL_CHARACTERS_NORMALIZED,
        DiagnosticCode.LABEL_TRUNCATED,
    }
    assert definition.name == "Local Repeater"


def test_capacity_ranking_and_numbering_are_deterministic() -> None:
    definitions = (
        make_definition("normal", priority=Priority.NORMAL),
        make_definition("high", priority=Priority.HIGH),
        make_definition("low", priority=Priority.LOW),
        make_definition("mandatory", priority=Priority.MANDATORY),
    )
    catalog = make_catalog(definitions)
    radio = make_radio(memory_capacity=3, memory_start=10)

    first = compile_profile(catalog, selected_profile(), radio)
    second = compile_profile(
        make_catalog(tuple(reversed(definitions))),
        selected_profile(),
        radio,
    )

    expected_ids = ["mandatory", "high", "normal"]
    assert [item.source_frequency_definition_id for item in first.memories] == expected_ids
    assert [item.source_frequency_definition_id for item in second.memories] == expected_ids
    assert [item.memory_number for item in first.memories] == [10, 11, 12]
    assert first.capacity_summary.omitted_for_capacity == 1
    assert first.omitted_frequency_definitions[0].frequency_definition_id == "low"


@pytest.mark.parametrize(
    ("definition", "radio", "expected_code"),
    [
        (
            make_definition("am", mode=Mode.AM),
            make_radio(),
            DiagnosticCode.MODE_UNSUPPORTED,
        ),
        (
            make_definition(
                "dtcs",
                tone=ToneSpec(mode=ToneMode.DTCS, dtcs_code=23),
            ),
            make_radio(supported_tone_modes=frozenset({ToneMode.NONE})),
            DiagnosticCode.TONE_UNSUPPORTED,
        ),
    ],
)
def test_unsupported_mode_or_tone_is_omitted(
    definition: FrequencyDefinition,
    radio: RadioModel,
    expected_code: DiagnosticCode,
) -> None:
    plan = compile_profile(
        make_catalog((definition,)),
        selected_profile(),
        radio,
    )

    assert plan.memories == ()
    assert plan.diagnostics[0].code is expected_code


def test_selected_sets_map_to_banks_or_degrade_visibly() -> None:
    definition = make_definition("grouped")
    catalog = make_catalog((definition,))

    degraded = compile_profile(catalog, selected_profile(), make_radio())
    mapped = compile_profile(
        catalog,
        selected_profile(),
        make_radio(supports_banks=True, bank_count=4),
    )

    assert degraded.memories[0].bank_assignments == ()
    assert any(
        item.code is DiagnosticCode.GROUPING_DEGRADED
        for item in degraded.diagnostics
    )
    assert mapped.memories[0].bank_assignments == ("selected",)


def test_user_set_can_reference_a_shared_preset_definition() -> None:
    definition = make_definition("shared", origin=CatalogOrigin.PRESET)
    catalog = FrequencyCatalog(
        definitions=(definition,),
        sets=(
            FrequencySet(
                "preset",
                "Preset",
                CatalogOrigin.PRESET,
                (FrequencySetMember("shared", 0),),
            ),
            FrequencySet(
                "user",
                "User",
                CatalogOrigin.USER,
                (FrequencySetMember("shared", 0),),
            ),
        ),
    )

    assert catalog.frequency_set("preset").read_only is True
    assert catalog.frequency_set("user").read_only is False
    assert catalog.frequency_set("user").members[0].frequency_definition_id == "shared"


def test_preset_set_cannot_reference_mutable_user_definition() -> None:
    definition = make_definition("user-owned")

    with pytest.raises(ValueError, match="cannot depend on user definition"):
        FrequencyCatalog(
            definitions=(definition,),
            sets=(
                FrequencySet(
                    "bad-preset",
                    "Bad preset",
                    CatalogOrigin.PRESET,
                    (FrequencySetMember(definition.id, 0),),
                ),
            ),
        )
