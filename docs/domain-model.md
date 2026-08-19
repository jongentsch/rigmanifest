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
- transmit-access signaling
- receive-squelch signaling
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
- transmit_access: SignalingSpec
- receive_squelch: SignalingSpec
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

Transmit access and receive squelch are independent target-neutral values. Each can
be none, CTCSS (with a frequency), or DCS (with a code and direction-specific
polarity). CHIRP's combined `Tone`, `TSQL`, `DTCS`, and `Cross` modes are derived only
when compiling or exporting a radio memory. For example, transmit CTCSS with no
receive squelch becomes CHIRP `Tone`; equal CTCSS in both directions becomes `TSQL`;
and transmit CTCSS plus receive DCS becomes `Cross` / `Tone->DTCS`.

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
- valid_cross_modes[]
- valid_tuning_steps_hz[]
- valid_ctcss_tones_hz[]
- valid_dtcs_codes[]
- max_label_length
- supported_label_characters
- supports_banks
- bank_count
- supports_transmit_disable
- supports_split
- supports_separate_rx_dtcs
- supports_dtcs_polarity
- source_notes[]
```

Capability data comes from the pinned CHIRP driver's `RadioFeatures` wherever that
API expresses the fact. Small RigManifest overlays provide separately sourced facts
that CHIRP cannot represent, especially transmit ranges distinct from wideband
receive coverage, usable capacity, and bank count. Proven facts and unknowns remain
distinguishable.

The catalog does not validate a definition against any radio. Any positive
integer-Hz frequency is valid canonical intent. The compiler determines whether the
selected target can receive it, transmit it when requested, and represent the final
memory through its CHIRP driver.

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

## Frequency plans

Frequency plans are sourced advisory data, separate from both frequency definitions
and radio capabilities. A plan records jurisdiction, authority tier, review date,
source URL, and bounded segments. A segment may suggest a repeater offset and may
define a raster using both an anchor and spacing.

The first built-in plan is the ARRL US national baseline. It includes exact paired
repeater-output segments on 10 m, 6 m, 2 m, 1.25 m, 33 cm, and 23 cm, plus the
national 2 m simplex segments. National data intentionally leaves the 2 m and 70 cm
regional raster/sign choices unspecified where the ARRL plan delegates them to local
coordinators. The editor displays the source and only mutates transmit behavior when
the user explicitly accepts an offset suggestion. It never suggests CTCSS or DCS
from a band segment.

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
- transmit_access
- receive_squelch
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
9. Signaling intent is stored independently by direction; target encodings are derived.
10. Identical inputs produce identical outputs.

## Desktop persistence boundary

The desktop stores only the user-owned partition locally. Schema v2 separates
transmit access from receive squelch; stored v1 combined-tone records are migrated
in place without changing the source frequency definitions. On load, the
UI combines those records with immutable presets returned by Python. On compile, it
sends the complete user partition back across IPC; Python reconstructs and validates
the shared catalog before invoking the compiler. Local storage is therefore an
authoring store, not a trusted compiler input.

CHIRP CSV import crosses the same validation boundary. A CHIRP memory is translated
into a new user-owned frequency definition and provenance is retained in notes; its
radio memory number is not promoted into canonical identity. The resulting set and
definitions are persisted through the ordinary user-catalog path.
