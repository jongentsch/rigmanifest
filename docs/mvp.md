# MVP

## MVP question

The first release exists to answer:

> Is capability-aware set compilation meaningfully better than maintaining separate
> CHIRP memory lists by hand?

Everything in the MVP should serve that experiment.

## v0.1 scope

### Shared frequency catalog

The catalog stores preset and user-owned frequency definitions in one table. Canonical
records support at least:

- stable internal ID
- origin (`PRESET` or `USER`)
- display name
- receive frequency
- transmit behavior
- offset or explicit transmit frequency
- independent transmit-access and receive-squelch signaling
- mode
- optional coordinates
- tags
- priority
- notes

No radio-specific memory number belongs in a frequency definition.

### Frequency sets

Preset and user-owned sets use the same set and membership tables.

- preset sets and their definitions are read-only
- user sets may reference either preset or user-owned definitions
- memberships are ordered
- genuinely channelized services may include a membership-level designation

Initial examples:

- `Home essentials` (user-owned)
- `US NOAA Weather Broadcasts` (preset)

### Radio inventory

Support user-named radio instances such as:

- Yaesu VX-6R
- Quansheng UV-K5
- Retevis RT95

Each instance references a radio model and user configuration. Radio models contain
capabilities and may reference verified factory-provided preset sets. They never store
frequency definitions directly.

### Profiles and programming selection

A profile is a saved reusable loadout containing zero or more frequency-set IDs and
zero or more individual frequency-definition IDs. It may also carry an advisory
frequency-plan context. The compile/export page combines one radio with zero or more
profiles, additional sets, and additional individual definitions. The compiler
deduplicates shared definitions while retaining every source for review.

### Compiler

Evaluate at least:

- selected frequency sets
- verified factory-set coverage
- programmable-memory capacity
- receive frequency range
- transmit frequency range
- supported modes
- supported CHIRP tone and cross modes
- valid CTCSS values, DCS codes, and DCS polarity behavior
- maximum label length
- receive-only handling
- set-to-bank mapping where modeled
- advisory band-plan raster, offset, and use checks

Radio capability facts come from the pinned headless CHIRP dependency. Sourced
overlays fill only gaps in `RadioFeatures`, such as separate transmit ranges. The
shared catalog itself is not limited to frequencies supported by the current radio
inventory; incompatibility is a compile result.

### Diagnostics

Return structured diagnostics with:

- code
- severity
- frequency-definition or set reference
- human-readable message
- machine-readable details

### Compiled radio plan

The compiled plan contains:

- target radio model
- selected frequency-set IDs
- selected profiles and one-off definitions
- ordered programmable memories
- factory-set coverage
- assigned memory numbers
- target-specific labels
- mapped banks
- omissions
- diagnostics
- capacity summary

Band-plan diagnostics are warnings. They never omit a compatible memory or prevent
CSV export.

### CHIRP CSV export

The first external artifact is CHIRP-compatible CSV. The exporter serializes only
programmable memories. It does not duplicate factory-provided sets or make capability,
selection, or transmit-safety decisions.

### CLI

Initial command:

```bash
rigmanifest compile home --target yaesu-vx6r
```

### Desktop UI

The first desktop UI proves the same vertical slice with separate pages for:

- frequency definitions and sets
- user radio inventory
- set selection, compilation, diagnostics, and CHIRP CSV export

Preset sets must be visibly read-only. Factory-provided sets must be set apart from
programmable output.

Users can create, rename, and delete their own sets; create and edit their own
frequency definitions; add either preset or user definitions to a user set; and
remove memberships without deleting shared definitions. User records persist across
desktop sessions and are validated by Python before compilation.

## Initial target sequence

1. VX-6R
2. UV-K5
3. RT95
4. AT2 later

## Explicitly out of scope

- direct programming
- custom clone protocols
- DMR
- online repeater APIs
- accounts
- cloud sync
- commercial licensing
- plugin marketplaces
- mobile apps
- collaborative editing

## Definition of success

The MVP succeeds if a user can:

1. Maintain one shared frequency catalog.
2. Reuse definitions across preset and user-owned sets without copying them.
3. Select sets for a radio.
4. Compile the same selection for at least two radio models.
5. See which selected sets are factory-provided on each model.
6. Understand why programmable results differ.
7. Export valid CHIRP CSVs.
