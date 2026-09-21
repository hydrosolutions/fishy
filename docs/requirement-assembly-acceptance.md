# Requirement assembly acceptance

## Source and execution boundary

Technical interpretation: accepted Taqsim Effort31 vision; owner-selected
`fishy_taqsim_handover_candidate_2026-09-19`. Normative proposed-method sections:
`part4_assembly_contract.qmd` D.10 (selection, component assembly, deterministic
failure and complete synthetic calculation), Appendix A steps8–12,
`part4_lowflow_safeguard.qmd` D.5, `part4_quality_calculation.qmd` D.4 and
`part4_hydraulic_assessment.qmd` D.9. Test constants are derived synthetic witnesses,
not copies of private chapters or originals. No hypothetical result adopts policy.

Ramsar VIII.1 Annex §§1–2,18–20 and BoxE support joint quantity/quality/timing,
not the scenario thresholds. USGS WRIR96-4013 distinguishes cross-section mixing
and travel-time evidence; EPA WASP documents process/state limits, not a required
software dependency. The source bundle's historical software baseline is not the
executed revision. Exact compatible commits and command outputs are recorded with
the delivery evidence, not inferred from package version strings.

## Requirement → public boundary → expected observation → executed test

| Requirement/source | Public operation / supplied inputs | Expected observation | Test |
| --- | --- | --- | --- |
| U5/D.10 whole-family selection | `assess_selected_family`, complete 366-day four-class families | 8/12→12,D=.4;9/11→10,D=.2;allzero→0;0/0/3→3,D=∞ | `test_requirement_family.py::test_complete_leap_year_selection` |
| U5 contributor identity | Same operation, swapped8/12 members | Entire-family upper branch; per-slot contributors swap, ties retained | `test_envelope_contributors_can_swap_but_retained_set_cannot`, `test_ties_and_even_middle_pair_contributors_retained` |
| U5 incomplete/unsupported | One retained member; named exclusion; stale evidence; failed support | Screening retained; no complete selection; failure plus missing stays failure/incomplete | `test_single_member_screening_and_named_failed_exclusion`, `test_stale_acceptance_cannot_follow_changed_values`, `test_failed_member_support_survives_missing_selection` |
| C2/C5/U5 identities | Different method/config/activation/scenario; incomplete year; changing member | Refused, never mixed into one uncertainty family | `test_policy_or_scenario_changes_are_separate_studies`, `test_incomplete_class_calendar_and_changing_member_refused` |
| U5 selection before cap | Supply already capped5 against members8/12 | Selection fails; uncapped12 must precede later obligation5/deficit7 | `test_retained_set_exclusion_overlap_and_delivery_capped_selection_refused`; issuance slice and chain tests |
| U7 same-water/lateral | `compose_requirement` with actual subject-bound `control_equivalent` | same-water3/2→3; lateral2+continuing3→5 | `test_requirement_composition.py::test_same_water_max_and_lateral_signed_balance` |
| U7 missing mapping | Same operation, missing exact mapping evidence | No integrated candidate; separate3 and1 preserved | `test_missing_mapping_keeps_separate_requirements_visible` |
| U7 natural floor | `natural_floor`, complete class95 year with winter minimum2 | min2; cross-class wet-day1 causes crossing1 and whole-family decline | `test_floor_minimum_uses_entire_final_year_not_summer`, `test_final_95_minimum_crosses_other_class_declines_without_repair` |
| U7 direct floors | Actual `apply_quality_component` FLOOR_ONLY and `finalize_floors` | Base3→floor9; no regime, obligation or baseline gate | `test_active_quality_survives_direct_floor_and_no_requirement_is_created`; chain floor-only test |
| C3 final conditions | `assess_requirement`, actual mixing/receptor/hydraulic/study inputs | All actual boundary methods run; known failure survives missing hydraulics; empty required set cannot pass | `test_recheck_candidate_binding_and_all_actual_physical_operators`, `test_known_quality_failure_survives_missing_hydraulics`, `test_empty_final_conditions_cannot_pass` |
| M11 final gate | Actual active quality8→10 plus `finalize_regime` and all365 windows/classes | Provisional deficit2 retained; final pass/floor10; advisory stays8 and declines | `test_requirement_finalization.py::test_m11_actual_active_quality_repairs_final_not_provisional`, `test_m11_advisory_quality_cannot_repair_final_gate` |
| M15 multi-test/class | One threshold11 against10; another class test omitted | Failure plus incomplete coverage; no new requirement/floor | `test_m15_known_failed_test_plus_missing_class_keeps_failure_and_incompleteness` |
| F1/F6 deterministic descent | `FinalRegime.route_failure` → `select_natural_route` with exact eligible inputs | Failed baseline not retried; eligible entry selected; no numerical repair | `test_failed_family_invokes_eligible_descent_without_repair` |
| F1 final route binding | `NaturalRouteInputs` and actual `select_natural_route` on each retained source | U9 selects eligible baseline; designation, resource prohibition and wrong-member disclosure cannot bypass the boundary | `test_final_boundary_rechecks_classification_eligibility_and_exact_disclosure`, `test_missing_route_proof_is_diagnostic_not_new_eligibility`; full U9 construction routes |
| F6 retained source binding | `assess_construction` re-evaluates actual baseline/transfer/study inputs and every composition | Missing or changed source cannot issue; crossed natural bounds survive active uplift and passing safeguard | `test_changed_source_cannot_hide_behind_exact_final_candidate_acceptance`, `test_active_uplift_and_passing_safeguard_cannot_repair_crossed_natural_bounds`, `test_missing_typed_member_source_cannot_issue` |
| F6 result binding | Finalizer re-runs external selection and physical calculations, separately for retained and selected candidates | Replaced PASS cannot certify changed candidate; incomplete retained member cannot be silently dropped | `test_replaced_selection_summary_cannot_certify_wrong_uncapped_candidate`; complete-chain member checks |
| F6/F10 bypass refusal | Missing baseline test manifest; wrong route; stale class assessment; precursor replacing final day | Missing remains pending; incompatible identities refused | `test_missing_baseline_manifest_and_exact_method_cannot_bypass_gate`, `test_stale_class_assessment_and_prefix_overwrite_refused` |
| U9 integrated F1/F6/F7/F10 | `examples/requirement_chain.py::run_chain`, complete two-year references and four complete design classes | U25/50/75/95≈16.000000000000007/13.252172596032329/12.112273310225769/12.112273310225769; D≈.3703703703703707 | `test_requirement_chain.py` full-chain test |
| U9 duration | Construct actual annual duration minima with six wet precursors, fittedT100 and selected class precursors | A4.976270579072646,B7.464405868608971; all365 windows/class/member pass | Same full-chain test; missing-context test refuses issue |
| U9/C4 issue and assessment | `issue_obligation` then actual `assess_issued_delivery` for all365 dry-class days | Floor≈12.112273310225769;deliverability6→obligation6/deficit≈6.112273310225769;delivery5→raw shortfall1 | Same full-chain test |
| M1 independent floor | Actual `assess_low_flow` and `assess_floor` | mean10 equality passes; independent floor6/actual4/butfor8 gives margin−2 | Chain M1 test |
| U9 upper-bound and C3 | Original quality recheck after final uplift; receptor salt fail plus missing temperature | Complete family declined for intrinsic failure; failed component stays visible with incomplete coverage | Chain final upper-bound and receptor failure tests |

## Alternative routes and direct-floor source checks

`tests/test_alternative_requirements.py` uses complete 365-day four-class
families and exact rational comparisons (zero numerical tolerance).
TOP and transfer each run all 1460 retained-member and 1460 selected physical
checks. These examples use accepted direct imported natural references, not
reconstruction alternatives; `NOT_REQUIRED` does not waive diversity on a route
that requires reconstruction. All permissions and physical relations are explicit
hypothetical support, not basin validation.

| Source/requirement | Real public operations | Actual = expected | Executed test |
| --- | --- | --- | --- |
| U11 top tier | `StudySource`, actual daily `assess_natural_study`, bound TOP route and `finalize_regime` | ordinary12; June1 pulse20 remains above natural50=10; final floor12 | `test_u11_complete_supported_top_preserves_pulse_above_baseline_median` |
| U11 missing study | Same typed source, missing original relation | Declined whole regime/floor; TOP failure retained | `test_u11_missing_actual_study_relation_declines_complete_regime` |
| U6 local transfer | Actual qualified `transfer_ecological_regime`, active mixing, final checks/floor | pre-quality3/5; local quality6; final requirement/floor6; no implicit duration gate | `test_u6_qualified_transfer_rechecks_local_quality_before_floor_without_baseline_gate` |
| U6 incomplete/tampered | Missing selected physical day; replaced transfer candidate | UNKNOWN or source-bindingFAIL; no new regime/floor | `test_u6_missing_one_final_quality_day_is_not_complete_acceptance`, `test_u6_tampered_transfer_output_does_not_override_recomputed_source` |
| U7 consistent components but crossed floor | Actual top studies dry13/other12 with successful source and physical checks | Diagnostic floor13; whole family declined; no class/floor repair | `test_u7_top_floor_crossing_declines_without_lowering_floor_or_lifting_other_classes` |
| U7 presumptive | Actual `presumptive_floor`, active quality, typed source and `finalize_floors` | base1.2/2→365 final floors6; no regime/obligation | `test_u7_presumptive_actual_sizing_keeps_active_quality_in_final_floors_only` |
| U7 entry | Actual `evaluate_graduated_entry`, configured curve/screen/statistic5; final source/composition | scalar4→365 quality-adjusted floors6; no invented classes/obligation | `test_u7_observed_entry_sizing_keeps_active_quality_in_final_floors_only` |
| F1 eligibility | Actual `NaturalRouteInputs` missing on otherwise computed top/transfer | UNKNOWN; no new regime/floor | `test_complete_source_cannot_finalize_without_bound_natural_route` |
| Direct-floor proof | Actual entry/presumptive/potential source inputs, compatible classification, repeated member/selected checks | Missing source remains pending; changed source or incompatible classification cannot issue; earlier results unchanged | Source-binding and missing-member cases in both integration files |
| Missing direct-floor inputs | Freshly recomputed entry with no curve; presumptive with no profile | UNKNOWN, not a fabricated failure or pass | `tests/test_alternative_requirements.py` missing-source-input cases |

`floor_construction.assess_floor_construction` repeats actual source operators.
Entry/presumptive still need natural eligibility; potential repeats its own
classification and route hierarchy. No baseline uncertainty-member count or
statistical gate is added. `FloorMemberAssessment` preserves every original
member's physical coverage separately from the selected floor.

The complete potential example executes `size_potential_floor` on every day:
joint depth/velocity gives base3, then active quality gives floor9. The earlier
unsized habitat need remains visible. Its current tests also reject missing
source, a relabelled natural origin and changed source sizing while keeping the
previous floor records unchanged.

Independent-duty isolation and immutable quantities are exercised by
`test_availability_deliverability_and_independent_duties_do_not_rewrite_history`:
availability8, requirement10, deliverability6 and actual5 remain separate.
Independent sanitary9 and prescribed foreign11 retain shortfalls4 and6.
A later version12/7 does not rewrite the earlier10/6 issue.

Shared-water final quality is tested by
`test_same_water_uplift_rechecks_quality_at_actual_shared_flow_not_old_lower_bound`:
original total9 passes an exact concentration target; a same-water receptor uplift
to10 fails its lower concentration bound. The old minimum cannot conceal the final
shared flow. Lateral mapping instead retains the actual continuing-river flow.

Numerical tolerance in the U9 tests is absolute `5e-12 m3/s`, relative zero.
It covers floating log/normal-inverse differences from the source fixture, not a
policy-bound tolerance. Selection, composition and floor comparisons use exact
fractions. Full accounting calendars include leap days where applicable.

Run the owned suites with:

```console
uv run pytest tests/test_requirement_family.py tests/test_requirement_composition.py tests/test_requirement_finalization.py tests/test_requirement_chain.py
```

The evidence log records actual execution and test counts. Source inspection and
this table alone are not acceptance. Application evidence, national adoption,
independent scientific validation and legal responsibility remain outside these
synthetic results.
