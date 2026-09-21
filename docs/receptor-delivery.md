# Receptor delivery accounting

`fishy.receptor_delivery` checks one supplied operating schedule. It does not
allocate unknown pathways, run a hydraulic model, issue a duty or certify ecology.
Its native representation is a discrete storage balance with fixed interval
losses, stocks and travel time. Specialists supply and accept that representation.

## Use

1. Build a `DeliveryContext` with the physical receptor `Location`, exact
   `Interval`, candidate, compartment/domain and `Provenance`.
2. Build a `StorageBalance`. Its `Volume` target is a specialist-selected storage
   trajectory point, not the midpoint of an ecological range. Give rainfall,
   groundwater and other boundary exchanges unique carrier identities and named
   destinations. Positive exchange amounts have an explicit direction.
3. Supply `EvidenceFindings` for `delivery_scope(context, balance)`. Call
   `storage_arrival(balance, evidence)`. Missing targets or unsupported relations
   return an unsized result, never an accepted zero.
4. Supply each `Pathway` with its actual control point, control period, delay,
   initial/final stocks, loss destinations, release domain, predecessor and
   separate ramp limits. `map_arrival(pathway, arrival)` gives only an algebraic
   candidate volume. It is **not** an accepted schedule. It returns `None` if the
   stocks imply a negative control release.
5. Supply selected `PathwayRelease` values in a `DeliveryStep`. Each pathway needs
   evidence for `delivery_scope(context, pathway)`. Several unknown pathways stay
   unresolved until the operator supplies a schedule; no contribution shares are
   inferred.
6. Supply the required process/quality target identifiers and attributable
   `ProcessTest` records. Each carries the state variable, units, compartment or
   reference, candidate, interval, value, bounds and strictness. Acceptance uses
   `delivery_scope(context, test)`. A source-water concentration must not be
   relabelled as resident-water concentration. An empty process profile remains
   incomplete.
7. Supply independent checking evidence for
   `delivery_scope(context, step.checking_subject)`. Its source must differ from
   the storage-relation source. This records independent acceptance of the exact
   selected schedule and tests; it does not replace the numerical recheck.
8. Call `assess_delivery(steps, period=assessment_period)`. Missing boundary
   intervals stay incomplete. Nonadjacent steps and contradictory identities are
   rejected. Omitting `period` limits the assessment to the supplied steps' span,
   not a larger season or operating horizon.

Run the standalone public example with `uv run python examples/receptor_delivery.py`.
It supplies every input above without Taqsim or Incidence. Its public calls are:

```python
need = storage_arrival(step.balance, step.evidence)
control_candidate = map_arrival(step.pathways[0].pathway, need.arrival)
result = assess_delivery((step,), period=step.balance.context.period)
```

The synthetic example starts at 100 m³ and targets 200 m³. Rain adds 20 m³;
evaporation removes 10 m³. Arrival need is **90 m³**. The pathway starts with
3 m³, ends with 5 m³ and loses 8 m³ to its named destination. Control release is
**100 m³**, six hours before the corresponding arrival interval. Re-evaluation
returns arrival 90 m³, final receptor storage 200 m³ and zero target residual.
The mean release is exactly `100 / 86400` m³/s.

## What the result means

The output retains the source records, versions, scenario/reference member,
locations, time intervals, numerical diagnostics and evidence. Scientific-use
acceptance and official admissibility remain separate. Exact record fingerprints
prevent changed targets or relations from reusing another record's acceptance.

For each step, the evaluator repeats the pathway balance, capacity and ramp
checks, receptor balance and selected endpoint target. It also repeats supported
imported numeric process criteria. A supported failure survives missing evidence.
The next step must use the actual preceding storage and pathway stocks. Ramping
uses changes between adjacent interval means at interval-end timestamps. It does
not certify unseen peaks. Control and predecessor warm-up exclusions remain
binding even if the later arrival is outside warm-up.

A negative storage residual is reported as surplus, with zero additional managed
arrival and an unresolved operating response. It does not prove the target is
met. Capacity failure does not reduce a requirement. Duplicate carriers across
pathway and receptor accounts are rejected. Do not include a managed arrival a
second time as another receptor inflow.

## Supplied coupled-state objectives

A supported head, wet-area, level or hydroperiod objective does not require an
invented storage target. Attach an explicit `CoupledStateObjective` to the
`DeliveryStep`, leaving `StorageBalance.target=None`. This selects a different
assessment path; a missing storage target alone still cannot pass.

The objective contains:

- A separately identified, accepted numeric quantity `ProcessTest`. Supported
  variables/units are `wet_area`/`m2`, `groundwater_head`/`m`, `level`/`m` and
  `hydroperiod`/`s`. Signed head/level are valid. Area and wet duration are
  nonnegative; duration cannot exceed its assessment interval. Bounds/ranges and
  strictness are tested directly, never replaced by midpoints.
- The independently supplied final water inventory, **not a target**. The actual
  pathway arrivals and receptor exchanges must reproduce it. Each trajectory
  step needs its own inventory and state response.
- Relation identity/version, boundary conditions and uncertainty. Supply
  `coupled_evidence` for `delivery_scope(context, step.coupled_subject)`. This binds
  the physical relation, numeric quantity, process criteria and exact selected
  releases together. Changing releases cannot reuse the old response evidence.
- Supplied and required `StateStatistic` values. An interval-end state cannot
  certify a required whole-interval condition. The exact `expected_intervals`
  axis must match the complete supplied trajectory. Missing slots, daily samples
  replacing expected subdaily samples, and gaps cannot be silently bridged.
- A separate `required_salinity` criterion ID in `required_processes`, plus a
  typed `ReceptorDomain` with `ReceptorVariable.SALINITY`, chemical identity,
  compartment and basis. Its numeric test must name `salinity`, use kg/m³ and
  match that basis exactly. Incoming-water compartments are refused. Root-zone
  or groundwater targets require an explicitly accepted domain, not a bulk
  resident-water substitution.
- Explicit `SalinitySupport.COUPLED_MODEL` or `INDEPENDENT_IMPORT`. A dependent
  salinity result loses supported status when model, temporal or physical-balance
  support fails. An independent import instead needs acceptance for
  `delivery_scope(context, step.salinity_subject)`, binding the exact chemical,
  compartment, basis and numeric test. Its independently supported failure can
  survive an unsupported quantity model. Generic test acceptance alone cannot
  establish that independent chemical/domain finding.

The evaluator rechecks every interval's physical account, imported quantity
criterion, processes and independent audit. A mid-trajectory failure survives a
passing terminal result. Missing or unsupported relation/state evidence remains
unknown. A supported quantity failure survives missing salinity as failure plus
incomplete coverage. A salt or temperature `ProcessTest` cannot be relabelled as
this non-storage quantity objective.

Run `examples/receptor_delivery.py` for both paths. Its `supplied_inundation()`
function supplies 120 m² against the range [100, 150] m² with whole-interval model
support, 200 m³ independently checked inventory, the original 100 m³ control
release and separate resident salinity. It passes without a storage target or
state-to-inflow inversion. Its arrival residual remains unsized because this
operation assesses the supplied schedule rather than deriving one.

Continuous exposure and internal transients require appropriately resolved,
accepted model evidence; software does not reconstruct them from endpoints.
Hydroperiod here is a supplied model duration statistic, not a native duration
solver. Salt accounting and joint receptor duration assessment are separate
operations. No conservative mass or chemistry calculation is performed here.

## Physical mapping for final assembly

`control_equivalent(mapping, evidence)` supports the explicit zero-loss,
zero-delay `ControlMapping` at named locations. Two bounds on the same water use
maximum; continuing flow plus a separate lateral withdrawal uses the carrier sum.
The result retains both needs and the mapping evidence. Missing mapping evidence
returns no upstream equivalent. Complex losses, delays and stocks must first be
accounted for with the pathway representation. This helper does not perform final
requirement/floor/quality assembly or issuance.

## Source and executed-test crosswalk

These are derived technical witnesses, not copies of the restricted source.
Authority: approved bundle `fishy_taqsim_handover_candidate_2026-09-19`.

- Appendix A: `report_snapshot/appendices.qmd`, `sec-recipe-step9`, conversion
  steps 1–4. SHA-256:
  `e520499b91cc72d25dbec430a266d672331c1e732c284129b4d125db1ea9eb76`.
- Component mapping: `report_snapshot/part4_assembly_contract.qmd`,
  `sec-component-assembly`. SHA-256:
  `0a97ef52784fbfd2dc21ba689a2edfbda4f182ed52a33757afc7b2753c329d85`.
- `ACCEPTANCE.md` U7/U8 and C2/C3/C5.

All tests below are in `tests/test_receptor_delivery.py`. Values are synthetic,
not policy defaults. Exact rational arithmetic uses **zero numerical tolerance**;
that is not a claim of zero scientific uncertainty.

| Requirement | Public operation/input | Test | Actual = expected |
|---|---|---|---|
| Step 9.2 residual | `storage_arrival`, 100→200, rain 20, outflow 10 | `test_storage_residual_counts_rain_and_outflow_once` | 90 m³ |
| Step 9.3 surplus | `storage_arrival`, target 50 | `test_negative_residual_is_surplus_not_satisfaction` | residual −60; surplus 60; attempted target fails |
| Steps 9.1–2 missing/unsupported | missing target/relation, rejected/restricted/changed relation | `test_unsized_missing_or_unsupported` | unsized, no numeric delivery |
| Steps 9.3–4 timing/stocks/loss | `map_arrival`, `assess_delivery` | `test_arrival_control_losses_delay_stocks_and_recheck` | control 100; arrival 90; storage 200; pass |
| Step 9.4 infeasible | capacity below 100/86400, zero rise limit, excess final pathway stock | `test_infeasible_schedule_never_reduces_requirement` | failure; retained need 90 |
| Step 9.3 allocation | two named unknown paths, then selected 55+55 control volumes | `test_unresolved_multiple_paths_and_supplied_operating_selection` | unknown, then arrivals 45+45 and pass |
| Step 9.4 whole trajectory | two endpoint targets, altered first target | `test_complete_discrete_trajectory_rechecks_intermediate_target` | states 200/300; altered first target fails despite final pass |
| Step 9.4 process coverage | salinity 2 versus limit 1, temperature absent | `test_unknown_quality_and_supported_failure_are_lossless` | fail + incomplete; unsupported salinity becomes unknown |
| Step 9.4 independent evidence | no checking evidence or absent process | `test_independent_check_and_missing_process_cannot_pass` | unknown |
| C5 identity/carrier isolation | duplicate rain/pathway, changed scenario/domain/time | `test_reject_duplicate_carriers_and_mismatched_identities` | rejection |
| C5 declared domains | negative ramp/volume, nonfinite volume | `test_nonnegative_and_exact_domain_validation` | rejection |
| C3 empty criteria | empty process profile | `test_required_empty_process_profile_does_not_certify_receptor` | unknown |
| C5 period coverage | one day supplied for two-day period | `test_declared_period_cannot_omit_first_or_last_step` | unknown; supported first step retained |
| C5 time support | excluded control interval, later arrival | `test_control_warmup_exclusion_is_not_hidden_by_later_arrival` | unknown |
| Assembly/U7 physical crosswalk | continuing 3, receptor 2; explicit mapping | `test_source_component_crosswalk_same_water_3_lateral_5` | same-water 3; lateral 5 m³/s; missing evidence unresolved |

The public example is executed by
`test_public_delivery_example_executes_without_simulator_import`, which blocks
Taqsim and Incidence imports and checks its printed 90/100/200 m³ values,
`pass` findings for both storage and non-storage examples, and `pending` official
admissibility. A cold standalone Python process also executed the example with
Taqsim and Incidence imports explicitly blocked. Fishy's ordinary Polars
dependency is used by the shared receptor vocabulary; no simulator is required.

Executed locally: `uv run pytest tests/test_receptor_delivery.py -q`: **52 passed**.
`uv run ruff check` and `uv run ty check` on the owned module pass.
Implementation base: Fishy `e02d43c9ed35eefd377b61f7ec201a6005843b06` plus this
change. Lockfile sources remain Taqsim
`396ad093c2b6f240e702a3b05aee1fb96a69b3f7` and Incidence
`665da4e0d81ab28921b8d5d2edbb9be27f4ec612`. These tests do not call a simulator or
claim additional integration validation. Final implementation commit identity is
recorded by the containing pull request.

### Coupled-objective regression crosswalk

The supported non-storage path was added after a failing test against Fishy
`38057c5bfee73cd92179def9482da3918a716c09`. The test exercised the actual prior
public schedule assessment with supported wet-area/process evidence and exposed
an unconditional missing-storage-target result. The explicit objective fixes the
missing path without converting a generally missing storage target into pass.

| Step 9 requirement | Executed test | Actual = expected |
|---|---|---|
| Supported non-storage candidate | `test_supported_nonstorage_schedule_is_assessed_without_fake_storage_target` | pass; final inventory 200 m³; no storage target or derived inflow |
| Variable/unit and ranges | `test_supported_coupled_quantity_domains` | wet area, signed head, level and hydroperiod pass their original ranges |
| Missing/unsupported/model timing | `test_nonstorage_missing_or_unsupported_remains_unresolved` | nine configurations return unknown |
| Quantity, strict equality, physical/capacity failure | `test_nonstorage_infeasible_candidate_preserves_quantity_requirement` | four failures retain the 100 m² lower bound |
| Explicit objective required | `test_nonstorage_cannot_replace_missing_storage_target_implicitly` | missing target remains unknown; false variable/unit and conflicting target rejected |
| Exact temporal axis | `test_coupled_expected_subdaily_axis_cannot_be_replaced_by_daily_endpoint` | incompatible daily/subdaily periods rejected |
| Full trajectory | `test_coupled_complete_trajectory_rechecks_intermediate_quantity_and_balance` | two-step pass; altered first quantity or physical inventory fails despite terminal pass |
| Schedule-specific support | `test_changed_release_invalidates_prior_coupled_evidence` | changed actual release cannot reuse prior coupled response; unknown |
| Failure with partial coverage | `test_nonstorage_required_quantity_failure_survives_missing_salinity` | supported failure + missing salinity remains fail; unsupported numeric failure becomes unknown |
| Separate quality requirement | `test_nonstorage_arbitrary_process_does_not_replace_named_salinity` | temperature-only process cannot satisfy named salinity; unknown |
| Salinity variable, not units alone | `test_coupled_quantity_units_do_not_authenticate_salinity_variable` | temperature labelled kg/m³ cannot satisfy salinity; unknown |
| Dependent salinity support | `test_unsupported_coupled_model_cannot_support_its_numeric_salinity_failure` | unsupported coupled model makes its numerical salinity failure unknown |
| Chemical/compartment identity | `test_coupled_salinity_domain_rejects_incoming_and_wrong_chemical_basis` | incoming compartment rejected; mismatched basis unknown |
| Explicit root-zone relation | `test_explicit_supported_root_zone_salinity_preserves_domain` | supported root-zone target passes without relabelling bulk resident water |
| Independent salinity evidence | `test_independent_salinity_failure_survives_unsupported_coupled_model` | independently accepted salt failure survives unknown quantity model; generic numeric acceptance does not |
