# CHIRP Integration

## Strategy

CHIRP is a pinned, headless Python dependency and the primary source of normalized
radio-driver facts. RigManifest does not maintain a parallel hand-authored copy of
facts that `RadioFeatures` already exposes.

The dependency is pinned to commit
`fa27a491d275f88b452d0488a51b4c85d4f7062a`. CHIRP publishes its Python package as
version `0`, so an exact source revision is required for reproducible builds.
wxPython is an optional CHIRP extra and is not part of the RigManifest core runtime.

RigManifest initializes CHIRP once per process for headless use. The initializer
installs CHIRP's gettext builtins and imports every driver module available through
the Python package loader. Package-loader discovery is required because PyInstaller
stores modules inside its archive, where CHIRP's normal filesystem glob cannot see
them. Release builds collect the complete `chirp.drivers` package and fail their
sidecar smoke test when a representative secondary driver module is not registered.

## Image-backed desktop workflow

Adding a radio to the desktop requires a CHIRP image downloaded from that radio.
CHIRP detects the exact driver and variant, then exposes the image's memories, bank
model, and radio settings. RigManifest imports non-empty memories as reusable
frequency definitions, populated banks as user sets, and a profile grouping those
sets. Unbanked memories remain direct profile selections; a radio without bank
support imports one flat set.

The exact source image is stored unchanged under `radios/<radio-id>/`; SQLite stores
only version metadata, relative paths, sizes, and hashes. Compilation loads that file
through CHIRP, applies normalized
memories with `set_memory()`, updates memberships through the bank model, validates
the result through the image-bound driver, and asks CHIRP to `save()` a new managed
image version. The selected export destination receives a copy of that managed
version. RigManifest never parses or serializes the binary image layout and never
overwrites the source image.

This is the primary desktop boundary:

```text
CHIRP image + detected driver
    ↓
memories + banks + settings + RadioFeatures
    ↓
RigManifest image adapter
    ↓
RadioCapabilities
    ↓
RigManifest compiler
    ↓
CompiledMemory
    ↓
CHIRP Memory + image driver validation + bank API
    ↓
CHIRP save() -> new IMG
```

The adapter currently obtains these facts from CHIRP:

- memory address bounds
- receive/programmable frequency ranges exposed by the driver
- valid modes and tone modes
- valid tuning steps
- valid CTCSS tones and DCS codes
- duplex, odd-split, and transmit-disable representations
- label length and character set
- bank support
- separate receive-DCS and DCS-polarity support
- image-dependent power selectors, native labels, and nominal dBm values

Power labels are driver-local provenance, never cross-radio identities. RigManifest
normalizes adjustable selectors into five relative tiers and also supports a
preferred nominal output. Radio Default leaves the source slot unchanged when
possible and otherwise allows the driver to initialize its default. Capability
snapshots drive the editor and audit trail; compilation reloads the exact source
image and treats the live driver as final authority, including immutable-memory
policy and read-back verification.

The frequency editor's shared CTCSS dropdown comes directly from CHIRP's
50-value `chirp_common.TONES` catalog. Compilation still checks the selected tone
against the chosen radio driver's narrower `valid_tones` capability when applicable.

## Legacy built-in targets

The built-in registry below remains temporarily for CLI compatibility and isolated
compiler fixtures. Desktop radio selection and compilation use the imported image
instead of these hand-authored targets.

The selectable target registry currently contains:

- Yaesu VX-6R (USA), backed by `Yaesu_VX-6`;
- Quansheng UV-K5 with stock firmware ranges, backed by `Quansheng_UV-K5`;
- Retevis RT95 using CHIRP's permissive region variant until an image supplies its
  region byte, backed by `Retevis_RT95`.

The UV-K5 overlay limits transmission to the stock-manual 136-174 and 400-470 MHz
ranges even though CHIRP intentionally exposes expanded receive/firmware bands. The
RT95 driver exposes three region variants and, without an image, documents and uses
136-174 and 400-490 MHz. Its transmit overlay matches that explicit CHIRP fallback.

Sources: [CHIRP UV-K5 driver](https://github.com/kk7ds/chirp/blob/fa27a491d275f88b452d0488a51b4c85d4f7062a/chirp/drivers/uvk5.py),
[CHIRP RT95 family driver](https://github.com/kk7ds/chirp/blob/fa27a491d275f88b452d0488a51b4c85d4f7062a/chirp/drivers/anytone778uv.py),
[Retevis RT95 manual](https://v3.retevis.com/Themes/Retevis/Assets/files/download/Manuals_Mobile_Radios/RT95-Multi-Language-Manual.pdf),
and the Quansheng UV-K5 user manual supplied with the radio.

The compiler still owns selection, capacity policy, deterministic ordering, safety
policy, diagnostics, and omission behavior. A compiled memory that passes the
RigManifest capability checks is translated to `chirp_common.Memory` and passed to
the selected driver's `validate_memory()` method. A CHIRP validation error omits the
definition with `TARGET_MEMORY_REJECTED`; a CHIRP warning remains visible without
silently altering the memory.

## Why overlays still exist

`RadioFeatures.valid_bands` is one list and does not generally distinguish receive
coverage from transmit coverage. The VX-6 driver, for example, exposes its wideband
receive range but not the much narrower USA transmit ranges. It also does not expose
manufacturer-advertised usable capacity or the number of banks.

An overlay may therefore supply only facts absent from CHIRP, including:

- separately sourced transmit ranges
- manufacturer-advertised usable capacity when it differs from address bounds
- bank count
- firmware or regional caveats
- radio-model relationships to verified factory frequency sets

Every overlay fact carries source notes. It must not replace a CHIRP fact merely for
convenience.

## Catalog independence

CHIRP compatibility is a compilation concern, not a catalog-entry restriction. A
user can define any finite positive frequency as canonical intent, including an HF
frequency when no owned target supports it.

Compilation checks the selected target in this order:

1. RigManifest's separate receive and transmit capability ranges;
2. supported mode, derived tone/cross semantics, each direction's exact tone/code,
   DCS polarity, and duplex form;
3. CHIRP driver validation of the normalized target memory.

Consequently, an HF transmit definition remains valid catalog data but is omitted
when compiling for a VHF/UHF HT whose transmit ranges do not include it. A genuinely
receive-only HF definition may compile for a wideband receiver only when the target
can both receive it and safely represent transmit-disabled intent.

## Domain separation

CHIRP CSV rows and `chirp_common.Memory` objects represent destination radio memory
locations. They are not RigManifest frequency definitions. CHIRP does not replace:

- shared frequency definitions and sets
- preset versus user ownership
- profiles and selection intent
- factory-frequency-set relationships
- geographic frequency plans
- provenance
- ranking and capacity policy
- explicit explanations of degradation

Do not call CHIRP's import-conversion policy as the RigManifest compiler policy.
Some CHIRP conversions intentionally coerce unsupported values for interactive
copying between radios. RigManifest must instead explain and omit an unsafe or
unrepresentable result.

## CSV compatibility and direct programming

CHIRP generic CSV is bidirectional. Export serializes compiled memories. Import uses
CHIRP's own `CSVRadio` parser and converts every non-empty CHIRP memory into a
user-owned frequency definition, preserving duplex/split/receive-only intent,
independent signaling, DCS polarity, mode, label, comment, source filename, and
source memory location. One user-owned frequency set references the imported
definitions, after which they behave exactly like records authored in RigManifest.

Import does not treat a CHIRP memory location as part of canonical RF identity and
does not call every imported frequency a channel. Unsupported modes or malformed
CSV fail visibly rather than being coerced. Re-importing creates a separate set with
collision-resistant IDs, so it cannot overwrite an existing user catalog.

CSV remains useful for generic frequency interchange, but it cannot carry radio bank
membership or general settings and is not the primary desktop output. Direct radio
programming can later replace the final CHIRP `save()` call with clone-out while
reusing the same compiler and image-bound adapter.

## License

RigManifest and CHIRP are GPLv3-compatible. Preserve upstream copyright notices,
record the pinned revision, prefer normalized APIs over copied driver code, and keep
all CHIRP-specific behavior inside the adapter boundary.
