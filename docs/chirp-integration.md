# CHIRP Integration

## Strategy

CHIRP is a pinned, headless Python dependency and the primary source of normalized
radio-driver facts. RigManifest does not maintain a parallel hand-authored copy of
facts that `RadioFeatures` already exposes.

The dependency is pinned to commit
`fa27a491d275f88b452d0488a51b4c85d4f7062a`. CHIRP publishes its Python package as
version `0`, so an exact source revision is required for reproducible builds.
wxPython is an optional CHIRP extra and is not part of the RigManifest core runtime.

## Current boundary

```text
CHIRP driver
    ↓
RadioFeatures
    ↓
RigManifest CHIRP adapter + explicit overlays
    ↓
RadioCapabilities
    ↓
RigManifest compiler
    ↓
CompiledMemory
    ↓
CHIRP Memory + driver.validate_memory()
    ↓
CHIRP CSV
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

## Built-in targets

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

## Export and later direct programming

CHIRP CSV remains the first external artifact. Direct image and radio programming can
later reuse the same normalized-memory adapter and CHIRP drivers. It remains outside
the MVP until compilation and validation are stable.

## License

RigManifest and CHIRP are GPLv3-compatible. Preserve upstream copyright notices,
record the pinned revision, prefer normalized APIs over copied driver code, and keep
all CHIRP-specific behavior inside the adapter boundary.
