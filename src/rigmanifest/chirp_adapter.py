"""Narrow integration boundary around CHIRP's normalized driver APIs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any, TypeVar

from chirp import chirp_common, directory, errors

from rigmanifest.models import (
    CompiledMemory,
    FactoryFrequencySet,
    FrequencyRange,
    MemoryValidationIssue,
    Mode,
    RadioCapabilities,
    RadioModel,
    Severity,
    SignalingKind,
    SignalingSpec,
    ToneMode,
    TransmitBehavior,
)


CHIRP_COMMIT = "fa27a491d275f88b452d0488a51b4c85d4f7062a"

_SUPPORTED_DRIVER_MODULES = {
    "Yaesu_VX-6": "chirp.drivers.vx6",
    "Quansheng_UV-K5": "chirp.drivers.uvk5",
    "Retevis_RT95": "chirp.drivers.anytone778uv",
}

_Value = TypeVar("_Value")


@dataclass(frozen=True, slots=True)
class ChirpCapabilityOverlay:
    """Facts CHIRP's RadioFeatures does not express for a radio model."""

    transmit_ranges: tuple[FrequencyRange, ...]
    memory_capacity: int | None = None
    bank_count: int | None = None
    source_notes: tuple[str, ...] = ()


def radio_model_from_chirp(
    *,
    model_id: str,
    driver_reference: str,
    overlay: ChirpCapabilityOverlay,
    display_model: str | None = None,
    factory_frequency_sets: tuple[FactoryFrequencySet, ...] = (),
) -> RadioModel:
    """Build a target from a pinned CHIRP driver and a small explicit overlay."""

    driver_class = _driver_class(driver_reference)
    features = driver_class(None).get_features()
    return RadioModel(
        id=model_id,
        manufacturer=str(driver_class.VENDOR),
        model=display_model or str(driver_class.MODEL),
        chirp_driver_reference=driver_reference,
        capabilities=_capabilities_from_features(
            driver_reference,
            features,
            overlay,
        ),
        factory_frequency_sets=factory_frequency_sets,
    )


def chirp_memory_validator(
    driver_reference: str,
) -> Callable[[CompiledMemory], tuple[MemoryValidationIssue, ...]]:
    """Return a reusable validator backed by one CHIRP driver instance."""

    driver = _driver_class(driver_reference)(None)
    features = driver.get_features()

    def validate(memory: CompiledMemory) -> tuple[MemoryValidationIssue, ...]:
        try:
            chirp_memory = _to_chirp_memory(memory, features)
        except (ValueError, errors.InvalidDataError) as error:
            return (_issue(Severity.ERROR, str(error)),)

        return tuple(
            _issue(
                Severity.ERROR
                if isinstance(message, chirp_common.ValidationError)
                else Severity.WARNING,
                str(message),
            )
            for message in driver.validate_memory(chirp_memory)
        )

    return validate


def _capabilities_from_features(
    driver_reference: str,
    features: Any,
    overlay: ChirpCapabilityOverlay,
) -> RadioCapabilities:
    lower_memory, upper_memory = features.memory_bounds
    address_count = upper_memory - lower_memory + 1
    memory_capacity = overlay.memory_capacity or address_count
    if memory_capacity > address_count:
        raise ValueError("memory capacity override exceeds CHIRP memory bounds")

    # CHIRP validates these ranges as lower-inclusive and upper-exclusive.
    receive_ranges = tuple(
        FrequencyRange(int(lower), int(upper) - 1)
        for lower, upper in features.valid_bands
    )
    if not receive_ranges:
        raise ValueError(f"CHIRP driver {driver_reference} exposes no valid bands")

    supported_modes = frozenset(
        Mode(value)
        for value in features.valid_modes
        if value in Mode._value2member_map_
    )
    tone_mode_mapping = {
        "": ToneMode.NONE,
        "Tone": ToneMode.TONE,
        "TSQL": ToneMode.TSQL,
        "DTCS": ToneMode.DTCS,
        "Cross": ToneMode.CROSS,
        "TSQL-R": ToneMode.TSQL_REVERSE,
    }
    supported_tone_modes = frozenset(
        tone_mode_mapping[value]
        for value in features.valid_tmodes
        if value in tone_mode_mapping
    )

    supports_banks = bool(features.has_bank)
    if supports_banks and overlay.bank_count is None:
        raise ValueError(
            f"bank-capable CHIRP driver {driver_reference} requires a bank-count overlay"
        )

    return RadioCapabilities(
        memory_capacity=memory_capacity,
        memory_start=int(lower_memory),
        receive_ranges=receive_ranges,
        transmit_ranges=overlay.transmit_ranges,
        supported_modes=supported_modes,
        supported_tone_modes=supported_tone_modes,
        max_label_length=max(1, int(features.valid_name_length)),
        supported_label_characters=features.valid_characters or " ",
        supports_banks=supports_banks,
        bank_count=overlay.bank_count or 0,
        supports_transmit_disable="off" in features.valid_duplexes,
        supports_split=(
            "split" in features.valid_duplexes or bool(features.can_odd_split)
        ),
        valid_cross_modes=tuple(features.valid_cross_modes),
        valid_tuning_steps_hz=_unique(
            int(round(float(step) * 1_000))
            for step in features.valid_tuning_steps
        ),
        valid_ctcss_tones_hz=_unique(
            float(tone) for tone in features.valid_tones
        ),
        valid_dtcs_codes=_unique(int(code) for code in features.valid_dtcs_codes),
        supports_separate_rx_dtcs=bool(features.has_rx_dtcs),
        supports_dtcs_polarity=bool(features.has_dtcs_polarity),
        source_notes=(
            f"CHIRP {driver_reference} RadioFeatures at {CHIRP_COMMIT}",
            *overlay.source_notes,
        ),
    )


def _to_chirp_memory(memory: CompiledMemory, features: Any) -> Any:
    result = chirp_common.Memory()
    result.number = memory.memory_number
    result.name = memory.target_name
    result.freq = memory.receive_frequency_hz
    result.mode = memory.mode.value

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

    result.tuning_step = chirp_common.required_step(
        result.freq,
        allowed=list(features.valid_tuning_steps),
    )
    return result


def apply_signaling_to_chirp_memory(
    memory: Any,
    transmit_access: SignalingSpec,
    receive_squelch: SignalingSpec,
) -> None:
    """Encode independent signaling intent into CHIRP's tone fields."""

    chirp_common.split_tone_decode(
        memory,
        _chirp_signal_tuple(transmit_access),
        _chirp_signal_tuple(receive_squelch),
    )

    # Keep both conventional fields explicit. Some drivers use rtone for TSQL
    # even though CHIRP's normalized split helper treats ctone as canonical.
    if transmit_access.kind is SignalingKind.CTCSS:
        assert transmit_access.ctcss_hz is not None
        memory.rtone = transmit_access.ctcss_hz
    if receive_squelch.kind is SignalingKind.CTCSS:
        assert receive_squelch.ctcss_hz is not None
        memory.ctone = receive_squelch.ctcss_hz
    if transmit_access.kind is SignalingKind.DCS:
        assert transmit_access.dcs_code is not None
        memory.dtcs = transmit_access.dcs_code
        if receive_squelch.kind is not SignalingKind.DCS:
            memory.rx_dtcs = transmit_access.dcs_code
    if receive_squelch.kind is SignalingKind.DCS:
        assert receive_squelch.dcs_code is not None
        memory.rx_dtcs = receive_squelch.dcs_code
        if transmit_access.kind is not SignalingKind.DCS:
            memory.dtcs = receive_squelch.dcs_code


def signaling_from_chirp_memory(
    memory: Any,
) -> tuple[SignalingSpec, SignalingSpec]:
    """Decode CHIRP tone fields into independent RigManifest intent."""

    transmit, receive = chirp_common.split_tone_encode(memory)
    return _signaling_from_chirp_tuple(transmit), _signaling_from_chirp_tuple(receive)


def _chirp_signal_tuple(spec: SignalingSpec) -> tuple[str, float | int | None, str | None]:
    if spec.kind is SignalingKind.NONE:
        return "", None, None
    if spec.kind is SignalingKind.CTCSS:
        return "Tone", spec.ctcss_hz, None
    return "DTCS", spec.dcs_code, spec.dcs_polarity


def _signaling_from_chirp_tuple(
    value: tuple[str, float | int | None, str | None],
) -> SignalingSpec:
    mode, signal_value, polarity = value
    if mode == "Tone":
        assert signal_value is not None
        return SignalingSpec(
            kind=SignalingKind.CTCSS,
            ctcss_hz=float(signal_value),
        )
    if mode == "DTCS":
        assert signal_value is not None
        return SignalingSpec(
            kind=SignalingKind.DCS,
            dcs_code=int(signal_value),
            dcs_polarity=polarity or "N",
        )
    return SignalingSpec()


def _issue(severity: Severity, message: str) -> MemoryValidationIssue:
    return MemoryValidationIssue(
        severity=severity,
        message=message,
        details=(("source", "CHIRP"),),
    )


@lru_cache(maxsize=1)
def _import_chirp_drivers() -> None:
    directory.import_drivers()


@lru_cache(maxsize=None)
def _driver_class(driver_reference: str) -> type[Any]:
    module_name = _SUPPORTED_DRIVER_MODULES.get(driver_reference)
    if module_name is None:
        _import_chirp_drivers()
    else:
        # Frozen Windows builds cannot discover CHIRP's driver modules by
        # globbing. Every model RigManifest exposes therefore names the
        # concrete module that registers it with CHIRP's directory.
        import_module(module_name)
    try:
        return directory.get_radio(driver_reference)
    except Exception as error:
        raise ValueError(f"unknown CHIRP driver: {driver_reference}") from error


def _unique(values: Iterable[_Value]) -> tuple[_Value, ...]:
    return tuple(dict.fromkeys(values))
