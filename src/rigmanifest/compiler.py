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
from rigmanifest.frequency_plans import PlanUse, matching_plan_segment


MemoryValidator = Callable[[CompiledMemory], tuple[MemoryValidationIssue, ...]]


@dataclass(frozen=True, slots=True)
class _Selection:
    definition: FrequencyDefinition
    source_set_ids: tuple[str, ...]
    source_profile_ids: tuple[str, ...]
    advisory_plan_ids: tuple[str, ...]
    selected_directly: bool
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
    """Compile one profile; retained as the CLI-compatible convenience boundary."""

    return compile_profiles(
        catalog,
        (profile,),
        target,
        settings,
        memory_validator=memory_validator,
    )


def compile_profiles(
    catalog: FrequencyCatalog,
    profiles: tuple[Profile, ...],
    target: RadioModel,
    settings: CompilationSettings | None = None,
    *,
    additional_frequency_set_ids: tuple[str, ...] = (),
    additional_frequency_definition_ids: tuple[str, ...] = (),
    advisory_plan_id: str | None = None,
    memory_validator: MemoryValidator | None = None,
) -> CompiledRadioPlan:
    """Compile profiles plus ad-hoc selections for one target without mutation."""

    settings = settings or CompilationSettings()
    profiles = tuple(profiles)
    additional_frequency_set_ids = tuple(additional_frequency_set_ids)
    additional_frequency_definition_ids = tuple(additional_frequency_definition_ids)
    if len({profile.id for profile in profiles}) != len(profiles):
        raise ValueError("compile selection contains a duplicate profile")
    if len(set(additional_frequency_set_ids)) != len(additional_frequency_set_ids):
        raise ValueError("compile selection contains a duplicate additional set")
    if len(set(additional_frequency_definition_ids)) != len(
        additional_frequency_definition_ids
    ):
        raise ValueError("compile selection contains a duplicate additional definition")
    if advisory_plan_id is not None:
        matching_plan_segment(advisory_plan_id, 1)

    factory_by_set_id = _validated_factory_sets(catalog, target)
    diagnostics: list[Diagnostic] = []
    grouping_diagnostics: list[Diagnostic] = []
    omitted: list[OmittedFrequencyDefinition] = []
    factory_coverage: list[FactorySetCoverage] = []
    source_sets_by_definition: dict[str, list[str]] = {}
    source_profiles_by_definition: dict[str, list[str]] = {}
    plan_ids_by_definition: dict[str, list[str]] = {}
    directly_selected: dict[str, bool] = {}
    selection_order: dict[str, int] = {}
    profile_by_id = {profile.id: profile for profile in profiles}

    selected_set_ids: list[str] = []
    profiles_by_set: dict[str, list[str]] = {}
    additional_sets = set(additional_frequency_set_ids)
    for profile in profiles:
        if profile.frequency_plan_id is not None:
            matching_plan_segment(profile.frequency_plan_id, 1)
        for set_id in profile.frequency_set_ids:
            if set_id not in selected_set_ids:
                selected_set_ids.append(set_id)
            sources = profiles_by_set.setdefault(set_id, [])
            if profile.id not in sources:
                sources.append(profile.id)
    for set_id in additional_frequency_set_ids:
        if set_id not in selected_set_ids:
            selected_set_ids.append(set_id)

    selected_sets = _resolve_selected_sets(catalog, tuple(selected_set_ids))

    def record_definition(
        definition_id: str,
        *,
        source_set_id: str | None = None,
        source_profile_ids: tuple[str, ...] = (),
        selected_directly: bool = False,
    ) -> None:
        try:
            catalog.definition(definition_id)
        except KeyError as error:
            raise ValueError(
                f"compile selection references unknown frequency definition: {definition_id}"
            ) from error
        if definition_id not in selection_order:
            selection_order[definition_id] = len(selection_order)
        if source_set_id is not None:
            sources = source_sets_by_definition.setdefault(definition_id, [])
            if source_set_id not in sources:
                sources.append(source_set_id)
        profile_sources = source_profiles_by_definition.setdefault(definition_id, [])
        for profile_id in source_profile_ids:
            if profile_id not in profile_sources:
                profile_sources.append(profile_id)
        plan_sources = plan_ids_by_definition.setdefault(definition_id, [])
        for profile_id in source_profile_ids:
            plan_id = profile_by_id[profile_id].frequency_plan_id or advisory_plan_id
            if plan_id is not None and plan_id not in plan_sources:
                plan_sources.append(plan_id)
        if advisory_plan_id is not None and advisory_plan_id not in plan_sources:
            plan_sources.append(advisory_plan_id)
        directly_selected[definition_id] = (
            directly_selected.get(definition_id, False) or selected_directly
        )

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

        if settings.map_sets_to_banks and not target.capabilities.supports_banks:
            grouping_diagnostics.append(
                Diagnostic.with_details(
                    code=DiagnosticCode.GROUPING_DEGRADED,
                    severity=Severity.INFO,
                    frequency_set_id=frequency_set.id,
                    message=(
                        f"{frequency_set.name} will export and program normally on "
                        f"{target.model}, but CHIRP reports no bank support; this set "
                        "will not become a radio bank"
                    ),
                    details={
                        "set_id": frequency_set.id,
                        "programming": "unaffected",
                        "grouping": "not_mapped",
                    },
                )
            )

        for member in frequency_set.ordered_members:
            record_definition(
                member.frequency_definition_id,
                source_set_id=frequency_set.id,
                source_profile_ids=tuple(profiles_by_set.get(frequency_set.id, ())),
                selected_directly=frequency_set.id in additional_sets,
            )

    for profile in profiles:
        for definition_id in profile.frequency_definition_ids:
            record_definition(definition_id, source_profile_ids=(profile.id,))
    for definition_id in additional_frequency_definition_ids:
        record_definition(definition_id, selected_directly=True)

    selections = tuple(
        _Selection(
            definition=catalog.definition(definition_id),
            source_set_ids=tuple(source_sets_by_definition.get(definition_id, ())),
            source_profile_ids=tuple(
                source_profiles_by_definition.get(definition_id, ())
            ),
            advisory_plan_ids=tuple(plan_ids_by_definition.get(definition_id, ())),
            selected_directly=directly_selected.get(definition_id, False),
            selection_order=order,
        )
        for definition_id, order in sorted(
            selection_order.items(), key=lambda item: item[1]
        )
    )

    candidates: list[_Candidate] = []
    for selection in selections:
        diagnostics.extend(_frequency_plan_diagnostics(selection))
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

    diagnostics.extend(grouping_diagnostics)
    primary_profile = profiles[0] if profiles else Profile("ad-hoc", "Ad hoc", ())
    return CompiledRadioPlan(
        target=target,
        profile=primary_profile,
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
        profiles=profiles,
        additional_frequency_set_ids=additional_frequency_set_ids,
        additional_frequency_definition_ids=additional_frequency_definition_ids,
        advisory_plan_id=advisory_plan_id,
    )


def _resolve_selected_sets(
    catalog: FrequencyCatalog,
    set_ids: tuple[str, ...],
) -> tuple[FrequencySet, ...]:
    selected: list[FrequencySet] = []
    for set_id in set_ids:
        try:
            selected.append(catalog.frequency_set(set_id))
        except KeyError as error:
            raise ValueError(
                f"compile selection references unknown frequency set: {set_id}"
            ) from error
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


def _frequency_plan_diagnostics(selection: _Selection) -> list[Diagnostic]:
    definition = selection.definition
    diagnostics: list[Diagnostic] = []
    expectations: dict[str, tuple[str, int | None, int | None]] = {}
    for requested_plan_id in selection.advisory_plan_ids:
        match = matching_plan_segment(
            requested_plan_id,
            definition.receive_frequency_hz,
        )
        if match is None:
            continue
        matched_plan, segment = match
        expectations[requested_plan_id] = (
            segment.use.value,
            segment.suggested_offset_hz,
            segment.raster_spacing_hz,
        )
        details = {
            "requested_plan_id": requested_plan_id,
            "matched_plan_id": matched_plan.id,
            "segment_id": segment.id,
            "source_url": matched_plan.source_url,
            "profile_ids": ",".join(selection.source_profile_ids),
        }
        on_raster = segment.is_on_raster(definition.receive_frequency_hz)
        if on_raster is False:
            diagnostics.append(
                Diagnostic.with_details(
                    code=DiagnosticCode.PLAN_RASTER_UNUSUAL,
                    severity=Severity.WARNING,
                    frequency_definition_id=definition.id,
                    message=(
                        f"{definition.name} is off the normal raster for "
                        f"{segment.name}"
                    ),
                    details={
                        **details,
                        "raster_spacing_hz": segment.raster_spacing_hz,
                    },
                )
            )
        if segment.use is PlanUse.SIMPLEX and definition.transmit_behavior in {
            TransmitBehavior.OFFSET,
            TransmitBehavior.SPLIT,
        }:
            diagnostics.append(
                Diagnostic.with_details(
                    code=DiagnosticCode.PLAN_USE_MISMATCH,
                    severity=Severity.WARNING,
                    frequency_definition_id=definition.id,
                    message=(
                        f"{definition.name} uses repeater-style transmit behavior "
                        f"in the selected plan's simplex segment"
                    ),
                    details=details,
                )
            )
        if (
            segment.use is PlanUse.REPEATER_OUTPUT
            and segment.suggested_offset_hz is not None
            and _transmit_delta(definition) != segment.suggested_offset_hz
        ):
            diagnostics.append(
                Diagnostic.with_details(
                    code=DiagnosticCode.PLAN_OFFSET_UNUSUAL,
                    severity=Severity.WARNING,
                    frequency_definition_id=definition.id,
                    message=(
                        f"{definition.name} does not use the "
                        f"{segment.suggested_offset_hz / 1_000_000:+.3f} "
                        f"MHz offset suggested by {segment.name}"
                    ),
                    details={
                        **details,
                        "suggested_offset_hz": segment.suggested_offset_hz,
                        "actual_offset_hz": _transmit_delta(definition),
                    },
                )
            )
    if len(set(expectations.values())) > 1:
        diagnostics.append(
            Diagnostic.with_details(
                code=DiagnosticCode.PLAN_CONTEXT_CONFLICT,
                severity=Severity.WARNING,
                frequency_definition_id=definition.id,
                message=(
                    f"{definition.name} has conflicting advice across the selected "
                    "profile and compile plan contexts"
                ),
                details={
                    "plan_ids": ",".join(expectations),
                    "profile_ids": ",".join(selection.source_profile_ids),
                },
            )
        )
    return diagnostics


def _transmit_delta(definition: FrequencyDefinition) -> int | None:
    transmit_hz = definition.resolved_transmit_frequency_hz
    if transmit_hz is None:
        return None
    return transmit_hz - definition.receive_frequency_hz


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

    groups = (
        selection.source_set_ids
        if map_sets_to_banks and capabilities.supports_banks
        else ()
    )

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
            power_dbm=definition.power_dbm,
            power_label=definition.power_label,
            scan_skip=definition.scan_skip,
            tuning_step_hz=definition.tuning_step_hz,
            bank_assignments=groups,
            applied_transformations=tuple(transformations),
            source_profile_ids=selection.source_profile_ids,
            selected_directly=selection.selected_directly,
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
