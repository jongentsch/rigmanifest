"""Immutable domain objects shared by the compiler and its adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class CatalogOrigin(StrEnum):
    """Who controls a catalog record."""

    PRESET = "preset"
    USER = "user"


class CapabilityStatus(StrEnum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNKNOWN = "unknown"


class TransmitBehavior(StrEnum):
    """How a frequency definition derives (or disables) transmission."""

    SAME = "same"
    OFFSET = "offset"
    SPLIT = "split"
    DISABLED = "disabled"


class Mode(StrEnum):
    FM = "FM"
    NFM = "NFM"
    AM = "AM"
    WFM = "WFM"


class ToneMode(StrEnum):
    NONE = "none"
    TONE = "tone"
    TSQL = "tsql"
    DTCS = "dtcs"


class Priority(IntEnum):
    LOW = 10
    NORMAL = 20
    HIGH = 30
    MANDATORY = 40


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class DiagnosticCode(StrEnum):
    FACTORY_SET_AVAILABLE = "FACTORY_SET_AVAILABLE"
    LABEL_TRUNCATED = "LABEL_TRUNCATED"
    LABEL_CHARACTERS_NORMALIZED = "LABEL_CHARACTERS_NORMALIZED"
    RX_FREQUENCY_UNSUPPORTED = "RX_FREQUENCY_UNSUPPORTED"
    TX_FREQUENCY_UNSUPPORTED = "TX_FREQUENCY_UNSUPPORTED"
    MODE_UNSUPPORTED = "MODE_UNSUPPORTED"
    TONE_UNSUPPORTED = "TONE_UNSUPPORTED"
    GROUPING_DEGRADED = "GROUPING_DEGRADED"
    FREQUENCY_OMITTED_CAPACITY = "FREQUENCY_OMITTED_CAPACITY"
    TX_DISABLE_NOT_REPRESENTABLE = "TX_DISABLE_NOT_REPRESENTABLE"
    CAPABILITY_DATA_INCOMPLETE = "CAPABILITY_DATA_INCOMPLETE"


@dataclass(frozen=True, slots=True)
class FrequencyRange:
    """An inclusive frequency range expressed in integer Hz."""

    lower_hz: int
    upper_hz: int

    def __post_init__(self) -> None:
        if self.lower_hz <= 0:
            raise ValueError("frequency range lower bound must be positive")
        if self.upper_hz < self.lower_hz:
            raise ValueError("frequency range upper bound must not be lower")

    def contains(self, frequency_hz: int) -> bool:
        return self.lower_hz <= frequency_hz <= self.upper_hz


@dataclass(frozen=True, slots=True)
class ToneSpec:
    mode: ToneMode = ToneMode.NONE
    encode_hz: float | None = None
    decode_hz: float | None = None
    dtcs_code: int | None = None
    dtcs_polarity: str = "NN"

    def __post_init__(self) -> None:
        if self.mode in (ToneMode.TONE, ToneMode.TSQL) and self.encode_hz is None:
            raise ValueError(f"{self.mode.value} requires an encode tone")
        if self.mode is ToneMode.DTCS and self.dtcs_code is None:
            raise ValueError("DTCS requires a code")
        if self.dtcs_polarity not in {"NN", "NR", "RN", "RR"}:
            raise ValueError("DTCS polarity must be NN, NR, RN, or RR")


@dataclass(frozen=True, slots=True)
class FrequencyDefinition:
    """Canonical RF intent, independent of sets and radio memory locations."""

    id: str
    name: str
    receive_frequency_hz: int
    transmit_behavior: TransmitBehavior
    origin: CatalogOrigin = CatalogOrigin.USER
    transmit_frequency_hz: int | None = None
    offset_hz: int | None = None
    mode: Mode = Mode.FM
    tone: ToneSpec = field(default_factory=ToneSpec)
    tags: frozenset[str] = field(default_factory=frozenset)
    priority: Priority = Priority.NORMAL
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("frequency definition ID must not be blank")
        if not self.name.strip():
            raise ValueError("frequency definition name must not be blank")
        if self.receive_frequency_hz <= 0:
            raise ValueError("receive frequency must be positive")

        if self.transmit_behavior is TransmitBehavior.OFFSET:
            if self.offset_hz in (None, 0):
                raise ValueError("offset transmit behavior requires a non-zero offset")
            if self.transmit_frequency_hz is not None:
                raise ValueError("offset definition must not set an explicit TX frequency")
        elif self.transmit_behavior is TransmitBehavior.SPLIT:
            if self.transmit_frequency_hz is None or self.transmit_frequency_hz <= 0:
                raise ValueError("split transmit behavior requires a TX frequency")
            if self.offset_hz is not None:
                raise ValueError("split definition must not set an offset")
        elif self.transmit_frequency_hz is not None or self.offset_hz is not None:
            raise ValueError("same/disabled definitions must not set TX frequency or offset")

        object.__setattr__(self, "tags", frozenset(self.tags))

    @property
    def read_only(self) -> bool:
        return self.origin is CatalogOrigin.PRESET

    @property
    def resolved_transmit_frequency_hz(self) -> int | None:
        if self.transmit_behavior is TransmitBehavior.DISABLED:
            return None
        if self.transmit_behavior is TransmitBehavior.SAME:
            return self.receive_frequency_hz
        if self.transmit_behavior is TransmitBehavior.OFFSET:
            assert self.offset_hz is not None
            return self.receive_frequency_hz + self.offset_hz
        return self.transmit_frequency_hz


@dataclass(frozen=True, slots=True)
class FrequencySetMember:
    """A reference from a set to a shared frequency definition."""

    frequency_definition_id: str
    position: int
    channel_designator: str | None = None

    def __post_init__(self) -> None:
        if not self.frequency_definition_id:
            raise ValueError("frequency set membership requires a definition ID")
        if self.position < 0:
            raise ValueError("frequency set membership position must not be negative")


@dataclass(frozen=True, slots=True)
class FrequencySet:
    id: str
    name: str
    origin: CatalogOrigin
    members: tuple[FrequencySetMember, ...]
    description: str = ""

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("frequency set ID and name are required")
        object.__setattr__(self, "members", tuple(self.members))

        definition_ids = [item.frequency_definition_id for item in self.members]
        if len(definition_ids) != len(set(definition_ids)):
            raise ValueError(f"frequency set {self.id} contains a duplicate definition")
        positions = [item.position for item in self.members]
        if len(positions) != len(set(positions)):
            raise ValueError(f"frequency set {self.id} contains a duplicate position")

    @property
    def read_only(self) -> bool:
        return self.origin is CatalogOrigin.PRESET

    @property
    def ordered_members(self) -> tuple[FrequencySetMember, ...]:
        return tuple(
            sorted(
                self.members,
                key=lambda item: (item.position, item.frequency_definition_id),
            )
        )


@dataclass(frozen=True, slots=True)
class FrequencyCatalog:
    """Shared tables for preset and user-owned definitions and sets."""

    definitions: tuple[FrequencyDefinition, ...]
    sets: tuple[FrequencySet, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "definitions", tuple(self.definitions))
        object.__setattr__(self, "sets", tuple(self.sets))

        definition_ids = [item.id for item in self.definitions]
        if len(definition_ids) != len(set(definition_ids)):
            raise ValueError("duplicate frequency definition ID")
        set_ids = [item.id for item in self.sets]
        if len(set_ids) != len(set(set_ids)):
            raise ValueError("duplicate frequency set ID")

        definitions = {item.id: item for item in self.definitions}
        for frequency_set in self.sets:
            for member in frequency_set.members:
                definition = definitions.get(member.frequency_definition_id)
                if definition is None:
                    raise ValueError(
                        f"frequency set {frequency_set.id} references unknown definition "
                        f"{member.frequency_definition_id}"
                    )
                if frequency_set.read_only and not definition.read_only:
                    raise ValueError(
                        f"preset set {frequency_set.id} cannot depend on user definition "
                        f"{definition.id}"
                    )

    def definition(self, definition_id: str) -> FrequencyDefinition:
        try:
            return next(item for item in self.definitions if item.id == definition_id)
        except StopIteration as error:
            raise KeyError(definition_id) from error

    def frequency_set(self, set_id: str) -> FrequencySet:
        try:
            return next(item for item in self.sets if item.id == set_id)
        except StopIteration as error:
            raise KeyError(set_id) from error


@dataclass(frozen=True, slots=True)
class Profile:
    """A saved selection of frequency sets."""

    id: str
    name: str
    frequency_set_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("profile ID and name are required")
        if not self.frequency_set_ids:
            raise ValueError("profile requires at least one frequency set")
        object.__setattr__(self, "frequency_set_ids", tuple(self.frequency_set_ids))
        if len(self.frequency_set_ids) != len(set(self.frequency_set_ids)):
            raise ValueError("profile contains a duplicate frequency set")


@dataclass(frozen=True, slots=True)
class RadioCapabilities:
    memory_capacity: int
    receive_ranges: tuple[FrequencyRange, ...]
    transmit_ranges: tuple[FrequencyRange, ...]
    supported_modes: frozenset[Mode]
    supported_tone_modes: frozenset[ToneMode]
    max_label_length: int
    supported_label_characters: str
    supports_banks: bool
    bank_count: int = 0
    supports_transmit_disable: bool = False
    supports_split: bool = False
    memory_start: int = 1
    source_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.memory_capacity <= 0:
            raise ValueError("memory capacity must be positive")
        if self.memory_start < 0:
            raise ValueError("memory start must not be negative")
        if not self.receive_ranges:
            raise ValueError("at least one receive range is required")
        if self.max_label_length <= 0:
            raise ValueError("maximum label length must be positive")
        if self.supports_banks and self.bank_count <= 0:
            raise ValueError("bank-capable targets require a positive bank count")
        if not self.supports_banks and self.bank_count != 0:
            raise ValueError("targets without banks must have a zero bank count")
        object.__setattr__(self, "receive_ranges", tuple(self.receive_ranges))
        object.__setattr__(self, "transmit_ranges", tuple(self.transmit_ranges))
        object.__setattr__(self, "supported_modes", frozenset(self.supported_modes))
        object.__setattr__(self, "supported_tone_modes", frozenset(self.supported_tone_modes))
        object.__setattr__(self, "source_notes", tuple(self.source_notes))

    def supports_receive_frequency(self, frequency_hz: int) -> bool:
        return any(item.contains(frequency_hz) for item in self.receive_ranges)

    def supports_transmit_frequency(self, frequency_hz: int) -> bool:
        return any(item.contains(frequency_hz) for item in self.transmit_ranges)


@dataclass(frozen=True, slots=True)
class FactoryFrequencySet:
    """A radio-model relationship to a preset set supplied by the manufacturer."""

    frequency_set_id: str
    interface_label: str
    frequency_editing: CapabilityStatus = CapabilityStatus.UNKNOWN
    chirp_editing: CapabilityStatus = CapabilityStatus.UNKNOWN
    source_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.frequency_set_id or not self.interface_label:
            raise ValueError("factory set reference and interface label are required")
        object.__setattr__(self, "source_notes", tuple(self.source_notes))


@dataclass(frozen=True, slots=True)
class RadioModel:
    id: str
    manufacturer: str
    model: str
    capabilities: RadioCapabilities
    factory_frequency_sets: tuple[FactoryFrequencySet, ...] = ()
    chirp_driver_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.manufacturer or not self.model:
            raise ValueError("radio model identity is required")
        object.__setattr__(self, "factory_frequency_sets", tuple(self.factory_frequency_sets))
        set_ids = [item.frequency_set_id for item in self.factory_frequency_sets]
        if len(set_ids) != len(set(set_ids)):
            raise ValueError("radio model contains a duplicate factory frequency set")


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: DiagnosticCode
    severity: Severity
    frequency_definition_id: str | None
    frequency_set_id: str | None
    message: str
    details: tuple[tuple[str, str], ...] = ()

    @classmethod
    def with_details(
        cls,
        *,
        code: DiagnosticCode,
        severity: Severity,
        message: str,
        frequency_definition_id: str | None = None,
        frequency_set_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> Diagnostic:
        normalized = tuple(
            sorted((key, str(value)) for key, value in (details or {}).items())
        )
        return cls(
            code,
            severity,
            frequency_definition_id,
            frequency_set_id,
            message,
            normalized,
        )


@dataclass(frozen=True, slots=True)
class CompiledMemory:
    source_frequency_definition_id: str
    source_frequency_set_ids: tuple[str, ...]
    memory_number: int
    target_name: str
    receive_frequency_hz: int
    transmit_behavior: TransmitBehavior
    transmit_frequency_hz: int | None
    offset_hz: int | None
    mode: Mode
    tone: ToneSpec
    bank_assignments: tuple[str, ...] = ()
    applied_transformations: tuple[DiagnosticCode, ...] = ()


@dataclass(frozen=True, slots=True)
class OmittedFrequencyDefinition:
    frequency_definition_id: str
    reason: DiagnosticCode


@dataclass(frozen=True, slots=True)
class FactorySetCoverage:
    frequency_set_id: str
    frequency_set_name: str
    interface_label: str
    frequency_definition_ids: tuple[str, ...]
    frequency_editing: CapabilityStatus
    chirp_editing: CapabilityStatus

    @property
    def definition_count(self) -> int:
        return len(self.frequency_definition_ids)


@dataclass(frozen=True, slots=True)
class CompilationSettings:
    memory_start: int | None = None
    map_sets_to_banks: bool = True
    use_factory_sets: bool = True

    def __post_init__(self) -> None:
        if self.memory_start is not None and self.memory_start < 0:
            raise ValueError("memory start must not be negative")


@dataclass(frozen=True, slots=True)
class CapacitySummary:
    capacity: int
    compatible_candidates: int
    used: int
    omitted_for_capacity: int


@dataclass(frozen=True, slots=True)
class CompiledRadioPlan:
    target: RadioModel
    profile: Profile
    memories: tuple[CompiledMemory, ...]
    factory_sets: tuple[FactorySetCoverage, ...]
    omitted_frequency_definitions: tuple[OmittedFrequencyDefinition, ...]
    diagnostics: tuple[Diagnostic, ...]
    capacity_summary: CapacitySummary
    compiler_version: str = "0.3.0"

    @property
    def warning_count(self) -> int:
        return sum(item.severity is Severity.WARNING for item in self.diagnostics)

    @property
    def error_count(self) -> int:
        return sum(item.severity is Severity.ERROR for item in self.diagnostics)

    @property
    def factory_definition_count(self) -> int:
        return len(
            {
                definition_id
                for coverage in self.factory_sets
                for definition_id in coverage.frequency_definition_ids
            }
        )
