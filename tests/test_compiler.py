from __future__ import annotations

from dataclasses import replace

import pytest

from rigmanifest.compiler import compile_profile, compile_profiles
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
    SignalingKind,
    SignalingSpec,
    ToneMode,
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
    transmit_access: SignalingSpec | None = None,
    receive_squelch: SignalingSpec | None = None,
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
        transmit_access=transmit_access or SignalingSpec(),
        receive_squelch=receive_squelch or SignalingSpec(),
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


def test_profiles_sets_and_direct_definitions_merge_with_provenance() -> None:
    shared = make_definition("shared")
    direct = make_definition("direct", frequency_hz=146_550_000)
    catalog = make_catalog((shared,), set_id="shared-set")
    catalog = FrequencyCatalog(catalog.definitions + (direct,), catalog.sets)

    plan = compile_profiles(
        catalog,
        (
            Profile("home", "Home", ("shared-set",), frequency_definition_ids=("direct",)),
            Profile("travel", "Travel", ("shared-set",)),
        ),
        make_radio(),
        additional_frequency_definition_ids=("shared",),
    )

    assert [memory.source_frequency_definition_id for memory in plan.memories] == [
        "shared",
        "direct",
    ]
    assert plan.memories[0].source_profile_ids == ("home", "travel")
    assert plan.memories[0].source_frequency_set_ids == ("shared-set",)
    assert plan.memories[0].selected_directly is True
    assert plan.memories[1].source_profile_ids == ("home",)


def test_profile_plan_conflicts_are_warnings_and_never_block_compilation() -> None:
    definition = make_definition(
        "boundary-repeater",
        frequency_hz=147_000_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=600_000,
    )
    catalog = make_catalog((definition,))

    plan = compile_profiles(
        catalog,
        (
            Profile("kansas", "Kansas", ("selected",), "kansas-repeater-council"),
            Profile(
                "nevada",
                "Nevada",
                ("selected",),
                "southern-nevada-repeater-council",
            ),
        ),
        make_radio(),
    )

    codes = {diagnostic.code for diagnostic in plan.diagnostics}
    assert DiagnosticCode.PLAN_OFFSET_UNUSUAL in codes
    assert DiagnosticCode.PLAN_CONTEXT_CONFLICT in codes
    assert all(
        diagnostic.severity is Severity.WARNING
        for diagnostic in plan.diagnostics
        if diagnostic.code in {
            DiagnosticCode.PLAN_OFFSET_UNUSUAL,
            DiagnosticCode.PLAN_CONTEXT_CONFLICT,
        }
    )
    assert len(plan.memories) == 1


def test_compile_wide_plan_warns_for_off_raster_frequency_without_omitting_it() -> None:
    definition = make_definition(
        "off-raster",
        frequency_hz=147_005_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=600_000,
    )
    plan = compile_profiles(
        make_catalog((definition,)),
        (),
        make_radio(),
        additional_frequency_set_ids=("selected",),
        advisory_plan_id="kansas-repeater-council",
    )

    assert any(
        item.code is DiagnosticCode.PLAN_RASTER_UNUSUAL
        for item in plan.diagnostics
    )
    assert len(plan.memories) == 1


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
                transmit_access=SignalingSpec(
                    kind=SignalingKind.DCS,
                    dcs_code=23,
                ),
                receive_squelch=SignalingSpec(
                    kind=SignalingKind.DCS,
                    dcs_code=23,
                ),
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


def test_independent_transmit_and_receive_signaling_compiles_as_cross_mode() -> None:
    definition = make_definition(
        "mixed-signaling",
        transmit_access=SignalingSpec(
            kind=SignalingKind.CTCSS,
            ctcss_hz=100.0,
        ),
        receive_squelch=SignalingSpec(
            kind=SignalingKind.DCS,
            dcs_code=23,
            dcs_polarity="R",
        ),
    )
    radio = make_radio(
        supported_tone_modes=frozenset({ToneMode.NONE, ToneMode.CROSS}),
        valid_cross_modes=("Tone->DTCS",),
        valid_ctcss_tones_hz=(100.0,),
        valid_dtcs_codes=(23,),
        supports_dtcs_polarity=True,
    )

    plan = compile_profile(make_catalog((definition,)), selected_profile(), radio)

    assert plan.error_count == 0
    assert plan.memories[0].transmit_access == definition.transmit_access
    assert plan.memories[0].receive_squelch == definition.receive_squelch


@pytest.mark.parametrize(
    ("capability_changes", "receive_squelch", "detail"),
    [
        (
            {
                "supported_tone_modes": frozenset({ToneMode.NONE, ToneMode.CROSS}),
                "valid_cross_modes": ("DTCS->Tone",),
            },
            SignalingSpec(kind=SignalingKind.DCS, dcs_code=23),
            ("cross_mode", "Tone->DTCS"),
        ),
        (
            {
                "supported_tone_modes": frozenset({ToneMode.NONE, ToneMode.CROSS}),
                "valid_cross_modes": ("Tone->DTCS",),
                "valid_dtcs_codes": (25,),
            },
            SignalingSpec(kind=SignalingKind.DCS, dcs_code=23),
            ("dcs_code", "023"),
        ),
        (
            {
                "supported_tone_modes": frozenset({ToneMode.NONE, ToneMode.CROSS}),
                "valid_cross_modes": ("Tone->DTCS",),
                "supports_dtcs_polarity": False,
            },
            SignalingSpec(
                kind=SignalingKind.DCS,
                dcs_code=23,
                dcs_polarity="R",
            ),
            ("dcs_polarity", "R"),
        ),
    ],
)
def test_cross_mode_capability_mismatch_is_explained(
    capability_changes: dict[str, object],
    receive_squelch: SignalingSpec,
    detail: tuple[str, str],
) -> None:
    definition = make_definition(
        "mixed-signaling",
        transmit_access=SignalingSpec(
            kind=SignalingKind.CTCSS,
            ctcss_hz=100.0,
        ),
        receive_squelch=receive_squelch,
    )

    plan = compile_profile(
        make_catalog((definition,)),
        selected_profile(),
        make_radio(**capability_changes),
    )

    assert plan.memories == ()
    assert plan.diagnostics[0].code is DiagnosticCode.TONE_UNSUPPORTED
    assert dict(plan.diagnostics[0].details)[detail[0]] == detail[1]


def test_target_without_separate_receive_dcs_rejects_different_codes() -> None:
    definition = make_definition(
        "different-dcs",
        transmit_access=SignalingSpec(kind=SignalingKind.DCS, dcs_code=23),
        receive_squelch=SignalingSpec(kind=SignalingKind.DCS, dcs_code=25),
    )
    radio = make_radio(
        supported_tone_modes=frozenset({ToneMode.NONE, ToneMode.CROSS}),
        valid_cross_modes=("DTCS->DTCS",),
        valid_dtcs_codes=(23, 25),
        supports_separate_rx_dtcs=False,
    )

    plan = compile_profile(make_catalog((definition,)), selected_profile(), radio)

    assert plan.memories == ()
    assert "different transmit and receive DCS" in plan.diagnostics[0].message


def test_selected_sets_map_to_banks_or_degrade_visibly() -> None:
    definition = make_definition("grouped")
    second_definition = make_definition("also-grouped", frequency_hz=146_550_000)
    catalog = make_catalog((definition, second_definition))

    degraded = compile_profile(catalog, selected_profile(), make_radio())
    mapped = compile_profile(
        catalog,
        selected_profile(),
        make_radio(supports_banks=True, bank_count=4),
    )

    assert degraded.memories[0].bank_assignments == ()
    assert degraded.memories[1].bank_assignments == ()
    grouping_diagnostics = [
        item
        for item in degraded.diagnostics
        if item.code is DiagnosticCode.GROUPING_DEGRADED
    ]
    assert len(grouping_diagnostics) == 1
    assert grouping_diagnostics[0].severity is Severity.INFO
    assert grouping_diagnostics[0].frequency_set_id == "selected"
    assert grouping_diagnostics[0].frequency_definition_id is None
    assert "export and program normally" in grouping_diagnostics[0].message
    assert not any(
        item.code is DiagnosticCode.GROUPING_DEGRADED
        for item in mapped.diagnostics
    )
    assert mapped.memories[0].bank_assignments == ("selected",)
    assert mapped.memories[1].bank_assignments == ("selected",)


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
