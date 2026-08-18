"""Immutable domain objects shared by the compiler and its adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum, StrEnum


class TransmitBehavior(StrEnum):
    """How a channel derives (or disables) its transmit frequency."""

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
    LABEL_TRUNCATED = "LABEL_TRUNCATED"
    LABEL_CHARACTERS_NORMALIZED = "LABEL_CHARACTERS_NORMALIZED"
    RX_FREQUENCY_UNSUPPORTED = "RX_FREQUENCY_UNSUPPORTED"
    TX_FREQUENCY_UNSUPPORTED = "TX_FREQUENCY_UNSUPPORTED"
    MODE_UNSUPPORTED = "MODE_UNSUPPORTED"
    TONE_UNSUPPORTED = "TONE_UNSUPPORTED"
    GROUPING_DEGRADED = "GROUPING_DEGRADED"
    CHANNEL_OMITTED_CAPACITY = "CHANNEL_OMITTED_CAPACITY"
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
class Channel:
    """Canonical channel data with no target-specific memory fields."""

    id: str
    name: str
    receive_frequency_hz: int
    transmit_behavior: TransmitBehavior
    transmit_frequency_hz: int | None = None
    offset_hz: int | None = None
    mode: Mode = Mode.FM
    tone: ToneSpec = field(default_factory=ToneSpec)
    tags: frozenset[str] = field(default_factory=frozenset)
    priority: Priority = Priority.NORMAL
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.id.strip():
            raise ValueError("channel ID must not be blank")
        if not self.name.strip():
            raise ValueError("channel name must not be blank")
        if self.receive_frequency_hz <= 0:
            raise ValueError("receive frequency must be positive")

        if self.transmit_behavior is TransmitBehavior.OFFSET:
            if self.offset_hz in (None, 0):
                raise ValueError("offset transmit behavior requires a non-zero offset")
            if self.transmit_frequency_hz is not None:
                raise ValueError("offset channels must not set an explicit TX frequency")
        elif self.transmit_behavior is TransmitBehavior.SPLIT:
            if self.transmit_frequency_hz is None or self.transmit_frequency_hz <= 0:
                raise ValueError("split transmit behavior requires a TX frequency")
            if self.offset_hz is not None:
                raise ValueError("split channels must not set an offset")
        elif self.transmit_frequency_hz is not None or self.offset_hz is not None:
            raise ValueError("same/disabled channels must not set TX frequency or offset")

        object.__setattr__(self, "tags", frozenset(self.tags))

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
class LogicalGroup:
    id: str
    name: str
    include_tags: frozenset[str]

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("logical group ID and name are required")
        if not self.include_tags:
            raise ValueError("logical group requires at least one tag")
        object.__setattr__(self, "include_tags", frozenset(self.include_tags))


@dataclass(frozen=True, slots=True)
class Profile:
    id: str
    name: str
    include_tags: frozenset[str] = field(default_factory=frozenset)
    exclude_tags: frozenset[str] = field(default_factory=frozenset)
    include_channel_ids: frozenset[str] = field(default_factory=frozenset)
    exclude_channel_ids: frozenset[str] = field(default_factory=frozenset)
    minimum_priority: Priority = Priority.LOW
    groups: tuple[LogicalGroup, ...] = ()

    def __post_init__(self) -> None:
        if not self.id or not self.name:
            raise ValueError("profile ID and name are required")
        object.__setattr__(self, "include_tags", frozenset(self.include_tags))
        object.__setattr__(self, "exclude_tags", frozenset(self.exclude_tags))
        object.__setattr__(self, "include_channel_ids", frozenset(self.include_channel_ids))
        object.__setattr__(self, "exclude_channel_ids", frozenset(self.exclude_channel_ids))
        object.__setattr__(self, "groups", tuple(self.groups))


@dataclass(frozen=True, slots=True)
class RadioCapabilities:
    id: str
    manufacturer: str
    model: str
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
class Diagnostic:
    code: DiagnosticCode
    severity: Severity
    channel_id: str | None
    message: str
    details: tuple[tuple[str, str], ...] = ()

    @classmethod
    def with_details(
        cls,
        *,
        code: DiagnosticCode,
        severity: Severity,
        channel_id: str | None,
        message: str,
        details: dict[str, object] | None = None,
    ) -> Diagnostic:
        normalized = tuple(
            sorted((key, str(value)) for key, value in (details or {}).items())
        )
        return cls(code, severity, channel_id, message, normalized)


@dataclass(frozen=True, slots=True)
class CompiledMemory:
    source_channel_id: str
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
class OmittedChannel:
    channel_id: str
    reason: DiagnosticCode


@dataclass(frozen=True, slots=True)
class CapacitySummary:
    capacity: int
    compatible_candidates: int
    used: int
    omitted_for_capacity: int


@dataclass(frozen=True, slots=True)
class CompiledRadioPlan:
    target: RadioCapabilities
    profile: Profile
    memories: tuple[CompiledMemory, ...]
    omitted_channels: tuple[OmittedChannel, ...]
    diagnostics: tuple[Diagnostic, ...]
    capacity_summary: CapacitySummary
    compiler_version: str = "0.1.0"

    @property
    def warning_count(self) -> int:
        return sum(item.severity is Severity.WARNING for item in self.diagnostics)

    @property
    def error_count(self) -> int:
        return sum(item.severity is Severity.ERROR for item in self.diagnostics)
