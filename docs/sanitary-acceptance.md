# Sanitary acceptance crosswalk

This record covers F8, S1–S5 and the relevant common isolation, evidence and
completeness behavior of C1–C6. Read the [workflow](sanitary-workflow.md) for use.
Synthetic witnesses establish software behavior, not authenticated law, basin
science or official admissibility. This is a sanitary boundary crosswalk, **not**
a claim to the complete shared hydraulic suite owned by Taqsim Effort #28.

## Exact source identities

The approved sole handover is `fishy_taqsim_handover_candidate_2026-09-19`.
The following SHA-256 digests identify held source bytes; the private documents
are not distributed here.

| Held source | SHA-256 |
|---|---|
| `IMPLEMENTATION_BRIEF.md` | `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8` |
| `ACCEPTANCE.md` | `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba` |
| `SHA256SUMS.txt` | `7dcf598b23a282a88a12af6ca2aee89795df27a119842ed17603403398dc97f0` |
| `SOURCE_INDEX.md` | `6fcd88742af839b7bd0f51e354cf77b3c8e7d4b6ba09573660b6566a4157187c` |
| `SOURCE_LIMITATIONS.md` | `c81e23f0f5763e92acd735efadd4aa0cdef1dceef0aae9aa4aca9c6836b90a6d` |
| `report_snapshot/part1_sanitary_baseline.qmd` | `46844f5a85ca59b63c974672f7b7a5e6e39e0b1289fdb4acd1184ca1c2922d1b` |
| `report_snapshot/part1_sanitary_scenarios.qmd` | `5d14d781b8a2f0c510e25ef8b0c43551d13f25df4af6ee64ce1ed03407e67c17` |
| `report_snapshot/appendices.qmd` | `e520499b91cc72d25dbec430a266d672331c1e732c284129b4d125db1ea9eb76` |
| `report_snapshot/part4_hydraulic_assessment.qmd` | `8dcd61476b7b9170de71ab912e2ad05d97822c71cda7262f73d8cb6aa64aa6a8` |
| `report_snapshot/quality_support/hydraulic_assessment_fixtures.json` | `2169b7362cebcb047dc3ae4e578a6249a5a53ff709109581257350568606d6b8` |
| `references/uzbekistan/supporting_discharge_and_entry/su_sanpin_3907_85_reservoirs_ru.txt` | `97792c2539bcf040799883ec84773365d6b3e54c61a4fd412234c474caa94837` |

The implementation vision is
[`planning/visions/2026-09-21-sanitary-duties-and-hypothetical-seasonal-profile.md`](https://github.com/hydrosolutions/taqsim/blob/3a86b1c53bafd9d8c474620e6083ad4ea8b05201/planning/visions/2026-09-21-sanitary-duties-and-hypothetical-seasonal-profile.md)
at Taqsim `3a86b1c53bafd9d8c474620e6083ad4ea8b05201`,
Git blob `d96bdb26039cf7a16bb4acccc0aa8f9cd29e6d2f`.
The Fishy starting revision is `389dcdac7a34585ee179c8b2acdb7b65584095f5`.
The optional physical exchange uses the locked Taqsim
`396ad093c2b6f240e702a3b05aee1fb96a69b3f7` and Incidence
`665da4e0d81ab28921b8d5d2edbb9be27f4ec612` revisions. The vision revision is
not a change to that dependency lock. Standalone sanitary inputs require neither
optional dependency nor a running simulator.

The report anchors are `sec-sanitary-baseline`, `sec-sanitary-scenarios` (D.1),
`sec-recipe-step3`, and `sec-hydraulic-assessment` (D.9).
The 3907-85 reproduction is secondary; current force and Uzbek object-specific
applicability remain unresolved. The government-hosted 0315-14 copy is marked
unofficial translation. Its register entry and bibliographic reference do not
authenticate the inherited estimator. Article 122 supplies the governing framework,
not a numerical estimator. Numerical findings, purpose-specific scientific
adequacy and source authority remain separate.

## Numerical comparison contract

All numerical witnesses below use exact rational assertions: `Fraction` equality,
including unit-bearing values backed by `Fraction`. **Absolute tolerance is 0;
relative tolerance is 0.** Decimal displays such as `0.95`, `0.6` and `0.24` mean
`19/20`, `3/5` and `6/25`, respectively. Construct exact inputs from integers,
strings or rational pairs, not a rounded display of the selected probability.
Enum, identity, dates and exception assertions are exact and have no numerical
tolerance. No statistical confidence tolerance is implied.

## Requirement → operation → expected result → test

Tests listed here were executed on the assembled source revision recorded below.
The expected results are checked by exact assertions; the final section records
the commands, counts and principal actual-versus-expected values.

Test paths: **D** = `tests/test_sanitary_duties.py`, **P** =
`tests/test_sanitary_profile.py`, **H** = `tests/test_sanitary_hydraulics.py`.
All operation names below are public; module names are `fishy.sanitary_duties`,
`fishy.sanitary_profile`, and `fishy.sanitary_hydraulics` unless noted.

| Requirement/source | Public operation and input | Expected observable result | Test witness |
|---|---|---|---|
| F8/S1; baseline; step 3; §4.2 | `assess_sanitary_duty`: daily prescribed `[2,3]`, delivery `[1.5,3.5]` m³/s | Shortfalls `[1/2,0]`; `known_shortfall_volume = 43200` m³; no estimator or surplus cancellation | D `test_s1_shortfall_exact_and_s4_complete_import_success_failure_and_unknown` |
| S1/C1–C6 state distinctions | Same operation: missing, outside-horizon or unsupported second delivery; first interval fails | First failure survives; coverage incomplete; unknown shortfall is `None`, not zero | D `test_s1_presence_is_preserved_and_does_not_cancel_known_failure` |
| S1 matching/domain | Same operation: present zero, wrong interval or location | Zero delivery gives shortfall `2`; mismatch raises rather than resampling | D `test_s1_zero_and_mismatched_interval_or_location` |
| F8/S1 inventory and authority | `SanitaryDuty`, `InstrumentEvidence`, `DutyApplicability` | Four inventory outcomes retained; secondary/outdated evidence cannot become binding applicability | D `test_inventory_outcomes_authenticity_currency_and_applicability_are_distinct`; `test_unauthenticated_or_outdated_instrument_cannot_become_binding` |
| S1/S4 missing schedule, non-flow clauses | `assess_sanitary_duty` with empty schedule and declared hydraulic scope | Missing flow remains unknown; supported hydraulic failure remains failure/incomplete; supported non-flow-only duty can pass | D `test_missing_schedule_preserves_supported_hydraulic_failure_nonflow_can_pass` |
| S1 missing magnitude with observed deliveries | Foundation `assess_duty` with missing schedule and supplied deliveries | `uncompared_deliveries` retains observations; discharge unknown; supported hydraulic findings retained; no invented comparison | `tests/test_duties.py::test_missing_magnitude_can_retain_delivery_without_inventing_comparison` |
| C1–C6 empty requirements | `assess_sanitary_duty` with no required components | Unknown, not manufactured satisfaction | D `test_empty_components_cannot_manufacture_satisfaction` |
| S2/D.1 empirical profile | `annual_sanitary_profile`: complete 2001–2019 witness, declared Jan–Feb/Jul–Aug windows | 2019 annual mean `2`, rank `19`, probability `19/20`; winter `3/5` on Jan 1, summer `9/10` on Jul 1; `value_on` outside windows is `None` | P `test_complete_annual_selection_exact_witness_and_fixed_offset` |
| S2 support before rounding | Same operation, remove 2019; tied lower annual means | 18-year maximum `18/19 < 19/20` unsupported; ties may reduce support despite record length | P `test_support_before_rounding_and_ties_reduce_support` |
| S2 ties | Same operation, equal distances or annual-mean ties | Larger probability wins equal distance; earliest year wins equal probability; tied candidates retained | P `test_equal_distance_prefers_larger_probability_and_tied_years_earliest` |
| S2 completeness and calendar | Same operation, missing/duplicate days, leap days, invalid or overlapping windows, DST calendar | Invalid inputs rejected; complete fixed-offset leap years retained; inclusive boundaries respected | P `test_invalid_daily_evidence_stops_calculation`; `test_leap_day_completeness_window_validity_and_dst_rejection` |
| S3 nomination/import | `nominated_sanitary_profile`: summer `[4,2,5]`, winter `[6,3,7]`; `imported_sanitary_profile` with its own method | Minima `2`, `3`; no empirical-selection claim; zero stays zero; missing windows/interpretation pending; no complete-year/19-year gate | P `test_nomination_import_zero_and_pending_do_not_claim_annual_selection` |
| S2/S3/C1–C6 attribution | `ProfileAttribution`, `Flow`, profile operations with mismatched member/evidence, invalid quantities or dates | Reject mismatched identity, nonfinite/negative flows and dates outside reference period; unsupported numerical evidence cannot supply values | P `test_evidence_identity_and_invalid_quantities_are_rejected`; `test_import_minimum_dates_cannot_escape_reference_period`; `test_invalid_numerical_evidence_cannot_support_import_or_calculation` |
| S2/S3 failed members | Independently call `annual_sanitary_profile` for two identified members | Supported member retained; failed member remains unsupported/incomplete, not omitted or a confidence interval | P `test_independent_failed_member_remains_visible_without_comparison` |
| S4 §4.2–§4.4 | `assess_sanitary_duty` with discharge plus velocity, continuity, uniformity, stage-change and velocity-change findings | Full attributable component set; flow failure + unknown hydraulics = failure/incomplete; flow pass + unknown hydraulics is not whole-duty pass; supported success/failure retained | D `test_s1_shortfall_exact_and_s4_complete_import_success_failure_and_unknown` |
| S4 §4.3 cascade requirements | `assess_imported_hydraulics`: separately scoped velocity/current findings | Study/source identity retained; no replacement of local velocity/current by discharge | H `test_s4_attributable_imported_success_failure`; D `test_scope_mismatch_and_daily_only_cannot_certify_within_day` |
| S4 §4.4; D.9 | `assess_sanitary_rate`: stage `1 → 28/25` m in `1/2` hour; hypothetical inclusive rise `1/5`, fall `3/10` | Forward `6/25` fails; reverse `-6/25` passes; inclusive equality passes | H `test_s4_half_hour_stage_witness` |
| S4 D.9 strict bounds | Same operation with strict rise/fall equality; empty strict zero range | Equality fails; empty admissible range is disjoint even with uncertainty | H `test_strict_equality_fails`; `test_empty_strict_zero_range_is_disjoint_even_with_uncertainty` |
| S4/C1–C6 empty directional criterion | `assess_sanitary_rate` with both directional bounds intentionally absent | Unknown, not manufactured satisfaction | H `test_no_directional_criteria_cannot_manufacture_satisfaction` |
| S4 D.9 uncertainty | `StateBounds`, `HydraulicTransition`, supplied criterion | Conservative rate interval; containment pass, disjoint fail, overlap unknown; tighter supported joint evidence retained | H `test_conservative_uncertainty`; `test_irregular_elapsed_and_tighter_supported_joint_evidence` |
| S4/C3 safe native transfer | `rate_check` attempts to transfer a matching incomplete native rate into foundation `assess_duty` | Raises rather than silently reporting complete duty coverage; `assess_sanitary_rate` and `directional_checks` retain the lossless failure/incomplete result | H `test_incomplete_scalar_rate_transfer_is_rejected_instead_of_claiming_complete_duty` |
| S4 D.9 directional completeness | `assess_sanitary_rate` with rise `6/25 > 1/5` and fall bound missing, or fall `-2/5 < -3/10` and rise missing | Failure survives with incomplete directional coverage; change/rate/elapsed and attribution remain; pass plus missing stays unknown | H `test_supported_direction_failure_survives_missing_other_bound`; `test_passed_direction_cannot_hide_missing_other_bound` |
| S4 D.9 gaps and seasons | Same operation: missing predecessor/state, expected gap, unresolved boundary, missing required bound | Unknown; no gap bridging, wrapping, invented state or missing-bound default | H `test_expected_gaps_never_bridged`; `test_missing_state_season_boundary_and_required_bound` |
| S4 §4.4 temporal/domain support | Native rate or import with daily-only support or mismatched scope | Daily means do not certify within-day maxima; endpoint changes remain discrete; no variable/domain substitution | H `test_daily_means_cannot_certify_within_day_or_endpoints_peak`; D `test_scope_mismatch_and_daily_only_cannot_certify_within_day` |
| S4/C1–C6 evidence | `ImportedHydraulicFinding`, `HydraulicTransition`, `assess_sanitary_rate` | Reject unattributed/invalid states; unsupported or warm-up states cannot pass; numerical result does not promote scientific or official acceptance | H `test_unsupported_states_and_imports_do_not_gain_validity`; `test_invalid_domains_and_unattributed_findings`; `test_numeric_finding_does_not_promote_or_depend_on_scientific_acceptance`; `test_warmup_states_cannot_certify` |
| S4 D.9 relation/domain support | Optional `HydraulicRelationEvidence` on an import or transition; mismatched target scope | Geometry/version, boundaries, interpolation, uncertainty and intended-use metadata retained; unsupported domain stays unknown; rate cannot transfer across location, variable or period | H `test_relation_metadata_retained_and_no_extrapolation`; `test_rate_cannot_transfer_to_other_location_variable_or_period`; `test_imported_permission_and_warmup_remain_distinct` |
| S5 isolation and combined use | `CombinedAssessment`, `EcologicalRequirementAssessment`, `RequirementConflict`; foundation `assess_feasibility` | Separate requirements, control points, versions and conflicts; shortage does not rewrite duty; no sum/max/precedence/activation | D `test_s5_independent_versions_locations_conflicts_no_sum_or_maximum_and_shortage_no_rewrite` |
| S3/S5 method isolation | Independently import changed hypothetical profiles and leave nomination pending beside a prior duty and Swiss source calculation | Original import identity and duty unchanged; Swiss 160 → 130 l/s unchanged; pending derivation cannot disable supplied-duty assessment | D `test_hypothetical_profile_changes_do_not_rewrite_other_methods_or_prior_duties` |
| F8/S5 standalone workflow | `examples/sanitary_assessment.py:main` | Sanitary-only assessment and separate ecological findings/conflict without simulator | D `test_executable_sanitary_only_and_combined_example` |

§4.2 supplies the minimum-flow condition; the annual-selection operator remains an
explicit hypothetical interpretation. §4.3 adds pre-impoundment minimum velocity
and downstream current in cascades. §4.4 concerns uniformity and abrupt within-day
level/velocity changes without a numerical threshold. The §3.7.3 **0.5 m/hour**
beach-siting provision is not a ramp default. The synthetic `0.20`/`0.30` rate
limits above are not adopted sanitary law. Imported findings remain specialist
findings, not falsely labelled native calculations.

## Executed validation

Production code, tests and executable example were validated at Fishy
`7df5a2d9cff5deb77820351b24db276687c8e9ed`. Documentation records that revision;
subsequent documentation-only edits do not change the tested source identity.
The execution log is `.implementation-evidence/sanitary-validation.txt`.

| Executed command | Result |
|---|---|
| `uv run --all-extras pytest -q` | 1,355 passed in 23.39 s |
| `uv run --all-extras pytest tests/test_duties.py tests/test_sanitary_duties.py tests/test_sanitary_profile.py tests/test_sanitary_hydraulics.py -q` | 93 passed in 0.74 s |
| `uv run --all-extras ruff format --check` | 100 files already formatted |
| `uv run --all-extras ruff check` | All checks passed |
| `uv run --all-extras ty check` | All checks passed |
| `uv run --all-extras python examples/sanitary_assessment.py` | Output below; successful exit |

```text
Sanitary shortfall m3: 43200
Sanitary finding: fail complete
Independent ecological finding: unknown
Retained conflicts: 1
Hypothetical supplied evidence; no legal compliance or ecological-entry permission.
```

The executed exact assertions in the mapped tests establish the following
actual-versus-expected results. Numerical tolerances remain zero as declared above.

| Witness | Expected exact value | Actual assembled-tree result |
|---|---|---|
| S1 shortfalls/volume | `[1/2, 0]` m³/s; `43200` m³ | `[1/2, 0]` m³/s; `43200` m³ |
| S2 selected year/probability/minima | `2019`; `19/20`; winter `3/5`, summer `9/10` m³/s | `2019`; `19/20`; winter `3/5`, summer `9/10` m³/s |
| S2 removed-year support | Unsupported, maximum `18/19` | Unsupported, maximum `18/19` |
| S3 nominated minima | Summer `2`, winter `3` m³/s | Summer `2`, winter `3` m³/s |
| S4 half-hour rate | `6/25` fail; `-6/25` pass | `6/25` fail; `-6/25` pass |
| S5 requirements | Separate sanitary/ecological findings and one example conflict | Sanitary fail/complete; ecological unknown; one retained conflict |

The full repository test count is a regression result, not a claim that this
Effort implements the complete shared hydraulic suite. The sanitary hydraulic
witnesses above cover only their declared components and supplied domains.
