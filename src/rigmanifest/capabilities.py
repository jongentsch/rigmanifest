"""Built-in radio targets composed from CHIRP facts and explicit overlays."""

from rigmanifest.chirp_adapter import ChirpCapabilityOverlay, radio_model_from_chirp
from rigmanifest.models import CapabilityStatus, FactoryFrequencySet, FrequencyRange


VX6R_USA = radio_model_from_chirp(
    model_id="yaesu-vx6r",
    driver_reference="Yaesu_VX-6",
    display_model="VX-6R (USA)",
    overlay=ChirpCapabilityOverlay(
        # RadioFeatures has one wide receive range and cannot express the
        # narrower USA transmit ranges, advertised usable capacity, or bank count.
        memory_capacity=900,
        transmit_ranges=(
            FrequencyRange(144_000_000, 148_000_000),
            FrequencyRange(222_000_000, 225_000_000),
            FrequencyRange(430_000_000, 450_000_000),
        ),
        bank_count=24,
        source_notes=(
            "Yaesu VX-6R/E USA documentation: transmit ranges, 900 user memories, and 24 banks",
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


UVK5 = radio_model_from_chirp(
    model_id="quansheng-uv-k5",
    driver_reference="Quansheng_UV-K5",
    overlay=ChirpCapabilityOverlay(
        transmit_ranges=(
            FrequencyRange(136_000_000, 174_000_000),
            FrequencyRange(400_000_000, 470_000_000),
        ),
        source_notes=(
            "Quansheng UV-K5 user manual: stock TX/RX ranges 136-174 and 400-470 MHz",
            "CHIRP UV-K5 driver: 200 memories and firmware-dependent receive coverage",
        ),
    ),
)


RT95 = radio_model_from_chirp(
    model_id="retevis-rt95",
    driver_reference="Retevis_RT95",
    overlay=ChirpCapabilityOverlay(
        # With no downloaded image CHIRP deliberately reports its most
        # permissive region variant. Target selection is therefore explicit.
        transmit_ranges=(
            FrequencyRange(136_000_000, 174_000_000),
            FrequencyRange(400_000_000, 490_000_000),
        ),
        source_notes=(
            "Retevis RT95 manual: dual-band VHF/UHF mobile radio with 200 memories",
            "CHIRP anytone778uv driver: region variants; fallback 136-174 and 400-490 MHz",
        ),
    ),
)


BUILTIN_TARGETS = {
    target.id: target
    for target in (
        UVK5,
        RT95,
        VX6R_USA,
    )
}
