# CHIRP Integration

## Strategy

RigManifest is intentionally GPLv3-compatible so that CHIRP can be treated as an upstream dependency rather than something to avoid.

The first release should still use CHIRP CSV as the programming boundary.

## Phase 1: CSV only

```text
RigManifest
    ↓
CompiledRadioPlan
    ↓
CHIRP CSV exporter
    ↓
CHIRP
    ↓
Radio
```

This proves the core product without coupling the MVP to CHIRP internals.

## Phase 2: Capability extraction

CHIRP drivers expose normalized feature information through structures such as `RadioFeatures`.

Investigate mapping CHIRP feature data into RigManifest capabilities.

Likely useful fields include:

- memory bounds/capacity
- valid bands
- valid modes
- valid tone modes
- valid duplex modes
- tuning steps
- power levels
- maximum name length
- valid characters
- bank support
- settings support

Architecture:

```text
CHIRP driver
    ↓
RadioFeatures
    ↓
RigManifest CHIRP adapter
    ↓
Base RadioCapabilities
    +
RigManifest overlays
    ↓
Compiler
```

## Phase 3: Direct normalized-memory integration

Later, RigManifest may produce CHIRP normalized memory objects and hand them directly to CHIRP drivers.

Possible future path:

```text
RigManifest compiler
    ↓
CompiledRadioPlan
    ↓
CHIRP Memory objects
    ↓
CHIRP driver
    ↓
Radio
```

Do not implement this in the MVP.

## Why overlays are still needed

CHIRP models programming capabilities, but RigManifest also cares about policy and degradation semantics.

Examples:

- whether TX disable can be represented safely
- how logical groups degrade
- whether certain memories should be reserved
- firmware-specific caveats
- target-specific naming strategies
- compiler warnings not represented by CHIRP

## License direction

Because RigManifest is intended to be GPLv3-compatible, using CHIRP source and APIs is an intentional design choice.

Still:

- preserve CHIRP copyright notices where required
- document imported/copied/adapted code clearly
- prefer adapter boundaries over scattered CHIRP assumptions
- avoid copying driver code when normalized APIs are sufficient
