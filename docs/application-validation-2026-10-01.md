# Application validation: Zarafshan campaign

This record describes independently reviewed application checks completed by
1 October 2026. It complements the [assessment crosswalk](assessment.md) with
longer records, saved simulator outputs and adverse evidence cases. Passing
means the declared software behavior was reproduced, not that Fishy validated a
basin, ecological method or legal duty.

The tested source revisions were:

| Component | Revision |
|---|---|
| Fishy | `881660e8901987d63d89caf61ef0d30991000301` |
| Taqsim | `54c00a8784704dd12ef74de38cd5bb881df30f6d` |
| Incidence | `665da4e0d81ab28921b8d5d2edbb9be27f4ec612` |

These are historical campaign pins, not a replacement for this repository's
dependency lock or evidence that later revisions behave identically. Evidence
IDs below resolve in the [selected evidence excerpt](evidence/application-validation-2026-10-01.json).
Counts overlap across applications and saved-output reuse; do not sum them as
independent tests.

## What the applications established

**Pulse diagnostics (F09).** The 2010–2023 Ravatkhoza record has 5,113 daily
values. Original and perturbed histories, plus engineered boundary cases, produced
256 pulse comparisons across eight scenarios. An independent state-machine scan
reconstructed all results, including null/reason states. Cases covered leap day,
cross-year events, equality plateaus, initially active events and terminal-event
warnings; gaps and nulls were refused. This closes the earlier application's 224
unchecked pulse rows. It does not establish natural-reference suitability or
ecological condition from descriptive indicators alone.

**Saved Taqsim interoperability (F15).** Eight public-model applications on
separate reduced reservoir systems included multi-year histories: 4,628
overlapping case-days yielded 9,256 Fishy comparisons. Loaded saved runs repeated
the same comparisons exactly. These are delivery assessments of physical
projections; loading is neither restart nor replay. The applications do not
demonstrate full-basin or large SWAT+ performance.

**Missing chemistry (F12).** Fourteen saved native transport cases passed 1,088
independent constituent-day comparisons without rerunning water. Dry, missing
and unsupported evidence remained distinct. A known quality failure survived a
missing second constituent, with incomplete support retained. Limits and chemistry
were hypothetical. Daily volume-weighted concentrations do not establish
instantaneous maxima; see [quality operations](quality.md).

**Thermal evidence (F13).** Four external sensible-heat scenarios used a completed
92-day, five-node corridor. Independent reconstruction checked conservation,
mixing and delayed parcels. All 368 daily-mean thermal-movement assessments
remained unknown for an extrema-dependent criterion. Four separate supplied
extrema/access controls returned one pass, two failures and one unknown.
This is synthetic external heat accounting, excluding weather, latent heat,
stratification and feedback on water—not native or calibrated thermal physics.

## Snow trout: published habitat versus synthetic timing

[Hayes et al.](https://doi.org/10.1007/s13762-025-06761-2) and the associated
[habitat supplement](https://doi.org/10.5281/zenodo.14887129) supplied reported
habitat values and a seasonal flow schedule (F18). Four rounded mean habitat
retention points were imported exactly. Ten unsupported-input controls and a
hypothetical 366-day delivery ledger were checked independently; the ledger had
64 shortfall days totaling 920,160 m³. This does not reproduce CASiMiR hydraulics
or calibrate a Zarafshan fish response.

Juvenile, subadult and adult habitat classes do not supply daily spawning
chronology. Six explicitly labelled synthetic observer fixtures therefore tested
the [daily-stage pathway](spawning.md) across leap day, New Year and shifted
onsets: 270 coefficient/volume checks and 2,430 adverse-control daily checks,
including 822 correctly unsupported days. `OBSERVED` denotes the daily-flow role
inside the test double; it is not field authenticity. Biological timing was
invented, and the original Fishy Kazakhstan catalogue coefficients were retained
as such—not relabelled snow trout coefficients.

## Remaining gate and evidence access

The continuous 92-day full-basin retry timed out after approximately 7,200 seconds
before a water result (F20). Full-basin thermal and Fishy assessment were not
reached; [Incidence issue 28](https://github.com/hydrosolutions/incidence/issues/28)
tracks that blocker. Reduced applications do not clear it.

The excerpt preserves selected result/review fields, original source identifiers
and SHA-256 hashes, plus evidence-archive identities. It is not the complete
reproduction harness: raw data, scripts and full reviews remain in the named
campaign archives held by the campaign authors. No public archive download is
asserted. Request those archives before attempting a full independent rerun.
