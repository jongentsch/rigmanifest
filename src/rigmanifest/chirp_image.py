"""Image-backed radio integration through CHIRP's driver APIs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from chirp import chirp_common, directory, errors

from rigmanifest.chirp_adapter import apply_signaling_to_chirp_memory
from rigmanifest.chirp_version import CHIRP_COMMIT
from rigmanifest.chirp_import import definition_from_chirp_memory
from rigmanifest.chirp_runtime import initialize_chirp_runtime
from rigmanifest.models import (
    CatalogOrigin,
    CompiledMemory,
    CompiledRadioPlan,
    FrequencyDefinition,
    FrequencyRange,
    FrequencySet,
    FrequencySetMember,
    MemoryValidationIssue,
    Mode,
    Profile,
    RadioCapabilities,
    RadioModel,
    Severity,
    ToneMode,
    TransmitBehavior,
)
from rigmanifest.power import (
    RadioPowerCapability,
    inspect_radio_power,
    power_intent_from_observed,
    power_levels_from_features,
)


@dataclass(frozen=True, slots=True)
class ChirpImageImport:
    """Reusable catalog records and target facts extracted from one image."""

    source_path: Path
    driver_reference: str
    target: RadioModel
    frequency_definitions: tuple[FrequencyDefinition, ...]
    frequency_sets: tuple[FrequencySet, ...]
    profile: Profile
    setting_count: int
    power_capability: RadioPowerCapability

    @property
    def definition_count(self) -> int:
        return len(self.frequency_definitions)

    @property
    def bank_count(self) -> int:
        return self.target.capabilities.bank_count


def import_chirp_image(path: Path, *, radio_id: str) -> ChirpImageImport:
    """Load a CHIRP image and translate its memories and banks into intent."""

    if path.suffix.casefold() != ".img":
        raise ValueError("radio import requires a CHIRP .img file")
    if not path.is_file():
        raise ValueError(f"CHIRP image does not exist: {path}")
    if not radio_id.strip():
        raise ValueError("radio ID must not be blank")

    radio = load_chirp_image(path)
    target = radio_model_from_image(radio)
    features = radio.get_features()
    power_capability = inspect_radio_power(radio)
    observed_power = {
        item.memory_number: item
        for item in power_capability.observed_memories
    }
    lower, upper = features.memory_bounds
    definitions: list[FrequencyDefinition] = []
    definition_ids_by_memory: dict[int, str] = {}
    for number in range(int(lower), int(upper) + 1):
        memory = radio.get_memory(number)
        if memory.empty or not memory.freq:
            continue
        definition_id = f"user-radio-{radio_id}-memory-{number}"
        observed = observed_power.get(number)
        definitions.append(
            definition_from_chirp_memory(
                memory,
                definition_id=definition_id,
                source_name=path.name,
                power_intent=(
                    power_intent_from_observed(
                        native_label=observed.native_label,
                        nominal_dbm=observed.nominal_dbm,
                        normalized_tier=observed.normalized_tier,
                        driver_reference=target.chirp_driver_reference,
                        level_count=len(power_capability.levels),
                    )
                    if observed is not None
                    else None
                ),
            )
        )
        definition_ids_by_memory[number] = definition_id

    sets = _sets_from_image(radio, radio_id, definition_ids_by_memory)
    unbanked_set_id = f"user-radio-{radio_id}-unbanked"
    profile_set_ids = tuple(
        item.id for item in sets if item.id != unbanked_set_id or not features.has_bank
    )
    profile_definition_ids = tuple(
        member.frequency_definition_id
        for item in sets
        if item.id == unbanked_set_id and features.has_bank
        for member in item.ordered_members
    )
    profile = Profile(
        id=f"radio-{radio_id}-image",
        name=f"{target.manufacturer} {target.model} image",
        frequency_set_ids=profile_set_ids,
        frequency_definition_ids=profile_definition_ids,
        description=f"Banks imported from {path.name}.",
    )
    return ChirpImageImport(
        source_path=path,
        driver_reference=target.chirp_driver_reference or "",
        target=target,
        frequency_definitions=tuple(definitions),
        frequency_sets=sets,
        profile=profile,
        setting_count=_setting_count(radio),
        power_capability=power_capability,
    )


def load_chirp_image(path: Path) -> Any:
    """Ask CHIRP to detect and load an image without interpreting its bytes."""

    initialize_chirp_runtime()
    try:
        return directory.get_radio_by_image(str(path))
    except errors.ImageMetadataInvalidModel as error:
        metadata = getattr(error, "metadata", {})
        description = _image_metadata_description(metadata)
        raise ValueError(
            f"CHIRP has no bundled driver matching this radio image{description}"
        ) from error
    except errors.ImageDetectFailed as error:
        raise ValueError(f"CHIRP could not identify this radio image: {error}") from error


def _image_metadata_description(metadata: Mapping[str, Any]) -> str:
    vendor = str(metadata.get("vendor", "")).strip()
    model = str(metadata.get("model", "")).strip()
    variant = str(metadata.get("variant", "")).strip()
    chirp_version = str(metadata.get("chirp_version", "")).strip()
    identity = " ".join(value for value in (vendor, model) if value)
    details = []
    if variant:
        details.append(f"variant {variant}")
    if chirp_version:
        details.append(f"created by CHIRP {chirp_version}")
    suffix = f" ({'; '.join(details)})" if details else ""
    return f": {identity}{suffix}" if identity else suffix


def radio_model_from_image(radio: Any) -> RadioModel:
    """Build compiler capabilities from a loaded, image-aware CHIRP driver."""

    features = radio.get_features()
    lower, upper = features.memory_bounds
    receive_ranges = tuple(
        FrequencyRange(int(start), int(end) - 1)
        for start, end in features.valid_bands
        if int(start) > 0 and int(end) > int(start)
    )
    if not receive_ranges:
        raise ValueError(
            f"CHIRP driver {radio.VENDOR} {radio.MODEL} reports no frequency bands"
        )

    bank_count = 0
    if features.has_bank:
        bank_count = len(radio.get_bank_model().get_mappings())

    driver_class = getattr(radio, "_orig_rclass", radio.__class__)
    driver_reference = directory.radio_class_id(driver_class)
    supported_modes = frozenset(
        Mode(value) for value in features.valid_modes if value in Mode._value2member_map_
    )
    tone_mapping = {
        "": ToneMode.NONE,
        "Tone": ToneMode.TONE,
        "TSQL": ToneMode.TSQL,
        "DTCS": ToneMode.DTCS,
        "Cross": ToneMode.CROSS,
        "TSQL-R": ToneMode.TSQL_REVERSE,
    }
    supported_tones = frozenset(
        tone_mapping[value]
        for value in features.valid_tmodes
        if value in tone_mapping
    )
    return RadioModel(
        id=f"chirp:{driver_reference}",
        manufacturer=str(radio.VENDOR),
        model=str(radio.MODEL),
        chirp_driver_reference=driver_reference,
        capabilities=RadioCapabilities(
            memory_capacity=int(upper) - int(lower) + 1,
            memory_start=int(lower),
            receive_ranges=receive_ranges,
            # RadioFeatures exposes one programmable-band list. Driver validation
            # remains the final authority for a concrete image and memory.
            transmit_ranges=receive_ranges,
            supported_modes=supported_modes,
            supported_tone_modes=supported_tones,
            max_label_length=max(1, int(features.valid_name_length or 1)),
            supported_label_characters=features.valid_characters or " ",
            supports_banks=bool(features.has_bank and bank_count),
            bank_count=bank_count,
            supports_transmit_disable="off" in features.valid_duplexes,
            supports_split=(
                "split" in features.valid_duplexes or bool(features.can_odd_split)
            ),
            valid_cross_modes=tuple(features.valid_cross_modes),
            valid_tuning_steps_hz=tuple(
                dict.fromkeys(
                    int(round(float(step) * 1_000))
                    for step in features.valid_tuning_steps
                )
            ),
            valid_ctcss_tones_hz=tuple(
                dict.fromkeys(float(tone) for tone in features.valid_tones)
            ),
            valid_dtcs_codes=tuple(
                dict.fromkeys(int(code) for code in features.valid_dtcs_codes)
            ),
            supports_separate_rx_dtcs=bool(features.has_rx_dtcs),
            supports_dtcs_polarity=bool(features.has_dtcs_polarity),
            power_levels=power_levels_from_features(features),
            source_notes=(
                f"CHIRP {driver_reference} loaded from radio image at {CHIRP_COMMIT}",
            ),
        ),
    )


def image_memory_validator(radio: Any):
    """Return validation bound to the exact driver and loaded image."""

    features = radio.get_features()

    def validate(memory: CompiledMemory) -> tuple[MemoryValidationIssue, ...]:
        existing = radio.get_memory(memory.memory_number)
        chirp_memory = _compiled_to_chirp(memory, features, existing)
        issues = [
            MemoryValidationIssue(
                severity=(
                    Severity.ERROR
                    if isinstance(message, chirp_common.ValidationError)
                    else Severity.WARNING
                ),
                message=str(message),
                details=(("source", "CHIRP image driver"),),
            )
            for message in radio.validate_memory(chirp_memory)
        ]
        try:
            radio.check_set_memory_immutable_policy(existing, chirp_memory)
        except chirp_common.ImmutableValueError as error:
            issues.append(
                MemoryValidationIssue(
                    severity=Severity.ERROR,
                    message=str(error),
                    details=(("source", "CHIRP immutable memory policy"),),
                )
            )
        return tuple(issues)

    return validate


def write_compiled_image(
    plan: CompiledRadioPlan,
    source_path: Path,
    output_path: Path,
    *,
    bank_names: Mapping[str, str],
) -> None:
    """Apply a compiled plan through CHIRP and ask CHIRP to save a new image."""

    if output_path.suffix.casefold() != ".img":
        raise ValueError("compiled radio output must use the .img extension")
    if source_path.resolve() == output_path.resolve():
        raise ValueError("compiled image must not overwrite its source image")

    radio = load_chirp_image(source_path)
    features = radio.get_features()
    bank_model = radio.get_bank_model() if features.has_bank else None
    bank_mappings = bank_model.get_mappings() if bank_model is not None else []
    assignment_order = tuple(bank.frequency_set_id for bank in plan.banks)
    if not assignment_order:
        assignment_order = tuple(
            dict.fromkeys(
                assignment
                for memory in plan.memories
                for assignment in memory.bank_assignments
            )
        )
    if len(assignment_order) > len(bank_mappings):
        raise ValueError("compiled plan contains more sets than the radio has banks")
    mapping_by_assignment = {
        assignment: bank_mappings[index]
        for index, assignment in enumerate(assignment_order)
    }

    compiled_numbers = {memory.memory_number for memory in plan.memories}
    lower, upper = features.memory_bounds
    for number in range(int(lower), int(upper) + 1):
        if number in compiled_numbers:
            continue
        existing = radio.get_memory(number)
        if existing.empty:
            continue
        if bank_model is not None:
            for mapping in tuple(bank_model.get_memory_mappings(existing)):
                bank_model.remove_memory_from_mapping(existing, mapping)
        radio.erase_memory(number)

    for assignment, mapping in mapping_by_assignment.items():
        if features.has_bank_names and hasattr(mapping, "set_name"):
            mapping.set_name(bank_names.get(assignment, assignment))

    for compiled in plan.memories:
        existing = radio.get_memory(compiled.memory_number)
        chirp_memory = _compiled_to_chirp(compiled, features, existing)
        issues = radio.validate_memory(chirp_memory)
        errors_found = [
            str(issue)
            for issue in issues
            if isinstance(issue, chirp_common.ValidationError)
        ]
        if errors_found:
            raise ValueError(
                f"CHIRP rejected memory {compiled.memory_number}: "
                + "; ".join(errors_found)
            )
        try:
            radio.check_set_memory_immutable_policy(existing, chirp_memory)
        except chirp_common.ImmutableValueError as error:
            raise ValueError(
                f"CHIRP rejected immutable memory {compiled.memory_number}: {error}"
            ) from error
        radio.set_memory(chirp_memory)

        written = radio.get_memory(compiled.memory_number)
        if (
            compiled.power_label is not None
            and str(getattr(written, "power", "")) != compiled.power_label
        ):
            raise ValueError(
                f"CHIRP did not preserve power {compiled.power_label} on memory "
                f"{compiled.memory_number}"
            )
        if bank_model is None:
            continue
        for mapping in tuple(bank_model.get_memory_mappings(written)):
            bank_model.remove_memory_from_mapping(written, mapping)
        for assignment in compiled.bank_assignments:
            bank_model.add_memory_to_mapping(
                written,
                mapping_by_assignment[assignment],
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    radio.save(str(output_path))


def _sets_from_image(
    radio: Any,
    radio_id: str,
    definition_ids_by_memory: Mapping[int, str],
) -> tuple[FrequencySet, ...]:
    features = radio.get_features()
    included: set[int] = set()
    sets: list[FrequencySet] = []
    if features.has_bank:
        bank_model = radio.get_bank_model()
        for index, bank in enumerate(bank_model.get_mappings()):
            numbers = sorted(
                int(memory.number)
                for memory in bank_model.get_mapping_memories(bank)
                if int(memory.number) in definition_ids_by_memory
            )
            if not numbers:
                continue
            included.update(numbers)
            bank_name = str(bank.get_name()).strip() or f"Bank {index + 1}"
            sets.append(
                _frequency_set(
                    set_id=f"user-radio-{radio_id}-bank-{index + 1}",
                    name=bank_name,
                    description=f"Imported from {radio.VENDOR} {radio.MODEL} bank {index + 1}.",
                    memory_numbers=numbers,
                    definition_ids_by_memory=definition_ids_by_memory,
                )
            )

    unbanked = [
        number for number in definition_ids_by_memory if number not in included
    ]
    if unbanked or not sets:
        numbers = unbanked or list(definition_ids_by_memory)
        if numbers:
            sets.append(
                _frequency_set(
                    set_id=f"user-radio-{radio_id}-unbanked",
                    name=(
                        "Unbanked memories"
                        if features.has_bank
                        else f"{radio.VENDOR} {radio.MODEL} memories"
                    ),
                    description="Imported memories without a radio-bank assignment.",
                    memory_numbers=numbers,
                    definition_ids_by_memory=definition_ids_by_memory,
                )
            )
    return tuple(sets)


def _frequency_set(
    *,
    set_id: str,
    name: str,
    description: str,
    memory_numbers: list[int],
    definition_ids_by_memory: Mapping[int, str],
) -> FrequencySet:
    return FrequencySet(
        id=set_id,
        name=name,
        origin=CatalogOrigin.USER,
        description=description,
        members=tuple(
            FrequencySetMember(definition_ids_by_memory[number], position)
            for position, number in enumerate(memory_numbers)
        ),
    )


def _compiled_to_chirp(
    memory: CompiledMemory,
    features: Any,
    existing: Any | None,
) -> Any:
    result = existing.dupe() if existing is not None else chirp_common.Memory()
    result.empty = False
    result.number = memory.memory_number
    result.name = memory.target_name
    result.freq = memory.receive_frequency_hz
    result.mode = memory.mode.value
    result.skip = memory.scan_skip if memory.scan_skip in features.valid_skips else ""

    if memory.transmit_behavior is TransmitBehavior.SAME:
        result.duplex = ""
        result.offset = 0
    elif memory.transmit_behavior is TransmitBehavior.DISABLED:
        result.duplex = "off"
        result.offset = 0
    elif memory.transmit_behavior is TransmitBehavior.SPLIT:
        result.duplex = "split"
        assert memory.transmit_frequency_hz is not None
        result.offset = memory.transmit_frequency_hz
    else:
        assert memory.offset_hz is not None
        result.duplex = "+" if memory.offset_hz > 0 else "-"
        result.offset = abs(memory.offset_hz)

    apply_signaling_to_chirp_memory(
        result,
        memory.transmit_access,
        memory.receive_squelch,
    )
    allowed_steps = list(features.valid_tuning_steps)
    desired_step = (
        memory.tuning_step_hz / 1_000
        if memory.tuning_step_hz is not None
        else None
    )
    result.tuning_step = (
        desired_step
        if desired_step in allowed_steps
        else chirp_common.required_step(result.freq, allowed=allowed_steps)
    )
    result.power = _power_level(memory, features, getattr(result, "power", None))
    return result


def _power_level(memory: CompiledMemory, features: Any, fallback: Any) -> Any:
    levels = list(features.valid_power_levels)
    if not levels or memory.power_dbm is None:
        return fallback
    if memory.power_label is not None:
        for level in levels:
            if str(level) == memory.power_label:
                return level
    return min(levels, key=lambda level: abs(float(level) - memory.power_dbm))


def _setting_count(radio: Any) -> int:
    if not radio.get_features().has_settings:
        return 0
    settings = radio.get_settings()

    def count(group: Any) -> int:
        total = 0
        for item in group:
            if item.__class__.__name__ == "RadioSetting":
                total += 1
            else:
                total += count(item)
        return total

    return count(settings)
