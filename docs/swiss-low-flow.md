# Swiss Q347 and the statutory starting minimum

Run `uv run python examples/swiss_low_flow.py`. The synthetic example prints
Q347 160 l/s and starting minimum 130 l/s. Neither is an intake prescription.
These operations need no Taqsim, HYDMOD, permit decision or Uzbek configuration.
Import public operations from `fishy.low_flow` and `fishy.residual_flow`.

## Calculate or import Q347

`pooled_q347(samples, conventions, provenance, status, uncertainty=None)` consumes
existing `FlowSample` records at one location and reference identity. Supply
`Q347Conventions(record_selection, DailyBasis.DAILY_OBSERVATIONS)` or the
supported reconstructed-daily basis. The caller selects the reference record and
records why it represents the requested use. Raw coarse means repeated across
calendar days are refused. A declared daily basis is input evidence, not proof of
validation; reconstructed records still need the scoped scientific review.

The implemented convention pools complete selected calendar years, uses UTC
Gregorian days including leap days, and refuses gaps, overlaps, partial days,
unsupported values and excluded warm-up intervals. It sorts exact flows in
descending order and evaluates the one-based rank `347 * number_of_years`.
The interpolation convention is linear between ranks; complete years make this
rank integral. Thus ten years give rank 3470, including in a 3653-day population.
This is a declared empirical convention, not a source-prescribed interpolation
algorithm. It does not replace 347 days with the Guide's rounded 95% shorthand.
It never averages independently calculated annual Q347 values.

Records shorter or longer than ten years remain numerically calculable. The
statutory target is the ten-year meaning, not automatic scientific acceptance of
any supplied historical period. Guide chapter 7 recommends the whole available
record without significant trend and the latest ten years with trend; specialist
selection and trend/representativeness findings must support that choice. Fishy
does not invent a trend test, correction factor or naturalisation model.

`imported_q347` accepts a supported observation/model estimate under Art. 59.
Supply its exact flow, physical location, reference period, provenance, method,
preliminary/final-submission status and any supported uncertainty bounds.
This route does not fabricate daily observations. Numerical availability,
scientific adequacy and official admissibility remain separate.

`assess_q347(estimate, review, scope)` returns a `CheckSummary`. Its `Q347Review`
consumes exact scoped `EvidenceFindings`, human-influence, representativeness and
trend checks, and a conditional verification decision. Keep the estimate and
review alongside the summary for all provenance, uncertainty and authority facts.
Use `scope.intended_use="final Q347 determination"` for final determination;
other named uses support scoped indicative scenarios. Final use requires a
final-submission estimate, accepted (not merely indicative) scientific findings,
and supported verification. No operation grants official admission.

The Guide's little/no-uplift condition is supplied as `VerificationRoute.REQUIRED`;
a passed verification then needs at least three calendar measurement years.
`JUSTIFIED_EXCEPTION` and `NOT_APPLICABLE` need a passed supplied decision and
explicit rationale, not a fabricated duration. An unresolved applicability stays
unknown. A known required failure survives other unknown checks. The guidance
version is fixed and retained. Preliminary scenarios cannot pass final use.

## Literal Art. 31(1)

`statutory_minimum(Flow(...))` returns an exact `Flow`; all units normalise to m³/s.
`attributed_starting_minimum(estimate)` retains the whole Q347 estimate and table
source. The table retains the 279.6→280 and 2497.5→2500 l/s jumps. It is neither
smoothed nor capped at Q347. Zero gives the raw table value 50 l/s, but fails the
separate numerical permanent-flow test. Any positive Q347 passes that numerical
test; the older Guide's pragmatic 10 l/s convention is not applied.
Safeguards, exceptions, balancing, applicability and delivery are separate stages.

## Sources and executable crosswalk

Sources are the German [GSchG consolidation, 2025-08-01](https://www.fedlex.admin.ch/eli/cc/1992/1860_1860_1860/de)
and [FOEN Wegleitung 2000](https://www.bafu.admin.ch/dam/de/sd-web/DURPl8AmZvgE/angemessene_restwassermengenwiekoennensiebestimmtwerdenwegleitun.pdf),
chapter 7, printed pp. 82–86. The guide supports the Act, not overrides it.
No private source extracts or project observations are distributed.

All tests below are in `tests/test_low_flow.py`; tolerance is zero (exact fractions).

| Requirement / source | Public operation | Executed witness and expected result |
| --- | --- | --- |
| Art.4(h), Guide pp.84–86 pooled distribution | `pooled_q347` | `test_pooled_not_mean_annual_and_short_accepted`: pooled1 versus annual mean50.5 l/s |
| Art.4(h) ten-year meaning and calendar | `pooled_q347` | `test_ten_year_meaning_and_leap_days`: 3653 days, rank3470,184 l/s |
| No coarse-data promotion; missing conventions | `pooled_q347` | `test_daily_support_rejects_gaps_coarse_and_false_identity`: all invalid paths refused |
| Art.59 estimates; preliminary evidence | `imported_q347`, `assess_q347` | `test_import_attribution_and_preliminary_scenario_not_final`: scenario pass, final unknown,160→130 |
| Guide pp.82,85–86 acceptance and conditional verification | `assess_q347` | `test_conditional_verification`: three years pass; missing/two years unknown; justified exception pass |
| Influence, trend and scoped adequacy | `assess_q347` | `test_failure_survives_missing_and_scoped_official_separation`: failure plus incomplete; different scope unknown |
| Art.31(1) every anchor ±0.001 l/s; both jumps | `statutory_minimum` | `test_literal_table`: exact published values in parameter table |
| Art.4(i), uncapped low end | `permanent_flow`, `statutory_minimum` | `test_zero_small_positive_and_uncapped`: zero fails,0.001 l/s passes,1→50 |
| Invalid quantities | `Flow`, `statutory_minimum` | `test_invalid_amount`: negative and nonfinite values refused |

Tests verify software and synthetic supplied decisions, not scientific or legal certification.
