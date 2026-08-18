from __future__ import annotations

from dataclasses import replace

import pytest

from rigmanifest.compiler import compile_profile
from rigmanifest.models import (
    Channel,
    DiagnosticCode,
    FrequencyRange,
    LogicalGroup,
    Mode,
    Priority,
    Profile,
    RadioCapabilities,
    Severity,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


def make_target(**changes: object) -> RadioCapabilities:
    target = RadioCapabilities(
        id="test-radio",
        manufacturer="Test",
        model="Test Radio",
        memory_capacity=10,
        receive_ranges=(FrequencyRange(100_000_000, 500_000_000),),
        transmit_ranges=(FrequencyRange(140_000_000, 150_000_000),),
        supported_modes=frozenset({Mode.FM}),
        supported_tone_modes=frozenset(
            {ToneMode.NONE, ToneMode.TONE, ToneMode.TSQL, ToneMode.DTCS}
        ),
        max_label_length=8,
        supported_label_characters=" ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-",
        supports_banks=False,
        supports_transmit_disable=True,
        supports_split=True,
    )
    return replace(target, **changes)


def make_channel(
    channel_id: str,
    *,
    frequency_hz: int = 146_520_000,
    priority: Priority = Priority.NORMAL,
    name: str | None = None,
    transmit_behavior: TransmitBehavior = TransmitBehavior.SAME,
    transmit_frequency_hz: int | None = None,
    offset_hz: int | None = None,
    mode: Mode = Mode.FM,
    tone: ToneSpec | None = None,
    tags: frozenset[str] = frozenset({"selected"}),
) -> Channel:
    return Channel(
        id=channel_id,
        name=name or channel_id,
        receive_frequency_hz=frequency_hz,
        transmit_behavior=transmit_behavior,
        transmit_frequency_hz=transmit_frequency_hz,
        offset_hz=offset_hz,
        mode=mode,
        tone=tone or ToneSpec(),
        tags=tags,
        priority=priority,
    )


def selected_profile(**changes: object) -> Profile:
    profile = Profile(
        id="test",
        name="Test",
        include_tags=frozenset({"selected"}),
    )
    return replace(profile, **changes)


@pytest.mark.parametrize(
    ("channel", "expected_code"),
    [
        (
            make_channel("bad-rx", frequency_hz=99_000_000),
            DiagnosticCode.RX_FREQUENCY_UNSUPPORTED,
        ),
        (
            make_channel(
                "bad-tx",
                transmit_behavior=TransmitBehavior.SPLIT,
                transmit_frequency_hz=155_000_000,
            ),
            DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
        ),
    ],
)
def test_unsupported_frequency_is_omitted(
    channel: Channel, expected_code: DiagnosticCode
) -> None:
    plan = compile_profile((channel,), selected_profile(), make_target())

    assert plan.memories == ()
    assert plan.omitted_channels[0].reason is expected_code
    assert plan.diagnostics[0].severity is Severity.WARNING


def test_mandatory_incompatibility_is_an_error() -> None:
    channel = make_channel(
        "mandatory-rx",
        frequency_hz=99_000_000,
        priority=Priority.MANDATORY,
    )

    plan = compile_profile((channel,), selected_profile(), make_target())

    assert plan.error_count == 1
    assert plan.diagnostics[0].code is DiagnosticCode.RX_FREQUENCY_UNSUPPORTED


def test_receive_only_is_never_silently_made_transmittable() -> None:
    channel = make_channel(
        "weather",
        frequency_hz=162_550_000,
        transmit_behavior=TransmitBehavior.DISABLED,
    )

    unsupported = compile_profile(
        (channel,),
        selected_profile(),
        make_target(supports_transmit_disable=False),
    )
    supported = compile_profile((channel,), selected_profile(), make_target())

    assert unsupported.memories == ()
    assert unsupported.diagnostics[0].code is DiagnosticCode.TX_DISABLE_NOT_REPRESENTABLE
    assert unsupported.diagnostics[0].severity is Severity.ERROR
    assert supported.memories[0].transmit_behavior is TransmitBehavior.DISABLED
    assert supported.memories[0].transmit_frequency_hz is None


def test_label_normalization_and_truncation_are_explained() -> None:
    channel = make_channel("long-name", name="Local Repeater")
    plan = compile_profile((channel,), selected_profile(), make_target(max_label_length=6))

    assert plan.memories[0].target_name == "LOCAL"
    assert plan.memories[0].applied_transformations == (
        DiagnosticCode.LABEL_CHARACTERS_NORMALIZED,
        DiagnosticCode.LABEL_TRUNCATED,
    )
    assert {item.code for item in plan.diagnostics} == {
        DiagnosticCode.LABEL_CHARACTERS_NORMALIZED,
        DiagnosticCode.LABEL_TRUNCATED,
    }
    assert channel.name == "Local Repeater"


def test_capacity_ranking_and_numbering_are_deterministic() -> None:
    channels = (
        make_channel("normal", priority=Priority.NORMAL),
        make_channel("high", priority=Priority.HIGH),
        make_channel("explicit-low", priority=Priority.LOW, tags=frozenset()),
        make_channel("mandatory", priority=Priority.MANDATORY),
    )
    profile = selected_profile(include_channel_ids=frozenset({"explicit-low"}))
    target = make_target(memory_capacity=3, memory_start=10)

    first = compile_profile(channels, profile, target)
    second = compile_profile(tuple(reversed(channels)), profile, target)

    expected_ids = ["mandatory", "explicit-low", "high"]
    assert [item.source_channel_id for item in first.memories] == expected_ids
    assert [item.source_channel_id for item in second.memories] == expected_ids
    assert [item.memory_number for item in first.memories] == [10, 11, 12]
    assert first.capacity_summary.omitted_for_capacity == 1
    assert first.omitted_channels[0].channel_id == "normal"


def test_explicit_exclusion_overrides_explicit_inclusion() -> None:
    channel = make_channel("excluded", tags=frozenset())
    profile = selected_profile(
        include_channel_ids=frozenset({channel.id}),
        exclude_channel_ids=frozenset({channel.id}),
    )

    plan = compile_profile((channel,), profile, make_target())

    assert plan.memories == ()
    assert plan.omitted_channels == ()


@pytest.mark.parametrize(
    ("channel", "target", "expected_code"),
    [
        (
            make_channel("am", mode=Mode.AM),
            make_target(),
            DiagnosticCode.MODE_UNSUPPORTED,
        ),
        (
            make_channel(
                "dtcs",
                tone=ToneSpec(mode=ToneMode.DTCS, dtcs_code=23),
            ),
            make_target(supported_tone_modes=frozenset({ToneMode.NONE})),
            DiagnosticCode.TONE_UNSUPPORTED,
        ),
    ],
)
def test_unsupported_mode_or_tone_is_omitted(
    channel: Channel,
    target: RadioCapabilities,
    expected_code: DiagnosticCode,
) -> None:
    plan = compile_profile((channel,), selected_profile(), target)

    assert plan.memories == ()
    assert plan.diagnostics[0].code is expected_code


def test_grouping_degradation_is_visible() -> None:
    channel = make_channel("grouped")
    profile = selected_profile(
        groups=(
            LogicalGroup("selected-group", "Selected", frozenset({"selected"})),
        )
    )

    degraded = compile_profile((channel,), profile, make_target(supports_banks=False))
    mapped = compile_profile(
        (channel,),
        profile,
        make_target(supports_banks=True, bank_count=4),
    )

    assert degraded.memories[0].bank_assignments == ()
    assert any(
        item.code is DiagnosticCode.GROUPING_DEGRADED
        for item in degraded.diagnostics
    )
    assert mapped.memories[0].bank_assignments == ("selected-group",)


def test_duplicate_channel_ids_are_rejected() -> None:
    channel = make_channel("duplicate")

    with pytest.raises(ValueError, match="duplicate channel ID"):
        compile_profile((channel, channel), selected_profile(), make_target())
