# Supplied ecological conditions

`fishy.ecological_conditions` assesses supported numerical and categorical study
inputs. It does not solve hydraulics, oxygen, temperature or fish behaviour.
Use it independently of a simulator or Uzbek method operands.

Run the complete synthetic example:

```sh
uv run python examples/ecological_conditions.py
uv run pytest -q tests/test_ecological_conditions.py
```

## Supply one identified study

1. Create `EcologicalScope` with the exact `Location`, `Interval`, `Provenance`,
   product, intended use and source version. Location includes section, reach,
   water-body and mapping revisions. Provenance includes scenario, reference,
   data, configuration and software versions.
2. Create `EvidenceFindings` using `scope.evidence_scope` and the same provenance.
   Scientific adequacy and official admissibility are separate supplied findings.
3. Create `EcologicalStudy` with that scope and findings. Identify the relation
   and criteria source. All operands supplied in a call belong to this study.
   This is an explicit caller assertion, not automatic study validation.
4. Select the actual temporal support. `INTERVAL_ENVELOPE` asserts supported
   interval extrema, durations and states. `ENDPOINTS` supports endpoint-average
   level rates only. `INTERVAL_MEAN` supports the monthly recommendation only.
5. Call the applicable named assessments. Retain each result and its diagnostics.

A study cannot transfer to another section, mapping, period, source version or
production version. Missing or mismatched studies and invalid numerical support
return unknown numerical checks. Warm-up periods are excluded. Scientific
rejection or a prohibited use does not erase an otherwise valid numerical
comparison: inspect `scientific_use` separately. Numerical success never changes
`study.findings.official_admissibility`.

Known failures survive missing other conditions and retain incomplete coverage.
A pass means only that the supplied operands meet the supplied criteria for that
operation. It is not a complete Order 179 assessment or a daily delivery regime.
The caller must retain all applicable required operations, including incomplete
ones. No flow-only pass establishes unassessed physical or biological conditions.

## Operations and source crosswalk

Authority: held Russian Ministry Order 179-НҚ (2025), methodology paragraphs
17(3), 24, 28–32. PDF page 10 contains paragraphs 28–32(1); page 11 continues
32(2)–(4). The locally supplied original layout was inspected. No private report
or source document is reproduced here. Source currency and applicable dates
remain caller evidence.

| Clause | Public operation and supplied inputs | Observable result / test |
|---|---|---|
| 17(3), 24, 31 | `assess_level_change`: signed endpoint stages, separate `LevelRate` rise/fall limits | Actual elapsed seconds; +0.6 m in 2 h passes 0.3 m/h, +0.6001 fails; -0.2 passes 0.1 m/h, -0.2001 fails. `test_separate_rise_fall_real_elapsed` |
| 17(3), 28 | `assess_floodplain`: depth, coincident inundation duration, velocity and site criteria | Inclusive independent comparisons, failure plus missing duration stays incomplete. `test_known_failure_survives_missing_other_condition` |
| 28 | `apply_hydraulic_correction`: located base flow, model-derived signed additive discharge adjustment, explicit `CorrectionPosition` | 8 + 2 = 10 m3/s; missing position unresolved; 8 - 9 infeasible, not clipped. `test_supplied_hydraulic_correction_computes_supported_flow` |
| 17(3), 29, 31 | `assess_oxygen_gas`: minimum oxygen concentration and dimensionless gas saturation, supplied criteria | 5 versus 6 mg/l fails despite missing gas check. `test_low_oxygen_thermal_and_movement_fail` |
| 17(3) | `assess_thermal_movement`: supported temperature/velocity extrema, natural/site bounds and fish access | Temperature outside bounds or blocked movement fails. Same test above |
| 17(3) | `assess_thermal_variation`: supported maximum within-period swing and selected limit | 3 degC swing fails a 2 degC limit; interval mean cannot pass. `test_temperature_swings_need_sufficient_temporal_support` |
| 24, 32(2) | `assess_seasonal_timing`: natural and managed peak instants, supported allowed shift | Two-day difference passes two-day limit; three days fails. `test_natural_seasonal_peak_timing` |
| 29, 32(3) | `assess_winter_continuity`: supported interval minimum flow, positive criterion, ice state | No mean-to-continuity inference; zero flow and frozen-to-bed fail. `test_depth_literal_and_frozen_conditions_fail` |
| 30 | `assess_winter_recommendation`: whole November or December, observed long-term mean monthly low flow and `WinterShare` | Explicit selection in [0.30, 0.50] sets recommended lower bound only. 9 versus 0.3 × 10 passes; no 50% cap. `test_winter_recommendation_is_lower_bound_not_upper_cap` |
| 24, 31 | `assess_special_release`: supported sensitive-area arrival flow/criterion and floodplain connection | Supply 2 below 3 fails while missing connection remains incomplete. `test_special_release_supply_and_connection_are_not_reservoir_discharge` |
| 32(1), 32(4) | `assess_small_river`: drying origin, depth, velocity, explicit `SmallRiverVelocity` | Natural drying differs from induced drying. Depth 0.1 m is inclusive; 0.0999 fails. Selection 0.2 versus 0.6 changes the result at 0.4 m/s. `test_drying_origin_is_not_inferred_from_zero_flow`, `test_small_river_velocity_requires_selected_threshold` |

## Interpretation and support limits

- Site thresholds are supplied, not inferred national defaults. All numbers in
  the example except literal 0.1 m and permitted selection ranges are synthetic.
- Level-rate tests use the actual UTC-normalized elapsed interval. A negative
  datum-relative stage is permitted. These tests cannot establish unseen
  instantaneous fluctuations. Separate supported subinterval/envelope evidence
  is needed for that claim.
- Depth uses `SignedState(STAGE, ..., "m", "depth above bed")`, with nonnegative
  depth operands. Velocity uses a declared directional domain. Compared states
  require the same domain; discharge cannot substitute for either.
- Floodplain duration is the supplied duration **at the required depth** for the
  study's biological phase. Separate marginal durations are not interchangeable.
- Thermal range and maximum swing are distinct assessments. Oxygen/gas inputs
  must come from supported observations or process results, not conservative
  substance registration. Applicable quality criteria remain caller inputs.
- The winter-share operation applies to regulated waters. Call separately for
  each whole November/December UTC reporting month. Its study identifies the
  observed long-term low-flow statistic and explicit supported share selection.
  Unregulated natural low flow does not require this recommendation. The
  recommendation does not replace winter oxygen, continuity or freezing checks.
- The small-river source range does not choose one universal velocity minimum.
  `SmallRiverVelocity` records the selected minimum and its interpretation.
  Natural seasonal drying passes only the induced-drying check; it is not an
  invented exemption from the separate depth, winter or seasonal provisions.
- Special-release supply is downstream arrival, not raw reservoir discharge.
  Routing, protected-area applicability and the upstream reservoir relation are
  identified by the supplied study. Level changes and oxygen remain separate
  required assessments; no extra water source or consumptive demand is created.
- The hydraulic correction consumes a model-derived additive relation for this
  exact base discharge, period and location. `BEFORE_SPAWNING` and
  `AFTER_SPAWNING` record composition position. This function does not execute a
  spawning operator or resolve bound priority. Its output is a candidate flow,
  not an issued duty; monthly/annual volume accounting remains downstream.

## Reproducibility

Arithmetic uses exact `Fraction` quantities with inclusive comparisons, so the
listed test expectations use exact equality, not a hidden rounding tolerance.
The runnable example exercises every operation with supported supplied inputs.
The tests also cover missing states/criteria, source and production-version
mismatches, partial failures, invalid quantities, unsupported temporal evidence,
scientific restrictions and immutable records. Synthetic acceptance does not
establish field calibration, ecological adequacy or authority approval.
