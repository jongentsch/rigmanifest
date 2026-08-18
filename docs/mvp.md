# MVP

## MVP question

The first release exists to answer:

> Is capability-aware intent compilation meaningfully better than maintaining separate CHIRP memory lists by hand?

Everything in the MVP should serve that experiment.

## v0.1 scope

### Channel library

Canonical channel records should support at least:

- stable internal ID
- display name
- receive frequency
- transmit behavior
- offset or explicit transmit frequency
- tone information
- mode
- optional coordinates
- tags
- priority
- receive-only intent
- notes

No radio-specific memory number belongs in canonical channel data.

### Radio inventory

Support radio instances such as:

- Yaesu VX-6R
- Quansheng UV-K5
- Retevis RT95

Each instance references a model/capability definition.

### Profiles

Profiles should support:

- include by tag
- exclude by tag
- explicit inclusion
- explicit exclusion
- optional geographic radius
- minimum priority
- basic logical groups

Example:

```yaml
name: Home

include:
  - tag: local-repeater
  - tag: weather
  - tag: simplex

exclude:
  - tag: temporary

radius:
  center: home
  miles: 40
```

### Compiler

Evaluate at least:

- memory capacity
- receive frequency range
- transmit frequency range
- supported modes
- supported tone modes
- maximum label length
- receive-only handling
- bank/group support where modeled

### Diagnostics

Return structured diagnostics with:

- code
- severity
- channel reference
- human-readable message
- machine-readable details

### Compiled radio plan

The compiled plan contains:

- target radio
- ordered compiled memories
- assigned memory numbers
- target-specific names
- mapped groups
- omissions
- diagnostics
- capacity summary

### CHIRP CSV export

The first external artifact is CHIRP-compatible CSV.

The exporter consumes the compiled plan and does not make capability or selection decisions.

### CLI

Initial command:

```bash
rigmanifest compile home --target yaesu-vx6r
```

Support file output and human-readable diagnostics.

### Desktop UI

The first desktop UI only needs enough functionality to prove the same vertical slice:

- view a small channel library
- choose a profile
- choose a radio
- compile
- inspect diagnostics
- export CSV

Do not build the entire product shell before the compiler works.

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

1. Maintain one canonical library.
2. Define `Home`.
3. Compile it for at least two radios.
4. Understand why the results differ.
5. Export valid CHIRP CSVs.
6. Import those CSVs into CHIRP and program the radios normally.
