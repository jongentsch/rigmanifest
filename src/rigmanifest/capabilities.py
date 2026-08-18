"""Built-in radio capability definitions for the first vertical slice."""

from rigmanifest.models import (
    FrequencyRange,
    Mode,
    RadioCapabilities,
    ToneMode,
)


VX6R_USA = RadioCapabilities(
    id="yaesu-vx6r",
    manufacturer="Yaesu",
    model="VX-6R (USA)",
    # Yaesu advertises 900 user memories. CHIRP exposes locations 1-999;
    # model usable capacity separately from address bounds before expanding.
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
    # CHIRP's VX-6R duplex list has no `off` value. Do not claim a safe
    # receive-only representation without a tested overlay.
    supports_transmit_disable=False,
    supports_split=True,
    source_notes=(
        "Yaesu VX-6R/E brochure and operating specifications",
        "CHIRP chirp/drivers/vx6.py RadioFeatures",
    ),
)


BUILTIN_TARGETS: dict[str, RadioCapabilities] = {VX6R_USA.id: VX6R_USA}
