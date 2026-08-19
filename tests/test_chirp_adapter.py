from __future__ import annotations

from dataclasses import replace

import pytest

from rigmanifest.capabilities import VX6R_USA
from rigmanifest.chirp_adapter import (
    CHIRP_COMMIT,
    ChirpCapabilityOverlay,
    chirp_memory_validator,
    radio_model_from_chirp,
)
from rigmanifest.compiler import compile_profile
from rigmanifest.models import (
    CatalogOrigin,
    DiagnosticCode,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencyRange,
    FrequencySet,
    FrequencySetMember,
    Profile,
    RadioModel,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


def _catalog_for(definition: FrequencyDefinition) -> FrequencyCatalog:
    return FrequencyCatalog(
        definitions=(definition,),
        sets=(
            FrequencySet(
                id="test-set",
                name="Test set",
                origin=CatalogOrigin.USER,
                members=(FrequencySetMember(definition.id, 0),),
            ),
        ),
    )


def _profile() -> Profile:
    return Profile("test", "Test", ("test-set",))


def _vx6_without_factory_sets() -> RadioModel:
    return replace(VX6R_USA, factory_frequency_sets=())


def test_vx6_capabilities_come_from_the_pinned_chirp_driver() -> None:
    capabilities = VX6R_USA.capabilities

    assert VX6R_USA.chirp_driver_reference == "Yaesu_VX-6"
    assert capabilities.memory_start == 1
    assert capabilities.receive_ranges[0].lower_hz == 500_000
    assert capabilities.receive_ranges[0].upper_hz == 998_989_999
    assert capabilities.valid_tuning_steps_hz[:4] == (
        5_000,
        10_000,
        12_500,
        15_000,
    )
    assert len(capabilities.valid_ctcss_tones_hz) == 50
    assert len(capabilities.valid_dtcs_codes) == 104
    assert capabilities.supports_split is True
    assert capabilities.supports_transmit_disable is False
    assert capabilities.source_notes[0].endswith(CHIRP_COMMIT)


@pytest.mark.parametrize(
    ("driver_reference", "transmit_ranges", "expected_model", "expected_capacity"),
    [
        (
            "Quansheng_UV-K5",
            (
                FrequencyRange(136_000_000, 174_000_000),
                FrequencyRange(400_000_000, 470_000_000),
            ),
            "UV-K5",
            200,
        ),
        (
            "Retevis_RT95",
            (
                FrequencyRange(136_000_000, 174_000_000),
                FrequencyRange(400_000_000, 490_000_000),
            ),
            "RT95",
            200,
        ),
    ],
)
def test_initial_driver_families_map_through_the_same_adapter(
    driver_reference: str,
    transmit_ranges: tuple[FrequencyRange, ...],
    expected_model: str,
    expected_capacity: int,
) -> None:
    model = radio_model_from_chirp(
        model_id="test-model",
        driver_reference=driver_reference,
        overlay=ChirpCapabilityOverlay(transmit_ranges=transmit_ranges),
    )

    assert model.model == expected_model
    assert model.capabilities.memory_capacity == expected_capacity
    assert model.capabilities.valid_tuning_steps_hz
    assert model.capabilities.valid_ctcss_tones_hz
    assert model.capabilities.valid_dtcs_codes


def test_hf_definition_is_valid_catalog_intent_but_not_vx6_transmit_intent() -> None:
    hf_definition = FrequencyDefinition(
        id="forty-meters",
        name="Forty meters",
        receive_frequency_hz=7_200_000,
        transmit_behavior=TransmitBehavior.SAME,
    )

    plan = compile_profile(
        _catalog_for(hf_definition),
        _profile(),
        _vx6_without_factory_sets(),
    )

    assert hf_definition.receive_frequency_hz == 7_200_000
    assert plan.memories == ()
    assert plan.omitted_frequency_definitions[0].reason is (
        DiagnosticCode.TX_FREQUENCY_UNSUPPORTED
    )


def test_chirp_driver_validation_rejects_an_unrepresentable_frequency_step() -> None:
    definition = FrequencyDefinition(
        id="off-step",
        name="Off step",
        receive_frequency_hz=146_520_001,
        transmit_behavior=TransmitBehavior.SAME,
    )

    plan = compile_profile(
        _catalog_for(definition),
        _profile(),
        _vx6_without_factory_sets(),
        memory_validator=chirp_memory_validator("Yaesu_VX-6"),
    )

    assert plan.memories == ()
    assert plan.omitted_frequency_definitions[0].reason is (
        DiagnosticCode.TARGET_MEMORY_REJECTED
    )
    assert plan.diagnostics[-1].code is DiagnosticCode.TARGET_MEMORY_REJECTED
    assert dict(plan.diagnostics[-1].details)["source"] == "CHIRP"


def test_chirp_tone_catalog_is_enforced_at_compile_time() -> None:
    definition = FrequencyDefinition(
        id="unsupported-tone",
        name="Unsupported tone",
        receive_frequency_hz=146_520_000,
        transmit_behavior=TransmitBehavior.SAME,
        tone=ToneSpec(mode=ToneMode.TONE, encode_hz=60.0),
    )

    plan = compile_profile(
        _catalog_for(definition),
        _profile(),
        _vx6_without_factory_sets(),
    )

    assert plan.memories == ()
    assert plan.omitted_frequency_definitions[0].reason is (
        DiagnosticCode.TONE_UNSUPPORTED
    )
