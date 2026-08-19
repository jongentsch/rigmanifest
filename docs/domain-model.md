# Domain Model

The central separation is:

```text
Shared Frequency Catalog
    ↓
Selected Frequency Sets
    ↓
Radio Model + Capabilities + Factory Set Relationships
    ↓
Compiler
    ↓
Programmable Radio Memories + Factory Set Coverage
    ↓
Exporter
```

## Terminology

A frequency definition is not a radio channel.

`Channel` is reserved for contexts where it is genuinely part of an interface or
standard: a numbered GMRS/FRS/CB designation, a radio memory location, or CHIRP's
radio-memory terminology.

## Shared catalog tables

Preset and user-owned records live in the same tables. They are distinguished by
origin and mutability, not by separate schemas.

```text
frequency_definition
- id
- origin: PRESET | USER
- name
- receive_frequency_hz
- transmit_behavior
- transmit_frequency_hz
- offset_hz
- mode
- tone fields
- priority
- notes

frequency_set
- id
- origin: PRESET | USER
- name
- description

frequency_set_member
- frequency_set_id       -> frequency_set.id
- frequency_definition_id -> frequency_definition.id
- position
- channel_designator?    # only when the set is genuinely channelized
```

Preset definitions and preset sets are read-only. A user set may reference either
preset or user-owned definitions, so users can reuse canonical data without copying
it. A preset set may reference only preset definitions, which prevents a read-only
set from changing through a mutable dependency.

A user set may be empty while it is being authored. Empty sets compile to no radio
memories; they do not require placeholder frequency definitions.

## FrequencyDefinition

Represents canonical RF intent independently of any set or target radio.

```text
FrequencyDefinition
- id
- origin
- name
- receive_frequency
- transmit_behavior
- transmit_frequency
- offset
- mode
- tone
- tags[]
- priority
- notes
```

It never contains:

- a radio memory number
- a target-shortened label
- a radio bank assignment
- a factory interface label
- a CHIRP workaround

## FrequencySet

A named, ordered collection of references to shared frequency definitions.

Examples:

- US NOAA Weather Broadcasts (preset, read-only)
- US MURS (preset, read-only)
- My Home Essentials (user-owned)
- Repeaters Along I-77 (user-owned)

For channelized services, `FrequencySetMember.channel_designator` records labels such
as `FRS 1`, `GMRS 15`, or `WX1`. The base frequency definition remains a frequency
definition.

## Transmit behavior

```text
TransmitBehavior
- SAME
- OFFSET
- SPLIT
- DISABLED
```

`DISABLED` is explicit receive-only intent. Compilation must never silently replace
it with a transmittable memory.

## RadioModel and capabilities

```text
RadioModel
- id
- manufacturer
- model
- chirp_driver_reference
- capabilities
- factory_frequency_sets[]

FactoryFrequencySet
- frequency_set_id
- interface_label
- frequency_editing: SUPPORTED | UNSUPPORTED | UNKNOWN
- chirp_editing: SUPPORTED | UNSUPPORTED | UNKNOWN
- source_notes[]
```

A radio model never stores frequency definitions directly. It references a preset set
when manufacturer or verified-driver evidence establishes that the set comes with the
model.

For the US Yaesu VX-6R, the model references `us-noaa-weather` with interface label
`WX CH`. Factory presence is verified. Frequency editing remains `UNKNOWN`; current
CHIRP editing is `UNSUPPORTED` because the VX-6 driver does not expose the factory
special set.

## RadioCapabilities

```text
RadioCapabilities
- memory_capacity
- memory_start
- receive_ranges[]
- transmit_ranges[]
- supported_modes[]
- supported_tone_modes[]
- max_label_length
- supported_label_characters
- supports_banks
- bank_count
- supports_transmit_disable
- supports_split
- source_notes[]
```

Capability data may come from CHIRP `RadioFeatures`, manufacturer documentation,
RigManifest overlays, or verified testing. Proven facts and unknowns must remain
distinguishable.

## Profile

A profile is a saved selection of frequency sets.

```text
Profile
- id
- name
- frequency_set_ids[]
```

Users program radios by selecting sets. If individual definitions need special
treatment, the user can create another user-owned set instead of embedding target
memory rows in a profile.

## Compilation outputs

```text
CompiledMemory
- source_frequency_definition_id
- source_frequency_set_ids[]
- memory_number
- target_name
- receive_frequency
- transmit fields
- mode
- tone
- bank_assignments[]
- applied_transformations[]

FactorySetCoverage
- frequency_set_id
- frequency_set_name
- interface_label
- frequency_definition_ids[]
- frequency_editing
- chirp_editing

CompiledRadioPlan
- target_radio_model
- profile
- memories[]
- factory_sets[]
- omitted_frequency_definitions[]
- diagnostics[]
- capacity_summary
- compiler_version
```

Factory coverage is resolved by set identity. The compiler never infers it by matching
frequencies.

## Key invariants

1. Compilation never mutates frequency definitions or sets.
2. Preset and user records use the same catalog tables.
3. User sets may reference shared preset definitions without copying them.
4. Radio models never define frequencies directly.
5. Factory availability is a radio-model-to-preset-set relationship.
6. Profiles select sets, not radio memory rows.
7. Exporters consume compiled memories and make no selection decisions.
8. Diagnostics explain every meaningful omission or degradation.
9. Identical inputs produce identical outputs.

## Desktop persistence boundary

The first desktop slice stores only the user-owned partition locally. On load, the
UI combines those records with immutable presets returned by Python. On compile, it
sends the complete user partition back across IPC; Python reconstructs and validates
the shared catalog before invoking the compiler. Local storage is therefore an
authoring store, not a trusted compiler input.
