# HYDMOD-F acceptance crosswalk

## Scope and reproducibility

This record covers F9, the HYDMOD-F section of the supplied acceptance index,
and applicable common C1–C6 behavior. The governing source is BAFU (2011),
*Methoden zur Untersuchung und Beurteilung der Fliessgewässer: Hydrologie –
Abflussregime, Stufe F*, chapters 2–6 and relevant appendices. Printed page
numbers are two less than one-based PDF page numbers.

Manual SHA-256: `1fddd85c31265a7474d566bb7faab6bbacf571a6428f8702942b1ee1ec987bc2`.
The primary PDF layouts, including Figures 17, 19, 21–23, 25, 27–28, 30, 33
and Tables 2–10, were inspected during transcription. Original PDFs, report
snapshots and source images are not distributed here.

The executed implementation revision is
`ccdce60646b38535d94b0ea5dcd97d43e34fb421`. This acceptance record is a
subsequent documentation-only commit; the implementation, tests and example are
unchanged from that revision. The starting Fishy revision is
`f61b91b9b94f7055d640c608068d098babda8bea`. `uv.lock` pins runtime and test
dependencies. Optional Taqsim is `396ad093c2b6f240e702a3b05aee1fb96a69b3f7`;
Incidence is `665da4e0d81ab28921b8d5d2edbb9be27f4ec612`. Neither is required
for these hydrological operations.

Reproduce the focused checks and example:

```sh
uv sync --locked
uv run pytest tests/test_flow_interventions.py tests/test_flow_regime.py \
  tests/test_flow_events.py tests/test_flow_pulses.py \
  tests/test_catchment_conditions.py tests/test_hydrological_transfer.py \
  tests/test_hydrological_condition.py tests/test_hydrological_assessment.py \
  tests/test_hydrological_example.py
uv run python examples/hydrological_condition.py
```

Every expected/actual entry below is a synthetic software assertion, not a
calibration, scientific acceptance finding or official certification. Successful
numerics do not change supplied evidence restrictions or official admissibility.

## Precision and source support

- Source decimal tables, ratios, thresholds, areas and linear corrections use
  exact `Fraction` arithmetic. Tests for these quantities use exact equality.
- Quantiles use declared linear interpolation at `(n−1)p`. Q347 is a pooled
  daily 5% nonexceedance quantile; annual Q347 values separately feed sample-SD
  CV `(n−1)`. The manual specifies the statistics, not this interpolation choice.
- Circular timing uses the printed angle `2π JD/365`, including leap years.
  Annual tied extrema require an explicit earliest/latest/unresolved choice.
  Circular/ellipse geometry is binary64; explicit geometry tests use `1e-12`
  absolute tolerance. CV tests use `pytest.approx` relative tolerance `1e-6`.
- Figure 25 is linear-linear. Native raster x pixels 71…762 map to 0…3.25;
  y pixels 423…9 map to 1…7. Figure 27 is log-log: x pixels 59…755 map to
  log10(stress) −1…2; y pixels 413…11 map to log10(frequency) −1…2.
  Four coloured-region edges are sampled at ten-pixel spacing with explicit
  plot endpoints; edge ordinates are derived from colour transitions, not tick
  extrapolation. The source grey review region is not a class.
- Graph uncertainty is a ±2-native-pixel rectangle in **both** axes: about
  ±0.0094 horizontal and ±0.0290 vertical units for Figure 25; ±0.00862 and
  ±0.01493 log10 units for Figure 27. Ambiguous rectangles/shared edges and
  off-domain values remain unclassified. This is transcription precision, not
  physical/ecological uncertainty. A native-raster audit found zero supported
  colour mismatches at the inspected five-pixel mesh: Figure 25 had 9,616
  matches/525 undetermined; Figure 27 had 7,917 matches/463 undetermined.
  Committed tests exercise independent interior/edge witnesses without private files.
- Appendix A4 MHQ exponent 0.7 uses binary64 with relative test tolerance
  `1e-12`. Its other arithmetic and missing-area/normal-rounding rules are exact.

## Inventory, reference and selection

Tests in this section are in `tests/test_flow_interventions.py`.
| Requirement / source | Public operation and input | Expected / actual | Executed test |
|---|---|---|---|
| Ch2 current landscape vs pristine/naturalisation; evidence remains supplied | `ReferenceConditions`, `reference_eligibility` | structural preparation cannot establish eligible reference; explicit supported current-landscape source/adaptation preserved, no river class without metric calculation | `test_reference_naturalisation_not_scientific_acceptance` |
| Ch2 canals, drains, lakes | `reference_eligibility` | not-applicable river condition; no fabricated natural class | `test_reference_excludes_artificial_and_lake_class` |
| Table8 A1–A6,D1 | `screen_intervention` + typed magnitude and Q347 reference | 0.02/0.1 equals 20% not significant; 0.020001 significant, absolute cutoff applied first | `test_abstraction_relative_strict_boundary` |
| Table8 B1–B4,B7 | typed area/population/power plus operating discharge | absolute equality included; discharge ratio 25% excluded, larger included | `test_supply_absolute_and_relative_boundaries` |
| Table8 B6,B8 | max transfer/return discharge | strict 10% /25% ratios | `test_transfer_and_turbine_returns` |
| Table8 C1,C2,C4 | volume / reference MQ /3600 | 12h or 1.5h equality not significant, +1m3 significant | `test_storage_hours_strict_threshold` |
| Table8 C3 | lake total volume OR area, regulated volume for significance | 10ha can qualify despite small lake volume; 43200m3 at MQ1 not significant, 43201 significant | `test_lake_or_threshold_and_regulated_not_total_volume` |
| Table8 E1,E2 | additional flushing discharge and frequency | exact <10/<20/<40/>40 bands, >85/65/50/25%; 150l/s excluded; 40/year at ratio0.4 undetermined | `test_flushing_bands_and_strict_ratio`, `test_flushing_absolute_strict_and_40_unresolved` |
| Ch2/§4.4 exclusions B5,D2,D3,diffuse,engineering | `screen_intervention` | explicit source exclusion, not measured proof of no impact | `test_source_exclusions_not_measured_absence` |
| §4.2 impoundments | inventory + `indicator_selection` | inventory-only, no fabricated river class | `test_impoundment_inventory_not_river_class` |
| §§4.3–4.4 nearby cumulative effects | `screen_group` | two12l/s intakes cross20l/s threshold; 100/115km2 equality allowed,115.000001 refused; different river/type/duplicates refused | `test_cumulative_small_abstractions_and_15_percent_equality` |
| Cumulative input gaps | `screen_group` | missing additive magnitude not treated as zero | `test_missing_cumulative_component_is_not_zero` |
| Cumulative flushing | `screen_group(...,combined_characteristics=...)` | supplied combined operating/event analysis computes significant class selection; no independent maxima/frequency averaging; originals and combined analysis retained | `test_combined_flushing_operating_analysis_retained` |
| Table9 indicative x/(x)/() selection | `selection_advice`, `indicator_selection` | recommended and exceptional require metric/site judgement; indirect exclusion distinct from blank | `test_table9_distinct_recommendation_symbols` |
| §5.1 upstream and situational selection | local/upstream screens + `SiteSelection` | still significant B6 upstream effects not hidden by B5 local exclusion; groundwater flood exclusion and drainage addition retained | `test_selection_upstream_exceptional_and_site_attribution` |
| §5.11 class1 vs missing | `indicator_selection` | below threshold source-screened1; missing A1 magnitude leaves its mean-flow unresolved but unrelated stormwater source-screened1; empty inventory cannot establish assessment | `test_screened_one_differs_missing_affected_indicator` |
| §3.2.3 concession virtual series | `estimate_abstracted_flows` + `AbstractionConcession` | Qr10,5,1,0,missing with capacity6,residual2 -> Qb4,2,1,0,missing; leap day and raw input provenance retained; subdaily and observed relabel refused | `test_daily_concession_estimate_preserves_inflow_floor_and_missing` |
| Invalid vs unsupported | constructors + screen references | nonfinite/negative/wrong unit invalid; zero or missing denominator undetermined | `test_invalid_units_nonfinite_negative_and_missing_reference` |

Additional source routes and boundary guards:

| Source / requirement | Public operation and input | Expected = actual | Executed test |
|---|---|---|---|
| §3.2.3 actual operation | `estimate_operated_flows(reference, operations, provenance)` | 10−3=7; absent operation stays missing; abstraction above reference is infeasible, not clipped | `test_actual_operating_abstraction_success_gap_and_infeasible` |
| §5.1 close abstraction/return | `reuse_pre_abstraction`, `AbstractionReturn` | Attributed close-in-space/time judgement permits reuse; unknown relationship does not | `test_close_abstraction_return_reuses_attributed_prior_findings` |
| Table 8 excluded inventory | `screen_magnitude`, `magnitude_screens` | B5/D2/D3 retain absolute magnitude screening even though method significance is excluded | `test_excluded_types_still_have_absolute_inventory_screen`, `test_absolute_inventory_equality_independent_of_reference` |
| Complete Table 9 | `selection_advice` | All 207 source cells retain recommended/exceptional/indirect/blank distinctions | `test_all_table9_cells_match_primary_grid` |
| Unlisted interventions | `InterventionType.OTHER` | Inventory retained; no guessed no-impact selection | `test_unlisted_intervention_keeps_inventory_without_guessed_exclusion` |
| Source support | Virtual daily routes and reference/inventory identity | Warmup cannot become supported flow; foreign scenario/member rejected; MANAGED transition is explicit | `test_virtual_series_warmup_cannot_become_supported`, `test_virtual_series_refuses_identity_relabelling`, `test_inventory_refuses_foreign_reference_and_selection_context` |

Reference qualification additionally uses `reference_limitations` and the
subject-bound `reference_application_scope`. A `ReferenceApplication` binds the
exact original source provenance/period to the exact receiving context and
scoped `EvidenceFindings`. Distinct historical source periods remain unchanged;
a changed source, target, stale/missing/failed application finding, missing
correction or relevant warmup cannot reuse permission. Executed cases:
`test_reference_eligibility_binds_source_identity`,
`test_reference_eligibility_honours_unavailable_source`,
`test_reference_application_cannot_reuse_relationship_after_source_mutation`,
`test_reference_application_rejects_unbound_or_failed_evidence`, and
`test_historical_source_period_controls_warmup_scope` in the intervention suite.

## Mean flow, low flow and seasonality

Tests in this section are in `tests/test_flow_regime.py`.
| Source / requirement | Public operator and inputs | Expected = observed | Test(s) |
|---|---|---|---|
| F9/C2, §§3.4.2–3 Tables2/3 | `regime_mean_flow(RegimeReference, Area)` | Type1,10km²: MQ510l/s then monthly Pk products; all16 Table2 and192 Table3 cells implemented without normalisation | `test_regime_source_estimates`, `test_estimate_table_transcription_all_types`, `test_table3_all_192_cells_from_primary_pdf_columns` (16 columns), `test_parde_ratio_and_unmodified_rounded_source_coefficients` |
| §3.4.1–2 raster alternatives | `RunoffDepth(mm,seconds,source)`, `raster_discharge`, `monthly_from_raster` | 100mm ×20km² /30d =2,000,000/2,592,000m³/s; originals retained on monthly record | `test_raster_and_parde_routes_preserve_units_and_inputs` |
| §3.4.1 third route / §3.4.3 | `monthly_from_parde`, `parde_from_means` | MQ3 ×Pk2 =6; MMQ2/MQ4=.5; zero MQ yields unknown Pk | same; `test_parde_ratio_and_unmodified_rounded_source_coefficients` |
| §3.3.1 A2 band determination | `PardeCoefficients`, 16 supplied `PardeEnvelope`, `match_parde_regime` | 12/12 vs10/10 hits resolves; one-hit lead or insufficient total-band lead does not; missing candidates unresolved | `test_regime_matching_both_hit_counts_and_two_hit_margin` |
| §3.4.1 observed MMQ | `monthly_from_observations(FlowSample tuple)` | Complete months only. Leap February pool=85/57, not equal-year average; excluded partial January remains disclosed | `test_complete_months_only_and_daily_pooled_annual_means`, `test_excluded_months_retain_incomplete_coverage` |
| §3.4.2 observed MQ | `annual_mean_from_observations` → `MeanFlowEstimate` | Years2000/2001 flows1/2 give1096/731; excluded partial2000 yields selected2001 and coverage INCOMPLETE; source intervals retained | same; `test_mean_estimate_selected_excluded_years_and_source_intervals` |
| §5.2 Table10/Fig17 | `assess_mean_flow`, `assess_mean_flow_observations` | R36 type3→2, type10→1; all48 table values; strict30/45/60/85 bounds; absolute monthly deviations not cancellation | `test_table10`(16), `test_source_36_percent_contrast`(2), `test_absolute_mean_boundaries`(6), `test_mean_flow_sums_absolute_monthly_changes_not_net_change` |
| §5.2 missing evidence | same | Missing month/ref→unknown; zero denominator→unknown; absent type permits class only when all16 source types agree, including R100→5 | `test_mean_missing_zero_and_independent_absolute_class_one`, `test_missing_regime_cannot_disable_type_independent_worst_class` |
| §§3.6.1–2 Tables6/7 | `regime_low_flow(RegimeReference,Area)` | Type16 area2km²→18.4l/s, CV21%; all16 values retained | `test_regime_source_estimates`, `test_estimate_table_transcription_all_types` |
| §3.6.1 source Q347 / §3.6.2 annual CV | `low_flow_from_observations` | Annual constant1/9 series: pooledQ347=1, annual values1/9, CV=100sqrt32/5; NOT mean annual Q347=5 | `test_pooled_q347_not_annual_mean_and_annual_cv` |
| §3.6.1 flushing subtraction | `FlushingCorrection` ABSENT/SUBTRACT/UNKNOWN + daily components | Daily sequence5…369 givesQ34723.2; subtract4 each day gives19.2; missing component unknown, excess subtraction invalid | `test_linear_quantile_and_flushing_correction`, `test_flushing_components_cannot_cross_scenarios` |
| §3.6.1 HADES5.8 imported route | `LowFlowStatistics(q347=Flow, coefficient_of_variation=Percent,source,inputs)` | Accept source-attributed prepared HADES estimate/area/location/A4 transfer in inputs; no statutory profile/operator substitution | Import path exercised by all low magnitude tests; A4 transfer integration belongs lead |
| §5.5 Fig22 | `low_flow_thresholds`, `assess_low_flow_magnitude`, `assess_low_flow_observations` | All50/200/500/1000l/s anchors exact, intermediate125/350/750 linear, source endpoints below/above | `test_figure22_anchors_interpolation_and_endpoint_rule`(9), `test_all_low_magnitude_class_boundaries`(4) |
| §5.5 best class, increased flow, QSunk | same + `TroughApplicability`, `TroughDischarge` | CV90/D80→class1; CV80/D80→5; increased flow→1 even CV absent; Q34745 vs ref50 with QSunk10l/s→D80,class5; missing trough→unknown | `test_cv_better_class_increase_and_trough_substitution` |
| §§3.5.4,3.6.4 observed circular timing | `circular_timing`, `seasonality_from_observations` | Dec31/Jan1 resultant nearJanuary, not midsummer; annual max/min dates use complete years; unresolved ties remain unknown | `test_circular_year_boundary`(2), `test_observed_extrema_and_explicit_tie_policy` |
| §§5.4,5.6 Fig21 direct reference | `assess_seasonality`, `assess_seasonality_observations` | Inclusive.3/.6/.9/1.2→classes1/2/3/4 | `test_direct_seasonality_boundaries`(5) |
| §§5.4,5.6 reference ellipse | `ReferenceEllipse`, `ellipse_distance`, `assess_seasonality` | Point.38 from radius.1 ellipse hasdistance.28→2; directdistance.28→1; ellipse interior0; rotated anisotropic cases verified | `test_ellipse_and_direct_distinct_thresholds_and_geometry`, `test_ellipse_inclusive_thresholds_at_declared_numerical_precision`(5) |
| §§3.6.3,5.7 Fig23 | `low_flow_duration`, `assess_low_flow_duration`, `assess_duration_observations` | Two15day spells at equality total30 but longest15→class1; thresholds20/35/50/65 enter2/3/4/5 | `test_annual_longest_not_total_and_threshold_equality`, `test_duration_intervals`(8) |
| §3.6.3 cross-year rule | same | 30day spell crossing2001/2002 assigned entirely2001; annual30/0, mean15 | `test_cross_year_spell_whole_and_assigned_start_year` |
| §3.6.3 censored/gapped spell | same | Unknown initial start or terminal end and unsupported interval remain unknown; predecessor/successor high days resolve | `test_missing_and_terminal_spell_stay_unknown`, `test_initial_low_spell_has_unknown_start_not_invented_january_start`, `test_predecessor_and_successor_resolve_boundary_spells` |
| C2/C5 attribution and physical validity | observation assessment wrappers | Original scenario/member/location/version/intervals retained; wrong target/reference location or changed member refused; historical reference period/scenario/kind preserved; short affected record retains INCOMPLETE | `test_observation_assessments_and_unknowns_keep_original_inputs`, `test_observation_assessment_refuses_relabelled_context`, `test_observation_reference_location_must_be_explicitly_transferred`, `test_observation_member_cannot_be_relabelled`, `test_shorter_observation_window_retains_partial_assessment_coverage`, `test_reference_period_and_kind_are_not_silently_relabelled` |
| C5 warmup/presence/invalid | all preparation routes | Warmup incomplete year excluded from MQ/Q347; negative/nonfinite/bad units fail rather than unknown; overlaps/coarse means refused; input ordering does not change coverage | `test_warmup_year_cannot_enter_q347_or_annual_mean`, `test_invalid_domain_inputs_raise_not_unknown`(8), `test_invalid_daily_overlap_resolution_and_location`, `test_observation_order_does_not_change_coverage` |

## Independent floods and additional stormwater

Tests in this section are in `tests/test_flow_events.py`.
| Source | Operation/input | Expected and actual | Executed evidence |
|---|---|---|---|
| §3.5.1 Table4 all16 types | estimate_mhq_from_mean(Flow,regime_type) | MQ × source factor, e.g type3 factor4.7 | test_source_mhq_tables (16 cases) |
| §3.5.1 Table5 all16 types | estimate_mhq_from_area(Area,regime_type) | specific l/s/km² × area; type14 706 | test_source_mhq_tables |
| §3.5.1 observed MHQ | observed_mhq complete daily FlowSample tuple | annual maxima then mean, leap day retained; missing/partial years refused | test_observed_mhq_complete_leap_year_and_missing_day |
| §3.5.2/.3 | flood_frequency_from_record(InstantaneousRecord, daily-mean-statistic MHQr:Flow,regime_type) | Q*=0.6 MHQr; strict > crossing; intervening ≤Q*/2; ≥5 days after qualifying drop; flush excluded ecological exception included | test_independent_crossings_drop_five_days_and_flushing_exception, test_strict_crossing_and_five_day_equality |
| §3.5.3 calendar | same | independence state retained across year boundary; annual rate over calendar years, not365-day approximation | test_cross_year_separation_keeps_predecessor |
| §3.5.3 numerical support | same with support DAILY_ONLY/INCOMPLETE, missing sample, partial year | undetermined, not zero or inferred event absence | test_daily_or_incomplete_cannot_certify_frequency, test_missing_and_partial_year_keep_undetermined |
| §5.3 Fig19 | flood_frequency(context,EventFrequency,regime_type) | HIGH minima2 for1–5/13,3.5 for6/7/10–12/14/15,6 for8/9/16; lower boundaries1,2/3,1/3 | test_flood_natural_regime_groups (16 cases), test_flood_boundaries |
| §5.3 independent gaps | imported frequency without regime | <1 still classified; ≥1 undetermined best-class distinction | test_missing_regime_only_affects_best_classes |
| §3.7.9 observation/catalogue | stormwater_events(context,StormwaterEvent tuple,MQ,MHQ,support) | independent drainage-event catalogue only; MQ+QE>Q*, equality excluded, natural receiving-river peaks not operands | test_stormwater_additional_drainage_events_not_natural_peaks |
| §3.7.9 GEP numerical estimate | stormwater_rainfall(context,MQ,MHQ,DrainageResponse,RainfallFrequency) | inverse critical intensity (Q*−MQ)/(Aψ); matching supplied IDF point at concentration duration; f=1/T | test_gep_inverse_rainfall_and_frequency |
| §5.10 Fig28 | stormwater_frequency(context,EventFrequency) | <.2,[.2,2),[2,4),[4,8),≥8 | test_stormwater_boundaries |
| Common C2/C5 | InstantaneousDischarge and all attributed records | exact m3/s/l/s; reject mean Flow, nonfinite, negative, duplicate/misaligned samples; preserve context, inputs, windows | test_instantaneous_types_and_invalid_inputs and observation tests |

`EventSupport.COMPLETE` requires supplied annual event-resolution evidence;
it is not inferred from the number of listed knots. A premature re-crossing
interrupts the separation interval (`test_premature_recrossing_restarts_required_drop_wait`).
`ReferenceFloodMagnitude` records are accepted directly by the event/rainfall
routes, preserving their daily-MHQ source and preparation inputs. Warmup,
missing-correction and reference-kind guards are exercised by the regression
cases at the end of this test module. Missing source data remain different from
invalid typed input.

The GEP route computes critical intensity from `(Q*−MQ)/(Aψ)` and uses a supplied
matching intensity/duration/return-period relation point. It does not invent a
rainfall curve or interpolate an unsupported external relation.

## Hydropeaking, flushing and finite graphical support

Tests in this section are in `tests/test_flow_pulses.py`.
| Source | Public operation/input | Expected/actual | Test |
|---|---|---|---|
| §§3.7.1–3.7.3 | estimate_hydropeaking / HydropeakingOperation | turbine3+residual2→peak5, trough2, ratio2.5 | test_operating_estimates_and_zero_trough |
| §§3.7.1–3.7.5 | observe_hydropeaking / PulseSampling + PulseObservation | five years × ten Monday-starting calendar weeks; extrema40/1; daily ratio quantile4, NOT40 | test_observation_daily_ratio_quantile_not_ratio_of_quantiles |
| §§3.7.4–3.7.5 | observed SignedState stage | rise1/60, fall1/20 cm/min; daily median extrema, not discharge derivative | same test |
| §5.8.2 | stage_correction / StageRate | anchors0.5→.65,1→.75,2→1,4→1.5; interpolation1.5→.875; outer constants | test_stage_correction_anchors_and_interpolation |
| §5.8.2 | catchment_correction / Area |250→.5,750→.75,1250→1; intermediate/outer values | test_catchment_correction |
| §5.8.3 Figure25 | assess_hydropeaking / HydropeakingMetrics | all five classes at multiple x; successful observed class2 | test_figure25_supported_interiors; test_observation_successful_interior |
| §5.8.3 source gaps | assess_hydropeaking | (.1,2),(.1,2.01), off-domain → undetermined | test_figure25_edges_precision_and_domain |
| §§3.7.6,3.7.8 | observe_flushing / typical event hydrograph | peak22−base2=20; max rise4cm/min→1.5 | test_flushing_observation_and_operating_estimate |
| §§3.7.6–3.7.8 | estimate_flushing / FlushingOperation | excess20; mean rise2.5cm/min→1.125 | same test |
| §§3.7.7,5.9.2 | FlushingMetrics.events_per_year | frequency for the supplied threshold/type retained from operational evidence, not invented event separation | flushing tests |
| §5.9.2 | FlushingTiming HIGH/MEAN/LOW | correction.75/1/1.5; interpolated rise retained | test_flushing_timing_and_rise_interpolation |
| §5.9.2 | assess_flushing / several types | worst class4, not average; unknown blocks except known worst5 retains incomplete | test_worst_flushing_combination_not_average |
| §5.9.3 Figure27 | assess_flushing | all five coloured interiors supported at x1 and x10 | test_figure27_supported_interiors |
| §5.9.3 gaps/review | assess_flushing + HydropeakingReview | .05/year off plot; ≥60 retains explicit review and supplied judgement; gray has no class | test_figure27_below_plot_and_review_at60 |
| §5.9 independent calculations | missing ≥60 review | stress1 still computed | test_high_frequency_review_does_not_erase_computable_stress |
| C2,C3,C5 | all attributed routes | context identity and original inputs retained; stage gaps retain discharge metrics; daily means rejected | test_missing_stage_does_not_erase_independent_metrics; test_observation_gaps_and_stage_gaps; test_invalid_daily_evidence_and_window; test_invalid_types_and_units; test_invalid_rates |

| Additional source requirement | Public operation/input | Expected = actual | Executed test |
|---|---|---|---|
| §§3.7.1–3 residual estimate | `estimate_hydropeaking_from_residuals` | Concession residuals 1+0.5 plus intermediate Q347 0.5 give trough 2 and peak 5 | `test_residual_sum_and_intermediate_reference_estimate` |
| §3.7.7 threshold-specific frequency | `FlushingAnnualEvents`, `assess_flushing_events` | Annual excess lists (1,2,3),(2), threshold 2 → 1.5/year; equality counts | `test_flushing_frequency_counts_threshold_equality_not_lower_events` |
| Annual/type coverage | Same operation | Wrong calendar window, duplicate years or mixed unrelated event types rejected | `test_flushing_annual_catalogue_rejects_outside_window_and_mixed_types` |
| Finite endpoint transcription | `assess_hydropeaking` | (3.25,2.2) lies in declared edge uncertainty, not a clamped class 4 | `test_figure25_exact_right_endpoint_does_not_use_last_interior_sample` |
| Warmup and presence | Observation routes | Excluded discharge/transition/event intervals cannot assess; unsupported numerical observations retain their value and status | `test_hydropeaking_warmup_discharge_and_stage_intervals`, `test_flushing_observation_warmup_interval_is_not_assessed`, `test_observation_presence_preserves_unsupported_numbers` |

At 60 flushing events/year and above, results retain both the required
hydropeaking review and any supplied applicability judgement. The grey graphical
region supplies no colour class, even when a judgement retains the flushing
route. This is separate from Table 8's exactly-40 band gap and from finite-plot
cases such as frequency 0.05/year.

## Reach delineation, propagation and Appendix A4

| Source / requirement | Public operation and input | Expected = actual | Executed test |
|---|---|---|---|
| §6.1.1 reach changes | `delimit_reach(ReachBoundaryInputs)` | Growth 15% does not split, >15% does; significant intervention/tributary and groundwater doubling do | `test_catchment_conditions.py::test_all_reach_delimitation_thresholds` |
| §6.1.1 lakes and end of influence | Same; `screen_ended_influence` | 1h/3h equality does not cross strict lake threshold; >3h ends influence; lake never a river class; all nine class1 can end, eight cannot | Same; `test_source_lake_end_can_feed_downstream_river_without_classifying_lake` |
| §6.1.2 Figure 30 | `propagate_indicator(DrainageNetwork,outlet,indicator)` | Nearest point classes 2×20+4×20+1×10 over50 →2.6→class3; nested upstream class5 not double counted; different indicator can use farther point | `test_catchment_conditions.py::test_nearest_upstream_per_indicator_and_no_nested_double_count` |
| §6.1.2 missing coverage | Same, 100km² target | Missing14.9%→class2/incomplete; 15%→equality unresolved;15.1%→unknown; ultra-close decimal neighbors use unrounded branch | `test_unrounded_missing_area_threshold` (5 cases) |
| §6.1.2 rounding/lake | Same | Exact2.5→3, not ties-to-even2; lake not applicable | `test_half_up_rounding_not_bankers_rounding_and_lake_not_classified` |
| Topology and identity | `CatchmentNode`, `DrainageNetwork`, boundary inputs | Cycles, repeated nested branches, excess upstream area, missing IDs, foreign-scenario classes rejected | `test_topology_and_area_refusals`, `test_boundary_refuses_foreign_scenario_results` |
| A4 one upstream interpolation | `interpolate_discharge` | Areas10/20/30, quantities2/8 →5 | `test_hydrological_transfer.py::test_one_and_two_upstream_linear_interpolation` |
| A4 two upstream interpolation | Same, two disjoint branches | Areas15+15/target40/down60; quantities2+4/down12 →8 | Same |
| A4 one/two donor extrapolation | `extrapolate_discharge` | Donor20/5 to40 →10; combined20+30/5+10 to40 →12; MHQ5×2^0.7 | `test_one_two_donor_extrapolation_and_mhq_exponent` |
| A4 specific discharge | `estimate_specific_discharge` | 2l/s/km² ×50km² →0.1m³/s; missing qualification stays unknown | `test_specific_discharge_estimate_and_missing_qualification` |
| A4 area-independent quantities | `transfer_area_independent` | Source difference weights3/7,5/14,3/14 give3; one donor copies; all equal-area singularity unknown, not equal-weight guess | `test_area_independent_weights_not_inverse_distance` |
| A4 support and topology | Typed donor/target values, qualifications and atomic catchment memberships | Unqualified/30–250%-out-of-domain estimates unknown; missing independence unknown; overlapping donor units rejected; missing/warmup donor or target unknown | `test_invalid_versus_unsupported_transfer`, `test_two_donor_sum_requires_independent_catchment_evidence`, `test_nested_transfer_catchments_are_not_summed`, `test_transfer_cannot_promote_missing_or_excluded_source` (6 cases) |

## Source aggregation and runnable composition

| Source / requirement | Public operation and input | Expected = actual | Executed test |
|---|---|---|---|
| §6.4 Figure33 all transitions | `overall_class(worst,points)` | W2:10→1/11→2; W3:12→1/13–14→2/15→3; W4:16→2/17–22→3/23→4; W5:24→3/25–30→4/31→5 | `test_hydrological_condition.py::test_every_figure33_transition` (15 cases incl W1) |
| §6.4 published example | `assess_hydrology` with5,3,3,1,1,1,1,1,1 | 26points→class4; single class5 hydropeaking overrides matrix result | `test_26_points_and_hydropeaking_override` |
| §6.4 incomplete exception | Omitted required indicators | One known5 does not assess; two known5 →overall5 with seven explicit unknowns/incomplete | `test_missing_and_two_known_bad_exception` |
| §§5.11/6.4 source screening | Nine screened1 results versus one missing | Screened set→complete1; unknown prevents result; classed partial spatial coverage stays incomplete | `test_screened_is_not_missing_and_partial_spatial_coverage_survives` |
| Ch2/4 composition | `assess_river_hydrology` and `InventorySurvey` | Positively surveyed empty inventory→screened1; unknown inventory cannot; canal/drain/lake never natural-river class; raw calculations remain inspectable | `test_hydrological_assessment.py::test_known_empty_inventory_distinct_unknown_inventory`, `test_artificial_and_lake_references_cannot_acquire_river_class` |
| Missing preparation | Same with nine computed values | Incomplete inventory retains incomplete coverage; structural naturalisation does not establish reference | `test_incomplete_inventory_not_hidden_by_nine_computations` |
| Reference scope | Same with foreign scenario/member/data/config | No overall reference-authorised class; numerical calculations retained | `test_unrelated_reference_cannot_authorise_composed_river_class` |
| Complete F9 chain | `examples.hydrological_condition.scenario()` | Point classes2,1,1,3,1,2,2,2,2 →17points/class3; downstream class2/complete; missing stage→overall unknown/incomplete, independent R36 unchanged | `test_hydrological_example.py::test_complete_and_partial_hydrological_example` |
| Independent Swiss prescription | Computed pulse class2 versus5 linked as scoped `ConditionFinding` | Same nominal 220l/s prescription and same delivery assessment; only condition finding changes | `test_computed_conditions_do_not_change_swiss_prescription_or_delivery` |

## Applicable common behavior

| Acceptance | Observable behavior and evidence |
|---|---|
| C1 | Existing origin/designation/use identities remain unchanged. The reference/composition tests cover river versus canal/drain/lake; prepared river identity does not infer a biological or legal status. Existing spatial-track tests continue to cover heavy modification and use-category independence. |
| C2 | `AssessmentContext`, original input records, explicit Swiss regime evidence and `ReferenceProfile` preserve method, scenario, member, mapping, calendar, units and versions. Raster/Pardé/operating coefficients are supplied inputs; source tables remain immutable tuples. Identity mutation tests refuse unrelated inputs. |
| C3 | Screened class1 differs from unknown. Required omissions become explicit positions; one missing blocks the overall class except the source two-known5 rule. Classed incomplete catchment coverage is never marked complete. |
| C4 | HYDMOD has no duty/deliverability-cap operator. The computed-condition/Swiss integration test proves it neither uplifts nor rewrites an independently supplied prescription or delivery result. |
| C5 | Typed quantities refuse wrong units, negative nonnegative quantities and nonfinite values. Signed stages remain allowed. Daily/instantaneous distinction, duplicate/overlap/location/time guards, leap calendar, warmup, zero versus missing/unsupported/outside and partial coverage are exercised in the four metric suites and propagation tests. |
| C6 | The example runs one supplied configuration without a live model, adopted plan or completed pilot. Caller comparisons and scientific acceptance remain external; no scenario orchestration or optimisation is introduced. Supported outputs remain available on the partial path. |

## Executed integrated gates

Executed on implementation `ccdce60646b38535d94b0ea5dcd97d43e34fb421` with
Python 3.13.8, Fishy 0.1.2, Polars 1.44.2, pytest 9.0.2, Ruff 0.15.0 and ty 0.0.66.
The optional transport revisions are the exact Git pins listed above.

| Command / check | Actual result |
|---|---|
| Focused nine test modules, without optional simulator packages | **413 passed** |
| `uv sync --locked`, then standalone import check and example | Taqsim and Incidence both absent; downstream class2 and partial unknown computed successfully |
| `uv run python examples/hydrological_condition.py` | Point classes `[2,1,1,3,1,2,2,2,2]`, 17points/class3; downstream class2/complete; missing stage unknown/incomplete |
| `uv sync --locked --all-extras` | Locked optional revisions installed successfully |
| `uv run --all-extras pytest -q` | **2,274 passed**, no skips |
| `uv run --all-extras ruff format --check` | 163 files already formatted |
| `uv run --all-extras ruff check` | All checks passed |
| `uv run --all-extras ty check` | All checks passed |
| `git diff --cached --check` before implementation commit | No whitespace errors |

The nine focused suites contain 93 inventory/reference, 114 regime, 73 event,
71 pulse, 11 catchment, 13 transfer, 27 aggregation, 9 composition and 2 example/
Swiss-integration tests. These are executed software tests, not site validation.
During implementation review, defects were first reproduced on the actual path
before correction: reference permission binding, warmup use, identity relabelling,
interrupted event separation, source graph endpoints, censored spells, missing
coverage and overlapping donor areas. The same regression cases now pass.

Full-repository type checking uses the optional packages because existing
transport examples import Taqsim; their presence is not required by this method.
No private source file or source rendering is needed to run the committed tests.
