# Shared hydraulic assessment

`fishy.hydraulics` assesses supplied states and discrete transitions. It does not
select ecological thresholds, run a hydraulic model, or certify sanitary compliance.
Use `assess_state_range`, `assess_discrete_rate`, `assess_imported_hydraulics`, and
`assess_hydraulics`. Existing imports from `fishy.sanitary_hydraulics` remain available;
`assess_sanitary_rate` is the same discrete operator.

Run the public caller example:

```console
uv run python examples/hydraulic_assessment.py
# pass complete
```

The example assesses a supplied depth interval [0.4, 0.5] m against a selected
minimum 0.3 m. Change the state to [0.2, 0.2] to fail. Change it to [0.25, 0.35]
to leave the test indeterminate. These are synthetic settings, not policy defaults.

## Input and output meaning

- `HydraulicScope` retains component, physical location, spatial domain, candidate,
  scenario, variable, units, interval, datum/bed/direction reference and time support.
  Local and section-mean velocities are distinct variables. Datum-relative stage
  and directional velocities may be negative. Depth, speed and release discharge may not.
- `StateCriterion` has signed lower/upper limits with separate strictness.
  `RateCriterion` has separate nonnegative rise/fall magnitudes in variable units/hour.
  Intentionally absent bounds differ from missing required bounds. Empty targets do not pass.
- `HydraulicState` preserves present zero, missing, outside-horizon and unsupported
  presence. Supported closed `StateBounds` are not confidence intervals.
- `HydraulicRelationEvidence` retains geometry/version, boundary conditions, valid
  domain, interpolation, uncertainty and intended-use acceptance. The supplier must
  establish relation-domain applicability, including backwater/hysteresis/changing
  geometry where relevant. No relation interpolation or extrapolation is performed.
- A discrete transition uses the exact UTC timestamp pair in `scope.period`.
  `TemporalSupport` states whether these are endpoints or interval means.
  Expected gaps and missing predecessors prevent bridging; seasonal applicability
  must cover the whole transition. No periodic wrapping or invented subdivision occurs.
- The rate result retains change bounds, elapsed hours and conservative rate bounds.
  Supported joint error evidence can tighten bounds. Endpoints cannot prove unseen
  peaks, and daily means cannot prove within-day conditions.
- Native results retain numerical findings and separate `permission` for scientific
  use. `assess_hydraulics` admits only permitted supported findings to the joint
  result. Unsupported numeric output remains inspectable, not a supported failure/pass.
  Official admissibility remains in the original evidence and is never promoted.
- Joint assessment requires exactly the same candidate, scenario, reference member,
  configuration version, location and period. Independent specialist source, data and
  software revisions may differ and remain attached to each component.
  It retains all original component results. A required failure survives unknowns as
  failure with incomplete coverage. Missing components and empty required sets do not pass.
  Criterion identity includes all scope fields; no discharge-to-stage substitution is allowed.
- A current-continuity or other qualitative duty needs an attributable specialist
  finding on its exact domain, or remains missing. Positive flow is not a continuity test.

## Acceptance crosswalk

Source: approved bundle `fishy_taqsim_handover_candidate_2026-09-19`,
`report_snapshot/part4_hydraulic_assessment.qmd`, D.9 `sec-hydraulic-assessment`.
SHA-256: `8dcd61476b7b9170de71ab912e2ad05d97822c71cda7262f73d8cb6aa64aa6a8`.
Held suite: `report_snapshot/quality_support/hydraulic_assessment_fixtures.json`,
SHA-256 `2169b7362cebcb047dc3ae4e578a6249a5a53ff709109581257350568606d6b8`.
This crosswalk and the tests are derived implementation evidence, not report copies.
All 18 case meanings are represented in `tests/test_hydraulics.py`.
`UNKNOWN` represents unassessed/indeterminate findings; reasons and numerical bounds
preserve the distinction. Fractions and elapsed microseconds are exact: tolerance is zero.

| Held case / D.9 requirement | Public operation and input | Actual = expected observable | Executed test |
|---|---|---|---|
| `rise_exceeds_limit` | assess_discrete_rate: 1→1.12 m / 0.5 h, rise .20 | rate .24 m/h, FAIL | `test_held_rate[rise_exceeds_limit]` |
| `fall_uses_distinct_limit` | assess_discrete_rate: 1.12→1 m / 0.5 h, fall .30 | rate −.24 m/h, PASS | `test_held_rate[fall_uses_distinct_limit]` |
| `inclusive_equality_pass` | assess_discrete_rate: 1→1.10 m / .5 h, rise .20 inclusive | rate .20, PASS | `test_held_rate[inclusive_equality_pass]` |
| `strict_equality_fail` | same, strict rise | rate .20, FAIL | `test_held_rate[strict_equality_fail]` |
| `irregular_supported_elapsed_time` | assess_discrete_rate: .09 m / .75 h, adjacent | rate .12, PASS | `test_held_rate[irregular_supported_elapsed_time]` |
| `uncertainty_overlap` | assess_discrete_rate: [1,1.02]→[1.07,1.09], .5 h; rise .15 | [.10,.18], UNKNOWN | `test_held_rate[uncertainty_overlap]` |
| `uncertainty_disjoint` | assess_discrete_rate: [1,1.02]→[1.13,1.15], .5 h; rise .15 | [.22,.30], FAIL | `test_held_rate[uncertainty_disjoint]` |
| `uncertainty_contained` | assess_discrete_rate: [1,1.02]→[1.04,1.05], .5 h; rise .15 | [.04,.10], PASS | `test_held_rate[uncertainty_contained]` |
| `known_missing_interval_not_bridged` | assess_discrete_rate: endpoints 0,2 h with expected gap | UNKNOWN, no rate, incomplete | `test_known_missing_interval_not_bridged` |
| `missing_predecessor` | assess_discrete_rate: previous absent | UNKNOWN, no rate, incomplete | `test_missing_predecessor` |
| `daily_means_do_not_test_hourly_peak` | assess_discrete_rate: daily 1→1; within-day requirement | daily change 0; peak UNKNOWN | `test_daily_means_do_not_test_hourly_peak` |
| `discharge_not_downstream_stage` | assess_imported_hydraulics: discharge pass requested as stage; assess_hydraulics missing stage | stage UNKNOWN; joint UNKNOWN/incomplete | `test_discharge_not_downstream_stage` |
| `known_velocity_failure_with_uncertain_depth` | assess_state_range + assess_hydraulics: depth [.25,.35] ≥.30; speed .80 ≤.60 | depth UNKNOWN; velocity FAIL; joint FAIL/incomplete | `test_known_velocity_failure_with_uncertain_depth` |
| `qualitative_duty_has_no_numeric_limit` | assess_discrete_rate: required magnitudes missing | UNKNOWN; no invented limit | `test_qualitative_duty_has_no_numeric_limit` |
| `relation_outside_supported_domain` | assess_state_range: depth .5 ≥.3 from flow 6, valid domain 0..5 | exploratory PASS; supported UNKNOWN | `test_relation_outside_supported_domain` |
| `season_boundary_criterion_missing` | assess_discrete_rate: unresolved seasonal applicability | UNKNOWN; no intermediate state/rate | `test_season_boundary_criterion_missing` |
| `invalid_zero_elapsed_time` | Interval: identical timestamps | ValueError: positive elapsed duration | `test_invalid_zero_elapsed_time` |
| `invalid_negative_rate_magnitude` | RateBound: −.1 | ValueError: nonnegative magnitude | `test_invalid_negative_rate_magnitude` |

Additional executed tests cover scientific rejection, lossless directional coverage,
missing bounds, exact scoped identity, signed states, strict empty ranges, local versus
section-mean velocity, duplicate components, presence states and the public example.
Sanitary regression tests exercise supported specialist continuity findings, warm-up
exclusions, tighter joint-error bounds, invalid/nonfinite inputs and scalar-transfer refusal.

## Reproduction and compatibility

Implementation baseline: Fishy `e02d43c9ed35eefd377b61f7ec201a6005843b06`.
The unchanged lockfile pins optional Taqsim `396ad093c2b6f240e702a3b05aee1fb96a69b3f7`
and Incidence `665da4e0d81ab28921b8d5d2edbb9be27f4ec612`.
Shared hydraulic operations and the example run without either simulator dependency.

```console
uv run pytest tests/test_hydraulics.py tests/test_sanitary_hydraulics.py tests/test_sanitary_duties.py tests/test_sanitary_profile.py
uv run --all-extras pytest
uv run --all-extras ty check
uv run ruff check
```

No thresholds are inherited from Order 179 or foreign methods. No final Uzbek
assembly, hydraulic inversion, ecological target selection or release permission is supplied.

Failure-first regressions exercised the actual public path before each repair:
reference-member scope/provenance disagreement, joint member/configuration mixing,
and collisions between caller component names and internal coverage labels.
No input is renamed to avoid these collisions. Aggregate check IDs now encode the
component label and unique ordinal; full directional/bound findings remain in `components`.
