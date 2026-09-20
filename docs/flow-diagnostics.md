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
manual's fixed 366-position calendar and quarterly unwrapping, not a trigonometric mean.
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

The original daily ISPRA profile uses at least 20 reference years and the last five
impacted years. Each current annual parameter is summarized **before** measuring
its distance from the reference interquartile band. All 33 scores enter the overall
mean; missing components do not disappear through renormalization. Timing scores
are supported only when both records have an unambiguous shared quarterly transform.

Choose `SummaryStatistic.MEAN` or `MEDIAN`, and `QuantileEstimator.LINEAR`
(type 7) or `WEIBULL` (type 6). These are disclosed numerical choices, not verified
historical IMSL equivalence. A constant reference band gives zero for exact equality;
a value outside a zero-width band remains unsupported.

`records.compare_monthly_iari` accepts located and dated reference/impacted
`RegimeAttribution` records together with year/month/monthly-mean-discharge tables.
It retains both original input tables, their source/member/version/period, SPI,
correction factor and selected years. Input years must match attributed intervals. Missing evidence is refused.
Excluded warm-up is checked against the actual reference years and selected current
years; an excluded period outside these operands does not disable supported data.
`iari.monthly_iari` is the lower-level numerical primitive.
It requires 20 reference years and either five impacted years or one year with a
supplied `BasinPrecipitationSPI12`. The single-year correction applies to the final
index, not to discharge. Two to four years are not silently averaged. The monthly
profile does not calculate daily IHA parameters. No country release prescription,
expert assessment or spot-measurement route is implemented here.

## Numerical acceptance crosswalk

All examples are synthetic software witnesses, not river validation. Floating
arithmetic uses pytest relative tolerance 1e-6 unless an explicit exact result is
asserted; structural tables use `polars.testing.assert_frame_equal`.

| Requirement / public operation | Expected and observed witness | Maintained test |
|---|---|---|
| All 33 annual IHA, `annual_indicators` | Daily 1..365: January 16, 3-day minimum 2, 90-day maximum 320.5, baseflow 4/183; all 33 rows match independent table | `test_iha.py::test_all_33_independent_monotonic_witness` |
| Means vs medians | January 131/31 vs 1; 3-day maximum 103/3 in both | `test_mean_median_and_rolling_always_mean` |
| Leap day / ties | Leap February mean 33/29; first tied maximum day 60; nonleap March 1 day 61 | `test_leap_day_and_earliest_extreme_ties` |
| Rolling boundaries | Cross-year peak not treated as one 3-day annual maximum | `test_no_rolling_wrap_or_cross_year` |
| Pulses / transitions | Cross-year 5-day run assigned start year; equal thresholds excluded; plateau does not end trend | `test_cross_year_pulses_strict_threshold_and_truncation`, `test_duration_and_rate_mean_median_plateaus_reversals` |
| Interannual dispersion | [1,3,5]: mean 3, sample SD 2, population SD sqrt(8/3) | `test_statistics.py::test_sample_and_population_conventions_discriminate` |
| Circular timing | [365,1,2]: mean 2/3, timing CV sqrt(7/3)/366 | `test_winter_circular_unwrap_and_source_timing_cv` |
| Original IARI aggregation | Last-five current characteristic then distance; all 33 membership and missing propagation | `test_iari.py` daily tests |
| Monthly IARI / SPI | Exact signed Table 1.3 endpoints, zero IQR inside 0/outside unsupported, closed class limits | `test_iari.py` monthly, SPI and classification tests |
| Real dated standalone boundary | 20 complete synthetic reference/managed years → 33×20 rows, median IARI 0; separate provenance retained | `test_records.py::test_sufficient_record_public_path_keeps_identity_and_complete_numerical_iari` |
| Live/saved physical diagnostic boundary | 366 daily volumes 172800 m³ → January 2 m³/s, BFI 1, zero-days 0; leap day retained and empty rise rate undefined | `test_physical_indicators.py::test_live_saved_calendar_year_physical_path` |
| Reference qualification | Managed/observed-only/unspecified reference kinds rejected; observed production with explicit natural qualification supported | `test_records.py::test_unqualified_series_cannot_be_used_as_natural_reference`, `test_observed_production_with_explicit_natural_qualification_remains_supported` |
| Imported diagnostic attribution | Monthly SPI −2 factor 0.5, both located regimes and exact input years retained | `test_monthly_attribution_retains_inputs_years_and_spi` |
| Imported evidence eligibility | Both monthly reference and impacted inputs reject missing or excluded operands; outside-period exclusions remain valid | `test_imported_diagnostics_do_not_bypass_excluded_or_missing_evidence`, `test_imported_warmup_outside_selected_years_does_not_disable_supported_data` |
| Source-backed record invariants | Empty history or contradictory location/period cannot construct an IndicatorRecord | `test_indicator_record_cannot_erase_authoritative_source_history`, `test_indicator_record_cannot_contradict_source_location_or_period` |
