# Domain Model

The most important separation is:

```text
Canonical Data
    ↓
Profile / Intent
    ↓
Capabilities
    ↓
Compiler
    ↓
Compiled Radio Plan
    ↓
Exporter
```

## Channel

Represents a communications resource independently of any target radio.

Suggested fields:

```text
Channel
- id
- name
- receive_frequency
- transmit_behavior
- transmit_frequency
- offset
- mode
- tone
- location
- tags[]
- priority
- receive_only
- notes
- source_metadata
```

A canonical channel does not contain:

- memory number
- truncated target label
- radio bank assignment
- target-specific workaround

## Transmit behavior

Initial model:

```text
TransmitBehavior
- SAME
- OFFSET
- SPLIT
- DISABLED
```

## Tone

Initial model should cover common analog use without attempting every edge case.

Possible shape:

```text
ToneSpec
- mode
- encode_tone
- decode_tone
- dtcs_code
- dtcs_polarity
```

## Location

```text
Location
- latitude
- longitude
- locality
- region
```

Coordinates matter for geographic selectors.

## Tags

Examples:

```text
local-repeater
weather
simplex
rail
airband
emergency
Tuscarawas
ARES
travel
```

Tags carry user intent, not radio semantics.

## Priority

Initial values:

```text
MANDATORY
HIGH
NORMAL
LOW
```

## RadioModel

```text
RadioModel
- id
- manufacturer
- model
- capabilities
- chirp_driver_reference
```

## RadioInstance

```text
RadioInstance
- id
- radio_model_id
- nickname
- serial_number
- role
- notes
```

## RadioCapabilities

Initial fields:

```text
RadioCapabilities
- memory_capacity
- receive_ranges[]
- transmit_ranges[]
- supported_modes[]
- supported_tone_modes[]
- max_label_length
- supported_label_characters
- supports_banks
- bank_count
- supports_receive_only
```

Capability data may come from:

- CHIRP RadioFeatures
- manufacturer documentation
- RigManifest overlays
- verified testing

## Capability overlays

CHIRP will not represent every policy RigManifest cares about.

Use overlays for:

- receive-only workarounds
- grouping degradation policy
- reserved memories
- preferred naming behavior
- firmware-specific differences
- target-specific safety rules

## Profile

```text
Profile
- id
- name
- selectors[]
- exclusions[]
- groups[]
- ordering_policy
- capacity_policy
```

Profiles describe rules, not memory rows.

## Selector

Initial types:

```text
TAG
EXPLICIT_CHANNEL
GEOGRAPHIC_RADIUS
MIN_PRIORITY
```

## LogicalGroup

```text
LogicalGroup
- id
- name
- selector
- priority
```

A logical group may map to a bank, scan group, or nothing at all depending on target capability.

## CompiledMemory

```text
CompiledMemory
- source_channel_id
- memory_number
- target_name
- receive_frequency
- transmit_behavior
- transmit_frequency
- offset
- mode
- tone
- bank_assignments[]
- applied_transformations[]
```

## CompiledRadioPlan

```text
CompiledRadioPlan
- target_radio_instance
- profile
- memories[]
- omitted_channels[]
- diagnostics[]
- capacity_summary
- compiler_version
```

## Diagnostic

```text
Diagnostic
- code
- severity
- channel_id
- message
- details
```

Suggested codes:

```text
LABEL_TRUNCATED
RX_FREQUENCY_UNSUPPORTED
TX_FREQUENCY_UNSUPPORTED
MODE_UNSUPPORTED
TONE_UNSUPPORTED
GROUPING_DEGRADED
CHANNEL_OMITTED_CAPACITY
TX_DISABLE_NOT_REPRESENTABLE
CAPABILITY_DATA_INCOMPLETE
```

## Key invariants

1. Compilation never mutates canonical channels.
2. Profiles never contain radio-specific memory numbers.
3. Capability definitions never encode user preference.
4. Exporters never make selection decisions.
5. Diagnostics explain every meaningful omission/degradation.
6. Identical inputs produce identical outputs.
