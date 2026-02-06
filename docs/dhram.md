# DHRAM Module

Classify flow regime alteration using the Dundee Hydrological Regime Alteration Method (Black et al., 2005). Produces a 1–5 classification compatible with the EU Water Framework Directive's ecological status scheme.

## Design Philosophy

- **Two-series comparison**: Takes natural and impacted IHA results, computes deviation across all five IHA groups.
- **Fixed empirical thresholds**: Default scoring uses the original Black et al. (2005) thresholds derived from Scottish catchments. Simplified uniform thresholds available as an option.
- **Circular statistics for timing**: Group 3 (timing of extremes) uses circular mean to handle December–January wraparound.
- **Skip-and-collect evaluation**: `evaluate_dhram` processes multiple edges independently, returning partial results if some edges fail.
- **Immutable output**: `DHRAMResult` is a frozen dataclass with full audit trail.

## Quick Start

```python
import numpy as np
from fishy.iha import compute_iha
from fishy.dhram import compute_dhram

# Compute IHA for both series (using same pulse thresholds from natural record)
from fishy.iha import pulse_thresholds_from_record
thresholds = pulse_thresholds_from_record(natural_q)

natural_iha = compute_iha(natural_q, natural_dates, pulse_thresholds=thresholds)
impacted_iha = compute_iha(impacted_q, impacted_dates, pulse_thresholds=thresholds)

# Compute DHRAM classification
result = compute_dhram(natural_iha, impacted_iha)
print(result.summary())
```

## Core Concepts

### The Four Stages

1. **Compute IHA parameters** — 33 parameters per year for both natural and impacted series
2. **Summarise** — 10 summary indicators (mean change + CV change per IHA group)
3. **Score** — Each indicator scored 0–3 against deviation thresholds (max 30 points)
4. **Classify** — Total points mapped to DHRAM class 1–5, with optional supplementary adjustments

### The 10 Summary Indicators

| Indicator | Description |
|-----------|-------------|
| 1a | Average % change in means for Group 1 (12 monthly flows) |
| 1b | Average % change in CVs for Group 1 |
| 2a | Average % change in means for Group 2 (10 extreme magnitude params) |
| 2b | Average % change in CVs for Group 2 |
| 3a | Average % change in means for Group 3 (2 timing params) |
| 3b | Average % change in CVs for Group 3 |
| 4a | Average % change in means for Group 4 (4 pulse params) |
| 4b | Average % change in CVs for Group 4 |
| 5a | Average % change in means for Group 5 (3 rate-of-change params) |
| 5b | Average % change in CVs for Group 5 |

### Parameter Counts per Group

Group 2 uses **10 parameters** (excluding zero-flow days and BFI from the 12 IHA Group 2 parameters). Total parameters contributing to scoring: **31**.

| Group | IHA Parameters | DHRAM Parameters | Excluded |
|-------|---------------|-----------------|----------|
| 1 | 12 | 12 | — |
| 2 | 12 | 10 | zero_flow_days, BFI |
| 3 | 2 | 2 | — |
| 4 | 4 | 4 | — |
| 5 | 3 | 3 | — |

### Threshold Variants

**Empirical (default)** — From Black et al. (2005) Table 3, derived from 20 natural and 11 impacted Scottish catchments:

| Indicator | Lower (1pt) | Intermediate (2pt) | Upper (3pt) |
|-----------|------------|-------------------|------------|
| 1a | 19.9% | 43.7% | 67.5% |
| 1b | 29.4% | 97.6% | 165.7% |
| 2a | 42.9% | 88.2% | 133.4% |
| 2b | 84.5% | 122.7% | 160.8% |
| 3a | 7.0% | 21.2% | 35.5% |
| 3b | 33.4% | 50.3% | 67.3% |
| 4a | 36.4% | 65.1% | 93.8% |
| 4b | 30.5% | 76.1% | 121.6% |
| 5a | 46.0% | 82.7% | 119.4% |
| 5b | 49.1% | 79.9% | 110.6% |

**Simplified** — Uniform thresholds: 10% / 30% / 50% for all indicators.

### Classification

| Total Points | Class | WFD Status | Description |
|-------------|-------|-----------|-------------|
| 0 | 1 | High | Un-impacted |
| 1–4 | 2 | Good | Low risk |
| 5–10 | 3 | Moderate | Moderate risk |
| 11–20 | 4 | Poor | High risk |
| 21–30 | 5 | Bad | Severely impacted |

### Supplementary Questions

Two yes/no flags can each worsen the classification by one class (capped at 5):

- **Flow cessation**: Anthropogenic impacts cause zero flow where naturally there would be flow
- **Sub-daily oscillation**: Sub-daily flow variations exceed 25% of the un-impacted 95% exceedance flow

## API

### `compute_dhram`

```python
from fishy.dhram import compute_dhram, ThresholdVariant

result = compute_dhram(
    natural,                                  # IHAResult — un-impacted
    impacted,                                 # IHAResult — impacted
    *,
    threshold_variant=ThresholdVariant.EMPIRICAL,  # or SIMPLIFIED
    flow_cessation=False,                     # supplementary question 1
    subdaily_oscillation=False,               # supplementary question 2
    min_years=1,                              # minimum years per series
) -> DHRAMResult
```

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `IncompatibleIHAResultsError` | IHA results don't have 33 parameters |
| `InsufficientYearsError` | Either series has fewer than `min_years` years |

### `evaluate_dhram`

```python
from fishy.dhram import evaluate_dhram

results = evaluate_dhram(
    natural,                                  # WaterSystem — simulated natural
    impacted,                                 # WaterSystem — simulated impacted
    *,
    edge_ids=None,                            # Sequence[str] | None — defaults to shared natural-tagged edges
    threshold_variant=ThresholdVariant.EMPIRICAL,
    flow_cessation=False,
    subdaily_oscillation=False,
    zero_flow_threshold=0.001,
    min_years=1,
) -> dict[str, DHRAMResult]
```

Per-edge pipeline: extracts flows, derives pulse thresholds from natural record, computes IHA for both series using the same thresholds, then computes DHRAM.

**Raises:**

| Exception | Condition |
|-----------|-----------|
| `NonDailyFrequencyError` | Either system is not daily |
| `MissingStartDateError` | Either system has no `start_date` |
| `NoCommonEdgesError` | No shared natural-tagged edges found |
| `EdgeEvaluationError` | ALL edges failed (partial results returned otherwise) |

### `iha_from_trace`

```python
from fishy.iha import iha_from_trace

result = iha_from_trace(
    system,                                   # WaterSystem — simulated, daily
    edge_id,                                  # str — edge to extract
    *,
    zero_flow_threshold=0.001,
    pulse_thresholds=None,                    # PulseThresholds | None
    min_years=1,
) -> IHAResult
```

Bridge between taqsim `WaterSystem` and `compute_iha`. Extracts the `WaterDelivered` trace from the named edge and converts to numpy arrays.

## Result Types

### `DHRAMResult`

```python
result.indicators          # tuple[IndicatorDetail, ...] — 10 indicators
result.total_points        # int — 0 to 30
result.preliminary_class   # int — 1 to 5
result.flow_cessation      # bool
result.subdaily_oscillation # bool
result.final_class         # int — 1 to 5
result.wfd_status          # str — "High"/"Good"/"Moderate"/"Poor"/"Bad"
result.threshold_variant   # ThresholdVariant
result.natural_years       # int
result.impacted_years      # int

result.indicator("3a")     # IndicatorDetail — lookup by name
result.group_points(3)     # int — sum of 3a + 3b points
result.summary()           # str — human-readable table
```

### `IndicatorDetail`

```python
indicator.name        # str — e.g. "1a"
indicator.group       # int — 1 to 5
indicator.statistic   # str — "mean" or "cv"
indicator.value       # float — deviation percentage
indicator.points      # int — 0 to 3
indicator.thresholds  # ScoringThresholds
```

### `ScoringThresholds`

```python
thresholds.lower         # float
thresholds.intermediate  # float
thresholds.upper         # float
thresholds.score(42.0)   # int — 0, 1, 2, or 3
```

## Worked Example — Megget Water

From Black et al. (2005), Megget Water supply reservoir (13 years of data):

| Indicator | Value (%) | Points |
|-----------|-----------|--------|
| 1a | 21.7 | 1 |
| 1b | 39.8 | 1 |
| 2a | 31.0 | 0 |
| 2b | 124.0 | 2 |
| 3a | 30.9 | 2 |
| 3b | 17.6 | 0 |
| 4a | 46.3 | 1 |
| 4b | 22.7 | 0 |
| 5a | 34.2 | 0 |
| 5b | 41.4 | 0 |

**Total: 7 points → Class 3 (Moderate)**

No flow cessation, no sub-daily oscillation → Final Class 3.

## Error Handling

All DHRAM errors inherit from `DHRAMError`. Bridge errors inherit from `IHAError`.

```python
from fishy.dhram import (
    DHRAMError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonEdgesError,
    EdgeEvaluationError,
)
from fishy.iha import (
    MissingStartDateError,
    NonDailyFrequencyError,
    EdgeNotFoundError,
    EmptyTraceError,
)
```

## Complete Example

Full taqsim workflow: build → simulate → naturalize → evaluate.

```python
from datetime import date
from taqsim.testing import make_source, make_storage, make_sink, make_edge, make_system
from taqsim.time import Frequency
from fishy import naturalize, NATURAL_TAG, evaluate_dhram

# 1. Build impacted system
impacted = make_system(
    make_source("river", n_steps=730),
    make_storage("dam"),
    make_sink("downstream"),
    make_edge("inflow", "river", "dam", tags=frozenset({NATURAL_TAG})),
    make_edge("release", "dam", "downstream", tags=frozenset({NATURAL_TAG})),
    frequency=Frequency.DAILY,
    start_date=date(2020, 1, 1),
)
impacted.simulate(730)

# 2. Naturalize and simulate
natural_result = naturalize(impacted)
natural = natural_result.system
natural.simulate(730)

# 3. Evaluate DHRAM
results = evaluate_dhram(natural, impacted)
for edge_id, dhram in results.items():
    print(f"{edge_id}: Class {dhram.final_class} ({dhram.wfd_status})")
    print(dhram.summary())
```

## Integration Pipeline

```
WaterSystem (impacted) ──simulate──→ edge traces (impacted)
         │                                     │
         └── naturalize() → simulate ──→ edge traces (natural)
                                               │
         For each shared natural-tagged edge:   │
           natural flows → pulse_thresholds ────┤
           compute_iha(natural, thresholds)     │
           compute_iha(impacted, thresholds) ───┤
           compute_dhram(natural_iha, impacted_iha)
                        │
                  DHRAMResult (class 1-5)
```

## References

- Black, A.R., Rowan, J.S., Duck, R.W., Bragg, O.M. & Clelland, B.E. (2005). DHRAM: a method for classifying river flow regime alterations for the EC Water Framework Directive. *Aquatic Conservation: Marine and Freshwater Ecosystems*, 15, 427–446.
- Richter, B.D., Baumgartner, J.V., Powell, J. & Braun, D.P. (1996). A method for assessing hydrologic alteration within ecosystems. *Conservation Biology*, 10(4), 1163–1174.
