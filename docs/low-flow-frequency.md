# Supplied low-flow recurrence

`fishy.low_flow_frequency.LowFlowReturnPeriod` represents a finite return period
in years, strictly greater than one. Its exact probabilities are:

- `nonexceedance_probability = 1 / years`;
- `exceedance_probability = 1 - nonexceedance_probability`.

These probabilities describe a **declared annual or seasonal duration-minimum
population**. They are not daily flow-duration probabilities. A ten-year return
period does not schedule a drought every tenth year or grant permission to breach
a requirement.

```python
from fractions import Fraction
from fishy.low_flow_frequency import LowFlowReturnPeriod

recurrence = LowFlowReturnPeriod(10)
assert recurrence.nonexceedance_probability == Fraction(1, 10)
print(recurrence.exceedance_probability)  # 9/10
```

For an executable supplied-product example:

```sh
uv run python examples/supplied_low_flow_frequency.py
```

The example attributes a supplied seven-day minimum estimate of 2 m³/s to a
ten-year recurrence. It does not construct the minimum population or fit that
estimate.

## Bind a supplied product

Append `low_flow_return_period=recurrence` to a scientific `HydrologicalProduct`.
The product must declare:

- kind `HydrologicalProductKind.DURATION_MINIMUM`;
- positive `duration_days`;
- annual statistical resolution: one annual or selected seasonal minimum per
  accounting year, not a daily exceedance distribution;
- population attribution naming the selected annual or seasonal minimum domain;
- `target_probability=recurrence.exceedance_probability`.

The typed kind, duration and statistical resolution carry the enforceable
meaning. Fishy does not guess scientific semantics by parsing arbitrary labels.
Changing recurrence, duration or population changes the scientific product.
A previously accepted product cannot supply acceptance for that changed product.

A probability disagreement is refused, with no clamping or silent overwrite.
Return-period inputs use the same exact decimal-display convention as Fishy's
physical quantities. Float `.9` agrees with Tr10; a rounded float approximation
to `2/3` does not agree exactly with Tr3. Pass the exact derived `Fraction` property
for nonterminating probabilities. The optional field is appended, so existing
positional product constructors remain compatible. Independently declared
minimum probabilities still work without a return-period record.

Mathematical consistency does not establish scientific adequacy or official
permission. Supply the product's frozen acceptance record and evidence to
`assess_scientific_use`; missing review evidence remains missing. Native annual
means and daily-pattern products cannot be relabelled through this field.

Duration-minimum population/window construction, fitted minimum estimators,
multi-day safeguards and downstream assembly remain outside this operation.
Those implementation responsibilities belong to Taqsim Effort #31. This operation
only converts recurrence probabilities and checks supplied-product consistency.

## Source and executed crosswalk

Effort: https://github.com/hydrosolutions/taqsim/issues/29

The controlling source is the owner-selected private
`fishy_taqsim_handover_candidate_2026-09-19`, D.7
`report_snapshot/part4_statistical_estimation.qmd`, rule 2,
SHA-256 `10bb9e8feaaab5199575d1dbf0c2fd2a50c5867b5a55a92806294853c821a5df`.
Rule 1 separates annual means from annual/seasonal minima; rule 2 specifies
`u=1/Tr`, `Tr>1`. WMO 1029 §7.7 supports this interpretation; the supplied labelled
USGS summary (SHA-256
`55eea73d9dea805d7b2119797e37f999f76bdf605c43cda8ad74fb94de9589db`) explains why
recurrence is not a fixed schedule. No private report or reference is copied here.

All tests below use the real public primitive or scientific product/assessment
path in `tests/test_low_flow_frequency.py`. Exact means rational equality, not an
application acceptance tolerance. All supplied study values are synthetic.

| Contract | Actual = expected | Test |
|---|---|---|
| Tr2 / Tr10 | u=1/2, P=1/2 / u=1/10, P=9/10; exact | `test_exact_lower_tail_conversion` |
| Tr3 / Tr2.5 | u=1/3, P=2/3 / u=2/5, P=3/5; exact | same conversion test |
| Tr<=1/nonfinite/boolean | refused | `test_invalid_return_period_is_refused` |
| Consistent supplied minimum | Tr10 and P=.9 retained; exact | `test_product_requires_exact_probability_and_retains_return_period` |
| Mismatch or missing P | refused; no inferred replacement | same product test |
| Annual magnitude/daily/other kind | return-period relabelling refused | `test_return_period_cannot_relabel_other_populations` |
| Missing/invalid duration or population, daily statistical resolution | refused | `test_minimum_duration_population_and_annual_statistical_resolution_required` |
| Supplied minimum scientific use | supported indicative PASS; missing validation NOT_ACCEPTED | `test_actual_scientific_assessment_supports_supplied_minimum_without_constructing_it` |
| Changed Tr/duration/population | old acceptance cannot transfer | `test_acceptance_does_not_transfer_to_changed_recurrence_duration_or_population` |
| Existing probability-only minimum | remains independently usable | `test_existing_probability_only_supplied_minimum_remains_compatible` |
| Tr10^30 | exact 1-P=1/10^30, not rounded to zero | `test_exact_large_return_period_does_not_round_exceedance_to_one` |

Base Fishy revision: `f7d2179b03a7c16efad490da1a2aec92f4ede74d`.
Dependencies are unchanged in `uv.lock`: Python 3.13.8, Polars 1.44.2,
pytest 9.0.2, Ruff 0.15.0, ty 0.0.66. Optional integration pins remain
Taqsim `396ad093c2b6f240e702a3b05aee1fb96a69b3f7` and Incidence
`665da4e0d81ab28921b8d5d2edbb9be27f4ec612`.
