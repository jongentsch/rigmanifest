# RigManifest Roadmap

RigManifest has completed its first vertical slice and the original v0.1 experiment.
The project now has an image-backed CHIRP workflow, a reusable frequency catalog,
sets and profiles, bank-aware compilation, versioned radio images, desktop packaging,
signed updates, and automated Python, browser, accessibility, visual, and Rust tests.

The roadmap is organized by outcome rather than promised dates. GitHub milestones and
issues should carry the active implementation breakdown; this document records the
project-level direction.

## Current focus: image workflow hardening

### Real-radio compatibility

- Round-trip representative images through more CHIRP drivers and radio families.
- Verify that memories, banks, settings, special memories, and unknown image regions
  survive compilation as expected.
- Build a reusable, legally distributable fixture matrix for bank and non-bank radios.
- Improve recovery guidance when CHIRP cannot load, validate, or save an image.

### Bank and memory placement controls

- Let users edit prospective bank assignments before compilation.
- Support bank ordering, memory ordering, and definitions that belong to multiple sets.
- Make flattening behavior explicit for radios without bank support.
- Add policies for starting memory, reserved locations, gaps, existing-memory
  preservation, replacement, and capacity conflicts.

### Radio-image version management

- Compare source and compiled image versions at the memory and bank level.
- Restore, export, annotate, rename, and safely remove managed versions.
- Explain what changed between two compilations without parsing binary image formats.

### Catalog maintenance

- Add faster search, filtering, bulk editing, and set-membership tools.
- Detect likely duplicate definitions and provide an explicit merge workflow.
- Improve import review so incoming definitions can be accepted, edited, grouped, or
  skipped before they enter the shared catalog.
- Expand automated coverage toward complete branch coverage where it remains useful.

## Next: richer configuration maintenance

- Configuration drift detection between a saved profile, a compiled image, and a newly
  downloaded image from the same radio.
- More sourced advisory plans, including regional coordinator data where licensing and
  maintenance allow it.
- Repeater-directory discovery and import, subject to source terms, attribution,
  provenance, caching, and an explicit review-before-save workflow. See the
  [RepeaterBook integration investigation](docs/repeaterbook-integration.md).
- Better profile and bank previews for large collections.
- A broader documented radio/driver compatibility matrix.

## Later possibilities

- Direct radio programming through CHIRP's clone-out drivers.
- Route- and region-based travel profiles.
- Shared, importable frequency-set and profile libraries.
- Additional online frequency sources.
- Richer scan-list and bank semantics.
- Digital-radio and DMR extensions after the analog model is proven stable.

## Deliberately not planned

- Custom radio clone protocols that duplicate CHIRP.
- User accounts or required cloud services.
- Commercial licensing.
- Mobile applications.
- Collaborative editing or plugin marketplaces.

## Roadmap principles

1. RigManifest stores reusable operator intent; CHIRP owns radio drivers, image
   formats, target validation, and hardware communication.
2. Frequency definitions remain independent of the current radio inventory.
3. Advisory data may warn but must not block a compatible compilation.
4. Source images are immutable; every generated image is a new managed version.
5. Unsupported or unsafe intent is explained, never silently coerced.
6. New external data enters the catalog through a reviewable, provenance-preserving
   import boundary.
