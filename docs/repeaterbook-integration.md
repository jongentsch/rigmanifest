# RepeaterBook Integration Investigation

Status: design investigation, reviewed 2026-08-19. No RepeaterBook network access is
implemented in RigManifest yet.

## Summary

CHIRP already provides a useful headless RepeaterBook query source. RigManifest can
reuse its conversion from RepeaterBook records to normalized CHIRP memories, then pass
reviewed selections through the same definition-import boundary used by CSV and IMG
imports.

The integration should not ship until access and storage permission are confirmed.
RepeaterBook's current API policy requires approval for distributed applications,
uses per-user application-bound tokens for approved desktop applications, and asks
applicants to disclose storage, caching, export, and redistribution behavior.
RigManifest intentionally keeps selected definitions in a long-lived local catalog,
so that behavior must be part of the approval rather than treated as transient search.

## What CHIRP currently provides

The pinned CHIRP revision exposes `chirp.sources.repeaterbook.RepeaterBook`, an
immutable `NetworkResultRadio`. Its `do_fetch()` method accepts a query dictionary and
produces ordinary `chirp_common.Memory` or `DVMemory` objects.

The CHIRP query supports:

- country and state/province;
- Amateur or United States GMRS service;
- optional latitude, longitude, and distance;
- free-text matching across location, callsign, landmark, region, and notes;
- band and mode filters;
- open-repeaters-only filtering;
- FM, D-STAR, DMR, and System Fusion modes;
- optional conversion of dual-mode digital repeaters to analog FM; and
- proximity searches that merge previously cached neighboring areas.

CHIRP excludes records not marked `On-air`, sorts by calculated distance when
coordinates are supplied, and assigns sequential result locations after filtering.

Its record conversion maps:

- `Frequency` to receive frequency;
- `Input Freq` to transmit-disabled, offset, or split behavior;
- `PL` and `TSQ` to independent transmit and receive CTCSS/DCS signaling;
- analog, D-STAR, DMR, and System Fusion flags to CHIRP mode;
- landmark or callsign to the memory label; and
- callsign, locality, use, and notes to the memory comment.

This is a strong match for RigManifest's target-independent signaling and transmit
model. The existing CHIRP-memory import conversion can remain the normalization point.

## CHIRP's network and cache behavior

Since March 2026, CHIRP has fetched compressed regional datasets from
`data.chirpmyradio.com` instead of calling the RepeaterBook API directly. CHIRP's
stated reason was to reduce load on RepeaterBook and improve query performance.

The pinned implementation:

- partitions data by service, country, and state/region to stay below a 3,500-result
  source limit;
- stores regional JSON caches for 30 days;
- uses ETags to avoid downloading unchanged data;
- falls back to stale cached data when the proxy is unavailable; and
- can merge previously cached regions for a cross-border proximity search.

Calling this class directly would place its cache in CHIRP's platform configuration
directory. That conflicts with RigManifest's portable guarantee that application data
lives beside the portable application. Any implementation must explicitly redirect or
wrap the cache boundary so it stays inside the active RigManifest workspace.

## RepeaterBook access and data-use constraints

RepeaterBook's policy, effective March 2026, says:

- API access is restricted to approved clients;
- non-commercial access may be approved without charge but remains discretionary;
- distributed desktop applications must not embed one shared application token;
- each user instead generates an application-bound RepeaterBook token for an approved
  application;
- a valid, approved User-Agent is still required;
- rate limits are unpublished and authorization/rate-limit failures must not be
  blindly retried; and
- bulk extraction, mirroring, redistribution, offline bundling, secondary API use,
  or building another repeater directory requires written permission.

Attribution is required. The policy specifies “Data courtesy of RepeaterBook.com,”
and recommends linking to the relevant detail page when practical.

CHIRP's proxy arrangement does not automatically establish that another application
embedding CHIRP may use the proxy for a separate persistent catalog workflow. Before
implementation, the project should obtain written guidance from both RepeaterBook and
the CHIRP maintainers about whether RigManifest may consume that proxy or should use
RepeaterBook's approved per-user-token path directly.

## Recommended RigManifest workflow

RepeaterBook should be a discovery source, not a background catalog authority.

```text
User query
    -> transient RepeaterBook results
    -> review, filter, and edit
    -> explicitly selected records
    -> user-owned frequency definitions + one user-owned set
```

The UI should show source attribution and let the user choose individual records. No
query should silently populate or rewrite existing definitions. A later refresh should
produce a reviewable diff rather than mutating the catalog automatically.

### Required architecture work

1. Add a provider-neutral external-source query interface in the Python core.
2. Wrap CHIRP's RepeaterBook source behind that interface if permission allows.
3. Return transient candidate records over IPC; do not model search results as saved
   frequency definitions until the user accepts them.
4. Add structured provenance linked to a definition: provider, external record ID,
   detail URL, retrieval time, source update time when available, coordinates, and a
   source-data hash. The current definition model has only free-form notes, while
   source metadata exists only at the set level; that is insufficient for reliable
   refresh and duplicate detection.
5. Store only the minimum approved cache and provenance data in the active workspace.
   Do not bundle RepeaterBook datasets with releases.
6. Keep application-bound tokens outside ordinary catalog exports and avoid logging or
   exposing them through IPC diagnostics.
7. Test conversion with checked-in synthetic fixtures. Live RepeaterBook access must
   not be required by CI.

## Suggested delivery sequence

1. Request RepeaterBook approval and clarify use of CHIRP's proxy with CHIRP.
2. Add the structured external-provenance model and migration.
3. Build a headless CHIRP RepeaterBook spike using synthetic/cached data only.
4. Add query and preview IPC contracts.
5. Add a Frequency Library discovery/import interface with explicit selection.
6. Add manual refresh and diff after the one-time import workflow is stable.

## Sources

- [Pinned CHIRP RepeaterBook source](https://github.com/kk7ds/chirp/blob/fa27a491d275f88b452d0488a51b4c85d4f7062a/chirp/sources/repeaterbook.py)
- [CHIRP external-database documentation](https://www.chirpmyradio.com/projects/chirp/wiki/ExternalDatabases)
- [CHIRP commit moving RepeaterBook to its cached proxy](https://github.com/kk7ds/chirp/commit/2cd274dae9c1770f6aa652dc0cb7a6b498a6cfc1)
- [CHIRP cache reliability commit](https://github.com/kk7ds/chirp/commit/f5d57bd5784b85f9a37e316064d508bad5a70d2b)
- [RepeaterBook API and data-use policy](https://www.repeaterbook.com/wiki/doku.php?id=api)
