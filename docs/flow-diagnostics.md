# Flow diagnostics

Fishy consumes supplied daily discharge. It does not reconstruct natural flow.
Observations, supported imports and Taqsim interval projections share `FlowSample`.
The supplied source, scenario, reference member, versions and mapping remain on the
`IndicatorRecord`; numerical success does not change scientific or official findings.
An indicator record requires nonempty authoritative daily history; its location,
exact period and annual-table years must agree with that history.

Run the synthetic example:

```sh
uv sync
uv run python examples/flow_diagnostics.py
```

## Annual IHA

```python
from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary
from fishy.diagnostics.records import flow_indicators
from fishy.quantities import Flow

profile = IHAProfile(
    CentralStatistic.MEAN,
    PulseThresholds(Flow(4), Flow(18)),
    RateBoundary.WITHIN_YEAR,
)
record = flow_indicators(samples, profile)
print(record.annual)
```

Thresholds above are synthetic, not ecological defaults. Supply thresholds derived
from the reference, with their derivation in its configuration/source record. Apply
the same thresholds to both records. The numerical adapter refuses missing,
unsupported, partial or non-whole-day inputs. Annual IHA additionally requires
ordered dense complete Gregorian calendar years. These gates do not apply to
ordinary supplied-duty assessment.

`annual_indicators` is the lower-level table operation. Its input columns are
`date: Date` and `discharge_m3_s: Float64`. Output includes every annual parameter,
its source group, a nullable value and any undefined-value or boundary reason.
No-event counts can be zero while event durations remain undefined. Pulse runs
cross year boundaries and belong to their start year. First-horizon pulses are
omitted; terminal pulses retain a truncation warning. Means and medians are
explicitly selected. Rolling extrema always use arithmetic averages.

`statistics.summarize_indicators` computes interannual means, standard deviations
and CV. Select `DispersionConvention.SAMPLE` or `POPULATION` explicitly. Neither
is claimed to replicate an unspecified historical denominator. Timing uses the
manual's fixed366 calendar and quarterly unwrapping, not a trigonometric mean.
Ambiguous dominant-quarter ties and undefined ratios retain unsupported values.

## IARI

Use `records.compare_iari(reference, impacted, basis=..., summary=..., quantile=...)`.
`ComparisonBasis.MATCHED_PERIOD` requires identical exact intervals.
`HISTORICAL_BASELINE` requires the reference to precede the impacted interval.
Locations, mapping versions and annual definitions must agree. A reference must
explicitly identify present-climate natural or naturalised-historical meaning.
Observed production is supported when its natural-reference qualification is supplied;
observed production alone does not establish that qualification. Managed, future
and unspecified reference kinds are rejected. Numerical calculations do not confer
scientific or official acceptance.

The original daily ISPRA profile uses at least20 reference years and the last five
impacted years. Each current annual parameter is summarized **before** measuring
its distance from the reference interquartile band. All33 scores enter the overall
mean; missing components do not disappear through renormalization. Timing scores
are supported only when both records have an unambiguous shared quarterly transform.

Choose `SummaryStatistic.MEAN` or `MEDIAN`, and `QuantileEstimator.LINEAR`
(type7) or `WEIBULL` (type6). These are disclosed numerical choices, not verified
historical IMSL equivalence. A constant reference band gives zero for exact equality;
a value outside a zero-width band remains unsupported.

`records.compare_monthly_iari` accepts located and dated reference/impacted
`RegimeAttribution` records together with year/month/monthly-mean-discharge tables.
It retains both original input tables, their source/member/version/period, SPI,
correction factor and selected years. Input years must match attributed intervals. Missing evidence is refused.
Excluded warm-up is checked against the actual reference years and selected current
years; an excluded period outside these operands does not disable supported data.
`iari.monthly_iari` is the lower-level numerical primitive.
It requires20 reference years and either five impacted years or one year with a
supplied `BasinPrecipitationSPI12`. The single-year correction applies to the final
index, not to discharge. Two to four years are not silently averaged. The monthly
profile does not calculate daily IHA parameters. No country release prescription,
expert assessment or spot-measurement route is implemented here.

## DHRAM: supported summary scoring, daily path blocked

`records.assess_dhram` assesses a supplied summary import together with separate
located, dated and versioned reference/impacted `RegimeAttribution` records. It
retains all ten raw changes, their descriptor profile, supplementary evidence and
both source contexts. Missing evidence or warm-up overlapping either supplied
summary period is refused. It checks natural-reference qualification, mapping and the
selected temporal comparison basis.

`dhram.classify_dhram` is the numerical primitive. It applies Black2005 Tables3–4 to ten explicitly supplied
source-profile summary indicators. It retains point contributions and class bounds
when required indicators or supplementary evidence are unknown. Subdaily variation
and anthropogenic cessation require explicit evidence; daily means do not prove
that either is absent. These bounds express missing evidence, not scientific
uncertainty. A unique bounded class does not imply complete evidence.

The source's Table1 specifies32 descriptors, but its worked Tables5/6 use31.
The historical timing dispersion and general zero-denominator operators are also
unresolved. **A daily DHRAM calculation is not implemented and the required full
three-diagnostic delivery is incomplete.** No modern33-parameter substitution or
legacy simplified threshold profile is provided. See the [source register](flow-diagnostic-sources.md).

## Numerical acceptance crosswalk

All examples are synthetic software witnesses, not river validation. Floating
arithmetic uses pytest relative tolerance1e-6 unless an explicit exact result is
asserted; structural tables use `polars.testing.assert_frame_equal`.

| Requirement / public operation | Expected and observed witness | Maintained test |
|---|---|---|
| All33 annual IHA, `annual_indicators` | Daily1..365: January16, 3-day minimum2, 90-day maximum320.5, baseflow4/183; all33 rows match independent table | `test_iha.py::test_all_33_independent_monotonic_witness` |
| Means vs medians | January131/31 vs1; 3-day maximum103/3 in both | `test_mean_median_and_rolling_always_mean` |
| Leap day / ties | Leap February mean33/29; first tied maximum day60; nonleap March1 day61 | `test_leap_day_and_earliest_extreme_ties` |
| Rolling boundaries | Cross-year peak not treated as one3-day annual maximum | `test_no_rolling_wrap_or_cross_year` |
| Pulses / transitions | Cross-year5-day run assigned start year; equal thresholds excluded; plateau does not end trend | `test_cross_year_pulses_strict_threshold_and_truncation`, `test_duration_and_rate_mean_median_plateaus_reversals` |
| Interannual dispersion | [1,3,5]: mean3, sampleSD2, populationSDsqrt(8/3) | `test_statistics.py::test_sample_and_population_conventions_discriminate` |
| Circular timing | [365,1,2]: mean2/3, timingCVsqrt(7/3)/366 | `test_winter_circular_unwrap_and_source_timing_cv` |
| Original IARI aggregation | Last-five current characteristic then distance; all33 membership and missing propagation | `test_iari.py` daily tests |
| Monthly IARI / SPI | Exact signed Table1.3 endpoints, zeroIQR inside0/outside unsupported, closed class limits | `test_iari.py` monthly, SPI and classification tests |
| Real dated standalone boundary |20 complete synthetic reference/managed years →33×20 rows, median IARI0; separate provenance retained | `test_records.py::test_sufficient_record_public_path_keeps_identity_and_complete_numerical_iari` |
| DHRAM Table5 | Supplied Megget summaries →7points, class3 | `test_dhram.py::test_megget_source_table5` |
| DHRAM Table6 | Supplied Allt summaries →18points, class4 then cessation adjustment class5 | `test_allt_source_table6` |
| All thresholds and classes | Equality does not exceed; next representable value does; every class boundary tested | `test_every_threshold_equality_is_not_exceedance`, `test_every_class_boundary` |
| Unknown evidence | Zero points +two unknown supplementary findings →classes1..3, no asserted unique class | `test_unknown_is_not_false_and_two_confirmed_adjustments` |

| Live/saved physical diagnostic boundary |366 daily volumes172800m³ →January2m³/s, BFI1, zero-days0; leap day retained and empty rise rate undefined | `test_physical_indicators.py::test_live_saved_calendar_year_physical_path` |

| Reference qualification | Managed/observed-only/unspecified reference kinds rejected; observed production with explicit natural qualification supported | `test_records.py::test_unqualified_series_cannot_be_used_as_natural_reference`, `test_observed_production_with_explicit_natural_qualification_remains_supported` |
| Imported diagnostic attribution | Raw DHRAM changes and both located regimes retained; monthly SPI−2 factor0.5 and exact input years retained | `test_attributed_dhram_keeps_raw_changes_and_both_regimes`, `test_monthly_attribution_retains_inputs_years_and_spi` |

| Imported evidence eligibility | Both monthly/DHRAM reference and impacted inputs reject missing or excluded operands; outside-period exclusions remain valid | `test_imported_diagnostics_do_not_bypass_excluded_or_missing_evidence`, `test_imported_warmup_outside_selected_years_does_not_disable_supported_data` |
| Source-backed record invariants | Empty history or contradictory location/period cannot construct an IndicatorRecord | `test_indicator_record_cannot_erase_authoritative_source_history`, `test_indicator_record_cannot_contradict_source_location_or_period` |
