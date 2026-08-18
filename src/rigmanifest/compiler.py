"""Pure capability-aware compilation from canonical channels to radio memories."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from rigmanifest.models import (
    CapacitySummary,
    Channel,
    CompiledMemory,
    CompiledRadioPlan,
    Diagnostic,
    DiagnosticCode,
    OmittedChannel,
    Priority,
    Profile,
    RadioCapabilities,
    Severity,
    TransmitBehavior,
)


@dataclass(frozen=True, slots=True)
class _Candidate:
    channel: Channel
    compiled: CompiledMemory
    explicitly_included: bool


def compile_profile(
    channels: Sequence[Channel],
    profile: Profile,
    target: RadioCapabilities,
) -> CompiledRadioPlan:
    """Compile one profile for one target without mutating canonical inputs."""

    _ensure_unique_channel_ids(channels)
    diagnostics: list[Diagnostic] = []
    omitted: list[OmittedChannel] = []
    candidates: list[_Candidate] = []

    for channel in sorted(channels, key=lambda item: item.id):
        explicitly_included = channel.id in profile.include_channel_ids
        if not _selected(channel, profile, explicitly_included):
            continue

        incompatibility = _find_incompatibility(channel, target)
        if incompatibility is not None:
            diagnostics.append(incompatibility)
            omitted.append(OmittedChannel(channel.id, incompatibility.code))
            continue

        compiled, transformations = _transform_channel(channel, profile, target)
        diagnostics.extend(transformations)
        candidates.append(_Candidate(channel, compiled, explicitly_included))

    candidates.sort(key=_ranking_key)
    selected = candidates[: target.memory_capacity]
    capacity_omissions = candidates[target.memory_capacity :]

    for candidate in capacity_omissions:
        severity = _omission_severity(candidate.channel)
        diagnostic = Diagnostic.with_details(
            code=DiagnosticCode.CHANNEL_OMITTED_CAPACITY,
            severity=severity,
            channel_id=candidate.channel.id,
            message=f"{candidate.channel.name} was omitted because target memory is full",
            details={"capacity": target.memory_capacity},
        )
        diagnostics.append(diagnostic)
        omitted.append(OmittedChannel(candidate.channel.id, diagnostic.code))

    memories = tuple(
        replace(
            candidate.compiled,
            memory_number=target.memory_start + index,
        )
        for index, candidate in enumerate(selected)
    )

    return CompiledRadioPlan(
        target=target,
        profile=profile,
        memories=memories,
        omitted_channels=tuple(omitted),
        diagnostics=tuple(diagnostics),
        capacity_summary=CapacitySummary(
            capacity=target.memory_capacity,
            compatible_candidates=len(candidates),
            used=len(memories),
            omitted_for_capacity=len(capacity_omissions),
        ),
    )


def _ensure_unique_channel_ids(channels: Iterable[Channel]) -> None:
    seen: set[str] = set()
    for channel in channels:
        if channel.id in seen:
            raise ValueError(f"duplicate channel ID: {channel.id}")
        seen.add(channel.id)


def _selected(
    channel: Channel,
    profile: Profile,
    explicitly_included: bool,
) -> bool:
    if channel.id in profile.exclude_channel_ids:
        return False
    if channel.tags & profile.exclude_tags:
        return False

    included_by_tag = bool(channel.tags & profile.include_tags)
    if not explicitly_included and not included_by_tag:
        return False
    if not explicitly_included and channel.priority < profile.minimum_priority:
        return False
    return True


def _find_incompatibility(
    channel: Channel,
    target: RadioCapabilities,
) -> Diagnostic | None:
    severity = _omission_severity(channel)

    if not target.supports_receive_frequency(channel.receive_frequency_hz):
        return Diagnostic.with_details(
            code=DiagnosticCode.RX_FREQUENCY_UNSUPPORTED,
            severity=severity,
            channel_id=channel.id,
            message=f"{channel.name} is outside the target receive range",
            details={"frequency_hz": channel.receive_frequency_hz},
        )

    if channel.transmit_behavior is TransmitBehavior.DISABLED:
        if not target.supports_transmit_disable:
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_DISABLE_NOT_REPRESENTABLE,
                severity=Severity.ERROR,
                channel_id=channel.id,
                message=(
                    f"{target.model} cannot safely represent transmit-disabled "
                    f"intent for {channel.name}"
                ),
            )
    else:
        transmit_frequency_hz = channel.resolved_transmit_frequency_hz
        assert transmit_frequency_hz is not None
        if not target.supports_transmit_frequency(transmit_frequency_hz):
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
                severity=severity,
                channel_id=channel.id,
                message=f"{channel.name} is outside the target transmit range",
                details={"frequency_hz": transmit_frequency_hz},
            )
        if (
            channel.transmit_behavior is TransmitBehavior.SPLIT
            and not target.supports_split
        ):
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
                severity=severity,
                channel_id=channel.id,
                message=f"{target.model} cannot represent split TX for {channel.name}",
            )

    if channel.mode not in target.supported_modes:
        return Diagnostic.with_details(
            code=DiagnosticCode.MODE_UNSUPPORTED,
            severity=severity,
            channel_id=channel.id,
            message=f"{target.model} does not support {channel.mode.value} for {channel.name}",
            details={"mode": channel.mode.value},
        )

    if channel.tone.mode not in target.supported_tone_modes:
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            channel_id=channel.id,
            message=(
                f"{target.model} does not support {channel.tone.mode.value} "
                f"tone semantics for {channel.name}"
            ),
            details={"tone_mode": channel.tone.mode.value},
        )
    return None


def _transform_channel(
    channel: Channel,
    profile: Profile,
    target: RadioCapabilities,
) -> tuple[CompiledMemory, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []
    transformations: list[DiagnosticCode] = []
    original_name = channel.name
    normalized_name = "".join(
        character if character in target.supported_label_characters else " "
        for character in original_name.upper()
    ).rstrip()

    if normalized_name != original_name:
        code = DiagnosticCode.LABEL_CHARACTERS_NORMALIZED
        diagnostics.append(
            Diagnostic.with_details(
                code=code,
                severity=Severity.INFO,
                channel_id=channel.id,
                message=f"{original_name} was normalized for {target.model}",
                details={"original": original_name, "normalized": normalized_name},
            )
        )
        transformations.append(code)

    target_name = normalized_name[: target.max_label_length].rstrip()
    if len(normalized_name) > target.max_label_length:
        code = DiagnosticCode.LABEL_TRUNCATED
        diagnostics.append(
            Diagnostic.with_details(
                code=code,
                severity=Severity.WARNING,
                channel_id=channel.id,
                message=f"{original_name} was shortened to {target_name}",
                details={"original": original_name, "compiled": target_name},
            )
        )
        transformations.append(code)

    groups = tuple(
        group.id
        for group in profile.groups
        if channel.tags & group.include_tags
    )
    if groups and not target.supports_banks:
        diagnostics.append(
            Diagnostic.with_details(
                code=DiagnosticCode.GROUPING_DEGRADED,
                severity=Severity.WARNING,
                channel_id=channel.id,
                message=f"Logical groups for {channel.name} cannot map to {target.model}",
                details={"groups": ",".join(groups)},
            )
        )
        groups = ()

    return (
        CompiledMemory(
            source_channel_id=channel.id,
            memory_number=0,
            target_name=target_name,
            receive_frequency_hz=channel.receive_frequency_hz,
            transmit_behavior=channel.transmit_behavior,
            transmit_frequency_hz=channel.resolved_transmit_frequency_hz,
            offset_hz=channel.offset_hz,
            mode=channel.mode,
            tone=channel.tone,
            bank_assignments=groups,
            applied_transformations=tuple(transformations),
        ),
        diagnostics,
    )


def _ranking_key(candidate: _Candidate) -> tuple[int, str]:
    if candidate.channel.priority is Priority.MANDATORY:
        tier = 0
    elif candidate.explicitly_included:
        tier = 1
    elif candidate.channel.priority is Priority.HIGH:
        tier = 2
    elif candidate.channel.priority is Priority.NORMAL:
        tier = 3
    else:
        tier = 4
    return tier, candidate.channel.id


def _omission_severity(channel: Channel) -> Severity:
    if channel.priority is Priority.MANDATORY:
        return Severity.ERROR
    return Severity.WARNING
