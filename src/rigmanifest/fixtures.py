"""Small fact-based catalog fixtures used by the first vertical slice."""

from rigmanifest.models import (
    CatalogOrigin,
    FrequencyCatalog,
    FrequencyDefinition,
    FrequencySet,
    FrequencySetMember,
    Mode,
    Priority,
    Profile,
    ToneMode,
    ToneSpec,
    TransmitBehavior,
)


HOME_FREQUENCY_DEFINITIONS: tuple[FrequencyDefinition, ...] = (
    FrequencyDefinition(
        id="local-2m-repeater",
        name="2m Local Repeater",
        receive_frequency_hz=146_910_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=-600_000,
        tone=ToneSpec(mode=ToneMode.TONE, encode_hz=100.0),
        tags=frozenset({"local-repeater"}),
        priority=Priority.HIGH,
    ),
    FrequencyDefinition(
        id="local-70cm-repeater",
        name="70cm Local Repeater",
        receive_frequency_hz=444_500_000,
        transmit_behavior=TransmitBehavior.OFFSET,
        offset_hz=5_000_000,
        tone=ToneSpec(mode=ToneMode.TONE, encode_hz=100.0),
        tags=frozenset({"local-repeater"}),
        priority=Priority.HIGH,
    ),
    FrequencyDefinition(
        id="simplex-calling-2m",
        name="2m Calling",
        receive_frequency_hz=146_520_000,
        transmit_behavior=TransmitBehavior.SAME,
        tags=frozenset({"simplex", "calling"}),
        priority=Priority.MANDATORY,
    ),
)


NOAA_FREQUENCY_DEFINITIONS: tuple[FrequencyDefinition, ...] = tuple(
    FrequencyDefinition(
        id=f"us-noaa-weather-{index}",
        name=f"NOAA Weather {index}",
        receive_frequency_hz=frequency_hz,
        transmit_behavior=TransmitBehavior.DISABLED,
        origin=CatalogOrigin.PRESET,
        mode=Mode.FM,
        tags=frozenset({"weather", "noaa"}),
        priority=Priority.NORMAL,
        notes="Frequency published in the Yaesu VX-6R/E operating manual WX list.",
    )
    for index, frequency_hz in enumerate(
        (
            162_550_000,
            162_400_000,
            162_475_000,
            162_425_000,
            162_450_000,
            162_500_000,
            162_525_000,
            161_650_000,
            161_775_000,
            163_275_000,
        ),
        start=1,
    )
)


HOME_ESSENTIALS_SET = FrequencySet(
    id="home-essentials",
    name="Home essentials",
    origin=CatalogOrigin.USER,
    description="User-owned set for the first local operating configuration.",
    members=(
        FrequencySetMember("simplex-calling-2m", position=0),
        FrequencySetMember("local-2m-repeater", position=1),
        FrequencySetMember("local-70cm-repeater", position=2),
    ),
)


US_NOAA_WEATHER_SET = FrequencySet(
    id="us-noaa-weather",
    name="US NOAA Weather Broadcasts",
    origin=CatalogOrigin.PRESET,
    description="Read-only US weather broadcast preset set.",
    members=tuple(
        FrequencySetMember(
            frequency_definition_id=definition.id,
            position=index,
            channel_designator=f"WX{index + 1}",
        )
        for index, definition in enumerate(NOAA_FREQUENCY_DEFINITIONS)
    ),
)


BUILTIN_CATALOG = FrequencyCatalog(
    definitions=HOME_FREQUENCY_DEFINITIONS + NOAA_FREQUENCY_DEFINITIONS,
    sets=(HOME_ESSENTIALS_SET, US_NOAA_WEATHER_SET),
)


HOME_PROFILE = Profile(
    id="home",
    name="Home",
    frequency_set_ids=(HOME_ESSENTIALS_SET.id, US_NOAA_WEATHER_SET.id),
)


BUILTIN_PROFILES: dict[str, Profile] = {HOME_PROFILE.id: HOME_PROFILE}
