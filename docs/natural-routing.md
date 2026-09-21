# Natural route selection and entry floors

`select_natural_route` uses prepared origin/designation decisions from `spatial`.
Potential reaches bypass the natural ladder. An unknown category does not disable
independent hydrological sizing. Existing duties are not changed.

Supply a versioned `TierEvidence` inventory. Each required statistic names its
exact `HydrologicalProduct` and `ScientificAssessment`; missing required IDs remain
unknown. Baseline and top tiers also require the five accepted natural `DailyPattern` products
at .50/.75/.90/.97/.99, the accepted scalar `RecordedMinimum`, and a separate
`reconstruction_disclosure` prerequisite. Bind the latter with
`reconstruction_disclosure_scope(reference)` and complete disclosure findings for
that exact reference, member, scenario, period and sizing use. A smaller caller inventory cannot waive
these operands. Every natural pattern uses the same exact reference and intended-use scope.
Patterns already bind their annual acceptance; no duplicate annual
review is required. Supported indicative statistics can select a tier. Rating restrictions,
unsupported daily equivalence and failed scientific criteria still prevent use.
Top-tier habitat/holistic inputs reuse `assess_natural_study`, without a baseline median cap.
They add to—not replace—the full hydrological inputs. The delivered study vocabulary
uses `sizing` (or `obligation sizing`) for its intended-use scope; screening-only
study evidence cannot select the sizing tier.

The result reports both the highest data-supported tier and the highest eligible
tier. Missing resources and an absent top-tier priority/trigger remain separate.
Record a `RouteFailure` after an intrinsic route failure and call again. That route
cannot select itself again. Assessed transfer and presumptive results are next;
their retained inputs are rechecked. Without a supported result, selection is pending.
No number means neither zero nor permission to remove an existing duty.

## Graduated entry

Run `uv run python -m examples.graduated_entry` for a supported hypothetical
floor and a missing-screen result. The illustrative input 10 m³/s gives 8 m³/s.
These are explicit scenario coefficients, not an adopted table.

`select_entry_variant(None, applicability, adequacy)` records the current domestic
variant as unavailable. Availability is checked first, then source applicability,
then statistic adequacy. Failed adequacy goes to fallback, not another estimator.
The independent sanitary scenario estimator does not enable ecological entry.

`evaluate_graduated_entry` accepts a daily-frequency low-flow statistic with exact
scientific acceptance, a continuous concave `GraduatedCurve`, and a
`LargeRiverScreen`. The screen reproducibly refuses when all three configured
conditions hold: input is at least its threshold, marginal rate is no greater than
its limit, and retained share is no greater than its limit. The caller supplies
its sensitivity evidence and adoption or hypothetical basis. No cutoff is built in.

Curve arithmetic uses exact fractions. Junction continuity and concavity are
checked before evaluation. The unrounded result is retained. A candidate greater
than or equal to its input refuses the route; it is not capped. A missing screen
retains the exploratory candidate but supplies no floor. The literal Swiss table
in `residual_flow` remains independent, including its published jumps.

Entry supplies a **base floor only**. Active local quality must be applied during
later composition. It does not create a seasonal requirement or delivery obligation.

## Source and executed-test crosswalk

Derived from the owner-selected September 19, 2026 handover: Appendix A steps 5–7,
`sec-recipe-fork`, `sec-recipe-step6`, `sec-recipe-step7`; scientific acceptance D.8;
assembly D.10 route-failure sequence; ACCEPTANCE entry supplements and U4/U6.
The private chapters are not distributed here. The method is proposed, not adopted
Uzbek policy or certified basin science. Short records alone neither validate nor
reject a statistic.

| Source requirement | Public input/operation | Observable result | Test |
|---|---|---|---|
| Ordered tiers, indicative permission | `TierEvidence`, `select_natural_route` | selected and highest-data tier, separate restrictions | `test_natural_routing.py` |
| Natural/potential fork | prepared classification | no natural tier on potential/unknown track | `test_potential_and_undetermined_bypass_natural_ladder_and_unknown_category_does_not` |
| Existing study reuse and no median cap | supplied `NaturalStudyComponent` | supported 8 m³/s study, retained failures | `test_study_recomputed_and_preserves_supported_pulse_above_baseline_cap` |
| Ordered domestic availability/scope/adequacy | `select_entry_variant` | graduated versus fallback, not result shopping | `test_current_domestic_unavailable_and_ordered_branches_never_shop_on_adequacy_failure` |
| Continuous concave curve | explicit segments | exact junction 8 and unrounded 8.0000002 | `test_continuity_concavity_junction_equality_and_unrounded_values` |
| Floor >= input refusal | evaluated scalar | no capped floor | `test_floor_equal_or_greater_than_input_refuses_without_cap` |
| Large-river screen and absence | configured screen | 99 passes, 100 refuses; missing stays unknown | `test_large_river_exact_screen_and_missing_screen_retained` |
| Exact scientific subject | low-flow product plus assessment | changed value/reference/probability cannot inherit permission | `test_changed_exact_statistic_does_not_inherit_acceptance` |
| Daily and rating support | supplied evidence | unsupported disaggregation/rating cannot size | `test_rating_and_unsupported_daily_disaggregation_cannot_size` |
| Source isolation | independent Swiss operator | literal 500 l/s -> 280 l/s; same jumps refused as Uzbek | `test_literal_swiss_jumps_remain_independent_and_refused_as_uzbek_curve` |

Run `uv run pytest tests/test_graduated_entry.py tests/test_natural_routing.py`.
This executes public calculations and negative paths. It does not establish site
adequacy or official admissibility. Full-year baseline and transfer examples and
checks are documented separately in `natural-baseline.md` and `ecological-transfer.md`.
