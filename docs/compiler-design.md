# Compiler Design

## Inputs

```text
Frequency Catalog
+ Profile (selected frequency-set IDs)
+ Radio Model
+ Compilation Settings
```

## Output

```text
Compiled Radio Plan
├── programmable memories
├── factory-set coverage
├── omissions
└── diagnostics
```

## Pipeline

1. Resolve the profile's selected frequency sets.
2. Validate radio-model factory-set references against the catalog.
3. Separate selected sets that are verified as factory-provided on the target.
4. Resolve shared frequency definitions for the remaining sets.
5. Deduplicate definitions while preserving all source-set references.
6. Validate target compatibility.
7. Transform representable fields and validate the normalized memory with the
   pinned CHIRP driver.
8. Rank candidates deterministically.
9. Resolve programmable-memory capacity.
10. Map selected sets to radio banks where supported and requested.
11. Assign memory numbers.
12. Return the compiled plan and structured diagnostics.

## Factory-set resolution

Factory availability is set-based:

```text
selected frequency_set.id
        ==
radio_model.factory_frequency_sets.frequency_set_id
```

If the relationship exists and factory coverage is enabled, the compiler records one
`FactorySetCoverage` and does not generate duplicate programmable memories for that
set.

Frequency equality is never used to infer factory coverage. If the same shared
frequency definition is referenced through a different user-owned set, that user set
is compiled normally.

## Compatibility validation

### Receive frequency

Outside all supported receive ranges:

```text
omit
diagnostic: RX_FREQUENCY_UNSUPPORTED
```

This is a target compilation result. It never makes the canonical frequency
definition invalid or removes it from the shared catalog.

### Transmit frequency

If transmission is required but unsupported, omit it and report the reason. Mandatory
definitions raise the diagnostic severity to error.

### Receive-only

If `TransmitBehavior.DISABLED` cannot be represented safely in a programmable memory:

```text
omit
diagnostic: TX_DISABLE_NOT_REPRESENTABLE
severity: error
```

A verified factory set can satisfy receive-only intent without requiring CHIRP to
represent a programmable `duplex=off` memory.

### Mode and tone

Unsupported modes and tone semantics are omitted with structured diagnostics. They are
never silently converted.

Exact CTCSS tones and DCS codes are checked against the target driver's CHIRP
catalog. After target-independent policy checks, CHIRP `validate_memory()` is the
final representability check. Driver errors omit the result; warnings remain visible.

## Field transformations

Target label normalization and shortening are deterministic and diagnostic-producing.
Canonical frequency definitions remain unchanged.

## Ranking and capacity

Initial ranking:

1. mandatory
2. high
3. normal
4. low
5. stable set-selection order
6. stable definition ID

Capacity applies only to programmable memories. Factory-provided definitions do not
consume user-memory capacity.

## Set-to-bank mapping

Selected non-factory sets may map to radio banks. If the target has no compatible bank
support, logical source-set metadata remains in the plan and the compiler emits
`GROUPING_DEGRADED`.

## Export

The exporter consumes `CompiledRadioPlan.memories` only. It does not export factory
coverage, evaluate sets, rank definitions, query capabilities, or alter transmit
semantics.
