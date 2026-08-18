# Compiler Design

## Inputs

```text
Channel Library
+ Profile
+ Radio Capabilities
+ Compilation Policy
```

## Output

```text
Compiled Radio Plan
+ Diagnostics
```

## Pipeline

```text
1. Resolve profile
2. Select candidate channels
3. Apply exclusions
4. Validate target compatibility
5. Transform representable fields
6. Rank candidates
7. Resolve capacity
8. Map logical groups
9. Assign memory numbers
10. Produce diagnostics
11. Return compiled plan
```

## Candidate selection

Initial selectors:

- explicit inclusion
- tag inclusion
- geographic radius
- priority threshold

Explicit exclusions override broad inclusions.

## Compatibility validation

### Receive frequency

Outside all supported receive ranges:

```text
omit
diagnostic: RX_FREQUENCY_UNSUPPORTED
```

### Transmit frequency

If TX is required but unsupported:

- do not silently change semantics
- either omit, downgrade only under explicit policy, or emit an error

### Receive-only

If receive-only intent cannot be represented safely:

- emit a strong diagnostic
- do not silently enable transmission

### Mode

Do not silently convert incompatible modes.

### Tone

Unsupported tone modes require explicit diagnostics.

## Field transformations

### Label shortening

Initial strategy may be truncation.

Always preserve:

- original label
- compiled label
- diagnostic

### Character filtering

Normalize only when deterministic and safe.

## Ranking

Initial ranking should be deterministic.

Suggested order:

1. mandatory
2. explicit inclusions
3. high priority
4. distance
5. normal priority
6. low priority
7. stable ID tie-breaker

## Capacity resolution

If valid candidates exceed capacity:

```text
select highest-ranked N
omit remainder
```

All omissions must remain visible in the compiled result.

## Logical group mapping

If a target supports compatible banks:

- map groups

If not:

- preserve logical metadata
- emit `GROUPING_DEGRADED`

## Memory assignment

Assign memory numbers only after final selection.

Memory ordering must be deterministic.

## Diagnostics

Severity:

### Info
harmless normalization

### Warning
label truncation, grouping loss, optional feature loss

### Error
unsafe TX degradation, mandatory channel impossible, invalid canonical data

## Export

The exporter consumes `CompiledRadioPlan`.

It does not:

- evaluate profiles
- rank channels
- query capabilities
- decide omissions
- silently change semantics

## CLI example

```bash
rigmanifest compile home --target retevis-rt95
```

Potential output:

```text
Profile: Home
Target: Retevis RT95

Included: 87
Omitted: 6
Warnings: 4
Errors: 0

CSV written: home-retevis-rt95.csv
```
