# Source bounds and spawning corrections

`fishy.flow_bounds.correct_schedule` evaluates one configured candidate from Order
179-НҚ (23 July 2025). It does not choose which conflicting provision has priority.

Supply aligned `FlowSample` tuples for the uncorrected requirement, the recorded
long-term minimum, the natural annual P99 hydrograph and the natural annual P50
hydrograph. These natural schedules describe design years. They are not daily
percentiles. `DesignBounds` retains all three original schedules, their provenance,
the source version and separate `AnnualReferenceVolume` records for P99 and P50.
The interval lower bound is the larger of the recorded minimum and natural P99.

Supply one explicit `TimedCoefficient` for each interval, including explicit 1
outside a correction period. `None` represents a missing coefficient, not 1.
Use `fishy.spawning.spawning_schedule` to prepare supported spawning coefficients.
Select `CorrectionOrder.CORRECTION_THEN_BOUNDS` for `B(K*q)` or
`CorrectionOrder.BOUNDS_THEN_CORRECTION` for `K*B(q)`. No choice means no candidate.

Each result retains the original sample, coefficient, lower/upper values,
pre-bound value, all three signed bound adjustments and residual conflicts.
For q=8, lower=5, upper=10 and K=1.5, the orders yield 10 and 12 m³/s.
The first suppresses the increase; the second exceeds the upper bound. Neither
is labelled source compliance. Any supported crossing, including annual bounds,
stops both correction operators before multiplication.

`BoundedSchedule.samples` can be passed to monthly/annual reporting.
`actual_volume` integrates the corrected schedule using actual interval seconds.
It is absent when the supplied schedule does not cover its accounting year or
contains unavailable values. `supported_volume` is explicitly only the sum over
available intervals. Neither value is renormalised. Annual checks compare the
actual total against the preserved annual source bounds.

Inputs must match physical location, mapping, scenario, reference member and
interval. No interpolation or calendar transfer is performed. Missing/partial
bounds, warm-up exclusions and unsupported coefficients remain unresolved.
Coefficient findings use `coefficient_scope`; findings must match both that exact
scope and the coefficient's provenance. Numerical results and scientific-use
findings are separate. A numerically valid candidate may have rejected scientific
use. Annual numerical bounds remain usable without scientific findings, but their
scientific-use check is then unknown. Official admissibility is never inferred.

## Reproducible acceptance

Run `uv run pytest tests/test_flow_bounds.py -q`.

| Source requirement | Operation and observed test |
|---|---|
| 17(2), 19(3–4): recorded/P99/P50 bounds | `DesignBounds`; tests retain every source and adjustment, including recorded minimum |
| 19(3–4): annual bounds | `AnnualReferenceVolume`; annual crossing prevents candidate; corrected annual upper failure retained |
| 25–27: both arithmetic orders | `correct_schedule`; exact 10 vs 12 m³/s, distinct prebound values/conflicts |
| Unresolved priority | `CandidateStatus.INTERPRETED`; never a complete-source pass |
| Exact durations / partial annual coverage | leap February and March yield `(10*29+8*31)*86400` m³; annual total stays unavailable |
| Missing/unsupported/evidence identity | no order/coefficient, partial bound, warm-up and stale findings do not manufacture values |
| Independent evidence axes | scientific rejection stays separate from supported arithmetic |

All test numbers except attributed source coefficients are synthetic. These tests
establish software behavior, not calibrated ecological adequacy or legal priority.
