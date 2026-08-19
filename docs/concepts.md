# Core Concepts

RigManifest separates reusable operating intent from radio-specific memory layouts.
That boundary is the key to maintaining the same material across different radios.

## Frequency definition

A frequency definition is target-independent RF intent. It can describe receive and
transmit frequencies, offset behavior, mode, tuning step, transmit access, receive
squelch, label, priority, and notes.

A frequency definition is **not** a radio channel. “Channel” is reserved for a
genuinely channelized service such as FRS or GMRS, or for a numbered radio memory in
the destination interface.

Definitions are deliberately not limited by the radios you own. An HF definition can
live in the same catalog as VHF and UHF definitions. Compilation decides whether a
specific target can receive, transmit, and represent it safely.

## Frequency set

A frequency set is a named, ordered collection of references to shared definitions.
Examples include Local Repeaters, I-77 Travel, NOAA Weather, and MURS.

Preset and user-owned sets share the same structure. Presets are read-only; user sets
are editable and may reference either user or preset definitions. Imported radio
banks become ordinary user-owned sets.

## Profile

A profile is a reusable selection of sets and individual definitions. Profiles are
good for a location, trip, event, or operating role: Home, Dayton, Canada Trip,
Vacation Home, or Emergency.

Profiles remain target-independent. They do not store memory numbers or driver-specific
encodings. Multiple profiles can be combined during one compile.

## Radio and image versions

Adding a radio requires a CHIRP image downloaded from that device. CHIRP detects the
driver and exposes the actual memory range, modes, tones, tuning steps, label rules,
bank model, and other capabilities.

RigManifest stores source and compiled images as normal files under the workspace's
`radios/<radio-id>/` directory. SQLite tracks their metadata and relationships. The
original image is retained unchanged, and every export creates a new managed version.

An image also preserves settings and special radio areas that are not ordinary
programmable memories. RigManifest asks CHIRP to load, modify, validate, and save the
image rather than parsing the binary format itself.

## Banks and sets

Sets express reusable grouping intent; banks are a radio interface feature. During
compilation, RigManifest maps selected sets to banks through CHIRP when the target
supports them.

A profile can include many sets, and a definition can belong to many sets. If a radio
cannot reproduce that grouping exactly, the compiler explains the degradation. A
non-bank radio receives the compatible memories as a flat list.

## Compile

A compile combines:

- exactly one image-backed radio;
- zero or more profiles;
- zero or more additional sets; and
- zero or more additional definitions.

The compiler resolves duplicates, orders definitions deterministically, checks target
capabilities, derives CHIRP signaling semantics, applies labels and capacity policy,
maps banks where possible, and emits structured diagnostics.

Catalog data is never mutated by compilation. Identical inputs produce identical
plans.

## Advisory plans versus radio capabilities

An advisory frequency plan describes regional norms such as frequency segments,
rasters, and common repeater offsets. It can help during editing, profiling, and final
review, but its findings never block compilation.

Radio capabilities are different. They describe what the selected target and CHIRP
driver can safely represent. A definition outside those capabilities may be omitted
with an explanation. RigManifest never forces an invalid memory into an image merely
because the catalog allows the definition to exist.

## RigManifest and CHIRP

RigManifest owns:

- shared frequency definitions and sets;
- profiles and radio inventory;
- provenance, selection, ordering, and capacity policy;
- bank-mapping intent; and
- explainable diagnostics.

CHIRP owns:

- radio drivers and normalized capabilities;
- target-memory validation;
- radio-specific image formats and settings; and
- communication with hardware.

CSV remains useful for generic interchange, but it cannot represent banks or general
radio settings. CHIRP IMG is the primary import and export boundary.
