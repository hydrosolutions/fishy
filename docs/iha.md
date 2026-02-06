# IHA Module

Compute the 33 Indicators of Hydrological Alteration (Richter et al., 1996) from daily flow timeseries. Pure NumPy. No pandas dependency.

## Design Philosophy

- **Single-series input**: Takes one flow array + dates. Comparison between natural and altered regimes is the caller's responsibility.
- **Calendar year slicing**: Only complete calendar years (365 or 366 days) are processed. Partial years at the start/end of the record are silently dropped.
- **Fail-fast validation**: All input errors are caught before computation begins with specific, typed exceptions.
- **Numba-ready internals**: All group functions operate on raw numpy arrays with no Python objects. `@njit` decorators can be added without refactoring.
- **Immutable output**: `IHAResult` is a frozen dataclass wrapping an `(n_years, 33)` matrix.

## API

### `compute_iha`

```python
from fishy.iha import compute_iha, PulseThresholds

result = compute_iha(
    q,                                    # NDArray[float64] — daily flows
    dates,                                # NDArray[datetime64[D]] — daily dates, same length as q
    *,
    zero_flow_threshold=0.001,            # flows below this count as zero-flow days
    pulse_thresholds=None,                # PulseThresholds | None — if None, derived as Q25/Q75 of full record
    min_years=1,                          # minimum complete calendar years required
) -> IHAResult
```

**Raises** (all subclass `IHAError`):

| Exception | Condition |
|-----------|-----------|
| `DateFlowLengthMismatchError` | `len(q) != len(dates)` |
| `NegativeFlowError` | Any `q < 0` |
| `NonDailyTimestepError` | Gap != 1 day between consecutive dates |
| `InsufficientDataError` | Fewer than `min_years` complete calendar years |
| `ValueError` | `pulse_thresholds is None` and Q25 == Q75 (constant flow) |

### `pulse_thresholds_from_record`

```python
from fishy.iha import pulse_thresholds_from_record

thresholds = pulse_thresholds_from_record(q)  # PulseThresholds(low=Q25, high=Q75)
```

Derives Group 4 thresholds from the 25th/75th percentiles of the full record. Raises `ValueError` if Q25 >= Q75.

### `IHAResult`

```python
result.values                # NDArray[float64], shape (n_years, 33)
result.years                 # NDArray[intp], shape (n_years,)
result.zero_flow_threshold   # float
result.pulse_thresholds      # PulseThresholds | None

result.group(g)              # g in [1,5] → NDArray, shape (n_years, n_params_in_group)
result.param(col)            # col in [0,32] → NDArray, shape (n_years,)
result.year_row(year)        # year as int → NDArray, shape (33,)
```

### `Col` — Column Index Namespace

Access specific parameters by name:

```python
from fishy.iha import Col

result.param(Col.BASE_FLOW_INDEX)   # BFI for each year
result.param(Col.REVERSALS)         # reversal count for each year
result.values[:, Col.JAN]           # January mean for each year
```

Group slicing:

```python
Col.GROUPS[0]   # slice(0, 12)  — Group 1
Col.GROUPS[1]   # slice(12, 24) — Group 2
Col.GROUPS[2]   # slice(24, 26) — Group 3
Col.GROUPS[3]   # slice(26, 30) — Group 4
Col.GROUPS[4]   # slice(30, 33) — Group 5
```

### `PulseThresholds`

```python
from fishy.iha import PulseThresholds

pt = PulseThresholds(low=5.0, high=25.0)  # frozen dataclass
# Validates: low >= 0, high >= 0, low < high
```

## The 33 Parameters

### Group 1 — Monthly Flow Magnitude (12 parameters)

Mean daily flow for each calendar month.

| Col | Name | Index |
|-----|------|-------|
| `JAN` | January mean | 0 |
| `FEB` | February mean | 1 |
| `MAR` | March mean | 2 |
| `APR` | April mean | 3 |
| `MAY` | May mean | 4 |
| `JUN` | June mean | 5 |
| `JUL` | July mean | 6 |
| `AUG` | August mean | 7 |
| `SEP` | September mean | 8 |
| `OCT` | October mean | 9 |
| `NOV` | November mean | 10 |
| `DEC` | December mean | 11 |

### Group 2 — Extreme Flow Magnitude and Duration (12 parameters)

Rolling-mean extremes over 5 window sizes, plus zero-flow days and baseflow index.

| Col | Name | Formula | Index |
|-----|------|---------|-------|
| `MIN_1DAY` | 1-day minimum | `min(q)` | 12 |
| `MIN_3DAY` | 3-day minimum | `min(rolling_mean(q, 3))` | 13 |
| `MIN_7DAY` | 7-day minimum | `min(rolling_mean(q, 7))` | 14 |
| `MIN_30DAY` | 30-day minimum | `min(rolling_mean(q, 30))` | 15 |
| `MIN_90DAY` | 90-day minimum | `min(rolling_mean(q, 90))` | 16 |
| `MAX_1DAY` | 1-day maximum | `max(q)` | 17 |
| `MAX_3DAY` | 3-day maximum | `max(rolling_mean(q, 3))` | 18 |
| `MAX_7DAY` | 7-day maximum | `max(rolling_mean(q, 7))` | 19 |
| `MAX_30DAY` | 30-day maximum | `max(rolling_mean(q, 30))` | 20 |
| `MAX_90DAY` | 90-day maximum | `max(rolling_mean(q, 90))` | 21 |
| `ZERO_FLOW_DAYS` | Zero-flow count | `sum(q < threshold)` | 22 |
| `BASE_FLOW_INDEX` | Baseflow index | `min(7-day MA) / mean(q)` | 23 |

BFI is `NaN` when `mean(q) ≈ 0`. Range: `[0, 1]` for non-negative flows.

### Group 3 — Timing of Extremes (2 parameters)

| Col | Name | Formula | Index |
|-----|------|---------|-------|
| `DATE_OF_MIN` | Day of annual minimum | `day_of_year[argmin(q)]` | 24 |
| `DATE_OF_MAX` | Day of annual maximum | `day_of_year[argmax(q)]` | 25 |

Day-of-year is 1-indexed (Jan 1 = 1, Dec 31 = 365 or 366). Linear, not circular.

### Group 4 — Frequency and Duration of Pulses (4 parameters)

| Col | Name | Formula | Index |
|-----|------|---------|-------|
| `LOW_PULSE_COUNT` | Low pulse count | Number of runs where `q < low_thresh` | 26 |
| `LOW_PULSE_DURATION` | Low pulse mean duration | Mean length of low runs (0 if no pulses) | 27 |
| `HIGH_PULSE_COUNT` | High pulse count | Number of runs where `q > high_thresh` | 28 |
| `HIGH_PULSE_DURATION` | High pulse mean duration | Mean length of high runs (0 if no pulses) | 29 |

Default thresholds when `pulse_thresholds=None`: Q25 and Q75 of the full record.

### Group 5 — Rate and Frequency of Change (3 parameters)

| Col | Name | Formula | Index |
|-----|------|---------|-------|
| `RISE_RATE` | Rise rate | `median(diff[diff > 0])` | 30 |
| `FALL_RATE` | Fall rate | `median(diff[diff < 0])` | 31 |
| `REVERSALS` | Number of reversals | `sum(diff(signbit(diff(q))))` | 32 |

- Rise/fall use **strict** inequality — zero-change days are excluded from both.
- Fall rate preserves the **negative sign**.
- Both are 0.0 when no positive (or negative) changes exist.

## Deviations from sarawater

This implementation uses [sarawater](https://github.com/hydrosolutions/sarawater) as the authoritative reference, with the following documented corrections:

| Aspect | sarawater | fishy | Rationale |
|--------|-----------|-------|-----------|
| Group 2 BFI | `mean(q)` stored as "base_flow" | `min(7-day MA) / mean(q)` | Correct IHA definition (Richter 1996) |
| Group 4 thresholds | Per-year percentiles of Qnat | Full-record Q25/Q75 or external | Single-series design; caller controls thresholds |
| Group 4 duration | `median` of run lengths | `mean` of run lengths | Richter 1996 specifies mean |
| Group 5 rise/fall | `>= 0` / `<= 0` (includes zeros) | `> 0` / `< 0` (strict) | Specification says "positive"/"negative" changes |
| Date handling | Python datetime + pandas | `np.datetime64[D]` vectorized | Performance |
| Output format | Nested dict of arrays | Frozen dataclass + (n_years, 33) matrix | Structured, indexable |

## Module Structure

```
src/fishy/iha/
    __init__.py     # Public API: compute_iha, Col, IHAResult, PulseThresholds, errors
    types.py        # Col, IHAResult, PulseThresholds, ZERO_FLOW_THRESHOLD
    errors.py       # IHAError hierarchy (5 exception types)
    compute.py      # compute_iha(), pulse_thresholds_from_record()
    _groups.py      # compute_group1..5() — per-group numpy functions
    _util.py        # rolling_mean, run_lengths, date extraction helpers
```

Internal modules (`_groups.py`, `_util.py`) are not part of the public API.

## Error Hierarchy

```
IHAError (Exception)
├── InsufficientDataError    — too few complete calendar years
├── DateFlowLengthMismatchError — len(q) != len(dates)
├── NonDailyTimestepError    — gap in daily dates
└── NegativeFlowError        — q contains negative values
```

All are dataclasses with structured fields for programmatic access:

```python
from fishy.iha import InsufficientDataError

try:
    result = compute_iha(q, dates, min_years=10)
except InsufficientDataError as e:
    print(e.n_years)    # how many years were found
    print(e.min_years)  # how many were required
```
