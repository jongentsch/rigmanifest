"""Small in-memory fixtures used by the first CLI and desktop slice."""

from rigmanifest.models import (
    Channel,
    LogicalGroup,
    Mode,
    Priority,
    Profile,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


HOME_CHANNELS: tuple[Channel, ...] = (
    Channel(
        id="local-2m-repeater",
        name="2m Local Repeater",
        receive_frequency_hz=146_910_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=-600_000,
        tone=ToneSpec(mode=ToneMode.TONE, encode_hz=100.0),
        tags=frozenset({"local-repeater"}),
        priority=Priority.HIGH,
    ),
    Channel(
        id="local-70cm-repeater",
        name="70cm Local Repeater",
        receive_frequency_hz=444_500_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=5_000_000,
        tone=ToneSpec(mode=ToneMode.TONE, encode_hz=100.0),
        tags=frozenset({"local-repeater"}),
        priority=Priority.HIGH,
    ),
    Channel(
        id="noaa-weather-1",
        name="NOAA Weather 1",
        receive_frequency_hz=162_550_000,
        transmit_behavior=TransmitBehavior.DISABLED,
        mode=Mode.FM,
        tags=frozenset({"weather"}),
        priority=Priority.NORMAL,
    ),
    Channel(
        id="simplex-calling-2m",
        name="2m Calling",
        receive_frequency_hz=146_520_000,
        transmit_behavior=TransmitBehavior.SAME,
        tags=frozenset({"simplex", "calling"}),
        priority=Priority.MANDATORY,
    ),
)


HOME_PROFILE = Profile(
    id="home",
    name="Home",
    include_tags=frozenset({"local-repeater", "weather", "simplex"}),
    groups=(
        LogicalGroup(
            id="local-repeaters",
            name="Local Repeaters",
            include_tags=frozenset({"local-repeater"}),
        ),
        LogicalGroup(
            id="simplex",
            name="Simplex",
            include_tags=frozenset({"simplex"}),
        ),
    ),
)


BUILTIN_PROFILES: dict[str, Profile] = {HOME_PROFILE.id: HOME_PROFILE}
