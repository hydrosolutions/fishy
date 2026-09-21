# Study and service acceptance crosswalk

Effort: https://github.com/hydrosolutions/taqsim/issues/28

Owned scope: F5, U11 and the study/conveyance/designation portion of U8. Hydraulic and receptor fixture suites are separate sibling deliveries. Final component assembly is not implemented here.

## Source identity

Approved bundle: `fishy_taqsim_handover_candidate_2026-09-19`. Private originals are not included.

| Source | SHA-256 |
|---|---|
| `IMPLEMENTATION_BRIEF.md` | `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8` |
| `ACCEPTANCE.md` | `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba` |
| `report_snapshot/appendices.qmd` | `e520499b91cc72d25dbec430a266d672331c1e732c284129b4d125db1ea9eb76` |
| `report_snapshot/part4_recommended_method.qmd` | `6f88bb402cacb099766a84fa418f1cbe1f86122355bb9d7a403ecad708e2e177` |
| `report_snapshot/part4_assembly_contract.qmd` | `0a97ef52784fbfd2dc21ba689a2edfbda4f182ed52a33757afc7b2753c329d85` |

All numerical witnesses are synthetic. Tests below assert actual against expected values, including pending/unsupported/infeasible paths. No source fixture was altered to fit an implementation.

## Requirement → public input/operation → actual/expected → executed test

Test prefixes: S=`tests/test_study_requirements.py`, P=`tests/test_potential_requirements.py`, C=`tests/test_service_conveyance.py`.

| Clause | Public operation/input | Actual = expected | Test |
|---|---|---|---|
| U11; Appendix A step 7 top tier | `assess_study`, selected 2.5 on non-monotone points (0,0),(5,100),(10,20) | response 50; supported flow 2.5; selected 10 fails habitat ≥40; no least-flow inversion | S `test_selected_nonmonotone_habitat_and_interpolation_are_computed_not_inverted` |
| U11; recommended method high-flow coverage | `assess_natural_study`, selected pulse 8, baseline cap 3 | response 52; pulse 8 retained; PASS; no release permission | S `test_natural_pulse_exceeds_baseline_cap_with_supported_selected_study`, `test_public_study_example` |
| U11; steps 6–7 descent | missing criterion/relation/ramping; reason-specific restriction | UNKNOWN/no accepted flow; numeric diagnostic retained | S `test_missing_criterion_relation_ramping_and_restricted_evidence` |
| U11; sediment trigger ownership | missing pulse/owner/deadline | mandatory study and assignment unknown; supplied fallback retained | S `test_natural_missing_relation_ramping_and_owner_deadline_descent` |
| U11; operating-domain and ramp failure | failed ramp or trial 12 beyond relation | FAIL/descent or unavailable; never accepted pulse | S `test_natural_failed_ramping_and_out_of_domain_descent` |
| U8; ordered potential routes | `size_potential_floor`, supported habitat and joint targets | habitat first; floor 5; no derived requirement/obligation | P `test_habitat_first_route_returns_floor_only_not_natural_minimum` |
| U8; second route, preserve prior conditions | missing habitat, joint depth=1/velocity=1 at selected 5 | hydraulic floor 5; earlier UNKNOWN remains | P `test_joint_hydraulics_success_keeps_earlier_missing_ecology` |
| U8; joint same-candidate failure | missing depth, velocity 2 >1 | FAIL plus INCOMPLETE | S `test_joint_velocity_failure_survives_missing_depth_same_candidate` |
| U8; third route | `size_potential_floor`, no ecology, accepted service relation | service flow ≈10; both earlier unknown records and full trace remain | P `test_conveyance_third_route_success_retains_full_trial_trace` |
| U8; no winter rescue | all routes missing | floor None; winter suspended; high uncertainty/revisit retained | P `test_missing_all_routes_winter_suspended_and_no_zero_default` |
| U8; authenticated duty precedence | rule80, permit10, observed1 m³ | selected rule; absent rule selects permit; observed-only missing | C `test_operating_rule_precedes_permit_and_observations` |
| U8; iterative storage/loss balance | 10-second interval; duty80, storage change=q, aquifer seepage=q | q→10; trials8,9.6; first residual−16; 12th flow9.99999995904; residual−16/48828125 m³ | C `test_iterative_flow_storage_seepage_full_trace` |
| U8; through service plus named offtake | duty80 + downstream20, explicit zero losses/storage change | exact q10, residual0 | C `test_named_downstream_duty_and_explicit_zero_losses` |
| U8; timed inflows once/reversal | other inflow40 then200 m³ | q≈5; second gives required−104 and unsupported reversal | C `test_unsupported_reversal_and_inflow_counted_once` |
| U8; nonconvergence | iteration limit2; genuine oscillation q_next=12−q | None, full two trials; oscillation8,4 repeated30 with residual±40 | C `test_nonconvergence_full_trace_without_accepted_last_iterate`, `test_oscillating_accepted_relation_does_not_converge` |
| U8; capacity and ramp failure | carrier capacity9 / rise increment1 / offtake capacity7 | INFEASIBLE, no accepted last iterate | C `test_infeasible_never_accepts_last_iterate`; P `test_conveyance_infeasible_is_not_pending_pass_and_wrong_scenario_rejected` |
| U8; missing losses/capacity/ramp | relation/capacity/ramp None | MISSING, flow None; no zero | C `test_missing_input_is_not_zero` |
| U8; unsupported physical use/domain | rejected relation, wrong intended use, initial trial21, excluded warmup | UNSUPPORTED, flow None, attributable reasons | C `test_unsupported_relation_and_domain`, `test_required_evidence_scope_not_silently_relabelled`, `test_excluded_warmup_invalidates_relation_support` |
| U8; supported zero/designed dry | complete explicit hypothetical service determination | floor0, ZERO route, interpretation retained | P `test_supported_zero_and_designed_dry_are_explicit_hypothetical_determinations` |
| U8; zero safeguards | omit each of six required designed-dry fields; hydraulic zero without approval | floor None; numerical service zero not automatically approved | P `test_missing_designed_dry_condition_never_authorizes_zero`, `test_hydraulic_zero_still_needs_service_determination`; C `test_zero_not_approved_by_arithmetic` |
| U8; steps2/10 designation history | natural issued v1, designated potential proposal, supported/rejected revision | v1 persists unless competent supported v2; no invented prior version | P `test_designation_preserves_issued_natural_version_until_supported_revision` |
| U8; valid designation | new natural calculation after accepted designation | ValueError | S `test_valid_designation_stops_new_natural_calculation` |
| U8; designation distinctions | pending/expired/rejected and irrigation use | undetermined/natural/natural; states preserved | P `test_distinct_designation_states_and_irrigation_origin_preserved` |
| Steps7–10; additional process/quality/duty handoff | supported habitat plus unsized thermal/groundwater and active quality | floor5; conditions retained without claiming their satisfaction | P `test_pending_thermal_groundwater_and_active_quality_survive_success` |
| Common C2/C5 exact domain | mismatched candidate/period/scenario, duplicate relation/carrier, negative depth | rejected, no silent relabelling/resampling | S `test_scope_duplicates_and_negative_depth_rejected`; C `test_mismatched_interval_scenario_and_conflicting_duty_rejected`; P conveyance mismatch test above |

| U11; imported holistic objective | attributable `holistic_assessment` with criterion/value/domain and supported evidence | selected seasonal5 accepted; rejected evidence remains unaccepted | S `test_supported_imported_holistic_objective_can_supply_selected_requirement` |
| U11; natural eligibility and reference | observed/managed/historical/absent reference kind; unresourced/not selected | no supported natural requirement; numeric intermediate retained | S `test_wrong_reference_kind_cannot_supply_natural_requirement`, `test_ineligible_study_retains_arithmetic_not_supported_requirement` |

| U8; official replacement guard | scientifically supported but official-admissibility pending replacement | existing issued version stays in force | P `test_pending_official_replacement_cannot_displace_issued_requirement` |

Review regression evidence: the six eligibility/reference cases failed on the real public path before guards were added, then passed. The pending-official replacement test failed before adding its separate admissibility guard. The excluded-warmup service test likewise failed before the shared warmup exclusion was applied.

Conveyance tolerance is predeclared 10⁻⁶ m³ for a contraction factor0.2 and limit30; exact rational residuals are retained. The displayed fixed-point comparison permits 10⁻⁷ m³/s, narrower than the configured interval residual divided by10 seconds. Other numeric comparisons are exact `Fraction` equality. Neither tolerance represents scientific uncertainty.

## Compatible revisions and execution

Initial inspected Fishy: `e02d43c9ed35eefd377b61f7ec201a6005843b06`.
Integrated target/shared hydraulics: `6a92a9b8be2da154aafd60297565eb1533fea59f`.
Locked optional Taqsim: `396ad093c2b6f240e702a3b05aee1fb96a69b3f7`.
Locked Incidence: `665da4e0d81ab28921b8d5d2edbb9be27f4ec612`.
Python 3.13; use the unchanged `uv.lock`. The PR head identifies the exact implementation revision.

```console
uv sync --extra taqsim
uv run --extra taqsim pytest -q
uv run --extra taqsim ruff check
uv run --extra taqsim ty check
uv run python examples/study_requirements.py
```

Executed on the integrated target: **1442 tests passed**, including **53 focused study/potential/conveyance cases**. Global ruff format/check and ty passed. The executable example returned pulse8, habitat52 and `pass not_granted_by_calculation`. The example uses no live simulator. No private report originals are published.
