# Supplied Kazakh scenario

Run from the repository root:

```console
uv sync --locked --extra taqsim
uv run python examples/supplied_kazakh_scenario.py
uv run pytest tests/test_supplied_kazakh_scenario.py
```

The example itself does not import Taqsim. The extra enables the repository's optional
physical-exchange tests. All locations, reference quantities, shapes, studies and
acceptance statements in this example are **synthetic illustrations**, not calibration,
observations, regulatory decisions or legal certification.

## What the example supplies

The caller example composes existing public operations. It does not add a production
scenario runner, comparison service or report framework.

- A versioned basin with two direct tributaries and two successive main-river sections.
  Prepared context retains channel, floodplain, delta, terminal-water, river-type,
  climate, biology, water-use, operational and transboundary evidence. These are
  attributed supplied findings, not physical assessments derived from a topology.
- Natural annual P50/P75/P90/P97 volumes of 100/80/60/40 million m³.
  Both initial annual variants and all three observation routes are exercised in tests.
  The insufficient route supplies reconstruction/naturalisation evidence. The absent
  route supplies an accepted receiving-parent relationship and explicit donor basis.
- Four design conditions, not an actual operational-year selection. Each receiving
  calendar is leap-year **2028**, with twelve constant, explicitly shifted-class shapes.
  The hypothetical calculation date is 2029-01-01. The separate historical 2024 test
  verifies leap arithmetic and refuses backdated Order111 applicability.
- Recorded-minimum, natural P99 and natural P50 constant hydrographs equivalent to
  10/20/100 million m³ per year. Annual bounds retain their own evidence. These are
  annual design-condition hydrographs, not discharge percentiles of daily samples.
- Explicit dry-year-wording eligibility, monthly-average temporal basis, listed-value
  interpretation and correction-then-bounds order. Synthetic biological evidence
  supplies carp, 15 °C onset on April 15, and three two-day stages. Appendix4 row2's
  printed seasonal coefficient 1.18 applies to April in design75/95 only. The unexplained
  stars are retained but not relied upon for this illustrative eligibility decision.
- Eighty supplied ecological assessments per class. Specialist interval extrema,
  coincident floodplain inundation, temperature swing, fish access, ice, downstream
  arrival and drying state are supplied independently of monthly flow. Monthly flow
  is used only for the November/December mean-flow recommendation. Its selected
  40% of 2 m³/s is a **0.8 m³/s recommended lower bound**, not a cap.
- An Order111 selected oxygen/nitrite profile: dissolved oxygen 7 mg O₂/l and nitrite
  ion 0.05 mg/l pass the configured class1 cells (oxygen ≥6, explicitly interpreted
  nitrite ≤0.1). Ion and reporting identity are retained; no conversion to nitrogen
  is inferred. A separate saprobity-only profile at 3 with explicit closed ranges
  matches class4 and demonstrates the drinking-use table conflict. These profiles
  do not establish a unique national overall class or scientific acceptance.
- A recent study-review inventory and explicit source applicability. Paragraph11's
  2027 commencement is tested. Other provisions remain applicability-unknown when
  first-publication evidence is absent; no publication date is invented.

`supplied_basin_context.py` and `supplied_ecological_studies.py` hold readable external
fixtures. Their synthetic assumptions are not package defaults. The full example
prints interpreted candidates. No aggregate conceals an unresolved source clause.

## Expected and observed exact results

Tests use `Fraction`, `Volume` and `Flow` exact equality: **no numerical tolerance**.
Display rounding is not used in assertions. Let D = 366 × 86400 seconds.

| Design | Initial million m³ | Actual million m³ | April mean m³/s | February annual share, percent |
|---|---:|---:|---|---:|
| 25 | 100 | 100 | 100,000,000 / D | 1450/183 |
| 50 | 80 | 80 | 80,000,000 / D | 1450/183 |
| 75 | 60 | 3714/61 | 60,000,000 × 1.18 / D | 14500/1857 |
| 95 | 40 | 2476/61 | 40,000,000 × 1.18 / D | 14500/1857 |

The dry-class annual multiplier is `(366 + 0.18 × 30) / 366 = 619/610`.
Monthly volumes sum to the **actual**, not initial, annual volume. Monthly shares
sum to 100%. The original annual allocation remains unchanged. Basin accounting
retains explicit synthetic 3/5 and 2/5 disjoint tributary contributions to that total;
this is not an algorithm for issuing tributary duties. Successive main-river
requirements are not summed as consumptive demands.

The independent hydraulic-composition test adds a supplied 0.1 m³/s April correction
**before** spawning. Its actual annual increment is exactly `0.118 × 30 × 86400` m³.
Neither correction is renormalised away.

Numerical completeness means all **configured** checks have supported operands and
pass. Scientific use remains indicative within the supplied synthetic scope.
Official admissibility is pending. Missing legal reconciliation, source authentication,
publication evidence or full national parameter coverage is never called a pass.
Endpoint level-rate checks establish endpoint averages only, not unseen rapid changes.
The supplied temperature swing and other interval-envelope checks retain their own
support; a flow schedule alone cannot establish these processes.

## Partial and failure scenarios

`tests/test_supplied_kazakh_scenario.py` exercises these public paths:

| Test | Expected and observed result |
|---|---|
| `test_complete_supplied_regime` | 16 combinations: four classes × two annual variants × adequate/insufficient observations; exact table above, complete numerical bounds and studies, interpreted status retained |
| `test_absent_observations_supported_parent_enters_same_complete_chain` | Four accepted donor coefficients 1/.8/.6/.4 enter corrected reports; missing coefficient returns further study |
| `test_partial_annual_missing_shape_and_reconstruction` | Supported initial80 million m³ survives missing shape; no fabricated monthly/actual annual total; missing reconstruction blocks dependent initial result |
| `test_unsupported_biology_and_infeasible_bounds_preserve_initial` | Eligibility affected by unexplained stars stays unsupported; crossed source bounds calculate no candidate; initial40 remains available |
| `test_required_failure_survives_missing_condition` | Floodplain depth0.05 <0.2 m yields FAIL plus INCOMPLETE despite missing duration/velocity; missing study yields UNKNOWN |
| `test_configuration_isolation_and_review_triggers` | Scenario/config/data revisions stay separate; changing the listed basin row2→3 gives dry-class40,000,000 ×309/305 m³ while earlier outputs remain unchanged; changed basin plus missing evidence requires review with incomplete coverage; native coefficient override changes only the revised result; no Uzbek policy operand enters the operations |
| `test_use_mapping_keeps_conflict_and_replica_restrictions` | Class4 drinking: unresolved / conditional intensive treatment / not permitted under no selection / descriptive / matrix; both attributed findings retained |
| `test_prepared_basin_context_and_attributed_account_do_not_sum_repeated_sections` | Mouth→upstream→tributaries; all context kinds retained; exact sum; absent accounting unknown; duplicate river accounts rejected |
| `test_historical_2024_leap_shape_keeps_volume_but_quality_cannot_backdate` | February29/366 shares; annual100 million preserved; pre-commencement quality unknown despite later calculation date |
| `test_supplied_kazakh_duty_is_not_generated_or_capped_by_deliverability` | Actual corrected April requirement remains separate from supplied availability8, deliverability6, hypothetical duty10 and delivery5 m³/s; feasibility shortfall4, duty shortfall5 with incomplete hydraulic coverage; later11 leaves prior result and duty unchanged |
| `test_supplied_hydraulic_relation_changes_actual_report_without_renormalising` | Supported relation +0.1 before April1.18 correction gives exact additional305,856 m³, retaining initial40 million |

## Source clause → operation → result → executed test crosswalk

Authority is the supplied Russian Ministry Order179-НҚ dated 2025-07-23 and the held
12-page CAWater Order111 replica dated 2025-06-04. The latter is not authenticated
publisher-direct evidence. The local bundle's D.3 register defines candidate readings,
not legal amendments. Original PDF layouts were inspected for equations, coefficient
headings and Order111 use tables/row70. All seven vision-recorded bundle identities
matched SHA-256 before use. No source PDF or private report is redistributed here.

Test prefixes below identify files: **I**=`test_supplied_kazakh_scenario.py`,
**B**=`test_basin.py`, **A**=`test_kazakh_allocation.py`, **R**=`test_kazakh_review.py`,
**F**=`test_flow_bounds.py`, **S**=`test_spawning.py`, **E**=`test_ecological_conditions.py`,
**Q**=`test_water_classification.py`. Names are exact test functions.

| Requirement/source | Public operation and supplied input | Observable expected/actual result | Test |
|---|---|---|---|
| 4 | `SectionContext`, phase/channel/floodplain/delta/terminal `ContextEvidence` | Every context retained; no flow-only ecological verdict | B `test_context_evidence_preserves_every_supplied_kind_and_scope`; I basin-context test above |
| 5 | `PreparedTopology`, `mouth_to_source`, `tributary_sum` | Mouth precedes upstream; 30+20=50 m³; repeated same-water accounts rejected | B `test_mouth_to_source_sections_and_receiving_rivers_before_tributaries`, `test_supported_paragraph5_sum_preserves_source_and_exact_attribution`, `test_double_counting_and_mixed_support_cannot_produce_result` |
| 6 | Section river type, explicit connectivity, biology/transboundary findings | Mountain/plain transitions and source-order labels do not infer connectivity | B `test_source_order_labels_do_not_create_or_override_connectivity`; I basin-context test |
| 7 | `seasonal_schedule`, real intervals, explicit supported pattern | Monthly coarsest example; monthly mean cannot prove daily stages | A `test_explicit_shape_operators`; S `test_monthly_cannot_prove_daily_stage_and_partial_month_refused` |
| 8 | Scoped climate/context findings | Climate and feeding-source study attribution retained, no reconstruction invented | B `test_context_evidence_preserves_every_supplied_kind_and_scope` |
| 9 | `assess_actual_year_adjustment`, separate forecast/current issue evidence | Supported leap-month volume change; missing forecast blocks assessment, not arithmetic | R `test_successful_supplied_actual_year_decision_exact_leap_month_volumes`, `test_missing_operational_evidence_keeps_arithmetic_but_not_pass` |
| 10 | Natural reference/context and ecological studies | Supplied hydrological/chemical/biological/model/field evidence remains attributable, not fabricated | B context test; E `test_independent_complete_supplied_conditions`; I complete test |
| 11, enactment4 | `appendix1_report`, `order179_applicability` | Typed basin/river/section report; paragraph11 not in force2026, in force2027; others need publication | A `test_reporting_identities_and_meaningful_annual_only_result`; R `test_deferred_paragraph_11_without_publication`, `test_other_provisions_require_publication_and_start_after_its_day` |
| 12 | Reference, contextual inventories, `Order111Profile`, supplied studies | Source/period/location retained for all categories; no assumption every contaminant has been supplied | B context test; I complete and chemical profile |
| 13 | `DonorRelation`, reconstruction findings, specialist study | Accepted substitute evidence can run; unavailable donor remains further study | A `test_receiving_parent_transfer_success_missing_and_incompatible`; I absent route |
| 14 | Immutable `Provenance`, `EvidenceScope`, typed locations | Incompatible scenario, reference, location or version cannot be silently reused | A `test_invalid_inputs_identity_immutability_warmup`; E `test_study_cannot_transfer_physical_or_production_versions` |
| 15 | `initial_allocation` / `transfer_allocation` | Adequate, insufficient and absent routes available | I complete and absent-route tests |
| 16 | `NaturalAnnualReference.reconstruction` | Prepared annual/monthly reconstruction required, never estimated automatically | A `test_observation_routes_and_exact_evidence_scope`; I partial-annual test |
| 17(1) | `DesignClass`, initial variants | Design25/50/75/95 →100/80/60/40 million | A `test_both_initial_routes_not_second_reduction`; I complete |
| 17(2) | `DesignBounds.recorded_minimum`, correction diagnostics | Recorded lower adjustment retained separately | F `test_each_bound_adjustment_retained_and_recorded_floor_not_discarded` |
| 17(3) | Level/floodplain/oxygen/thermal/movement supplied-study operations | 80 supported configured assessments/class; missing relation not passed by discharge | E `test_independent_complete_supplied_conditions`, `test_low_oxygen_thermal_and_movement_fail`, `test_temperature_swings_need_sufficient_temporal_support`; I complete/failure |
| 18 | `AllocationRoute` explicit alternatives | Coefficient route reproduces initial shift, no second reduction | A `test_both_initial_routes_not_second_reduction` |
| 19(1–5) | Imported natural quantiles, annual/design hydrographs, `correct_schedule` | Natural annual basis retained; crossed bounds unresolved before arithmetic | F `test_crossed_bounds_refuse_before_any_candidate`, `test_crossed_annual_bounds_stop_schedule_and_remain_attributed` |
| 19(6) | Explicit `ShapeChoice` and weighted mean-one shape | [16,12,8,4] vs [4,8,12,16], same mean10; missing shape preserves annual | A `test_explicit_shape_operators`, `test_missing_choice_pattern_and_unsupported_pattern_keep_annual` |
| 20 | Median-normalised initial coefficient | 1/.8/.6/.4, positive denominator; 0/0 unresolved, independently supported zero shift survives | A `test_zero_ratio_unidentified_but_independent_shift_survives` |
| 21 | Insufficient route with reconstruction findings | Same supported annual and seasonal results; missing reconstruction blocks dependent result | I complete/partial-annual tests |
| 22 | `DonorReference`, `transfer_allocation`, receiving parent | Explicit accepted donor basis; not nearest or numerical-order choice; missing basis further study | B `test_receiving_parent_not_higher_order_child_or_unconnected_gauge`; A `test_unaccepted_coefficient_basis_cannot_transfer`, `test_transfer_accepts_explicit_distinct_donor_reference_but_not_undeclared_changes`; I absent route |
| 23 | `assess_review`, study date, basin/new-evidence inventories | Inclusive five-year deadline; known trigger survives missing evidence; immutable prior result | R `test_five_calendar_year_deadline_inclusive`, `test_known_basin_trigger_survives_missing_study_and_new_evidence_inventory`; I isolation |
| 24 | Level rates, seasonal timing, sensitive-area arrival | Separate rise/fall limits, supplied synchronisation and guaranteed-supply criteria | E `test_separate_rise_fall_real_elapsed`, `test_natural_seasonal_peak_timing`, `test_special_release_supply_and_connection_are_not_reservoir_discharge` |
| 25 | `CorrectionOrder` and timed coefficients | q8,L5,U10,K1.5→10 or12; suppressed correction versus upper exceedance; interpreted candidate remains | F `test_discriminator_real_volume_and_unresolved_priority` |
| 26 | Published stages / separately weighted study | Published1.18 not recalculated; weighted study1.2 separate | S `test_all_published_values_not_reaveraged_or_clamped`, `test_study_average_separate_weights_and_period` |
| 27(1) | `spawning_eligibility`, explicit interpretation | At50/75/95: true,true,false vs false,true,true; missing selection unknown | S `test_eligibility_both_readings_equality` |
| 27(2) | `BiologicalTiming`, species/water onset/durations | Missing or inadequate onset unsupported, not calendar guess | S `test_missing_and_unresolved`, `test_scoped_support_not_generic_check_passthrough` |
| 27(3) | Daily observations, `DAILY_STAGE` | 1.2,1.2,1.25,1.25,1.1,1.1,1; simulated daily input not observed route | S `test_daily_stages_and_explicit_neutral_outside_season`, `test_simulated_daily_flow_cannot_select_observed_daily_branch`, `test_daily_observation_versions_remain_distinguishable_in_coefficients` |
| 27(4) | `MONTHLY_AVERAGE` and biological period | April1.18 changes actual dry-class annual volume, neutral elsewhere | I complete; F `test_supplied_biological_monthly_schedule_enters_bounds_and_changes_annual_volume` |
| 27(5) | Annual ±15-day shift, same biological duration | ±15 allowed with revised evidence;16 invalid; duration unchanged | S `test_shift_preserves_duration_and_requires_annual_evidence`, `test_invalid_biology` |
| 28 | `apply_hydraulic_correction`, explicit relation/order | 8+2=10;8−9 infeasible; integrated April+0.1 adds305856 m³ after spawning | E `test_supplied_hydraulic_correction_computes_supported_flow`; I hydraulic test |
| 29 | Winter continuity, oxygen and ice studies | Continuous minimum1≥0.5; oxygen7≥6; missing/frozen evidence not passed by mean flow | E `test_depth_literal_and_frozen_conditions_fail`, `test_low_oxygen_thermal_and_movement_fail`; I complete |
| 30 | `WinterShare`, Nov/Dec observed long-term monthly low flow | Chosen30–50% lower recommendation, never50% upper cap; absent choice unresolved | E `test_winter_recommendation_is_lower_bound_not_upper_cap`, `test_winter_selection_missing_and_non_november_refused`; I complete |
| 31 | Sensitive-area arrival, connection, level and oxygen studies | Distinct arrival and reservoir discharge; insufficient arrival FAIL plus missing connection | E `test_special_release_supply_and_connection_are_not_reservoir_discharge`; I complete |
| 32(1–4) | Drying origin, seasonal timing, ice, depth/velocity selection | Natural versus induced drying; depth0.1 inclusive; velocity0.2–0.6 needs supported selection | E `test_drying_origin_is_not_inferred_from_zero_flow`, `test_small_river_velocity_requires_selected_threshold`, `test_depth_literal_and_frozen_conditions_fail`; I complete |
| Appendix1 | `appendix1_report`, corrected samples and `ReportingIdentity` | Exact table above, correct units and annual shares; zero total shares undefined | I complete; A `test_zero_missing_unsupported_outside_and_partial_are_distinct` |
| Appendix2 | `shifted_class`, both initial variants | Exact mapping25→50,50→75,75→90,95→97 | A `test_both_initial_routes_not_second_reduction` |
| Appendix3 | Recommended stage ranges | Migration1.10–1.15, spawning1.25–1.30, incubation1.05–1.10, seasonal1.13–1.18 retained | S `test_all_published_values_not_reaveraged_or_clamped` |
| Appendix4 | All eight attributed rows, printed averages and stars | Aral–Syrdarya migration1.20 retained above generic1.15; unresolved stars never invented | S `test_all_published_values_not_reaveraged_or_clamped`, `test_missing_and_unresolved` |
| Order111 commencement/scope | `assess_order111`, `WaterScope`, calculation/observation dates | Rivers/canals/in-channel reservoirs eligible; lakes/seas excluded; historical2024 unknown | Q `test_applicability`, `test_commencement_and_exact_identity_support`; I historical test |
| Order111 numerical table | `SourceValue`, exact unit/form, operators and cell interpretations | Six-class matches, strict/open ranges, printed gaps and qualified cells retained | Q `test_numerical_match_each_class_without_false_unique_algorithm`, `test_printed_operators_and_open_ranges`, `test_calcium_qualification`, `test_astana_phosphate_qualification_and_no_ion_conversion`; I chemical profile |
| Order111 complete held numerical table | All84 physical rows/504 cells with explicit source-specific candidate meanings | Every cell has an attributed evaluation route; ambiguous default meanings remain unresolved | Q `test_every_source_cell_has_attributed_evaluation_route`, `test_bacterial_counts_all_six_classes_with_explicit_scaled_unit_interpretation`, `test_merged_temperature_explicit_shared_seasonal_condition`, `test_macrobenthos_qualitative_alternative_and_unknown_not_zero` |
| Order111 row70/notes | Explicit `RatioTypography`, source cells | Ambiguous exponent transcription remains unresolved without selection; no silent repair | Q `test_row70_typography_never_silently_repaired`, `test_unresolved_cells_and_raw_catalogue_identity` |
| Order111 Tables1–2/sanitary notes | `assess_order111_use`, explicit mapping | Class4 drinking conflict preserved; treatment adequacy/sanitary compliance not inferred | Q `test_class4_drinking_conflict_all_branches`, `test_every_matrix_row_and_class`, `test_descriptive_conditions_and_separate_sanitary_notes`; I use test |

The detailed public-operation explanations remain in [basin](basin.md),
[allocation](kazakh-allocation.md), [review](kazakh-review.md), [bounds](flow-bounds.md),
[spawning](spawning.md), [ecological conditions](ecological-conditions.md) and
[water classification](water-classification.md). Those crosswalks include further
boundary and regression discriminators.

## Remaining source and application limits

Seasonal shape, coefficient notation, correction priority, spawning eligibility,
listed coefficients/stars, donor wording and class4 drinking mapping remain labelled
interpretations. None is officially reconciled by a numerical pass. The selected
quality profiles leave other chemical, biological and qualitative cells unclaimed.
The row70 typography and unauthenticated replica remain source limitations.

This is not a field basin pilot. No reconstruction engine, routing solver, thermal or
reactive-process simulator, optimisation or legal duty issuance is implied. No
available/deliverable water or actual delivery is invented from a requirement. The
Uzbek deliverability cap, quality-activation gate and advisory spawning semantics are
not used. `test_supplied_kazakh_duty_is_not_generated_or_capped_by_deliverability` calls native
`assess_feasibility` and `assess_duty` with an independently supplied hypothetical
Kazakh duty. Discharge failure survives missing hydraulic coverage. Duty10 is never
replaced by deliverability6; later delivery11 does not rewrite either duty or prior
shortfall5. Its monthly delivered amount does not establish within-month performance.

Common acceptance: C1 physical identities/context do not infer a track from water use;
C2 scenario/version isolation; C3 failure plus incomplete and unknown required checks;
C4 native supplied-duty test above, **not** the Uzbek capped-duty formula;
C5 exact calendar/units/support and zero-versus-missing tests; C6 independently runnable
supplied example with useful annual-only results and external comparisons.
