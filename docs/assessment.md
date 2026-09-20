# Supplied-duty assessment

## Public data path

1. Prepare versioned `WaterBody`, `Reach`, `CalculationSection` and `Location`
   records. `PreparedMapping` checks the declared reach set and explicit shared
   sections. Observation and compliance points remain separate records.
2. Supply `Provenance` and exact, timezone-aware `Interval` bounds. Construct
   `FlowSample` readings from observations or imports. `Flow` accepts m³/s or l/s;
   `Volume` accepts m³ or litres. Values normalise to exact rational SI amounts.
3. Keep the instrument's `Obligation` schedule and `SuppliedDuty` attribution.
   Wrap delivered readings in `Delivery`. `assess_duty` matches exact locations
   and intervals. It does not reconcile instruments or impose an issuance cap.
4. Inspect each interval and the required-check summary. `known_shortfall_volume`
   is a **subtotal** when coverage is incomplete. Its name is not a claim that
   omitted intervals had no shortfall.
5. Supply other required component checks explicitly. A velocity, quality or
   within-day condition cannot be passed by a discharge mean.

Run `uv run python examples/supplied_duty.py` for a complete observation-input
example. Imports use the same records with their own `ProductionMethod` and source
versions. There is no requirement to run a simulator first.

## Evidence and independent quantities

The six frozen role types `Requirement`, `Floor`, `Availability`, `Deliverability`,
`Obligation` and `Delivery` do not substitute for one another. `assess_feasibility`
compares a supplied duty with deliverability, without changing either. A supplied
10 m³/s duty and 6 m³/s deliverability return a 4 m³/s infeasibility; the duty remains
10. Deriving the Uzbek capped obligation is a later assembly-method responsibility.

`assess_duty` reports a **numerical** result. Each row separately retains the
comparison over supplied `FlowBounds`. No bounds means unavailable uncertainty,
not an invented zero-width interval. Observed comparisons are labelled as not
legal compliance. Simulated, reconstructed, imported and illustrative inputs do
not become observations. No result determines cause or responsibility.

`EvidenceFindings` retains distinct computability, numerical validity, disclosure,
scientific adequacy and official admissibility. `permitted_use` evaluates a supplied
finding only for its exact product/reach/member/period/use scope. Reason-specific
restrictions still apply to indicative acceptance. Official pending does not erase
scientific acceptance. Declare `permitted_use` among a duty's required components
when that gate applies, and pass its returned `Check` to `assess_duty`. The caller
chooses the required evidence contract; Fishy does not invent an approval rule.

`aggregate_checks(expected_ids, checks)` materialises omitted reach or group checks
as unknown. All supported passes give complete pass. Known failure survives unknown
checks and retains incomplete coverage. Empty required sets cannot pass. A useful
annual output is not a complete daily regime or passport.

## Physical and temporal boundary

`PhysicalProjection` consumes a live or restored Taqsim `TransportResult`. Choose
`ExchangeView.INCOMING` at an outlet or arrival point, or `OUTGOING` for a reach
transfer. `TimeInterpretation.UTC` explicitly interprets Taqsim's naive timestamps.
Stored inventories are not an available flow view.

`projection.flows()` returns `FlowSample` readings. It divides exact interval water
volume by elapsed seconds. The original physical result, exact counts/quanta,
metadata and support remain accessible on the projection; the physical content
digest is linked in the flow provenance. A failed water account retains its numeric
diagnostic amount but cannot pass a duty. Unsupported chemistry does not erase
independent water or constituent support.

`projection.constituent(...)` requires chemical form and reporting basis and sums
mass and water before concentration. Dry concentration is undefined. Unregistered,
missing, outside-horizon and unsupported constituents remain distinct. This is
physical exchange, not quality-limit assessment.

`aggregate_flow` accepts only whole, contiguous supported intervals and preserves
volume. It discloses lost resolution and does not infer aggregate uncertainty from
marginal bounds. Heterogeneous observation histories retain each original/corrected/
infilled status and source/version. Such an aggregate requires explicit aggregate
provenance; `components` retains every original reading. `daily_discharge` yields a native Polars frame with `date` and
`discharge_m3_s`. It requires complete UTC daily intervals but does not require
complete years; diagnostic operators apply their own record-length gates. Keep the
input samples with diagnostic outputs: the numeric frame does not replace their
per-interval evidence history. Neither operator fills gaps or disaggregates daily values. Excluded warm-up cannot enter
supported assessment or diagnostic conversion. Predecessor evidence is retained,
not fabricated.

`SignedState` retains supported signed stage, velocity, exchange and temperature
with units and domain/sign convention. These are not discharge-derived states.
Process-result validity and ownership remain supplied specialist evidence.

## Executed acceptance crosswalk

All amounts below compare exactly as `Fraction`; no tolerance is applied. Floating
output occurs only at the explicit native diagnostic dataframe boundary. These
synthetic checks are software acceptance, not scientific or official certification.

| Requirement | Public operation/input | Expected and actual | Executed test |
|---|---|---|---|
| S1 supplied duty | `assess_duty`, duties 2/3 and observed delivery 1.5/3.5 m³/s | shortfalls 0.5/0, subtotal 43200 m³, complete numeric fail | `test_duties::test_supplied_schedule_shortfall_does_not_cancel_and_versions_stay_immutable` |
| Successful path | same duty, scenario delivery 2/3 | complete numeric pass; scenario prediction, unchanged duty | same test |
| C1 prepared tracks | `assessment_track`, irrigation river/drinking canal/drain/designated reach | natural/potential independent of category; unresolved designation not inferred | `test_spatial.py` |
| C2 source isolation | frozen source/duty records and new scenario | earlier duty remains 2/3; independent metadata retained | `test_duties.py`, `test_evidence.py` |
| C3 required coverage | explicit IDs with pass/fail/unknown/omission | fail survives unknown; no failure + unknown indeterminate; empty incomplete | `test_evidence.py`, `test_duties::test_other_required_components_cannot_disappear` |
| C4 distinct roles | requirement 10, supplied obligation 6, delivery 5 | independent deficit 4 and shortfall 1; no new issuance operator | `test_duties::test_quantity_roles_are_distinct_and_no_foreign_duty_cap_is_applied` |
| Infeasible supplied case | duty 10, `assess_feasibility` with deliverability 6 | shortfall 4, duty still 10 | same test |
| C5 presence | present 0, missing/absent/outside/unsupported | zero produces real deficit; unavailable interval not zero, incomplete failure retained | `test_duties.py`, `test_physical.py` |
| C5 intervals/units | leap day, 3600 m³ over one hour, two daily means 1/3 | 1 m³/s; aggregate 2 m³/s and 345600 m³ | `test_duties::test_exact_intervals_leap_partial_and_volume_preserving_aggregation` |
| C5 invalid input | units, nonfinite/negative amounts, duplicate/mismatched intervals/maps | explicit rejection; signed stage −1.25 and velocity −0.2 remain valid | `test_duties::test_import_refuses_invalid_domains_units_nonfinite_duplicates_and_mappings` |
| C5 uncertainty/resolution | observed 2 within [1.9,2.1], within-day check omitted | numeric equality pass; uncertainty unknown; required summary incomplete | `test_duties::test_uncertainty_is_separate_and_daily_means_do_not_certify_within_day` |
| C6 useful partial result | accepted indicative annual product, missing daily/quality/receptor | supported annual retained, overall unknown/incomplete | `test_assessment_evidence.py` |
| C6 pending plan/split | `PlanAssignment`, new `Reach` predecessors | assignment does not change location; split has new IDs/history | `test_spatial.py` |
| Warm-up/correction | excluded interval and missing observation status | excluded cannot pass; missing cannot carry numeric reading | last two tests in `test_duties.py` |
| Physical exchange | real model, live and saved projection, explicit incoming view | interval conversion and S1 exact 43200 m³; support/metadata preserved | `test_physical::test_live_saved_supplied_duty_shortfalls`, `examples/taqsim_delivery.py` |
| Declared physical validity | unsupported model-domain result against a zero duty | numeric water retained; unknown/incomplete, never pass | `test_physical::test_global_physical_domain_support_cannot_pass_duty` |
| Projection cost | repeated flows over a real multi-step model, instrument actual digest getter | one full-document digest computation per projection | `test_physical::test_projection_hashes_complete_physical_document_once` |

The two warm-up/correction regressions were first executed against the prior code:
2 failed (an excluded sample passed; a missing-status numeric sample was accepted).
The same tests pass after the boundary fix. A further public-path regression proved
that original/corrected observations from different source revisions were wrongly
rejected as incompatible; it now passes with per-interval attribution retained.

## Sources and scope

The approved foundation vision is
[`planning/visions/2026-09-20-fishy-assessment-foundation.md`](https://github.com/hydrosolutions/taqsim/blob/396ad093c2b6f240e702a3b05aee1fb96a69b3f7/planning/visions/2026-09-20-fishy-assessment-foundation.md).
The owner-supplied 19 September handover supplied the requirements. Its restricted
original reports are not copied into this repository. The implementation read the
six mandated documents, Appendix A steps 1–4 and floor-uncertainty boundary,
Appendix C exchanges/checks/records, component responsibilities, scientific
acceptance and reference-regime sections. The vision records the verified source
hashes and provenance.

These tests cover C1–C6 **foundation semantics**, not full route-specific acceptance.
No Swiss, Kazakh, sanitary estimator, HYDMOD, Uzbek assembly, floor-causation,
quality-limit, hydraulic or receptor method is claimed here. Flow-alteration
diagnostics have their separate source/profile verification and delivery. No
naturalisation, optimiser, scientific-validation orchestrator or registry publication
is included.

## Verification commands

Executed on the supplied-duty branch:

- `uv run --all-extras pytest -q`: **158 passed**.
- `uv run --all-extras ruff format --check`, `ruff check`, `ty check`: passed.
- Both maintained examples: exact 43,200 m³ shortfall asserted.
- `uv run --isolated --no-dev --locked python examples/supplied_duty.py`: passed.
- `uv run --isolated --locked --extra taqsim python examples/taqsim_delivery.py`: passed.
- `uv build`: sdist and wheel built; sdist inspected, no cache files included.
- Isolated built-wheel import of `fishy.duties` and `fishy.physical` with no
  simulator installed: passed.

The physical performance regression instrumented the real source digest getter:
four full serialisations for repeated two-step reads before the fix, one after.
Source projections remain immutable; the cached attribution does not alter data.
