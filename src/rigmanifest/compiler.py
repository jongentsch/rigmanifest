"""Pure compilation from selected frequency sets to radio memory locations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace

from rigmanifest.models import (
    CapacitySummary,
    CompilationSettings,
    CompiledMemory,
    CompiledRadioPlan,
    Diagnostic,
    DiagnosticCode,
    FactoryFrequencySet,
    FactorySetCoverage,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencySet,
    MemoryValidationIssue,
    Mode,
    OmittedFrequencyDefinition,
    Priority,
    Profile,
    RadioModel,
    Severity,
    SignalingKind,
    SignalingSpec,
    ToneMode,
    TransmitBehavior,
)


MemoryValidator = Callable[[CompiledMemory], tuple[MemoryValidationIssue, ...]]


@dataclass(frozen=True, slots=True)
class _Selection:
    definition: FrequencyDefinition
    source_set_ids: tuple[str, ...]
    selection_order: int


@dataclass(frozen=True, slots=True)
class _Candidate:
    selection: _Selection
    compiled: CompiledMemory


def compile_profile(
    catalog: FrequencyCatalog,
    profile: Profile,
    target: RadioModel,
    settings: CompilationSettings | None = None,
    *,
    memory_validator: MemoryValidator | None = None,
) -> CompiledRadioPlan:
    """Compile selected sets for one target without mutating catalog records."""

    settings = settings or CompilationSettings()
    selected_sets = _resolve_selected_sets(catalog, profile)
    factory_by_set_id = _validated_factory_sets(catalog, target)
    diagnostics: list[Diagnostic] = []
    omitted: list[OmittedFrequencyDefinition] = []
    factory_coverage: list[FactorySetCoverage] = []
    source_sets_by_definition: dict[str, list[str]] = {}
    selection_order: dict[str, int] = {}

    for frequency_set in selected_sets:
        factory_relation = factory_by_set_id.get(frequency_set.id)
        if settings.use_factory_sets and factory_relation is not None:
            coverage = _factory_coverage(frequency_set, factory_relation)
            factory_coverage.append(coverage)
            diagnostics.append(
                Diagnostic.with_details(
                    code=DiagnosticCode.FACTORY_SET_AVAILABLE,
                    severity=Severity.INFO,
                    frequency_set_id=frequency_set.id,
                    message=(
                        f"{frequency_set.name} is factory-provided on {target.model} "
                        f"as {factory_relation.interface_label}"
                    ),
                    details={
                        "definition_count": coverage.definition_count,
                        "interface_label": factory_relation.interface_label,
                        "chirp_editing": factory_relation.chirp_editing.value,
                    },
                )
            )
            continue

        for member in frequency_set.ordered_members:
            definition_id = member.frequency_definition_id
            if definition_id not in selection_order:
                selection_order[definition_id] = len(selection_order)
            sources = source_sets_by_definition.setdefault(definition_id, [])
            if frequency_set.id not in sources:
                sources.append(frequency_set.id)

    selections = tuple(
        _Selection(
            definition=catalog.definition(definition_id),
            source_set_ids=tuple(source_sets_by_definition[definition_id]),
            selection_order=order,
        )
        for definition_id, order in sorted(
            selection_order.items(), key=lambda item: item[1]
        )
    )

    candidates: list[_Candidate] = []
    for selection in selections:
        incompatibility = _find_incompatibility(selection.definition, target)
        if incompatibility is not None:
            diagnostics.append(incompatibility)
            omitted.append(
                OmittedFrequencyDefinition(
                    selection.definition.id,
                    incompatibility.code,
                )
            )
            continue

        compiled, transformations = _transform_definition(
            selection,
            target,
            map_sets_to_banks=settings.map_sets_to_banks,
        )
        diagnostics.extend(transformations)
        candidates.append(_Candidate(selection, compiled))

    candidates.sort(key=_ranking_key)
    capacity = target.capabilities.memory_capacity
    memory_start = (
        settings.memory_start
        if settings.memory_start is not None
        else target.capabilities.memory_start
    )
    memories: list[CompiledMemory] = []
    capacity_omission_count = 0
    target_rejection_count = 0

    for candidate in candidates:
        definition = candidate.selection.definition
        if len(memories) >= capacity:
            diagnostic = Diagnostic.with_details(
                code=DiagnosticCode.FREQUENCY_OMITTED_CAPACITY,
                severity=_omission_severity(definition),
                frequency_definition_id=definition.id,
                message=f"{definition.name} was omitted because target memory is full",
                details={"capacity": capacity},
            )
            diagnostics.append(diagnostic)
            omitted.append(OmittedFrequencyDefinition(definition.id, diagnostic.code))
            capacity_omission_count += 1
            continue

        memory = replace(
            candidate.compiled,
            memory_number=memory_start + len(memories),
        )
        validation_issues = memory_validator(memory) if memory_validator else ()
        rejected = False
        for issue in validation_issues:
            code = (
                DiagnosticCode.TARGET_MEMORY_REJECTED
                if issue.severity is Severity.ERROR
                else DiagnosticCode.TARGET_MEMORY_WARNING
            )
            diagnostics.append(
                Diagnostic(
                    code=code,
                    severity=issue.severity,
                    frequency_definition_id=definition.id,
                    frequency_set_id=None,
                    message=issue.message,
                    details=issue.details,
                )
            )
            rejected = rejected or issue.severity is Severity.ERROR
        if rejected:
            omitted.append(
                OmittedFrequencyDefinition(
                    definition.id,
                    DiagnosticCode.TARGET_MEMORY_REJECTED,
                )
            )
            target_rejection_count += 1
            continue
        memories.append(memory)

    return CompiledRadioPlan(
        target=target,
        profile=profile,
        memories=tuple(memories),
        factory_sets=tuple(factory_coverage),
        omitted_frequency_definitions=tuple(omitted),
        diagnostics=tuple(diagnostics),
        capacity_summary=CapacitySummary(
            capacity=capacity,
            compatible_candidates=len(candidates) - target_rejection_count,
            used=len(memories),
            omitted_for_capacity=capacity_omission_count,
        ),
    )


def _resolve_selected_sets(
    catalog: FrequencyCatalog,
    profile: Profile,
) -> tuple[FrequencySet, ...]:
    selected: list[FrequencySet] = []
    for set_id in profile.frequency_set_ids:
        try:
            selected.append(catalog.frequency_set(set_id))
        except KeyError as error:
            raise ValueError(f"profile references unknown frequency set: {set_id}") from error
    return tuple(selected)


def _validated_factory_sets(
    catalog: FrequencyCatalog,
    target: RadioModel,
) -> dict[str, FactoryFrequencySet]:
    validated: dict[str, FactoryFrequencySet] = {}
    for relation in target.factory_frequency_sets:
        try:
            frequency_set = catalog.frequency_set(relation.frequency_set_id)
        except KeyError as error:
            raise ValueError(
                f"radio model references unknown factory frequency set: "
                f"{relation.frequency_set_id}"
            ) from error
        if not frequency_set.read_only:
            raise ValueError(
                f"radio model factory relationship must reference a preset set: "
                f"{frequency_set.id}"
            )
        validated[frequency_set.id] = relation
    return validated


def _factory_coverage(
    frequency_set: FrequencySet,
    relation: FactoryFrequencySet,
) -> FactorySetCoverage:
    return FactorySetCoverage(
        frequency_set_id=frequency_set.id,
        frequency_set_name=frequency_set.name,
        interface_label=relation.interface_label,
        frequency_definition_ids=tuple(
            member.frequency_definition_id for member in frequency_set.ordered_members
        ),
        frequency_editing=relation.frequency_editing,
        chirp_editing=relation.chirp_editing,
    )


def _find_incompatibility(
    definition: FrequencyDefinition,
    target: RadioModel,
) -> Diagnostic | None:
    capabilities = target.capabilities
    severity = _omission_severity(definition)

    if not capabilities.supports_receive_frequency(definition.receive_frequency_hz):
        return Diagnostic.with_details(
            code=DiagnosticCode.RX_FREQUENCY_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=f"{definition.name} is outside the target receive range",
            details={"frequency_hz": definition.receive_frequency_hz},
        )

    if definition.transmit_behavior is TransmitBehavior.DISABLED:
        if not capabilities.supports_transmit_disable:
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_DISABLE_NOT_REPRESENTABLE,
                severity=Severity.ERROR,
                frequency_definition_id=definition.id,
                message=(
                    f"{target.model} cannot safely represent transmit-disabled "
                    f"intent for {definition.name}"
                ),
            )
    else:
        transmit_frequency_hz = definition.resolved_transmit_frequency_hz
        assert transmit_frequency_hz is not None
        if not capabilities.supports_transmit_frequency(transmit_frequency_hz):
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
                severity=severity,
                frequency_definition_id=definition.id,
                message=f"{definition.name} is outside the target transmit range",
                details={"frequency_hz": transmit_frequency_hz},
            )
        if (
            definition.transmit_behavior is TransmitBehavior.SPLIT
            and not capabilities.supports_split
        ):
            return Diagnostic.with_details(
                code=DiagnosticCode.TX_FREQUENCY_UNSUPPORTED,
                severity=severity,
                frequency_definition_id=definition.id,
                message=f"{target.model} cannot represent split TX for {definition.name}",
            )

    if definition.mode not in capabilities.supported_modes:
        return Diagnostic.with_details(
            code=DiagnosticCode.MODE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support {definition.mode.value} "
                f"for {definition.name}"
            ),
            details={"mode": definition.mode.value},
        )

    required_tone_mode, required_cross_mode = _required_tone_encoding(
        definition.transmit_access,
        definition.receive_squelch,
    )
    if required_tone_mode not in capabilities.supported_tone_modes:
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support the required "
                f"{required_tone_mode.value} signaling for {definition.name}"
            ),
            details={"tone_mode": required_tone_mode.value},
        )
    if (
        required_cross_mode is not None
        and capabilities.valid_cross_modes
        and required_cross_mode not in capabilities.valid_cross_modes
    ):
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support {required_cross_mode} signaling "
                f"for {definition.name}"
            ),
            details={"cross_mode": required_cross_mode},
        )
    for direction, signaling in (
        ("transmit", definition.transmit_access),
        ("receive", definition.receive_squelch),
    ):
        incompatibility = _find_signaling_incompatibility(
            signaling,
            direction=direction,
            definition=definition,
            target=target,
        )
        if incompatibility is not None:
            return incompatibility
    if (
        definition.transmit_access.kind is SignalingKind.DCS
        and definition.receive_squelch.kind is SignalingKind.DCS
        and definition.transmit_access.dcs_code != definition.receive_squelch.dcs_code
        and not capabilities.supports_separate_rx_dtcs
    ):
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} cannot use different transmit and receive DCS "
                f"codes for {definition.name}"
            ),
        )
    return None


def _find_signaling_incompatibility(
    signaling: SignalingSpec,
    *,
    direction: str,
    definition: FrequencyDefinition,
    target: RadioModel,
) -> Diagnostic | None:
    capabilities = target.capabilities
    severity = _omission_severity(definition)
    if (
        signaling.kind is SignalingKind.CTCSS
        and capabilities.valid_ctcss_tones_hz
        and signaling.ctcss_hz not in capabilities.valid_ctcss_tones_hz
    ):
        assert signaling.ctcss_hz is not None
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support {direction} CTCSS "
                f"{signaling.ctcss_hz:.1f} Hz for {definition.name}"
            ),
            details={"direction": direction, "ctcss_hz": signaling.ctcss_hz},
        )
    if (
        signaling.kind is SignalingKind.DCS
        and capabilities.valid_dtcs_codes
        and signaling.dcs_code not in capabilities.valid_dtcs_codes
    ):
        assert signaling.dcs_code is not None
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support {direction} DCS "
                f"{signaling.dcs_code:03d} for {definition.name}"
            ),
            details={"direction": direction, "dcs_code": f"{signaling.dcs_code:03d}"},
        )
    if (
        signaling.kind is SignalingKind.DCS
        and signaling.dcs_polarity == "R"
        and not capabilities.supports_dtcs_polarity
    ):
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support reverse {direction} DCS polarity "
                f"for {definition.name}"
            ),
            details={"direction": direction, "dcs_polarity": "R"},
        )
    return None


def _required_tone_encoding(
    transmit_access: SignalingSpec,
    receive_squelch: SignalingSpec,
) -> tuple[ToneMode, str | None]:
    tx_kind = transmit_access.kind
    rx_kind = receive_squelch.kind
    if tx_kind is SignalingKind.NONE and rx_kind is SignalingKind.NONE:
        return ToneMode.NONE, None
    if tx_kind is SignalingKind.CTCSS and rx_kind is SignalingKind.NONE:
        return ToneMode.TONE, None
    if (
        tx_kind is SignalingKind.CTCSS
        and rx_kind is SignalingKind.CTCSS
        and transmit_access.ctcss_hz == receive_squelch.ctcss_hz
    ):
        return ToneMode.TSQL, None
    if (
        tx_kind is SignalingKind.DCS
        and rx_kind is SignalingKind.DCS
        and transmit_access.dcs_code == receive_squelch.dcs_code
    ):
        return ToneMode.DTCS, None

    names = {
        SignalingKind.NONE: "",
        SignalingKind.CTCSS: "Tone",
        SignalingKind.DCS: "DTCS",
    }
    return ToneMode.CROSS, f"{names[tx_kind]}->{names[rx_kind]}"


def _transform_definition(
    selection: _Selection,
    target: RadioModel,
    *,
    map_sets_to_banks: bool,
) -> tuple[CompiledMemory, list[Diagnostic]]:
    definition = selection.definition
    capabilities = target.capabilities
    diagnostics: list[Diagnostic] = []
    transformations: list[DiagnosticCode] = []
    original_name = definition.name
    normalized_name = "".join(
        character if character in capabilities.supported_label_characters else " "
        for character in original_name.upper()
    ).rstrip()

    if normalized_name != original_name:
        code = DiagnosticCode.LABEL_CHARACTERS_NORMALIZED
        diagnostics.append(
            Diagnostic.with_details(
                code=code,
                severity=Severity.INFO,
                frequency_definition_id=definition.id,
                message=f"{original_name} was normalized for {target.model}",
                details={"original": original_name, "normalized": normalized_name},
            )
        )
        transformations.append(code)

    target_name = normalized_name[: capabilities.max_label_length].rstrip()
    if len(normalized_name) > capabilities.max_label_length:
        code = DiagnosticCode.LABEL_TRUNCATED
        diagnostics.append(
            Diagnostic.with_details(
                code=code,
                severity=Severity.WARNING,
                frequency_definition_id=definition.id,
                message=f"{original_name} was shortened to {target_name}",
                details={"original": original_name, "compiled": target_name},
            )
        )
        transformations.append(code)

    groups = selection.source_set_ids if map_sets_to_banks else ()
    if groups and not capabilities.supports_banks:
        diagnostics.append(
            Diagnostic.with_details(
                code=DiagnosticCode.GROUPING_DEGRADED,
                severity=Severity.WARNING,
                frequency_definition_id=definition.id,
                message=(
                    f"Frequency sets for {definition.name} cannot map to {target.model}"
                ),
                details={"sets": ",".join(groups)},
            )
        )
        groups = ()

    return (
        CompiledMemory(
            source_frequency_definition_id=definition.id,
            source_frequency_set_ids=selection.source_set_ids,
            memory_number=0,
            target_name=target_name,
            receive_frequency_hz=definition.receive_frequency_hz,
            transmit_behavior=definition.transmit_behavior,
            transmit_frequency_hz=definition.resolved_transmit_frequency_hz,
            offset_hz=definition.offset_hz,
            mode=definition.mode,
            transmit_access=definition.transmit_access,
            receive_squelch=definition.receive_squelch,
            bank_assignments=groups,
            applied_transformations=tuple(transformations),
        ),
        diagnostics,
    )


def _ranking_key(candidate: _Candidate) -> tuple[int, int, str]:
    priority_tier = {
        Priority.MANDATORY: 0,
        Priority.HIGH: 1,
        Priority.NORMAL: 2,
        Priority.LOW: 3,
    }[candidate.selection.definition.priority]
    return (
        priority_tier,
        candidate.selection.selection_order,
        candidate.selection.definition.id,
    )


def _omission_severity(definition: FrequencyDefinition) -> Severity:
    if definition.priority is Priority.MANDATORY:
        return Severity.ERROR
    return Severity.WARNING
