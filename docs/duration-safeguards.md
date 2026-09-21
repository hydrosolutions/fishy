# Duration minima and safeguards

A duration threshold describes a population of annual or seasonal minimum flows.
It is not a daily floor, a daily percentile, or permission to breach an obligation.
Durations and return periods are supplied settings. There are no national defaults.

Run a complete-calendar example:

```console
uv run python examples/duration_safeguard.py
```

The example constructs two complete reference years and six predecessor days.
It fits a seven-day/T100 threshold of about 4.976270579073 m³/s. It then checks
all 366 windows in a leap-year candidate. Point and explicitly fixed synthetic
uncertainty checks pass. Scientific permission remains unknown because the example
has no independent scientific assessment. It does not issue a regime.

## Prepare a threshold

1. Supply immutable `FlowSample` records with location, interval, provenance and
   uncertainty. Missing or unsupported intervals remain identifiable.
2. Set `DurationWindowRule`: positive integer duration, annual or named continuous
   season, accounting-year start month, fixed UTC offset, and justification.
   Season end boundaries are exclusive. A November–March season is one continuous
   block, labelled by its ending year. January annual blocks use the calendar year;
   other accounting years use the year containing their final day.
3. Call `construct_duration_reference` with the declared reference period, climate
   treatment and dependence evidence. Inspect every `DurationMinimum`. An incomplete
   block has no usable minimum, even if a small evaluable window exists. Its
   diagnostic windows and exclusion reason remain visible.
4. Call `estimate_duration_threshold` with `LowFlowReturnPeriod` and an explicit
   `DurationEstimator`. Empirical estimation uses Weibull ranks and interpolation;
   targets outside rank support are unavailable. The zero-mixture lognormal profile
   retains parameters and distribution-jump diagnostics. Both reuse the same
   discharge-distribution operators as annual statistics, without treating minima
   as annual means.

Supported external minima can be represented by `DurationMinimum` with an
`ImportedDerivation`, not computed-window evidence. Include every declared block,
including exclusions, in `DurationReference`. Use `import_duration_threshold` for
an external threshold. Its equation, calibration, diagnostics, uncertainty method
and reproducibility record remain distinct from native estimators. For example,
minima 1,2,3,4 at T2 produce 2.5 with Weibull interpolation; an imported inverse
empirical CDF value of 2 keeps its different identity.

`threshold.product(UsePurpose.SIZING)` creates the exact duration-minimum subject
for the existing scientific-acceptance API. It binds duration, domain, estimator,
reference content, recurrence, value and uncertainty. Acceptance of another
threshold or an annual mean does not transfer. Untreated or unassessed climate
blocks stationary sizing permission but leaves exploratory numbers visible.

## Assess a candidate

Call `assess_low_flow` separately with `AssessmentStage.PROVISIONAL`, `FINAL`, or
`REALISED`. Retain each result. The operation never adds flow or modifies a prior
result. Active supported additions may repair a provisional duration failure;
advisory numbers do not change the supplied final schedule. A duration pass does
not repair natural-bound crossings or rejected daily-pattern evidence.

Results expose:

- Exact candidate input, threshold, stage and supplied reference relation.
- Every eligible window, mean, volume, contributors and missing-evidence reasons.
- Minimum and all attaining windows; nominal per-window shortfalls.
- Separate point, uncertainty and scientific-permission findings.
- Coverage that remains incomplete even when a known violation establishes failure,
  including the combined `checks` summary.

For an annual test, each assessed day ends one window. Windows may begin before
the year, but real predecessor inputs and a justification are required. No circular
wrap, repeated endpoint or zero padding is automatic. An explicitly hypothetical
repeated-year context must be supplied as such. Seasonal windows must lie entirely
inside the season. An empty eligible set cannot pass.

Volume is integrated from whole represented intervals. Finer unequal intervals are
weighted by elapsed seconds. A whole coarse interval can support its own total;
it cannot support an unknown fraction or a shorter window. Daily means do not
establish within-day constancy. Convert civil-day inputs explicitly to fixed
86,400-second days; variable-length local days are not silently converted.

Bounds need `WindowUncertaintySupport`: a supplied joint enclosing-support basis
for all contributing intervals. Marginal confidence limits are not automatically
joint temporal support. A window certainly passes when its lower bound reaches
the threshold upper bound; it certainly fails when its upper bound is below the
threshold lower bound. Otherwise it is indeterminate. Missing bounds are not
measured certainty. Fixed singleton synthetic assumptions remain labelled.

A selected family, realised scenario or changed natural/observed/future-stress
reference meaning uses an explicit
`CandidateReferenceRelation` to the retained reference identity. Multiple durations
and classes stay separate. Family issuance, component activation, floor tests and
fallback decisions belong to the composition layer, not this standalone operation.

## Sources and limitations

This technical contract derives from the accepted consolidated handover dated
19 September 2026: report D.5 `sec-lowflow-safeguard`, D.7
`sec-statistical-estimation`, D.8 `sec-scientific-acceptance`, and
`evidence/multiday_acceptance.md`. The report's proposed Uzbek gate is not adopted
policy. WMO 1029 (2008), §§2.3, 5.4.3 and chapter 7 supports duration-minimum
statistics, not Uzbek ecological durations or thresholds. The supplied USGS 2025
file is an authored source summary. Neither prescribes the gate. No private report
chapter or original source is included here.

The bundled pattern-development finding remains a separate limitation: all 21 dry
held-out cases overestimated seven-day minima. A safeguard pass supplies no
correction factor, rare-tail validation or ecological certification.

## Executed-test crosswalk

Tests use public operations in `tests/test_low_flow_safeguard.py`. They contain
complete annual calendars, leap days and explicit context as well as focused
single-window witnesses. Synthetic assumptions are not basin acceptance.

| Source/check | Public operation and observable test |
| --- | --- |
| D.5 M1 | `assess_low_flow`; `test_m1_seven_day_mean_is_not_daily_floor`: mean10, independent day deficit2 |
| M2 | `test_m2_every_eligible_window_not_just_first`: 10 and66/7; shortfall4/7 |
| M3/M4 | `test_m3_m4_known_violation_survives_missing_coverage`: unknown versus fail+incomplete |
| M5/M7 | `test_m5_m7_no_eligible_season_window_and_missing_annual_context_never_pass` |
| M6 | `test_m6_annual_boundary_uses_real_predecessor_and_last_daily_interval_year`: 2020 label |
| M8 | `test_m8_leap_day_once_with_exact_volume`:604800 seconds,6048000m³ |
| M9/M10 | Finer weighting10, not8; monthly fractions unavailable; whole coarse totals remain usable |
| M11 | Full leap-year provisional8 fails; final10 passes; advisory8 fails; natural bounds remain separate |
| M12 | Bound overlap unknown; lower11 passes threshold upper11; upper8 fails threshold lower9 |
| M13 | Explicit zero point passes; missing/invalid inputs do not |
| M14/D.7 | `construct_duration_reference`, `estimate_duration_threshold`, `import_duration_threshold`: full2001–2004 blocks give2.5 versus imported2 |
| M15 | Separate full-year class/duration checks retain failure and unknown; integrated issuance is tested by composition owner |
| Reference supplements | Gap/partial/context exclusions, attributable imported reconstruction, recurring cross-year season and fixed+05:00 boundaries |
| Estimator supplements/U9 inputs | Zeros/ties/failed fits and complete wet/dry2001–2002 references yield T100 thresholds4.976270579072646 and7.464405868608971 (absolute tolerance2e-13) |
| D.8 | Exact scientific subject, missing permission, untreated climate, independent daily-pattern failure |
| Input/isolation supplements | Duplicate/overlap/location/member/unit refusal; explicit realised/selected-family reference binding; no mutation of provisional result |

All rational means/shortfalls use exact comparisons. Fitted values use the stated
absolute tolerance. Full family M11/M15 and U9 issuance acceptance is additional
integration work, not claimed by the standalone arithmetic tests.
