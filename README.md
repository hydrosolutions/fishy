# Fishy

Environmental-flow intelligence for [taqsim](https://github.com/hydrosolutions/taqsim), including naturalization, IHA metrics, IARI objectives, and DHRAM classification.

## Overview

Fishy analyzes environmental flows in water systems modeled with taqsim. It can derive natural baseline systems, calculate the 33 Indicators of Hydrological Alteration (IHA), measure continuous alteration with the Index of Hydrological Regime Alteration (IARI), expose IARI as a taqsim optimization objective, and classify alteration with DHRAM.

## Installation

```bash
# Using uv (recommended)
uv add fishy

# Using pip
pip install fishy
```

## Quick Start

```python
from fishy import naturalize, NATURAL_TAG
from taqsim.system import WaterSystem
from taqsim.edge import Edge
from taqsim.time import Frequency

# Build your water system with taqsim
system = WaterSystem(frequency=Frequency.DAILY)
# ... add nodes ...

# Tag edges on the natural flow path
system.add_edge(Edge(
    id="river_reach",
    source="upstream",
    target="downstream",
    tags=frozenset({NATURAL_TAG}),  # Mark as natural
))

# Naturalize the system (remove human infrastructure)
result = naturalize(system)

# Use the naturalized system for IHA baseline
natural_system = result.system
print(result.summary())
```

## Modules

### `naturalize`

Transform water systems with human infrastructure into their natural state.

**What it does:**
- Removes non-natural edges (canals, diversions)
- Converts `Storage` nodes to `PassThrough` (dams become river reaches)
- Converts `Demand` nodes to `PassThrough` (withdrawals removed)
- Preserves natural river bifurcations with `NaturalRiverSplitter`

**Key exports:**
- `naturalize(system)` — Main transformation function
- `NATURAL_TAG` — Tag constant for marking natural edges
- `NATURAL_SPLIT_RATIOS` — Metadata key for mixed splitter natural ratios
- `NaturalRiverSplitter` — Split rule for natural bifurcations
- `NaturalizeResult` — Result with system + audit trail

```python
from fishy.naturalize import (
    naturalize,
    NATURAL_TAG,
    NATURAL_SPLIT_RATIOS,
    NaturalRiverSplitter,
    NaturalizeResult,
    NoNaturalPathError,
    AmbiguousSplitError,
)
```

### Natural River Splitter

For natural river bifurcations (like delta distributaries):

```python
from fishy import NaturalRiverSplitter

# Fixed ratios
splitter_rule = NaturalRiverSplitter(
    ratios={"main_channel": 0.6, "side_channel": 0.4}
)

# Time-varying ratios (seasonal)
splitter_rule = NaturalRiverSplitter(
    ratios={
        "main": (0.7, 0.6, 0.5, 0.5, 0.6, 0.7),  # monthly
        "side": (0.3, 0.4, 0.5, 0.5, 0.4, 0.3),
    },
    cyclical=True,  # Repeat pattern
)
```

### Mixed Splitters

For splitters with both natural and non-natural downstream edges, use `NATURAL_SPLIT_RATIOS` metadata instead of assigning a `NaturalRiverSplitter` policy directly:

```python
from fishy import NATURAL_SPLIT_RATIOS
from taqsim.node import Splitter

# Splitter with 2 natural + 1 canal downstream
splitter = Splitter(
    id="junction",
    split_policy=operational_rule,  # Your operational split rule
    metadata={NATURAL_SPLIT_RATIOS: {"main_channel": 0.6, "side_channel": 0.4}},
)
```

Ratio keys must be the direct downstream target node IDs on natural edges. During naturalization, the metadata is validated and a `NaturalRiverSplitter` is built automatically.

### `iha`

Compute the 33 IHA parameters (Richter et al., 1996) from daily flow timeseries.

**Key exports:**
- `compute_iha(q, dates)` — Compute IHA parameters per calendar year
- `iha_from_reach(system, reach_id)` — Bridge from taqsim Reach node to IHA
- `pulse_thresholds_from_record(q)` — Derive pulse thresholds from flow record
- `IHAResult` — Immutable result wrapping `(n_years, 33)` matrix

```python
from fishy.iha import compute_iha, iha_from_reach
```

### `iari`

Measure continuous deviation from the natural IHA interquartile range. IARI can evaluate one or more reaches and can be used directly as a taqsim optimization objective.

**Key exports:**
- `compute_iari(natural, impacted)` — Compute alteration from two IHA results
- `evaluate_iari(natural_system, impacted_system)` — Evaluate shared reaches in two simulated systems
- `iari_objective(bands, reach_id)` — Build a taqsim minimization objective for one reach
- `composite_iari_objective(bands_by_reach)` — Build an objective spanning multiple reaches
- `IARIResult` — Continuous score, classification, and parameter-level audit data

```python
from fishy.iari import compute_iari, evaluate_iari, iari_objective
```

### `dhram`

Classify flow regime alteration using the Dundee Hydrological Regime Alteration Method (Black et al., 2005). Produces a 1–5 classification compatible with the EU Water Framework Directive.

**Key exports:**
- `compute_dhram(natural, impacted)` — Classify from IHA results
- `evaluate_dhram(natural_system, impacted_system)` — Full pipeline from WaterSystem pairs
- `DHRAMResult` — Classification with full audit trail

```python
from fishy.dhram import compute_dhram, evaluate_dhram
```

## Development

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=src/fishy --cov-report=term-missing

# Lint and format
uv run ruff check --fix
uv run ruff format

# Update taqsim to latest and sync its documentation
make sync-docs
```

## Documentation

- [Naturalization](src/fishy/documentation/naturalize.md)
- [IHA parameter computation](src/fishy/documentation/iha.md)
- [IARI scoring and optimization](src/fishy/documentation/iari.md)
- [DHRAM classification](src/fishy/documentation/dhram.md)
- [Consuming the packaged documentation](src/fishy/documentation/consuming_docs.md)

Fishy ships these documents with the package. Use `fishy.get_docs_path()` to locate them in an installed environment.

## License

MIT

## Related Projects

- [taqsim](https://github.com/hydrosolutions/taqsim) — Water system simulation engine
