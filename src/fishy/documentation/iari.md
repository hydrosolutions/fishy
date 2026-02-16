# IARI Module

Compute the Index of Hydrological Regime Alteration (Greco et al., 2021) -- a continuous deviation score comparing impacted flow regimes against IQR bands derived from the natural record, suitable for use as an optimization objective.

## Design Philosophy

- **Continuous score for optimization**: Produces a float deviation that can drive taqsim's multi-objective optimizer, unlike categorical methods that lose gradient information.
- **All 33 IHA parameters**: Scores every IHA parameter against natural IQR bands, giving equal weight to magnitude, timing, frequency, duration, and rate of change.
- **IQR-band scoring**: Natural variability is captured as the interquartile range (Q25--Q75) of each parameter across years. Impacted values inside the band score 0; values outside are penalised proportionally.
- **Skip-and-collect evaluation**: `evaluate_iari` processes multiple Reach nodes independently, returning partial results if some Reach nodes fail.
- **Immutable output**: `IARIResult` is a frozen dataclass with full audit trail.

## Quick Start

```python
import numpy as np
from fishy.iha import compute_iha, pulse_thresholds_from_record
from fishy.iari import compute_iari

# Compute IHA for both series (using same pulse thresholds from natural record)
thresholds = pulse_thresholds_from_record(natural_q)

natural_iha = compute_iha(natural_q, natural_dates, pulse_thresholds=thresholds)
impacted_iha = compute_iha(impacted_q, impacted_dates, pulse_thresholds=thresholds)

# Compute IARI
result = compute_iari(natural_iha, impacted_iha)
print(result.summary())
```

Using IARI as an optimization objective:

```python
from fishy.iari import iari_objective, bands_from_iha

bands = bands_from_iha(natural_iha)
objective = iari_objective(bands, reach_id="downstream")
```

## Core Concepts

### The Deviation Formula

Per-parameter deviation (Greco et al., 2021, Eq. 1):

```
p_i = 0                                            if Q25 <= X_i <= Q75
p_i = min(|X_i - Q25|, |X_i - Q75|) / (Q75 - Q25) otherwise
```

Where `X_i` is the impacted value and `[Q25, Q75]` is the interquartile range from the natural record.

### Aggregation

1. **Per year**: Mean of all 33 parameter deviations for that year.
2. **Overall**: Mean of the per-year scores across all impacted years.

### Classification

| Overall IARI | Classification |
|-------------|----------------|
| <= 0.05 | Excellent |
| <= 0.15 | Good |
| > 0.15 | Poor |

### Natural Bands

The IQR bands are computed from the natural IHA record:

- **Q25**: 25th percentile of each parameter across natural years.
- **Q75**: 75th percentile of each parameter across natural years.
- **Degenerate bands** (IQR = 0): If the impacted value matches the natural value exactly, deviation is 0. Any mismatch yields a deviation of 1.0.

## API

### `compute_iari`

```python
from fishy.iari import compute_iari

result = compute_iari(
    natural,                                  # IHAResult -- un-impacted
    impacted,                                 # IHAResult -- impacted
    *,
    min_years=1,                              # minimum years per series
) -> IARIResult
```

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `IncompatibleIHAResultsError` | IHA results don't have 33 parameters |
| `InsufficientYearsError` | Either series has fewer than `min_years` years |

### `evaluate_iari`

```python
from fishy.iari import evaluate_iari

results = evaluate_iari(
    natural,                                  # WaterSystem -- simulated natural
    impacted,                                 # WaterSystem -- simulated impacted
    *,
    reach_ids=None,                           # Sequence[str] | None -- defaults to shared natural Reach nodes
    zero_flow_threshold=0.001,
    min_years=1,
) -> dict[str, IARIResult]
```

Per-Reach pipeline: extracts flows, derives pulse thresholds from natural record, computes IHA for both series using the same thresholds, then computes IARI.

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `NonDailyFrequencyError` | Either system is not daily |
| `MissingStartDateError` | Either system has no `start_date` |
| `NoCommonReachesError` | No shared natural Reach nodes found |
| `ReachEvaluationError` | ALL Reach nodes failed (partial results returned otherwise) |

### `iari_objective`

```python
from fishy.iari import iari_objective

objective = iari_objective(
    bands,                                    # NaturalBands -- pre-computed from natural record
    reach_id,                                 # str -- Reach node to evaluate
    *,
    zero_flow_threshold=0.001,
    min_years=1,
    priority=1,                               # objective priority for optimizer
) -> Objective
```

Builds a taqsim `Objective` that evaluates IARI at a single Reach. The `bands` argument is frozen and picklable, so the objective can be serialized for parallel optimization.

### `bands_from_iha`

```python
from fishy.iari import bands_from_iha

bands = bands_from_iha(
    natural,                                  # IHAResult -- must have pulse_thresholds
) -> NaturalBands
```

Derives IQR bands from a natural IHA record. The returned `NaturalBands` carries the pulse thresholds so they can be reused when computing IHA for the impacted series.

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `ValueError` | `natural.pulse_thresholds` is None |

## Result Types

### `NaturalBands`

```python
bands.q25                  # NDArray[np.float64] -- shape (33,), 25th percentile
bands.q75                  # NDArray[np.float64] -- shape (33,), 75th percentile
bands.pulse_thresholds     # PulseThresholds -- from the natural record
bands.width                # NDArray[np.float64] -- IQR width per parameter
bands.degenerate_mask      # NDArray[np.bool_] -- True where IQR == 0
```

### `IARIResult`

```python
result.deviations          # NDArray[np.float64] -- shape (n_years, 33)
result.years               # NDArray[np.intp] -- year labels
result.per_year            # NDArray[np.float64] -- mean deviation per year
result.overall             # float -- grand mean IARI score
result.classification      # str -- "Excellent", "Good", or "Poor"
result.bands               # NaturalBands -- the bands used for scoring
result.degenerate_params   # frozenset[int] -- column indices where IQR == 0
result.natural_years       # int -- number of years in natural record
result.impacted_years      # int -- number of years in impacted record

result.year_row(2022)      # NDArray[np.float64] -- all 33 deviations for a year
result.param_deviation(5)  # NDArray[np.float64] -- deviation for one param across years
result.summary()           # str -- human-readable table
```

## Error Handling

All IARI errors inherit from `IARIError`. Bridge errors inherit from `IHAError`.

```python
from fishy.iari import (
    IARIError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonReachesError,
    ReachEvaluationError,
)
from fishy.iha import (
    MissingStartDateError,
    NonDailyFrequencyError,
    ReachNotFoundError,
    NotAReachError,
    EmptyReachTraceError,
)
```

## IARI vs DHRAM

| | IARI | DHRAM |
|---|------|-------|
| **Output** | Continuous float (>= 0) | Categorical class 1--5 |
| **Use case** | Optimization objective | Impact reporting |
| **Scoring** | IQR-band deviation per parameter | Percent-change thresholds per IHA group |
| **Gradient** | Smooth -- suitable for minimization | Stepped -- loses information at class boundaries |
| **Parameters** | All 33 IHA parameters | 31 (excludes zero-flow days and BFI) |
| **Classification** | 3-level (Excellent/Good/Poor) | 5-level (High to Bad, WFD-compatible) |

**When to use IARI**: As a competitive environmental objective in taqsim multi-objective optimization, where the optimizer needs a continuous signal to minimize hydrological alteration.

**When to use DHRAM**: For regulatory impact assessment and reporting, where a WFD-compatible ecological status class is required.

## Use with taqsim Optimization

Full workflow: build system, simulate natural baseline, derive bands, attach IARI as an objective alongside operational objectives.

```python
from datetime import date
from taqsim.testing import make_source, make_storage, make_sink, make_edge, make_system
from taqsim.time import Frequency
from fishy import naturalize, NATURAL_TAG
from fishy.iha import compute_iha, pulse_thresholds_from_record, iha_from_reach
from fishy.iari import bands_from_iha, iari_objective, evaluate_iari

# 1. Build and simulate the impacted system
impacted = make_system(
    make_source("river", n_steps=1095),
    make_storage("dam"),
    make_sink("downstream"),
    make_edge("inflow", "river", "dam", tags=frozenset({NATURAL_TAG})),
    make_edge("release", "dam", "downstream", tags=frozenset({NATURAL_TAG})),
    frequency=Frequency.DAILY,
    start_date=date(2020, 1, 1),
)
impacted.simulate(1095)

# 2. Naturalize and simulate
natural_result = naturalize(impacted)
natural = natural_result.system
natural.simulate(1095)

# 3. Derive natural bands for the target Reach
natural_iha = iha_from_reach(natural, "downstream")
bands = bands_from_iha(natural_iha)

# 4. Create IARI objective for the optimizer
env_objective = iari_objective(bands, "downstream", priority=2)

# 5. Evaluate current IARI across all Reaches
results = evaluate_iari(natural, impacted)
for reach_id, iari in results.items():
    print(f"{reach_id}: {iari.overall:.4f} ({iari.classification})")
    print(iari.summary())
```

## Integration Pipeline

```
WaterSystem (impacted) --simulate--> flow traces (impacted)
         |                                     |
         +-- naturalize() -> simulate --> flow traces (natural)
                                               |
         For each shared natural Reach:         |
           natural IHA -> IQR bands (Q25/Q75) -+
           impacted IHA values vs bands -------+
           per-param deviation -> mean/year -> overall
                        |
                  IARIResult (continuous score)
```

## References

- Greco, M., Arbia, F. & Gioia, A. (2021). Definition of Ecological Flow Using IHA and IARI as an Operative Procedure for Water Management. *MDPI Environics* (Proceedings).
- Richter, B.D., Baumgartner, J.V., Powell, J. & Braun, D.P. (1996). A method for assessing hydrologic alteration within ecosystems. *Conservation Biology*, 10(4), 1163--1174.
