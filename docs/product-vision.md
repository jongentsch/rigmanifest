# Product Vision

## Problem

Most amateur-radio programming software models radio memories directly.

The user edits rows containing fields such as:

- memory number
- frequency
- offset
- tone
- mode
- name

That is useful after the desired configuration is known, but it does not represent how operators naturally think.

Operators tend to think in terms such as:

- local repeaters
- nearby repeaters
- repeaters along a route
- NOAA weather
- common simplex frequencies
- calling frequencies
- emergency frequencies
- receive-only services
- scan groups
- operating regions
- radio roles
- priority

These concepts are independent of any one radio.

## Central thesis

RigManifest separates **desired operating configuration** from **radio implementation**.

```text
desired configuration
        ↓
capability-aware compiler
        ↓
radio-specific configuration
```

The application should let the user define intent once and compile that intent for multiple radios.

## Example

A `Home` profile may mean:

- include analog repeaters within 40 miles
- include NOAA weather
- include common simplex/calling frequency sets
- include selected receive-only services
- group local repeaters together
- group simplex together
- prefer high-priority local frequency definitions when capacity is constrained

That same profile should compile differently for different radios.

## Explainability

A compiler result must answer:

- What was included?
- What was omitted?
- Why?
- What was renamed?
- Which groups mapped cleanly?
- Which were flattened?
- Which features degraded?
- How much memory capacity is used?
- Were any transmit-safety semantics weakened?

Example:

```text
TUSCARAWAS REPEATER FREQUENCY

VX-6R
✓ Included

UV-K5
✓ Included
⚠ Logical bank membership flattened

AT2
✗ Omitted
Reason: receive frequency outside target capability
```

## Relationship to CHIRP

RigManifest is not intended to replace CHIRP.

CHIRP remains the preferred final-mile programmer.

The first integration target is CHIRP-compatible CSV.

Later, because RigManifest is GPLv3-compatible and Python-based, it may directly consume CHIRP's normalized radio APIs and driver capability data.

## Open-source direction

RigManifest is intended to be fully open source.

Benefits include:

- direct compatibility with CHIRP's GPL ecosystem
- community-maintained radio capability mappings
- community-contributed profiles and examples
- self-hosting possibilities
- transparent compiler behavior
- easier testing against real radios
- lower barrier to contribution

## Long-term possibilities

Only after the compiler proves useful:

- direct CHIRP driver integration
- direct radio programming
- route-based travel profiles
- emergency profiles
- configuration diffing
- drift detection
- shared profile libraries
- online repeater providers
- capability overlays
- richer scan-group/bank semantics
- DMR and digital-radio extensions

These are extensions, not prerequisites.
