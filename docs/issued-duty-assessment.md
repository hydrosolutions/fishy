# Issued duties and floor comparisons

These operations implement the proposed Uzbek arithmetic. They do not adopt policy,
authenticate evidence, or approve a complete design family. They need no simulator.

## Keep the quantities separate

`fishy.uzbek_issuance.issue_obligation(requirement, deliverability, version=..., provenance=...)`
returns the two supplied operands, an immutable `Obligation`, and an ecological deficit.
It computes `min(requirement, deliverability)` for one exact location and interval.
For requirement 10 and deliverability 6 m³/s, the obligation is 6 and the deficit is 4.
The complete-family checks must run before the caller uses this arithmetic for new issue.
A `Floor`, actual `Delivery`, or physical `Availability` cannot replace either named operand.
Missing or unsupported operands raise an error. No zero or floor-only obligation is invented.

`fishy.delivery_assessment.assess_issued_delivery(obligation, actual, evidence=...)`
compares the fixed issued obligation with actual delivery. With delivery 5, raw shortfall
is 1 m³/s, or 86,400 m³ over one whole day. It never recomputes the issuance cap.
Raw shortfalls are nominal diagnostics; the supported uncertainty finding is separate.
An upper actual bound below the obligation is `below`. A lower bound at or above it is
`not_below`. Overlap is `indeterminate`. Missing bounds or rejected required evidence
make the uncertainty comparison `unavailable`, even when the nominal diagnostic exists.

The existing `fishy.duties.assess_duty` still assesses independent prescribed duties
without this Uzbek issuance cap. It retains its original nominal summary semantics.
Do not combine sanitary and ecological findings into an invented universal sum or maximum.

## Fixed floor and but-for flow

`fishy.floor_assessment.assess_floor(floor, actual, but_for, evidence=...)` keeps the
issued floor fixed. `ButForFlow` supplies the supported reconstructed flow without the
named tested conduct. Both flows must refer to the same location, interval and scenario.
The floor's historical estimation bounds do not widen or reduce the operative threshold.
Deliverability has no part in this comparison.

For fixed floor F, actual support [A_L, A_U], and but-for support [P_L, P_U], the result retains:

- `rectangular_margin`: [A_L − min(F, P_U), A_U − min(F, P_L)] in m³/s.
- `margin`: the operative supported enclosure.
- `numerical`: `below` if the upper margin is negative; `not_below` if the lower
  margin is nonnegative; otherwise `indeterminate`.
- `raw_shortfall`: the positive part of the nominal comparator minus actual flow.
- the original floor, actual, but-for, evidence and joint-support records.

For F=5, A=[3.8,4.2], P=[3,6], the margin is [−1.2,1.2]: indeterminate.
Using a central P=4.5 as certain would give a different, unsupported conclusion.
With P=[4.8,6], the margin is [−1.2,−0.6]: below throughout support.
Supported P=0 and A=0 instead gives [0,0]: not below. The floor remains 5.

`JointMargin` can supply a tighter enclosing margin with its method, source,
dependence and coverage. It binds the exact versioned operands. Finite draw extrema
alone cannot tighten the rectangular result. Their unsupported joint route remains
visible in `reasons`. Marginal confidence levels never imply independent errors or a
joint confidence guarantee. `FlowBounds` refuses negative, nonfinite or reversed
endpoints. Explicit fictional singleton bounds must retain their fixed-value assumption.

## Evidence and responsibility

`ComparisonEvidence` binds the exact threshold, actual and optional but-for records.
Changing a source, version, scenario, point or interval requires corresponding evidence.
Its named checks are `coverage`, `infill`, `authentication`, `reconciliation`, and
`uncertainty`. Floor tests also require `abstraction_metering` and
`downstream_of_conduct`. Each check carries its supporting source or missing/rejected
reason. The uncertainty reason declares the accepted coverage basis. Omitted checks
remain unknown. Any missing or rejected prerequisite makes the numerical test unavailable.

A `CompliancePoint` must identify the tested section and a supplied designation.
A measuring station is not a designation. Without one, supported technical results remain
visible but `official` is unknown. Official admissibility, observed versus scenario
meaning, and supplied attribution are separate. The threshold, actual, and but-for
operand trees retain their original production meaning. An imported wrapper cannot
promote illustrative or simulated contributors to an official or responsibility finding.
Supported reconstructed but-for evidence is not automatically hypothetical. Attribution to the tested conduct
requires evidence of operator control and the same conduct identifier as the but-for flow.
Even fully supported prerequisites return no legal liability decision. A `not_below`
result concerns only this comparator, not every other duty.

## Run a small example

```bash
uv run python examples/issued_duty.py
```

The example uses a real leap day and explicit fictional support. It returns obligation 6,
ecological deficit 4 and raw delivery shortfall 1. Its separate floor 8 comparison is below,
but it cannot establish an official finding or responsibility.

For a missing-evidence branch, keep the supplied record and remove its uncertainty:

```python
from dataclasses import replace
from datetime import UTC, datetime
from examples.issued_duty import scenario, scenario_evidence
from fishy.delivery_assessment import assess_issued_delivery

issue, delivery, floor = scenario(datetime(2020, 2, 29, tzinfo=UTC))
actual = replace(delivery.actual, sample=replace(delivery.actual.sample, uncertainty=None))
result = assess_issued_delivery(
    issue.obligation, actual,
    evidence=scenario_evidence(issue.obligation, actual),
)
assert result.numerical.value == "unavailable"
```

These APIs assess one whole declared interval. For a schedule, invoke them for every
required issued interval, including missing actual records as `None`. Keep each result;
a surplus on another day cannot offset a shortfall. Use `CheckSummary` with one check per
required interval to preserve known failures and incomplete coverage. An empty or
incomplete calendar cannot establish whole-year satisfaction. No within-day constancy
is inferred from a daily mean.

All returned records are frozen. Store the previous record, revision reason, changed
input/profile/reference/software identities, and new issued version in the caller's
history. Recalculation does not supply competent replacement authority or retire an
existing duty. These arithmetic functions do not manage an issuance registry.

## Source and executed-test crosswalk

Authority: accepted consolidated handover dated 19 September 2026, Appendix A steps
10–12 and `sec-floor-uncertainty`; brief §§2, 6; acceptance C2–C5 and ten floor fixtures.
The Water Code is the governing frame. Draft Пакет 7272 is nonbinding. The formulas
implemented here are the report's proposed Uzbek operators, not foreign duty rules.
Only derived synthetic witnesses and technical descriptions are included here, not
private chapters or primary-source copies.

| Source requirement | Public operation/input | Observable result | Executed test |
| --- | --- | --- | --- |
| Step 10; C4 | `issue_obligation`, requirement10/capacity6; then delivery5 | obligation6, deficit4, raw shortfall1; prior records unchanged | `test_c4_immutable_issued_values_and_independent_sanitary_foreign_duties` |
| Steps 10/12; C2 | new requirement/configuration/version | old issue remains; wrong scenario/interval/evidence refused | `test_new_issuance_retains_old_and_rejects_scenario_interval_version_evidence_reuse` |
| Step 10 floor-only boundary | Floor/Delivery/Availability as issuance operand | TypeError, no invented obligation | `test_floor_only_or_actual_or_availability_cannot_be_issuance_operand` |
| Step 11 delivery uncertainty | below, overlap, point equality, upper equality, zero | exact supported margin and finding | `test_supported_delivery_bounds_and_equality` |
| Step 11 admission | each of five rejected limbs | unavailable; raw shortfall retained | `test_rejected_admission_is_unavailable_even_with_supported_numeric_shortfall` |
| Floor fixtures, all ten IDs | `assess_floor`, derived numeric witnesses | exact expected margins/findings; reversed support refused | `test_all_ten_source_floor_witnesses` (ten parameter IDs) |
| Joint uncertainty limitation | finite draw extrema | rectangular indeterminate retained; no fabricated enclosure | `test_finite_draws_are_not_joint_support_and_do_not_change_rectangular_finding` |
| Fixed F | historical floor support0–100, operative F5 | margin−1.2/−0.6, floor unchanged | `test_floor_uncertainty_is_not_applied_to_fixed_issued_threshold` |
| Missing/rejected prerequisites | every floor evidence limb missing/rejected | unavailable, not overlap or cause-indeterminate | `test_each_rejected_or_missing_prerequisite_makes_numeric_comparison_unavailable` |
| Point/admission/causality | missing designation/admission/cause; scenario | numeric below remains separate; no responsibility finding | `test_numeric_shortfall_stays_separate_from_official_and_causal_findings` |
| Supported evidence branches | supplied observed evidence, designated point, operator control | supported official prerequisites and supplied cause; no legal liability claim | `test_supported_official_prerequisites_and_supplied_cause_are_not_legal_liability` |
| C3/C5 real calendars | all366 UTC days in2020; then one omitted day | exact daily volumes; known fail plus incomplete coverage | `test_complete_leap_year_has_no_surplus_offset_and_known_failure_survives_missing_day` |
| Step 10 separate duties | obligation6 delivered6, floor8, but-for9 | delivery not_below; floor below, no cap permission | `test_delivered_obligation_does_not_license_below_floor_abstraction` |
| C5 invalid/missing support | nonfinite, negative, unsupported, partial, mismatched | refusal or unavailable, never zero | `test_nonfinite_or_negative_flow_refused`, `test_unavailable_samples_and_partial_intervals_do_not_pass` |

Numeric comparisons in these tests use exact decimal-to-rational quantities, not a
floating tolerance. The integrated regime assembly, annual family approval and fallback
checks belong to their separate operations; these tests do not claim their acceptance.

Provenance isolation regression: `tests/test_assessment_provenance.py` exercises
illustrative/simulated floor and but-for operands through zero, one, and three
imported wrappers, plus real issuance from hypothetical requirement/capacity operands.
Technical shortfalls remain visible while official and responsibility findings stay
unknown. A supported reconstructed counterfactual retains the positive official path.
