"""Built-in fact-sourced radio model definitions for the first vertical slice."""

from rigmanifest.models import (
    CapabilityStatus,
    FactoryFrequencySet,
    FrequencyRange,
    Mode,
    RadioCapabilities,
    RadioModel,
    ToneMode,
)


VX6R_USA = RadioModel(
    id="yaesu-vx6r",
    manufacturer="Yaesu",
    model="VX-6R (USA)",
    chirp_driver_reference="Yaesu_VX-6",
    capabilities=RadioCapabilities(
        # Yaesu advertises 900 user memories. CHIRP exposes locations 1-999;
        # usable capacity and address bounds remain intentionally distinct facts.
        memory_capacity=900,
        memory_start=1,
        receive_ranges=(FrequencyRange(500_000, 998_990_000),),
        transmit_ranges=(
            FrequencyRange(144_000_000, 148_000_000),
            FrequencyRange(222_000_000, 225_000_000),
            FrequencyRange(430_000_000, 450_000_000),
        ),
        supported_modes=frozenset({Mode.FM, Mode.NFM, Mode.AM, Mode.WFM}),
        supported_tone_modes=frozenset(
            {ToneMode.NONE, ToneMode.TONE, ToneMode.TSQL, ToneMode.DTCS}
        ),
        max_label_length=6,
        supported_label_characters=(
            "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ +-/?[]_$%*#.|=\\@"
        ),
        supports_banks=True,
        bank_count=24,
        # The current CHIRP VX-6 driver has no duplex=off representation.
        supports_transmit_disable=False,
        supports_split=True,
        source_notes=(
            "Yaesu VX-6R/E brochure and operating specifications",
            "CHIRP chirp/drivers/vx6.py RadioFeatures",
        ),
    ),
    factory_frequency_sets=(
        FactoryFrequencySet(
            frequency_set_id="us-noaa-weather",
            interface_label="WX CH",
            # The manual proves factory presence but does not document frequency editing.
            frequency_editing=CapabilityStatus.UNKNOWN,
            # The current CHIRP driver does not expose VX-6 factory special sets.
            chirp_editing=CapabilityStatus.UNSUPPORTED,
            source_notes=(
                "Yaesu VX-6R/E operating manual, Weather Broadcast Channels",
                "CHIRP chirp/drivers/vx6.py (no valid_special_chans)",
            ),
        ),
    ),
)


BUILTIN_TARGETS: dict[str, RadioModel] = {VX6R_USA.id: VX6R_USA}
