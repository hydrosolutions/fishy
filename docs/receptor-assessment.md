# Receptor state and joint-duration assessment

Import from `fishy.receptor_states` and `fishy.receptor_inventory`. These operations assess a supplied candidate. They do not generate releases or adopt ecological targets.

## Run a supplied example

```console
uv run python examples/receptor_assessment.py
```

Expected and executed output:

```text
storage: pass
salinity: fail
joint: fail; coverage: complete
```

The example supplies an initial inventory of 100 m³ and 50 kg, an arrival of 100 m³ and 200 kg, and an independently supplied final inventory of 200 m³ and 250 kg. The balance closes exactly. The final concentration is 1.25 kg/m³. Storage ≥200 passes; salinity ≤1 fails. These targets and evidence permissions are synthetic, not policy defaults.

`import_receptor_inventory` checks a supplied `LoadAccount`. It does not solve a transport model. Keep its `InventoryStateImport`: it retains initial/final inventories, every carrier, counted-load identity, processes, precision disclosures and exact water/mass residuals. `assess_receptor` retains the imported states, target profile and supported versus exploratory component comparisons.

## Public inputs and meaning

- `ReceptorContext` identifies the physical `Location`, candidate, scenario, reference member and exact period. A plan assignment is not required.
- `ReceptorDomain` identifies storage, level, wet area, groundwater head or salinity. It retains compartment, datum/representation basis, chemical form and reporting basis. Root-zone, groundwater, incoming and resident water are different domains.
- `ReceptorValue` accepts only the domain's canonical unit. Storage, area and concentration are nonnegative. Datum-relative level and groundwater head may be signed. There is no chemistry conversion or discharge-to-state substitution.
- `ReceptorBounds` preserves a supported interval and its meaning/source. Use two targets for a range; do not substitute a midpoint.
- `ReceptorTarget` retains comparison strictness, season, resolution, ecological purpose and `EvidenceFindings`. Each required quantity and salinity target must be declared; an omitted family or target remains unknown.
- `ReceptorState` imports bounds with `Presence`, provenance-bearing evidence, exact interval and temporal statistic. `INTERVAL_END`, `INTERVAL_MEAN` and `WHOLE_INTERVAL` are not interchangeable. Whole-interval bounds must come from supported external evidence, not a point sample.
- Target evidence uses `context.evidence_scope(target.identifier, context.period)`. State evidence uses `context.evidence_scope(context.candidate, state.interval)`. The intended use is `receptor assessment`. Scientific permission and official admissibility remain separate. Indicative evidence can pass its supported configured use without official permission. Restrictions and excluded warm-up periods still bind.
- `ReceptorProfile` identifies a versioned hypothetical/adopted configuration and the exact requested slots. State tests concern those slots and statistics only. No continuous trajectory claim follows from a complete set of endpoint tests.

`assess_receptor(profile, states)` rejects duplicate domain/time carriers and incompatible candidate, scenario, reference, location and time. A supplied concentration from a different compartment remains available in `states`, but cannot satisfy a resident-water target. Missing, absent, outside-horizon, dry and unsupported records stay distinct. Unsupported numerical comparisons remain in `numerical`, never promoted to supported pass or failure. A supported required failure dominates unknown findings while completeness remains incomplete.

For other physical models, construct supported `ReceptorState` records directly. A supported root-zone or groundwater model can supply its own domain. Bulk mixed inventories cannot produce those states. Source composition from `PhysicalProjection.constituent` remains a transfer concentration; use it only in a correctly attributed carrier account, not as a resident-water reading.

## Inventory and dry-state boundary

`ReceptorBalance` reuses `LoadAccount`, `Inventory`, `Mass`, `Volume` and `AccountTransfer`. All nonzero mass entries must identify their physical loads with `CountedLoad`. A load cannot appear both in a carrier and a separate process. Existing account checks reject duplicate transfers and incompatible boundaries. Exchanges and processes retain their supplied directions, destinations and evidence. Nonvolatile conservative evaporation is represented by negative water change and zero mass change; no salt loss is inferred from removed water.

`MixedCompartmentEvidence` supplies permission for representative resident-water mixing. At positive volume, the importer checks and reports M/V. At zero volume, aqueous concentration is undefined and the full retained mass stays in the account. Refilling dry retained mass needs separately supported remobilisation evidence. Conservation failure invalidates the affected support but leaves arithmetic/residuals visible. Water support can survive an independent salt-balance failure. Closure alone does not establish mixing suitability, stratification, root-zone physics or ecological tolerance.

## Coincidence and duration

```python
from fishy.receptor_states import assess_joint_duration

# assessment: supported whole-interval quantity AND salinity tests
# criterion: DurationCriterion with supplied minimum, strictness, operator and evidence
result = assess_joint_duration(assessment, criterion)
```

`DurationCriterion` identifies a cumulative or consecutive minimum and its supplied scope/evidence. `Duration` uses exact seconds, hours or fixed 24-hour days. Evidence uses `context.evidence_scope(criterion.identifier, context.period)`.

The lower bound counts known joint passes. The upper bound includes intervals not ruled out by a supported required failure. Unknown raw components stay incomplete even when a known failure rules out an interval. A lower bound meeting the minimum passes; an upper bound below the minimum fails; overlap remains unknown, preserving strictness. `raw_coverage` is separate from the resolved duration `check`.

For consecutive duration, known failures break both runs and unknowns break only the lower-bound run. Explicit assessment gaps count as unknown, not fabricated suitable states. No boundary wrapping occurs. Required missing boundary history makes the duration check unknown. A cumulative result cannot replace a consecutive condition. A resolved duration test does not certify other receptor conditions.

For state-to-inflow and control mapping, see [receptor delivery](receptor-delivery.md). Final Uzbek assembly, issuance, quality activation and corrective release sizing are outside these operations.

## Maintained acceptance crosswalk

Traceability: Effort https://github.com/hydrosolutions/taqsim/issues/28; Program #4. Governing derived clauses: `report_snapshot/part4_quality_calculation.qmd#sec-receptor-quality`, Appendix A `appendices.qmd#sec-recipe-step9`, acceptance F5/U8/C2/C3/C5/C6 and receptor suite. The held report originals are not redistributed.

| Held fixture identifier | Public operation/input | Executed test in `tests/test_receptor_states.py` | Actual = expected |
|---|---|---|---|
| `saline_arrival_quantity_pass_salt_fail` | Inventory import and joint endpoint test; 100/50 + 100/200 | `test_held_inventory[saline_arrival_quantity_pass_salt_fail]` | V=200, M=250, C=1.25; quantity pass, salinity/joint fail; endpoint coverage complete |
| `fresh_arrival_endpoint_targets_pass` | Same input with arrival mass 10 | `test_held_inventory[fresh_arrival_endpoint_targets_pass]` | V=200, M=60, C=0.30; both pass; endpoint-only scope |
| `evaporation_preserves_salt` | Initial 200/160; evaporate 100 water, no salt | `test_held_inventory[evaporation_preserves_salt]` | V=100, M=160, C=1.6; quantity pass, salinity/joint fail |
| `quantity_failure_with_unknown_salinity` | Storage 100 <200, no salt evidence | `test_held_missing_salinity[quantity_failure_with_unknown_salinity]` | Joint fail, incomplete |
| `quantity_pass_unknown_salinity` | Storage 200, no salt evidence | `test_held_missing_salinity[quantity_pass_unknown_salinity]` | Joint unknown, incomplete |
| `transient_failure_hidden_by_final_pass` | Three endpoint concentrations 0.5,1.2,0.8 | `test_transient_failure_hidden_by_final_pass` | pass/fail/pass, aggregate fail, last endpoint alone pass |
| `dry_state_is_not_zero_concentration` | Final water 0, retained salt 10 | `test_dry_state_is_not_zero_concentration` | No concentration, salt 10 retained, joint unknown |
| `source_water_not_receptor_state` | Incoming 0.1 versus resident-water target | `test_source_water_not_receptor_state` | Resident salinity/joint unknown; also tests root-zone and groundwater distinction |
| `endpoint_only_cannot_certify_interval_maximum` | Endpoint 0.8 with whole-interval required target | `test_endpoint_only_cannot_certify_interval_maximum` | Endpoint pass; interval unknown/incomplete |
| `unsupported_model_output_remains_exploratory` | Numerical quantity pass/salinity fail; model use not accepted | `test_unsupported_model_output_remains_exploratory` | Numerical fail, supported unknown |
| `missing_required_target_set` | Empty quantity/salinity target families | `test_missing_required_target_set` | Two attributable unknown missing-family tests; no vacuous pass |
| `separate_durations_do_not_supply_coincidence` | Four days, quantity TTFF and salinity FFTT | `test_separate_durations_do_not_supply_coincidence` | Joint duration 0; minimum 2 fails |
| `duration_bound_resolves_partial_coverage` | Quantity TTTT, salinity TT?? | `test_duration_bound_resolves_partial_coverage` | Bounds [2,4] days; minimum 2 passes, raw incomplete |
| `consecutive_and_cumulative_duration_differ` | Quantity TTTT, salinity TFTF | `test_consecutive_and_cumulative_duration_differ` | Cumulative 2, longest run 1; consecutive minimum 2 fails |

Additional clause witnesses:

| Requirement | Test | Actual = expected |
|---|---|---|
| Duration strictness, missing boundary history | `test_duration_strictness_unknown_bounds_and_missing_boundary_history` | Strict min 2 with [2,4] unknown; [0,1] fails; missing history unknown |
| Duration known failure plus missing component | `test_duration_known_failure_keeps_missing_component_raw_coverage` | [0,0] fails with raw incomplete; regression first failed before fix |
| No gap bridging or boundary wrapping | `test_unknown_gaps_do_not_increase_consecutive_lower_bound_or_wrap` | Consecutive lower 1, upper 4 days, unknown |
| Point samples are not interval exposure | `test_point_samples_never_supply_duration` | Bounds [0,1] day, unknown despite endpoint pass |
| Signed heads, ranges, uncertainty, strictness | `test_bounds_range_and_signed_head_preserve_declared_domain` | Head -1 fails strict upper -1; supported [-2,-1] overlaps and is unknown |
| Full presence and permitted-use restrictions | `test_presence_and_use_restrictions_remain_explicit` | Missing/absent/outside/unsupported preserved; prohibited use unknown |
| Exact candidate/time/domain | `test_incompatible_context_rejected`, `test_duplicate_and_temporal_domain_inputs_rejected` | Invalid combinations raise; no resampling |
| Quantity invariants | `test_invalid_nonnegative_values`, `test_chemical_units_are_not_silently_converted` | Negative/nonfinite amounts and incompatible units refused |
| Water/salt balances independently supported | `test_balance_failure_invalidates_affected_support_without_erasing_residual` | Salt residual -190 kg visible; storage pass survives; salinity unknown |
| Dry retained salt on rewetting | `test_no_implicit_remobilisation_on_refill` | Without accepted remobilisation unknown; accepted explicit relation passes |
| Count fluxes once | `test_duplicate_carrier_load_and_account_mismatch_rejected` | Duplicate carrier/load and wrong receptor rejected |
| Supported specialist model imports | `test_supported_root_zone_import_and_target_evidence_restriction` | Correct root-zone target/import pass; restricted tolerance remains unknown |
| Evidence and warm-up retention | `test_exact_evidence_scope_and_warmup_restrictions`, `test_inventory_physical_warmup_cannot_be_erased_by_assessment_evidence` | Foreign candidate scope and physical warm-up cannot pass; physical warm-up regression first failed before fix |
| Supporting model and criterion warm-up | `test_supporting_inventory_model_warmup_prevents_supported_pass`, `test_duration_criterion_warmup_prevents_supported_pass`, `test_target_criterion_warmup_prevents_supported_pass`, `test_target_warmup_only_excludes_overlapping_requested_slots` | Excluded mixing/remobilisation/target/duration evidence cannot support pass or fail; numerical comparisons and independently supported storage survive; four original-head red cases preceded fixes |
| Immutable configuration isolation | `test_receptor_profile_immutable_scenario_isolation` | New version/limit can pass; earlier profile/result still fails |
| Executable public example | `test_public_receptor_example` | Storage pass, salt/joint fail, complete endpoint coverage |

All arithmetic uses exact `Fraction` values. Tests use exact equality with zero numerical tolerance. Bounds describe supplied uncertainty; software precision is not scientific uncertainty. Fixtures are synthetic and do not calibrate a basin.

### Verified source identities and compatible revisions

| Held bundle-relative file | SHA-256 |
|---|---|
| `IMPLEMENTATION_BRIEF.md` | `0ad077a69f27af74dd6cf340830438576d020d66b9bf5a8d568bb84eb5c757c8` |
| `ACCEPTANCE.md` | `851fc64c35e827fa3a072750f760108ddd5f445684ba65f85bb4037758b047ba` |
| `report_snapshot/appendices.qmd` | `e520499b91cc72d25dbec430a266d672331c1e732c284129b4d125db1ea9eb76` |
| `report_snapshot/part4_quality_calculation.qmd` | `e8188a9dce5bfad5b9b155b4e0962f676700679fdacb22f530c367a6de752d4f` |
| `report_snapshot/quality_support/receptor_quality_fixtures.json` | `30d83198d738fc6ed4940462cddf3c300e929b9bd13ed3aa27611b734404e474` |

Base Fishy: `e02d43c9ed35eefd377b61f7ec201a6005843b06`. Existing optional compatibility pins retained: Taqsim `396ad093c2b6f240e702a3b05aee1fb96a69b3f7`, Incidence `665da4e0d81ab28921b8d5d2edbb9be27f4ec612`. These receptor operations require no simulator import. Reproduce the maintained suite with `uv run pytest tests/test_receptor_states.py tests/test_receptor_delivery.py`.

Site targets, pathway/model suitability, groundwater exchange physics, biological tolerances, quality activation and official application remain supplied evidence. This capability does not claim full Uzbek assembly, an issued duty or ecological/legal status.

### Execution record

The receptor suites execute **122 tests** (49 state/inventory/duration and 73 delivery). After merging hydraulic and study delivery through `fe293c7efa5cd88034ae052057c876e017877612`, the repaired full repository suite executed **1579 passing tests**, including all 122 receptor tests. Ruff check, Ruff format check and ty check pass on the combined tree. The state example uses the ordinary mandatory Polars dependency but no simulator; `test_receptor_example_never_imports_simulator` blocks Taqsim/Incidence imports while executing its real public entry point. Both public examples execute with simulator imports blocked.
