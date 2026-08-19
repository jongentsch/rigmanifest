"""Pure compilation from selected frequency sets to radio memory locations."""

from __future__ import annotations

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
    Mode,
    OmittedFrequencyDefinition,
    Priority,
    Profile,
    RadioModel,
    Severity,
    ToneMode,
    TransmitBehavior,
)


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
    selected_candidates = candidates[:capacity]
    capacity_omissions = candidates[capacity:]

    for candidate in capacity_omissions:
        definition = candidate.selection.definition
        diagnostic = Diagnostic.with_details(
            code=DiagnosticCode.FREQUENCY_OMITTED_CAPACITY,
            severity=_omission_severity(definition),
            frequency_definition_id=definition.id,
            message=f"{definition.name} was omitted because target memory is full",
            details={"capacity": capacity},
        )
        diagnostics.append(diagnostic)
        omitted.append(OmittedFrequencyDefinition(definition.id, diagnostic.code))

    memory_start = (
        settings.memory_start
        if settings.memory_start is not None
        else target.capabilities.memory_start
    )
    memories = tuple(
        replace(candidate.compiled, memory_number=memory_start + index)
        for index, candidate in enumerate(selected_candidates)
    )

    return CompiledRadioPlan(
        target=target,
        profile=profile,
        memories=memories,
        factory_sets=tuple(factory_coverage),
        omitted_frequency_definitions=tuple(omitted),
        diagnostics=tuple(diagnostics),
        capacity_summary=CapacitySummary(
            capacity=capacity,
            compatible_candidates=len(candidates),
            used=len(memories),
            omitted_for_capacity=len(capacity_omissions),
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

    if definition.tone.mode not in capabilities.supported_tone_modes:
        return Diagnostic.with_details(
            code=DiagnosticCode.TONE_UNSUPPORTED,
            severity=severity,
            frequency_definition_id=definition.id,
            message=(
                f"{target.model} does not support {definition.tone.mode.value} "
                f"tone semantics for {definition.name}"
            ),
            details={"tone_mode": definition.tone.mode.value},
        )
    return None


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
            tone=definition.tone,
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
