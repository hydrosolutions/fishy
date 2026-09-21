# Build a daily design pattern

Use `construct_pattern` to distribute a receiving annual mean over a complete
design year using equal-weight analogue years. Annual magnitude and daily shape
are separate products. A calculated schedule is not an accepted requirement.

Run the complete synthetic example:

```console
uv run python examples/daily_patterns.py
```

It constructs two complete 2019 donor years, uses their full 2018–2019 annual
references for membership, and applies a receiving annual mean of 8 m³/s once.
The output has 365 daily intervals and volume 252,288,000 m³. The example also
shows a failed cluster-support requirement and a supported-format pattern import.
None of these illustrative records supplies scientific certification.

## Prepare complete records

A `DailyReferenceYear` contains an `AccountingYear`, a tuple of `FlowSample`
records, a climate-cluster identifier and quality checks. Each fixed-offset day
must be present, complete and identified as natural-reference data. Missing days
cannot become zero. Keep reconstructed records and their evidence attributable.

An `AnalogueReference` links those daily years to the source's **full** accepted
`AnnualReference`. Daily annual means must match the annual observations exactly.
The annual reference can contain additional years that are not daily shape
candidates. The [calendar guide](pattern_calendar.md) explains fixed offsets and
month-conservative leap mapping.

The example uses these first daily flows, followed by genuine zeros through the
rest of each 365-day year:

| Donor | First four daily flows, m³/s | Normalised first four volume shares |
|---|---|---|
| A | 1, 1, 2, 0 | 1/4, 1/4, 1/2, 0 |
| B | 20, 20, 0, 0 | 1/2, 1/2, 0, 0 |

Their mean shares are 3/8, 3/8, 1/4, 0. Because this is a real 365-day year,
not a four-slot calendar, the mean-one shape is **365 times** those shares,
with zeros on the remaining days. Receiving discharge is 8 times that shape.
Donor B's larger annual volume does not increase its weight.

## Declare membership and support

Supply a `PatternProfile` before construction. It names the target probability,
closed band, estimator, reference member, scenario, climate basis, eligible
donors, support counts, alignment settings, scientific acceptance profile and
an explicit `reference_period`. This frozen interval must contain every source's
full annual reference period, not only its selected daily years. It may differ
from the receiving annual reference period. Sources outside it are refused.
These are study inputs, not national defaults.

- `MembershipEstimator.EMPIRICAL` calculates Weibull membership from all annual
  observations in each source reference. Tied years retain their observations
  and receive the mean tied rank probability.
- `MembershipEstimator.FITTED` fits the specified stationary zero-mixture
  lognormal to that same full annual reference. It requires at least two
  positive observations and positive log standard deviation. It is not selected
  automatically because empirical tail support is weak.
- `MembershipEstimator.IMPORTED` requires an `ImportedMembership` with a
  probability for **every** accepted annual observation, including zeros, and
  a reproducible equation, calibration, diagnostics, uncertainty and provenance.

Membership uses annual **mean flow**, not volume ranks across unequal year
lengths. Probabilities are calculated before the daily candidate subset and
before band selection. The closed band retains ties at its edges. Zero years
stay in annual statistics but cannot provide positive-target shapes.

In the example, each donor has a wetter 2018 annual observation and a dry 2019
observation. The dry years each have probability 2/3, although only those years
are supplied as daily candidates. A target of 2/3 with band zero selects both.
They belong to one climate cluster, not two independent drought events.

Increasing the profile's required cluster count from one to two makes support
fail. The numerical candidate stays visible. The band remains zero: Fishy does
not widen it, replace the class or manufacture extra climate years. Inspect
`membership`, `support`, `exclusions` and `use_checks`, not only `samples`.
Shape extrapolation is reported separately when the target lies outside the
selected probability range.

## Choose calendar averaging or melt alignment

`AlignmentChoice.CALENDAR` maps each source year conservatively onto the receiving
calendar, normalises it and averages the fixed contributor set equally.
`AlignmentChoice.MELT` uses the configured half-volume season and maximum shift.

Melt alignment removes over-limit, unsupported-edge and zero-retained-volume
contributions simultaneously. It then recomputes the median until stable without
reinstating excluded contributors. Missing adjacent data is not wrapped or
zero-filled. Needed adjacent years use the original selected year's total as
their scale. Each retained contribution is normalised separately before averaging.

A boundary-crossing melt season or inadequate aligned support produces an
attributable calendar fallback on the original eligible set. That fallback
changes alignment only. It cannot repair missing donor eligibility, insufficient
climate clusters or unsupported rare-tail evidence.

Inspect each contribution's `mapped_shares`, `retained_shares`, marker, shift and
introduced/displaced shares. Exclusions identify their source year and iteration.
The same retained contributors apply to every design day.

## Keep numerical results separate from permission

The example deliberately supplies no scientific assessment. Its numerical
support passes, but its scientific-use checks are `unknown`. Requiring a second
climate cluster produces a known support failure while retaining the numbers.
The imported round-trip also remains scientifically unresolved.

For supported accepted or indicative use, supply independently evaluated
`ScientificAssessment` records matching the exact annual and daily products.
`annual_magnitude_product` and `pattern_product` build those product identities.
See `examples/scientific_use.py` for the separate assessment workflow when using
the scientific-use component. A narrower indicative use needs its own justified
scope and restrictions; it is not an automatic label for missing evidence.

An accepted zero annual target can return a zero schedule without positive
analogue membership or a fabricated mean-one shape. An unsupported numerical
zero cannot take that exception. Annual acceptance never establishes daily
shape or rare-tail acceptance. Rating restrictions and known scientific failures
remain controlling.

The method-development limitation remains explicit: all 21 dry held-out cases
in the retained two-US-record, 50-year-training comparison overestimated the
seven-day minimum. Those correlated development records are not naturalised
Uzbek evidence or independent rare-tail validation. Volume closure and successful
software tests do not remove that limitation.

## Import a supplied pattern without rescaling

`import_pattern` accepts the receiving `AnnualEstimate`, design calendar, complete
daily samples and `ImportedDerivation`. Include an equation, parameter estimation,
calibration data, diagnostics, extrapolation, uncertainty method and reproduction
reference. The example reimports its computed samples through this boundary.

The imported schedule keeps its daily provenance and values. Calendar, location,
member, coverage and annual mean must match. Wrong mean or incomplete daily
coverage is refused, not silently repaired. The result's method remains
`PatternMethod.IMPORTED`, rather than being relabelled as native construction.
An accepted import format does not independently validate an unseen model.

Construct median and rare-class patterns separately. `crossed_bounds` reports
strict daily crossings without clipping or sorting their ordinates. Annual
ordering does not guarantee pointwise ordering. Downstream baseline assembly,
duration-minimum safeguards and issuance remain separate operations.

## Acceptance crosswalk

The table links the synthetic required values to tests in
`tests/test_daily_patterns.py`, with calendar arithmetic in
`tests/test_pattern_calendar.py`. Expected numeric identities use exact
`Fraction` equality and **zero tolerance**. Status and refusal checks use exact
enum/reason or exception assertions. The runnable example has its own tests in
`tests/test_daily_pattern_example.py`. Execution results belong to the release
validation record; this table alone is not evidence of an executed pass.

| Requirement | Test / public operation | Required actual = expected |
|---|---|---|
| D1 band | `test_d1_closed_imported_band_uses_full_reference`; `construct_pattern` | .97 and .99 selected on closed .99 ± .02 band; centre .98; nearest distance 0 |
| D1 native empirical/ties | `test_d1_empirical_membership_precedes_daily_subset_and_retains_ties`; `construct_pattern` | Full annual values 40/20/20/10 give both daily 20-years membership .5 |
| D1 annual mean | `test_d1_annual_mean_not_volume_controls_membership_across_leap_years`; `construct_pattern` | Non-leap mean 1.001 selected over leap mean 1 despite lower total volume |
| D2 extrapolation | `test_d2_shape_extrapolation_is_independent_of_numeric_construction`; `construct_pattern` | Target .99 outside [.95,.97]; nearest distance .02; numerical candidate remains |
| D3 support | `test_d3_five_donors_do_not_manufacture_three_climate_clusters`; `construct_pattern` | Five source years, two clusters fail required three; band stays .02 |
| D4/D5 weights/scale | `test_d4_d5_equal_year_shares_and_scale_once_on_complete_year`; `construct_pattern` | Shares 3/8,3/8,1/4,0; shape 365 times shares; discharge 8 times shape; volume 252288000 m³ |
| D6 mapping | `test_d6_complete_year_february_mapping_preserves_monthly_share`; `construct_pattern` | February shares 28/29,1/29; monthly and annual share sum 1; leap volume 252979200 m³ |
| D7 marker and D9 truncation | `test_d7_d9_real_year_alignment_renormalizes_each_truncated_contribution`; `construct_pattern` | Markers 100/104 days, shifts +2/−2; displaced shares 1/2 and 0; each retained share sum 1 |
| D7 plateau/fraction | `test_marker_first_plateau_boundary_fractional_day_and_absent_volume`; `half_volume_marker` | First plateau boundary day 1; fractional marker 5/3 days; zero season undefined |
| D8 simultaneous removal | `test_d8_simultaneous_exclusion_recompute_and_order_invariance`; `construct_pattern` | Markers 60/80/140 removed together; remaining 100/104/110 shift +4/0/−6; row order does not change result |
| D8 iterative removal | `test_d8_missing_context_recomputed_until_stable_without_reinstatement`; `construct_pattern` | Marker 100 removed iteration 1; 104 removed iteration 2; 108 survives with shift zero |
| D8 fallback | `test_d8_missing_shifted_edge_falls_back_without_wrapping`; `construct_pattern` | Missing edges exclude both aligned candidates; fallback retains original calendar set |
| D9 miniature witness | `test_d9_individual_renormalisation_before_averaging`; `normalize_shares` | Equal-year mean 5/8,1/8,1/8,1/8, not a raw-share weighted average |
| D10 zero | `test_d10_zero_source_stays_in_frequency_but_not_positive_shape`, `test_d10_unsupported_zero_target_cannot_claim_zero_exception`; `construct_pattern` | Zero source stays in annual population; no positive source yields unavailable; unaccepted zero does not yield schedule |
| D11 crossings | `test_d11_bounds_cross_without_clipping_or_sorting`; `crossed_bounds` | Two daily intervals cross despite lower annual mean; input schedule unchanged |
| D12 duration | `test_d12_real_calendar_volume`; `construct_pattern` | Mean 8 yields 252288000 / 252979200 m³ on 365 / 366 days |
| D13 refusal | `test_d13_*`; domain constructors and `construct_pattern` | Missing profile/import/eligibility attributable; invalid bands/flow, missing days, duplicates and mixed members refused |
| D14 crossing season | `test_d14_crossing_melt_season_uses_original_calendar_set`; `construct_pattern` | Calendar fallback equals original calendar shape, not a December/January median |
| Import | `test_supported_import_preserves_complete_schedule_and_never_rescales`, `test_import_refuses_wrong_mean_identity_and_coverage`; `import_pattern` | Exact schedule/shape/volume retained; wrong mean/member/coverage refused |
| Reader example | `test_daily_example_preserves_scale_support_and_import`, `test_daily_example_output` | Two years / one cluster; probabilities 2/3 each; mean 8; volume 252288000 m³; support failure retains numbers and no scientific pass |

## Source attribution

The governing package is `fishy_taqsim_handover_candidate_2026-09-19`.
The operators are the proposed Uzbek construction. They are not a new Kazakh
statutory method, a WMO-prescribed algorithm or adopted national policy.
This page derives implementation guidance without distributing private chapters.

| Source | SHA-256 | Scope |
|---|---|---|
| `report_snapshot/part4_design_patterns.qmd`, D.6 | `b95f62ed797f174df926462a154834077126dfd65e995f445b608ef1426ba56e` | Conditional selection, calendar mapping, alignment, fallback and equal-year scaling |
| `report_snapshot/part4_statistical_estimation.qmd`, D.7 | `10bb9e8feaaab5199575d1dbf0c2fd2a50c5867b5a55a92806294853c821a5df` | Full-reference empirical/fitted membership and attributable imports |
| `report_snapshot/part4_scientific_acceptance.qmd`, D.8 | `c09d0d3afbb1766638c93951432ba09408f28135d5e2765d5579fb81079c3bd6` | Separate product/use acceptance and restrictions |
| `evidence/design_pattern_acceptance.md`, D1–D14 | `43a88113eb2a9619817b7bcac7c157048bde035d7157ce2c08917eaf16dc63a7` | Software witnesses and deterministic exclusion checks |
