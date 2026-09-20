# Swiss residual-flow exceptions

`fishy.swiss_exceptions.assess_exception` assesses supplied Art. 32 conditions and a supplied lower minimum. It does not decide whether a canton should grant an exception. Q347 and the ordinary minimum are `Flow` inputs, independent of the hydrology implementation.

## Inputs and result

1. Create `ExceptionScope` with a versioned `Location`, intake identifier, scenario, reference member, exact `Interval`, and `DownstreamExtent` in metres from that intake. Supply `configuration_version` and `data_version`; evidence provenance must match both. An extent ending at 1,001 m does not qualify for a 1,000 m exception, even if its length is less than 1,000 m.
2. Supply one condition record: `HighAltitudeWater`, `NonFishWater`, `LowEcologicalPotential`, `ProtectionUsePlan`, or `EmergencyAbstraction`. These contain actual site facts and specialist findings, not a list of passing check IDs. Optional fields set to `None` mean missing evidence. Enums express domain states; strings or booleans cannot replace them.
3. Attribute condition evidence with `EvidenceFindings`. Construct the condition record with `evidence=None`, then attribute its evidence using `condition_evidence_scope(scope, clause, conditions)` and attach it with `dataclasses.replace`. This binds all actual condition values. Changing those values requires new reviewed evidence. Its provenance must identify the same scenario and member. Scope includes physical-body/reach/section versions and downstream distances. Preserve study uncertainty and limitations in provenance and finding reasons.
4. Supply `ExceptionDecision` with the same scope and clause, lower numerical `Flow`, `DecisionBasis.AUTHORISED` or `HYPOTHETICAL`, issuer, reference and evidence. An authorised path additionally requires supplied official admissibility for the decision and condition evidence. Use `decision_evidence_scope(scope, clause, minimum, basis, issuer, reference)` to identify the reviewed decision. Changing its amount, basis or attribution invalidates the old evidence scope. The software does not authenticate that assertion.
5. Read `result.summary` and `result.applied_minimum`. The latter is `None` unless every required condition and decision is supported. `ordinary_minimum`, Q347, evidence, decision and exact scope remain in the immutable result.

For a non-fish scenario with Q347 = 40 l/s, ordinary minimum = 50 l/s and proposed minimum = 14 l/s:

```python
from fishy.quantities import Flow
from fishy.swiss_exceptions import NonFishWater, FishStatus, assess_exception

conditions = NonFishWater(condition_evidence, FishStatus.NON_FISH)
result = assess_exception(
    Flow(40, "l/s"), Flow(50, "l/s"), scope, conditions, supplied_decision
)
# Given matching supported evidence and a hypothetical decision for 14 l/s:
assert result.applied_minimum == Flow(14, "l/s")
assert result.ordinary_minimum == Flow(50, "l/s")
```

`condition_evidence`, `scope` and `supplied_decision` are application inputs as described above. `tests/test_swiss_exceptions.py` provides fully constructed synthetic examples for every branch, including evidence and decisions.

## Conditions and limits

- **32(a):** Q347 must be strictly below 50 l/s and the scope must remain within 1,000 m below the intake. Above 1,700 m is a strict branch that does not require non-fish status. Between 1,500 and 1,700 m requires non-fish evidence. At exactly either endpoint, supply `AltitudeEndpoints.INCLUSIVE_SCENARIO` with an attributed interpretation and hypothetical decision, or `AUTHORITY_INCLUSIVE` with attributed admissible authority evidence. No selection remains unresolved. An explicit exclusive reading fails at the endpoints.
- **32(b):** Non-fish evidence and reduced residual flow at least 35% of Q347. Arithmetic is exact; equality qualifies numerically.
- **32(bbis), Ordinance 33a:** At most 1,000 m below intake; low present significance AND low significance after proportionate restoration; identified restoration study; natural functions not substantially impaired. Present degradation alone is insufficient.
- **32(c), Ordinance 34:** An identified adopted plan and FOEN application; limited topographically connected area; water/dependent-habitat compensation in the same area; ecological adequacy and its explanation; compensation additional to legally required measures; arrangements binding everyone for the entire concession; Federal Council approval and reference. FOEN filing does not substitute for approval. The application supplies these specialist/legal findings, rather than the software inferring ecological equivalence from water volumes.
- **32(d):** An identified emergency and explicit temporary period covering the assessed interval. Ordinary scarcity is not an emergency decision.

`effective_minimum_for(requested_scope, assessment)` recomputes the stored condition and decision inputs before selecting a concrete residual minimum for a requested segment. Replacing a derived result field cannot introduce an unreviewed reduction. A contained segment receives the supported reduction. A spatially or temporally disjoint segment retains the ordinary minimum. A straddling segment returns `None` and requires subdivision. Unrelated physical, scenario, member, configuration or data identities return `None`, not a transferred ordinary value. Tests `test_effective_minimum_retains_normal_protection_outside_exception` and `test_effective_minimum_cannot_lower_on_unresolved_assessment` cover all these cases. `test_effective_minimum_recomputes_replaced_derived_value` proves that an altered derived value is not trusted.

A passing exception applies **only** inside its exact scope. Normal Arts. 31 and 33 protection remains beyond that extent and period. Callers must retain those other downstream requirements; this operation does not evaluate their routing or delivery. Art. 33 interest balancing remains separate after every exception. No result grants permission or certifies biological condition.

Missing and unsupported inputs have distinct reasons and prevent lowering. A known failure survives missing evidence, with incomplete coverage. Numerical calculations, scientific support and official admissibility remain separate. Decisions and conditions with mismatched reference kinds cannot be combined.

## Public-source crosswalk

Primary sources: [GSchG, German consolidation 2025-08-01](https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de) and [GSchV, German consolidation 2025-12-01](https://www.fedlex.admin.ch/eli/cc/1998/2863_2863_2863/de). Supporting [FOEN Guide 2000](https://www.bafu.admin.ch/dam/de/sd-web/DURPl8AmZvgE/angemessene_restwassermengenwiekoennensiebestimmtwerdenwegleitun.pdf), §§4.5–4.6, printed pp.48–58. The older Guide does not override the amended altitude/non-fish or bbis clauses.

All following tests are in `tests/test_swiss_exceptions.py`. Exact `Fraction` comparisons use zero numerical tolerance. Inputs are synthetic, not published application data.

| Requirement/source | Operation/input | Observable witness / test |
|---|---|---|
| 32(a), strict Q347 | `HighAltitudeWater`, `assess_exception` | 49.999 passes, 50 and 51 fail: `test_high_altitude_q_strict` |
| 32(a), altitude/fish status | `Elevation`, `FishStatus` | 1701 fish passes; 1700 fish fails; 1499 non-fish fails; 1600 non-fish passes: `test_altitude_and_nonfish` |
| Approved endpoint scenario | `AltitudeEndpoints` | 1500 and 1700 unresolved without selection, inclusive hypothetical passes, exclusive fails: `test_exact_altitude_endpoints_require_explicit_selection` |
| 32(a), 32(bbis), limited extent | `DownstreamExtent` | 999 and 1000 pass; 1001 fails: `test_limited_reach_boundaries` |
| 32(b), 35% | `NonFishWater`, decision minimum | q40: 13.999 fails, 14 and 14.001 pass: `test_nonfish_35_percent_exact`; fish fails: `test_nonfish_required` |
| 32(bbis), Ordinance33a | `LowEcologicalPotential` | Either significance not low or substantial impact fails: `test_low_potential_requires_present_and_restored_significance`; missing restored study unresolved: `test_present_degradation_alone_insufficient` |
| 32(c), Ordinance34 | `ProtectionUsePlan` | Connected same area, purpose, additionality, adequacy, Federal Council approval and whole-concession binding required: `test_protection_plan_real_conditions`; missing records unknown: `test_missing_plan_inputs_do_not_pass` |
| 32(d) | `EmergencyAbstraction` | Emergency passes, ordinary scarcity fails, missing time unresolved, insufficient time fails: `test_emergency_temporary_not_ordinary_scarcity` |
| 32, supplied decision | `ExceptionDecision` | All five exceptions unresolved without decision: `test_every_exception_needs_decision`; official evidence: `test_authorised_requires_admissible_decision_and_conditions` |
| 32 scope, Guide§4.5 | exact reach/member/scenario/period | Wrong scope cannot lower: `test_out_of_scope_decision_cannot_lower`; `test_section_version_evidence_cannot_transfer`; `test_mixed_reference_kinds_cannot_lower`; `test_evidence_configuration_and_data_cannot_transfer`; `test_reviewed_decision_amount_cannot_be_replaced`; `test_reviewed_condition_content_cannot_be_replaced` |
| Guide§§4.5–4.6, normal protection and separate Art33 | result ordinary value and restrictions | 50 retained while scoped minimum10 applies: `test_numeric_result_keeps_ordinary_protection_and_balancing` |
| Required evidence semantics | result summary | Known q50 failure plus missing evidence remains failure/incomplete; unsupported evidence prevents lowering: `test_failure_survives_missing_and_unsupported_evidence` |
| Units/domain invariants | quantity/record constructors | Nonfinite elevation, booleans and untyped periods rejected: `test_invalid_elevation`, `test_runtime_domain_validation` |

Validation command: `uv run pytest tests/test_swiss_exceptions.py -q`. The parent acceptance record supplies the integrated revision pin and executed counts; this module does not make a scientific or official certification claim.
