# US Amateur Frequency Practices

Status: reviewed baseline; national-plan editor suggestions implemented
Research date: 2026-08-19
Scope: United States amateur service, with emphasis on analog FM memories that a
CHIRP-oriented application is likely to compile. This document is not an operating
or licensing guide, and its conventions must not be generalized to other countries.

## Executive conclusions

1. A band edge, a band-plan segment, a tuning step, a coordinated frequency raster,
   and a repeater split are different facts. RigManifest must model them separately.
2. There is no single authoritative US table of repeater pairs. FCC rules define
   legal bounds; the ARRL publishes voluntary national recommendations; regional
   frequency coordinators publish the plan that matters for a particular location;
   an individual repeater record supplies the actual frequencies and access signal.
3. `500 kHz` is not a normal VHF tuning increment. It is a repeater split used in
   parts of some 6-meter plans. The familiar 2-meter repeater split is `600 kHz`.
   Typical coordinated FM rasters are measured in tens of kilohertz, not hundreds.
4. A radio's available tuning steps are device capabilities. They do not establish
   that every frequency reachable with a step is appropriate for every band segment.
5. CTCSS and DCS values are catalogs of encodings, not defaults by band. The access
   value is specific to a repeater or regional coordination and must not be inferred
   from a 2-meter or 70-centimeter frequency alone.
6. Store explicit receive and transmit intent in every frequency definition. Plan
   rules may suggest values while editing; they must not silently rewrite canonical
   user data.

## Vocabulary

This document uses **frequency definition**, never "channel," for RigManifest's
canonical RF intent. `Channel` is appropriate only where the underlying service is
actually channelized, a coordinator describes a frequency raster as channels, or a
radio/CHIRP memory interface uses that term.

- **Allocation:** frequencies on which FCC rules authorize an amateur station,
  subject to license-class, sharing, geographic, power, and emission restrictions.
- **Band plan:** a voluntary division of an allocation by expected operating use.
- **Frequency-coordination plan:** a regional plan used to reduce interference among
  repeaters and auxiliary stations.
- **Frequency raster:** an ordered grid of usable center frequencies. It needs an
  anchor and a spacing; spacing alone is insufficient.
- **Tuning step:** an increment the radio can use when tuning or representing a
  memory. This is a radio capability, not automatically a plan rule.
- **Repeater split:** the difference between the repeater input and output. For a
  user's memory, receive is normally the repeater output and transmit is the input.
- **Access signal:** CTCSS, DCS, or another signal required to open a repeater.

## Authority and precedence

Apply sources in this order, but do not confuse legal authority with practical
specificity:

1. **FCC rules.** Part 97 defines allocations, prohibited repeater sub-bands, emission
   constraints, and operating obligations. These are legal constraints.
2. **Documented repeater data.** A current record from the repeater operator or its
   coordinator is the best source for that repeater's output, input, and access
   parameters, provided it remains legal.
3. **Regional coordinator plan.** It is the best source for suggestions and validation
   within its geographic jurisdiction. FCC section 97.205(c) gives a coordinated
   repeater an interference-resolution advantage over an uncoordinated one.
4. **ARRL national band plan.** This is a useful voluntary baseline where no more
   specific regional plan is selected. ARRL itself says the plans are voluntary.
5. **Radio automatic-repeater-shift/default behavior.** This is a convenience feature,
   not evidence of a repeater's actual configuration.

FCC section 97.101 also requires good engineering and amateur practice, cooperation
in selecting transmitting frequencies, and recognizes no exclusive amateur
frequency assignment. ARRL does not coordinate repeaters itself; local or regional
coordinators do that work through voluntary participation.

## FCC allocation baseline

These are broad Region 2/US allocation bounds, not permission to use every mode at
every point and not frequency rasters:

| Band | Broad US allocation relevant here |
| --- | --- |
| 10 m | 28.000-29.700 MHz, with license-class and mode subdivisions |
| 6 m | 50.000-54.000 MHz |
| 2 m | 144.000-148.000 MHz |
| 1.25 m | 219.000-220.000 and 222.000-225.000 MHz |
| 70 cm | 420.000-450.000 MHz |
| 33 cm | 902.000-928.000 MHz |
| 23 cm | 1240.000-1300.000 MHz |

Section 97.205 does not permit repeaters in 28.000-29.500, 50.000-51.000,
144.000-144.500, 145.500-146.000, 222.000-222.150, 431.000-433.000, or
435.000-438.000 MHz. A band-plan suggestion must never override these exclusions.

LF, MF, and most HF amateur allocations are generally continuous operating ranges,
not channelized frequency grids. RigManifest should validate their legal bounds and
applicable emission rules without imposing one band-wide tuning raster.

### The current 60-meter exception

Do not encode the former US "five channels only" scheme as the current rule. As of
this research date, section 97.303 provides the 5351.5-5366.5 kHz segment plus four
discrete center frequencies: 5332.0, 5348.0, 5373.0, and 5405.0 kHz. On a discrete
frequency, a phone/data carrier is 1.5 kHz below the listed center while CW is at the
center; occupied bandwidth may not exceed 2.8 kHz. This is regulated special-case
data and should be represented as such, with an effective date and source revision.

## Analog FM repeater and raster conventions

The table below is an editing baseline, not a universal validator. The regional plan
and actual repeater record take precedence.

| Band | National or widespread pattern | Common user-memory split | Observed raster/spacing | Important exceptions |
| --- | --- | --- | --- | --- |
| 10 m | ARRL lists inputs 29.520-29.590, simplex calling at 29.600, and outputs 29.610-29.700 MHz | `-100 kHz` is the widespread pattern | `20 kHz` in SERA and WPRC plans | Verify regional pair list and the actual repeater |
| 6 m | ARRL lists paired input/output blocks within 51-54 MHz | Often `-500 kHz`; `-1 MHz` also appears regionally | Commonly `20 kHz` | SERA explicitly uses both 500 kHz and 1 MHz splits in different ranges, so one band default is wrong |
| 2 m | ARRL lists paired repeater blocks across 144.5-145.5 and 146-148 MHz | Usually `-600 kHz` below 147 MHz and `+600 kHz` at/above 147 MHz, according to the paired block | Commonly `15` or `20 kHz`; regional plans also use `10` and `12.5 kHz` | Wide/nonstandard pairs exist; simplex portions must not acquire an offset |
| 1.25 m | ARRL lists inputs 222.25-223.38 and outputs 223.85-224.98 MHz | Commonly `-1.6 MHz` | Commonly `20 kHz` | ARRL marks multiple segments as local coordinator options |
| 70 cm | Much of the ARRL plan is explicitly a local option | `5 MHz` magnitude is common, but sign depends on the regional input/output arrangement | `25 kHz` remains common; `12.5 kHz` narrow/interleaved assignments also occur | Kansas documents user `+5 MHz`; Southern Nevada documents user `-5 MHz`. Never infer sign from band alone |
| 33 cm | Current ARRL national plan pairs 902 MHz inputs with 927 MHz outputs | `-25 MHz` for those current pairs | `12.5 kHz` | Legacy regional plans also retain `-12 MHz` pairs on a `100 kHz` raster |
| 23 cm | ARRL pairs 1270-1276 inputs with 1282-1288 outputs | `-12 MHz` for that pair | `25 kHz` | A regional option pairs 1270-1274 inputs with 1290-1294 outputs, yielding `-20 MHz` |

### Two-meter detail

The national paired blocks explain the familiar sign convention when a user's radio
receives the repeater output:

| Repeater output range | Repeater input range | Suggested user transmit behavior |
| --- | --- | --- |
| 145.20-145.50 MHz | 144.60-144.90 MHz | `-600 kHz` |
| 146.61-146.97 MHz | 146.01-146.37 MHz | `-600 kHz` |
| 147.00-147.39 MHz | 147.60-147.99 MHz | `+600 kHz` |

The ARRL plan also places simplex operation in 146.40-146.58 and 147.42-147.57 MHz,
with 146.52 MHz as the national simplex calling frequency. The editor must therefore
match a specific plan segment; a crude test such as "2 meters below 147 gets minus"
would wrongly assign offsets to simplex frequencies.

SERA demonstrates why this remains a suggestion: its plan includes the ordinary
600 kHz pairs but also narrowband 1.4 MHz and 2.5 MHz wide-split pairs and several
rasters. An explicit repeater input/output pair must always win.

### Raster validation

A frequency raster is not correctly tested with `frequency_hz % spacing_hz == 0`.
Its definition needs an anchor:

```text
(frequency_hz - anchor_frequency_hz) % spacing_hz == 0
```

The anchor may be the first assignable center in a plan segment and need not be zero.
The validation also needs segment bounds, emission/mode applicability, effective
dates, and exceptions. It should say "not on the selected plan's normal raster," not
"invalid frequency," unless an actual regulatory rule makes the frequency illegal.

### Device steps are not plan rasters

The Kenwood TH-F6A manual illustrates the distinction. The radio offers 5, 6.25,
8.33 (air band), 9 (AM broadcast), 10, 12.5, 15, 20, 25, 30, 50, and 100 kHz steps.
Its US defaults differ by band, and it also has fine-tuning increments below 1 kHz
for some receive modes. The same manual supplies automatic repeater-offset defaults
of 600 kHz on 2 meters, 1.6 MHz on 1.25 meters, and 5 MHz on 70 centimeters.

Those facts describe what that radio can represent and what its firmware may suggest.
They do not turn a 5 kHz-capable radio into evidence that a regional coordinator uses
a 5 kHz repeater raster, nor do they make an automatic offset authoritative.

CHIRP likewise separates `valid_tuning_steps` from a memory's frequency and duplex
fields. Its common step catalog includes 5, 6.25, 10, 12.5, 15, 20, 25, 30, 50, 100,
125, and 200 kHz, while individual drivers advertise their actual subset.

## CTCSS and DCS access signals

### Rules for inference

- Do not choose a tone from the band, receive frequency, or offset.
- Prefer current repeater/operator or coordinator data.
- A regional tone plan is a geographic collision-avoidance convention, not proof of
  an individual repeater's setting.
- Model transmit access and receive squelch independently. A repeater may decode an
  input tone, encode a different output tone, encode no output tone, or use DCS.
- Preserve DCS polarity independently for transmit and receive where the target radio
  and CHIRP driver support it.

Regional examples reinforce this. SERA requires coordinated systems to use an access
method and discusses CTCSS as interference mitigation. Iowa and Wisconsin publish
geographic preferred-tone plans. These can aid data entry, but they are not US-wide
band defaults.

### CTCSS catalogs

A common 42-tone EIA-style set used by many amateur radios and coordinators is:

```text
67.0, 69.3, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8,
97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3,
131.8, 136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8,
179.9, 186.2, 192.8, 203.5, 206.5, 210.7, 218.1, 225.7, 229.1,
233.6, 241.8, 250.3, 254.1 Hz
```

CHIRP's cross-radio catalog contains 50 tones. In addition to that 42-tone set, it
contains:

```text
159.8, 165.5, 171.3, 177.3, 183.5, 189.9, 196.6, 199.5 Hz
```

The editor may visually prioritize the common 42, but its selectable values must be
filtered by the target radio's actual capabilities. For example, some manufacturer
specifications advertise 42 CTCSS tones while others advertise 50.

### CHIRP's common 104 DCS codes

Leading zeroes are significant for display and serialization:

```text
023 025 026 031 032 036 043 047 051 053 054 065 071 072 073 074
114 115 116 122 125 131 132 134 143 145 152 155 156 162 165 172
174 205 212 223 225 226 243 244 245 246 251 252 255 261 263 265
266 271 274 306 311 315 325 331 332 343 346 351 356 364 365 371
411 412 413 423 431 432 445 446 452 454 455 462 464 465 466 503
506 516 523 526 532 546 565 606 612 624 627 631 632 654 662 664
703 712 723 731 732 734 743 754
```

CHIRP also exposes cross modes such as tone-to-DCS and separate receive DCS values.
RigManifest therefore stores transmit access and receive squelch independently,
including direction-specific DCS polarity, and derives CHIRP's combined memory fields
only at the target boundary.

## RigManifest data-model recommendation

Do not add `default_step_hz`, `default_offset_hz`, or `default_tone` directly to a
band record. Introduce sourced plan data with geographic and temporal scope.

```text
RegulatoryAllocation
- id
- jurisdiction
- start_frequency_hz
- end_frequency_hz
- privileges_and_restrictions
- effective_from / effective_to?
- source

FrequencyPlan
- id
- authority_tier: NATIONAL_RECOMMENDATION | REGIONAL_COORDINATOR
- jurisdiction_or_region
- effective_from / reviewed_at
- source

FrequencyPlanSegment
- frequency_plan_id
- start_frequency_hz
- end_frequency_hz
- use: SIMPLEX | REPEATER_INPUT | REPEATER_OUTPUT | WEAK_SIGNAL | ...
- modes[]
- raster_anchor_hz?
- raster_spacing_hz?
- paired_segment_id?
- pairing_delta_hz?
- notes / exceptions[]

RadioCapabilities
- valid_tuning_steps_hz[]
- valid_ctcss_tones_hz[]
- valid_dcs_codes[]
- supported_access_modes[]
- supports_separate_tx_rx_access
- supports_dcs_polarity
- supports_automatic_repeater_shift

FrequencyDefinition
- receive_frequency_hz
- transmit_behavior
- transmit_frequency_hz?       # canonical for split; derivable display for offset
- offset_hz?
- transmit_access
- receive_squelch
```

The radio-capability fields above should be extracted from the pinned CHIRP driver,
not maintained as a parallel RigManifest catalog. Sourced overlays remain necessary
only for facts `RadioFeatures` cannot express, such as separate transmit limits when
a driver publishes one wide receive/programmable range. Frequency-plan segments and
regulatory allocations remain RigManifest data because they describe operating
practice and jurisdiction rather than radio hardware capability.

Each plan or regulatory fact should retain:

- source URL and document revision;
- jurisdiction/coverage geometry or region identifier;
- authority tier;
- effective and last-reviewed dates;
- whether the fact is exact, inferred from a paired range, or only a conventional
  suggestion;
- exceptions and conflicting-plan notes.

### Suggested editor behavior

1. The user enters or imports the repeater output frequency and selects a location or
   frequency plan.
2. RigManifest identifies the most specific matching output segment.
3. It suggests the paired transmit frequency, offset display, normal raster, and
   expected modes with a visible source label.
4. The user may accept or override the suggestion. An override remains explicit and
   may receive a warning, not automatic correction.
5. The user enters the documented access signal; no tone is auto-selected merely
   because the plan lists a preferred regional tone.
6. At compile time, the target radio capability model decides whether the exact
   frequency, tuning step, duplex form, tone/cross mode, code, and polarity can be
   represented. Any transformation or omission becomes a structured diagnostic.

Suggested precedence for a field is:

```text
explicit frequency definition
    > imported verified repeater record
    > selected regional coordination-plan suggestion
    > ARRL national-plan suggestion
    > target radio automatic/default behavior
```

No lower layer silently overwrites a higher one.

## What should and should not be enforced

Hard errors are appropriate for facts such as:

- outside a target radio's receive or transmit capability;
- outside a legally selected allocation/privilege where RigManifest has enough
  context to make that determination;
- a tone/code/step the target radio cannot represent;
- a transmit frequency present despite explicit receive-only intent.

Warnings or sourced suggestions are more appropriate for:

- off the selected coordinator plan's normal raster;
- nonstandard repeater split;
- frequency in a segment recommended for another use;
- absent or unusual access parameters;
- conflict between national and regional plans;
- radio automatic-shift behavior differing from explicit intent.

Do not impose a raster on continuous HF, weak-signal, experimental, satellite, or
other nonchannelized activity merely because a radio happens to tune in fixed steps.

## Review questions before implementation

The first implementation decisions are: ARRL national plan only, advisory checking
only, independent transmit/receive signaling now, and no repeater-directory import
in this slice. Regional-plan selection remains future work and will use the same
source/segment schema.

1. Should the first implementation support one selected regional plan per profile,
   or resolve plans from a saved station/location?
2. Should plan checking initially be advisory only, leaving regulatory legality
   checks for a later licensing/location feature?
3. Do we want the full transmit-access/receive-squelch model now, or introduce it in
   a migration after the shared catalog UI stabilizes?
4. Should imported repeater-directory facts be stored as user-owned definitions with
   provenance, given that licensed online data integrations are outside the MVP?
5. Which coordinator regions should be first-class fixtures after the national
   baseline: the user's home region plus one deliberately conflicting region would
   be enough to test precedence and offset-sign behavior.

## Primary sources

All sources were accessed 2026-08-19.

### Regulations and national guidance

- [47 CFR 97.101, General standards](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-B/section-97.101)
- [47 CFR 97.205, Repeater station](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-C/section-97.205)
- [47 CFR 97.301, Authorized frequency bands](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-D/section-97.301)
- [47 CFR 97.303, Frequency sharing requirements](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-D/section-97.303)
- [47 CFR 97.305, Authorized emission types](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-D/section-97.305)
- [47 CFR 97.307, Emission standards](https://www.ecfr.gov/current/title-47/chapter-I/subchapter-D/part-97/subpart-D/section-97.307)
- [ARRL national band plan](https://www.arrl.org/band-plan)
- [ARRL frequency coordinators](https://www.arrl.org/frequency-coordinators)
- [ARRL Standing Orders, including band-plan precedence](https://www.arrl.org/files/file/2024%20Director%20Workbook/1_2%20Standing%20Orders%202024-01-20%20Topic.pdf)

### Regional coordination examples

- [SERA 2024 Coordination Policies and Guidelines](https://sera.org/wp-content/uploads/2024/07/SERA-CPG-Rev-06-09-2024.pdf)
- [SERA frequency utilization plans](https://sera.org/frequency-coordination/frequency-utilization-plans-revision-band-plans/)
- [SERA 902 MHz plan, including current and legacy pairs](https://sera.org/wp-content/uploads/2016/11/sera-fup-900.pdf)
- [Kansas 2-meter frequency-use plan](https://kansasrepeater.org/kansas-2-meter-repeater-frequency-use-plan/)
- [Kansas 70-centimeter frequency-use plan](https://kansasrepeater.org/kansas-70-cm-repeater-frequency-use-plan/)
- [Southern Nevada band plan](https://snrc.us/band-plan/)
- [Western Pennsylvania coordination policies](https://www.wprcinfo.org/coord.htm)
- [SERA explanation of CTCSS](https://sera.org/frequency-coordination/what-is-ctcss/)
- [Iowa Repeater Council tone plan](https://iowarepeater.org/tone-plan/)
- [Wisconsin Association of Repeaters coordination instructions](https://wi-repeaters.org/forms/coordination_form_instructions.pdf)
- [Connecticut Spectrum Management Association CTCSS table](https://www.ctspectrum.com/other/ctcss-pl-tones)

### Radio and software behavior

- [CHIRP common model constants and feature fields](https://github.com/kk7ds/chirp/blob/master/chirp/chirp_common.py)
- [Kenwood TH-F6A/TH-F7E instruction manual](https://kasc.kenwood.com/files/prod/268/5/TH-F7-English.pdf)
- [Kenwood TM-281A specifications](https://www.kenwood.com/ca/com/amateur/tm-281a/)
- [Kenwood TH-K20A specifications](https://www.kenwood.com/ca/com/amateur/th-k20a/)
- [Yaesu FT-257 product specifications](https://www.yaesu.com/product-detail.aspx?CatName=Legacy&Model=FT-257)
