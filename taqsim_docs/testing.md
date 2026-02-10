# Testing Utilities

## Overview

`taqsim.testing` provides reusable building blocks for tests and prototyping: ready-made strategies, physical model rules, node/edge factories, and a system builder. It has **zero pytest dependency** and can be used in any context.

```python
from taqsim.testing import (
    # Decision policies (Strategy subclasses — optimizable)
    FixedRelease, ProportionalRelease, EvenSplit, FixedSplit,
    # Physical model rules (frozen dataclasses — NOT Strategy)
    ConstantLoss, ProportionalReachLoss,
    # Core no-ops (re-exported from taqsim)
    NoLoss, NoReachLoss, NoRouting,
    # Factory functions
    make_source, make_sink, make_storage, make_demand,
    make_splitter, make_passthrough, make_reach, make_edge,
    # System builder
    make_system,
)
```

## Decision Policies

These are `Strategy` subclasses — frozen, immutable, and optimizable via the GA. They satisfy `ReleasePolicy` or `SplitPolicy` protocols.

### FixedRelease

Releases a fixed `rate`, capped at current storage.

```python
FixedRelease(rate=50.0)
# __params__ = ("rate",)
# __bounds__ = {"rate": (0.0, 1e6)}
```

### ProportionalRelease

Releases a `fraction` of current storage.

```python
ProportionalRelease(fraction=0.5)
# __params__ = ("fraction",)
# __bounds__ = {"fraction": (0.0, 1.0)}
```

### EvenSplit

Splits water equally among all downstream targets. No tunable parameters.

```python
EvenSplit()
# __params__ = ()
```

### FixedSplit

Splits water by fixed weights. Not optimizable (no `__params__`).

```python
FixedSplit(weights=(0.6, 0.4))
# __params__ = ()
```

Weights are matched to targets by position. If there are more targets than weights, extra targets get nothing (via `zip(..., strict=False)`).

## Physical Model Rules

Plain frozen dataclasses — **not** `Strategy` subclasses, not optimizable. They satisfy `LossRule` or `ReachLossRule` protocols.

### NoLoss / NoReachLoss / NoRouting

Zero-loss and pass-through implementations re-exported from core.

```python
NoLoss()       # satisfies LossRule — returns {}
NoReachLoss()  # satisfies ReachLossRule — returns {}
NoRouting()    # satisfies RoutingModel — passes inflow straight through with no delay
```

### ConstantLoss

Proportional evaporation and seepage losses on storage nodes.

```python
ConstantLoss(evaporation_rate=0.01, seepage_rate=0.005)
# Returns {EVAPORATION: storage * 0.01, SEEPAGE: storage * 0.005}
```

### ProportionalReachLoss

Proportional loss on reach flow.

```python
ProportionalReachLoss(loss_fraction=0.1)
# Returns {SEEPAGE: flow * 0.1}
```

## Factory Functions

Each factory creates a node or edge with sensible defaults. Pass `**overrides` to customize any field.

| Factory | Default ID | Key Defaults |
|---------|-----------|--------------|
| `make_source(id, *, n_steps=12)` | `"source"` | `inflow=TimeSeries([100.0] * n_steps)` |
| `make_sink(id)` | `"sink"` | — |
| `make_storage(id)` | `"storage"` | `capacity=1000, initial_storage=500, release_policy=ProportionalRelease(), loss_rule=NoLoss()` |
| `make_demand(id, *, n_steps=12)` | `"demand"` | `requirement=TimeSeries([50.0] * n_steps)` |
| `make_splitter(id)` | `"splitter"` | `split_policy=EvenSplit()` |
| `make_passthrough(id)` | `"passthrough"` | — |
| `make_reach(id)` | `"reach"` | `routing_model=NoRouting(), loss_rule=NoReachLoss()` |
| `make_edge(id, source, target)` | *(required)* | — (pure topology, no defaults beyond id/source/target) |

```python
# Override any default
storage = make_storage("dam", capacity=5000.0, release_policy=FixedRelease(rate=80.0))

# Use defaults for quick setup
source = make_source("river", n_steps=24)

# Reach with custom loss
reach = make_reach("canal", loss_rule=ProportionalReachLoss(loss_fraction=0.05))
```

## System Builder

`make_system` assembles nodes and edges into a `WaterSystem` in a single call.

```python
system = make_system(
    make_source("src"),
    make_storage("dam"),
    make_sink("sink"),
    make_edge("e1", "src", "dam"),
    make_edge("e2", "dam", "sink"),
)
```

Nodes and edges can be passed in any order — the builder separates them by type. By default it calls `system.validate()`. Pass `validate=False` to skip.

```python
make_system(
    *components,
    frequency=Frequency.MONTHLY,  # default
    start_date=None,              # optional calendar anchor
    validate=True,                # default
)
```

## Example: Complete Test Setup

```python
from taqsim.testing import (
    FixedRelease, EvenSplit, ConstantLoss, ProportionalReachLoss,
    make_source, make_storage, make_splitter, make_sink,
    make_reach, make_edge, make_system,
)

system = make_system(
    make_source("river", n_steps=24),
    make_storage("reservoir", release_policy=FixedRelease(rate=30.0), loss_rule=ConstantLoss()),
    make_reach("canal", loss_rule=ProportionalReachLoss(loss_fraction=0.05)),
    make_splitter("junction", split_policy=EvenSplit()),
    make_sink("irrigation"),
    make_sink("municipal"),
    make_edge("e1", "river", "reservoir"),
    make_edge("e2", "reservoir", "canal"),
    make_edge("e3", "canal", "junction"),
    make_edge("e4", "junction", "irrigation"),
    make_edge("e5", "junction", "municipal"),
)

results = system.simulate(24)
```
