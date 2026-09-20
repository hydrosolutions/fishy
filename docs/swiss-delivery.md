# Swiss intake schedules and delivery

`fishy.swiss_delivery` connects supported downstream needs to a candidate intake
schedule. It also assesses an independently supplied Swiss duty. Neither operation
requires Taqsim, Q347 sizing history, or HYDMOD.

## Prepare a candidate intake schedule

1. Supply exact `FlowSample` intervals for the applicable Arts. 31–32 minima **at
   the intake**. Do not pass a downstream minimum as an intake minimum merely
   because both are flow quantities.
2. Supply the complete downstream protection-point and interval inventory as
   `downstream_needs`. Include affected points below powerhouse returns where
   storage operations affect them. A missing relationship remains unresolved.
3. For each need, supply an `IntakeRelationship`. This restricted relationship is
   `downstream = transmission × intake + gains − losses − other abstractions`.
   `transmission` is an exact `Fraction` in (0, 1]. `intake_domain` states the
   supported input range. Each `RoutingExchange` names a disjoint water account,
   its role, location and exact interval. Empty exchanges explicitly mean no
   gains or sinks, not unknown accounts. Source studies must support this equation;
   a topology map does not supply it. Travel delays, nonlinear losses and general
   storage routing are not implemented by this equation.
4. Supply scientific `EvidenceFindings` for each relationship and the study's
   `WaterBalance`. The balance uses initial storage, incoming volume, outgoing
   volume and final storage with an explicit absolute volume tolerance. Failure
   cannot pass. Missing balance remains unknown. Balance closure alone does not
   establish that the relationship represents the site.
5. Pass `upstream_checks` from the safeguards, exception and interest-balancing
   assessments. Empty, missing or failed checks cannot produce a supported
   prescription. Keep required `ProtectiveMeasure` records separate from flow
   needs. Rejected or unresolved measure evidence gates the relevant interval.
6. Pass `downstream_assessments`, the actual `BalancingAssessment` records for
   every required point and interval. The operation recomputes their original
   safeguards or scoped exception and Art. 33 decision. Each need must equal the
   recomputed supported final total. Cached summaries and free check IDs cannot
   replace these inputs.
7. Call `derive_intake_schedule`. It inverses each supported relation and takes
   the greatest required release for that shared intake interval, including its
   supplied intake minimum. It checks the resulting shared release against every
   relation's domain. It does not sum non-consumptive downstream requirements.
   It then projects that shared release to every downstream point and rechecks
   the actual site safeguard relationships, or the independently recomputed
   exact-scoped exception minimum. A larger shared release can exceed a site's
   supported upper domain even when that site's earlier lower total passed.

`numerical_schedule` and `projected_downstream` retain supported physical mapping
results separately from final scientific acceptance. Missing or failed actual
assessments prevent supported `.schedule` output, without erasing the independent
numerical mapping. For two needs 180/300 l/s, a shared release of 300 remains in
`numerical_schedule`; if the first site's upper domain is 200, final assessment
fails. Missing an assessment for a farther normal-protection point cannot extend
an exception to that point.

The result retains downstream needs, minima, relationships, measures, schedule and
checks. Unsupported intervals carry `Presence.UNSUPPORTED`, not zero. There is no
Uzbek deliverability cap. A supported schedule is a mathematical candidate, not
permission. The caller must separately supply the authority's decision or an
explicit `DutyApplicability.HYPOTHETICAL` scenario when constructing a `SuppliedDuty`.

## Bind evidence to the actual subject

For relationship findings, use
`relationship_scope(intake, downstream, transmission, intake_domain, exchanges,
balance, relation_source)`. It binds every reviewed operand, the full downstream
sample, both physical locations, the domain and the supporting account/source.
`IntakeRelationship.scope` exposes the same scope. Changing any relationship field
requires new attributed findings; an accepted coefficient cannot transfer to
another relation.

Use `proof_scope(sample, method, intended_use, balance=...,
unreasonable_measurement=...)` for proof findings. This binds the complete proof,
including its method, balance quantities and tolerance, and the measurement-burden
justification. `FlowProof.scope` exposes the same identity. Changes need new findings.
`delivery_scope` is the underlying sample identity helper, not the full proof scope.

- Inflow proof: `intended_use="inflow_proof"`, without the intake argument.
- Delivery proof: `intended_use="delivery_proof"`, without the intake argument.

The scope product binds the full immutable sample, including physical body,
reach, control-point and mapping revisions, interval, source/data/configuration,
scenario/member, value, support and uncertainty. Findings retain the sample's
full `Provenance`. Reusing findings after changing the subject is rejected.
The binding is an internal identity digest, not authentication or a public file format.

For measures and specialist results, use
`specialist_scope(location, interval, provenance, intended_use, subject)`:

- `"protective_measure"`, with `(identifier, description)`.
- `"specialist_condition"`, with `(indicator, result)`.

Scientific adequacy and official admissibility remain distinct. A supplied pending
or adverse official finding is retained; numerical/scientific success does not
promote it to authorisation.

## Assess an already prescribed duty

Call `assess_swiss_delivery(duty, deliveries, inflow_proofs=...,
delivery_proofs=..., conditions=...)`. The nominal duty is immutable.
`adjustments` retains each nominal obligation, supplied inflow proof, justified
interval obligation and proof checks. `delivery` is the existing `DutyAssessment`
against that justified schedule. Shortfalls do not cancel between intervals.

A `FlowProof` uses `ProofMethod.MEASUREMENT` or `ProofMethod.WATER_BALANCE`:

- Measurement uses observed data. Illustrative measurement witnesses can run
  explicitly hypothetical duties, but remain scenario predictions. A simulation
  cannot be labelled a measurement.
- Water-balance substitution additionally needs a nonempty site-specific
  `unreasonable_measurement` justification and a closing `WaterBalance`.
  Its incoming volume must equal inflow × exact interval duration for inflow
  proof. Its outgoing volume must equal delivery × duration for delivery proof.
  An unrelated closed account is rejected. No rate/volume conversion uses an
  assumed day length.
- Missing, partial, excluded, rejected or unsupported proof cannot lower the duty.
  Non-observed scenario proof cannot relieve an authenticated observed duty.
  A supported modelled balance can run a hypothetical assessment.
- This exact substitution operator conservatively leaves relief unresolved when
  supplied inflow bounds are nondegenerate. It does not invent a point-exact duty
  from an uncertain inflow. The original bounds and proof remain available.

For nominal 220 l/s, proven inflow 150 l/s and delivery 120 l/s, the justified
interval duty is 150 and shortfall is 30. The nominal remains 220. Without proof,
the shortfall is 100. Proven zero is different from no proof. New downstream
tributary gains never revise an issued intake duty.

`delivery.summary` is numerical discharge assessment, not an Art. 36 control
certificate. `control_evidence` separately checks the supplied delivery proof.
A numerical pass without proof therefore has unknown control evidence. Inspect
both, and the independent uncertainty findings, rather than treating arithmetic
as legal compliance.

`ConditionFinding` links supplied HYDMOD, seasonality or other specialist findings
to the same reach, scenario, member and exact period. These findings do not change
delivery shortfalls or create an uplift. There is no HYDMOD import dependency.

## Source and executed-test crosswalk

Sources: German [GSchG, consolidated 1 August 2025](https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de),
Arts. 4(k–l), 35–36; [FOEN residual-flow guide (2000)](https://www.bafu.admin.ch/dam/de/sd-web/DURPl8AmZvgE/angemessene_restwassermengenwiekoennensiebestimmtwerdenwegleitun.pdf),
§4.3 printed pp. 34–40 and §4.9 pp. 68–72. The later Act controls.
All tests use original synthetic inputs, not restricted source data. Values are
exact `Fraction` comparisons with zero numerical tolerance unless a supplied
balance explicitly declares another tolerance. Final implementation and optional
integration revision pins are recorded in the aggregate Swiss acceptance report.

| Source / requirement | Public operation and input | Expected = actual | Test in `tests/test_swiss_delivery.py` |
|---|---|---|---|
| Art. 4(k–l), Art. 35; Guide §§4.3, 4.9 | `derive_intake_schedule`: downstream 220, gain 50, loss 20, abstraction 10 | intake 200 l/s; additional below-return need 260 controls intake at 260 | `test_downstream_gains_losses_abstractions_and_return_points` |
| Art. 35(2) | exact dated minima and downstream seasonal needs; separate measure | 160/220 l/s, leap-day interval retained; gain cannot suppress intake minimum 130 | `test_exact_seasonal_schedule_keeps_intake_minima_and_separate_measures` |
| Supported mapping, not topology | transmission 4/5; need 220 | intake 275; maximum supported intake 250 fails, no candidate | `test_explicit_transmission_not_topology_sum_and_infeasible_domain` |
| Failed balance and omitted affected point | physical account residual 1 m³ plus absent relation | failure plus incomplete coverage | `test_missing_relationship_and_failed_balance_survive_incomplete_coverage` |
| Independent scientific coverage | required upstream checks / measures | failed, missing or empty checks cannot support candidate | `test_upstream_coverage_cannot_be_laundered_into_complete_prescription`, `test_required_measure_rejection_or_wrong_use_cannot_pass_prescription` |
| Actual post-routing safeguards / scoped exceptions | `downstream_assessments` and projected point flows | shared 300 exceeds first point upper 200: final fail, numerical 300 retained; missing farther normal study stays unknown | `test_shared_release_rechecks_actual_downstream_safeguard_domain`, `test_cached_balancing_pass_cannot_replace_actual_studies_or_need`, `test_scoped_exception_and_normal_protection_beyond_reach_remain_separate` |
| Full proof-subject acceptance | change balance tolerance 0→1 with previous accepted findings | evidence mismatch, no relief | `test_proof_balance_tolerance_cannot_change_under_existing_findings` |
| Art. 36(2) | `assess_swiss_delivery`: 220/150/120 | nominal 220; duty 150; shortfall 30 l/s = 2592 m³/day | `test_art36_exact_low_inflow_preserves_nominal_and_shortfall` |
| Art. 36(1–2) | balance and measurement-burden evidence | relief only with justified, closing, flow-linked account | `test_water_balance_relief_requires_unreasonable_measurement_and_closure`, `test_unrelated_closed_balance_cannot_prove_low_inflow_or_delivery` |
| Existing supplied duty / no retroactive revision | no sizing or inflow proof; later tributary study | 100 l/s shortfall, immutable nominal 220 | `test_existing_duty_independent_sizing_no_proof_no_relief_no_retroactive_tributary` |
| Art. 36 equality / zero | inflow 0,150,220,300 | justified 0,150,220,220 | `test_all_inflow_threshold_and_present_zero` |
| Physical import support / coverage | missing, absent, outside, unsupported flow and failed proof balance | preserved support; known failure survives missing interval | `test_physical_support_is_preserved_not_used_as_zero`, `test_delivery_known_failure_plus_unsupported_and_control_balance_failure` |
| Independent MSK condition evidence | same release, hydropeaking vs seasonality | identical discharge assessment, distinct attributed results | `test_same_release_compliance_different_specialist_conditions` |
| Exact evidence identity | wrong source version, point, intake, result, member or scenario | rejection, no transfer of accepted findings | `test_same_reach_other_control_point_or_data_version_cannot_reuse_evidence`, `test_routing_evidence_cannot_move_to_another_intake`, `test_specialist_evidence_cannot_move_within_reach_or_change_result`, `test_mixed_scenario_member_reference_configuration_rejected` |
| Scenario is not observation | model as measurement; illustrative proof with observed delivery | no false measurement; hypothetical result stays prediction | `test_simulated_measurement_cannot_enable_relief`, `test_observed_delivery_cannot_make_hypothetical_relief_observed_compliance` |
| Independent observed path | observed inflow/delivery against supplied applicable duty | 30 l/s shortfall, supported control evidence, observed comparison not legal verdict | `test_authenticated_observed_proof_remains_independently_runnable` |

Run `uv run pytest -q tests/test_swiss_delivery.py`.
