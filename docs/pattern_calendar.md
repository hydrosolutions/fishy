# Map and shift daily reference volumes

Use `fishy.pattern_calendar` to put complete daily volumes on a design-year
calendar. The operations use exact `Fraction` arithmetic. They do not select
analogue years, assess reference quality, or establish scientific acceptance.

## Map a non-leap February to a leap February

An `AccountingYear` starts on the first day of its configured month. Its `year`
is the calendar year in which it starts. Days are fixed 86,400-second intervals.
The UTC offset is in minutes and must lie between −840 and +840. `.dates` returns
local dates; `.interval` returns UTC-normalised bounds.

```python
from fractions import Fraction
from fishy.pattern_calendar import AccountingYear, map_calendar

source = AccountingYear(2023, 1, 0)
target = AccountingYear(2024, 1, 0)
volumes = tuple(Fraction(day == 31) for day in range(source.days))
mapped = map_calendar(source, volumes, target)

assert mapped[31:33] == (Fraction(28, 29), Fraction(1, 29))
assert sum(mapped, Fraction()) == 1
```

This example puts one unit of volume on February 1 and zero on every other day.
Mapping splits that volume across the first two target days. Each month's total
and the annual total stay unchanged. This is a calendar transformation, not new
observed daily detail. Source and target accounting years must start in the same
month. Every source day must have a nonnegative exact volume.

## Find a seasonal timing marker

`half_volume_marker(shares, start_day, end_day)` uses zero-based day offsets and
a half-open season: the start day is included and the end day is excluded.
It returns elapsed seconds from the accounting-year start. The first boundary
that attains half of seasonal volume wins on a plateau. A crossing inside a day
uses linear interpolation. A season with zero volume returns `None`.

For markers at days 100 and 104, the midpoint is day 102. Their alignment shifts
are +2 and −2 days. A season crossing the accounting-year boundary is not
supported by this marker operation; the pattern caller must use its documented
calendar fallback rather than take a linear median across the boundary.

## Shift without wrapping

```python
from fishy.pattern_calendar import shift_year, normalize_shares

result = shift_year(source, volumes, target, Fraction(86400))
assert result.shares is None
assert result.reason == "missing left adjacent-year context"
```

A positive shift delays the pattern and needs `left_volumes`, a complete raw
volume tuple for the preceding source accounting year. A negative shift needs
`right_volumes` for the following year. Supply these as keyword arguments.
Zero shift needs neither. Unknown edges are never wrapped or filled with zero.

Adjacent data is calendar-mapped to the preceding or following design year.
Both core and adjacent volumes are divided by the **original core year's total**.
Padding years are not independently normalised. Shifts that require context
beyond one adjacent year return an unsupported reason.

On success, `result.shares` contains retained volumes relative to that original
total. `result.introduced` and `result.displaced` record edge volumes on the same
scale. Shares are not yet normalised. Use `normalize_shares(result.shares)` on
**each** retained contribution before averaging years with equal weight.
Missing edges and zero retained totals return `shares=None` with a reason.
Malformed values and incomplete supplied years raise an error.

## Run the example and checks

```console
uv run python examples/calendar_mapping.py
uv run pytest tests/test_pattern_calendar.py tests/test_calendar_example.py
```

The example prints the February split, marker days 100/104, midpoint 102,
shifts +2/−2, and the missing-left-context reason. Its test runs the same `main`
entry point and compares the complete output.

## Numerical acceptance crosswalk

All numeric comparisons below are exact `Fraction` or integer equality: tolerance
is **zero**. These software witnesses do not accept a hydrological application.
The 25 parametrised cases in `tests/test_pattern_calendar.py` cover:

| Requirement | Public operation and test | Actual = expected |
|---|---|---|
| Fixed calendar | `AccountingYear`; `test_accounting_year_fixed_offset_and_dates` | October 2023 year: 366 days; UTC start 2023-09-30 18:30 for offset +330; local final date 2024-09-30 |
| Invalid calendar | `AccountingYear`; `test_invalid_calendars` (5 cases), `test_calendar_rejects_boolean_fields` | Invalid month, excessive offset and unsupported year raise `ValueError`; boolean field raises `TypeError` |
| D6 leap split | `map_calendar`; `test_d6_february_first_day_splits_exactly` | February shares 28/29 and 1/29; annual total 1 |
| D6 conservation | `map_calendar`; `test_every_month_and_annual_total_conserved` (3 cases) | Every mapped monthly total equals its source monthly total in both leap directions and an October-start calendar; annual total conserved |
| D13 completeness | `map_calendar`; `test_mapping_rejects_incomplete_or_incompatible_calendar` | Short tuple and different start months raise `ValueError` |
| D7 timing | `half_volume_marker`; `test_d7_markers_and_median_shift` | Days 100/104; midpoint 102; shifts +2/−2 |
| D7 plateau | `half_volume_marker`; `test_marker_first_plateau_boundary_fractional_day_and_absent_volume` | Plateau marker day 1; fractional marker day 5/3; zero season `None`; crossing season refused |
| D8 missing edge | `shift_year`; `test_d8_unknown_edges_never_wrap_or_zero_fill` (2 cases) | ±1 second without context yields no shares and names left/right missing context |
| Fractional overlap and scale | `shift_year`; `test_fractional_overlap_and_original_source_scaling` (2 cases) | ±1/2 day, core daily volume 1, padding daily volume 2: edge share 3/730; introduced 1/365; displaced 1/730 |
| Adjacent mapping | `shift_year`; `test_adjacent_year_is_calendar_mapped_before_translation` | Leap mapping before a 334-day shift introduces exactly 2/29, displaces 0 |
| No shift | `shift_year`; `test_zero_shift_needs_no_context` | 365 shares of 1/365; both edge accounts 0 |
| D13 zero retained | `shift_year`; `test_zero_retained_total_is_unsupported` | No shares; reason `zero retained design-interval volume` |
| Context extent | `shift_year`; `test_shift_beyond_available_context_is_unsupported` | No shares; reason `shift requires context beyond the adjacent year` |
| Context completeness | `shift_year`; `test_incomplete_adjacent_context_is_not_accepted` | Incomplete supplied padding raises `ValueError` |
| D9 equal-year weights | `normalize_shares`; `test_d9_individual_renormalisation_before_averaging` | Mean shares 5/8, 1/8, 1/8, 1/8 after separate normalisation |
| D10/D13 zero and negative | `normalize_shares`, `shift_year`; `test_zero_and_negative_values_refused` | Zero normalisation and negative volumes refused; zero source shift returns explicit unsupported reason |

## Source attribution

These operators implement the proposed Uzbek construction, not a Kazakh
statutory algorithm or a WMO-prescribed pattern. The governing package is
`fishy_taqsim_handover_candidate_2026-09-19`. This page describes derived
implementation behavior; the private source documents are not distributed here.

| Source and section | SHA-256 | Implemented scope |
|---|---|---|
| `report_snapshot/part4_design_patterns.qmd`, D.6, “Build a mean-one daily shape without losing annual accounting” | `b95f62ed797f174df926462a154834077126dfd65e995f445b608ef1426ba56e` | Month-overlap mapping, first half-volume crossing, physical translation, adjacent scale and individual normalisation |
| `evidence/design_pattern_acceptance.md`, D6–D9 and supplemental deterministic checks | `43a88113eb2a9619817b7bcac7c157048bde035d7157ce2c08917eaf16dc63a7` | Exact leap, timing, missing-edge and weighting witnesses |

Selection, iterative simultaneous exclusions, median recomputation, support
criteria and scientific-use decisions belong to pattern construction, not these
calendar primitives. The short plateau and weighting arrays test algebra;
calendar mapping and translation require complete real accounting years.
