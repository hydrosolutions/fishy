# Parameter Introspection

## Overview

Nodes expose their configurable strategies for parameter discovery through introspection methods. This enables optimization algorithms, sensitivity analysis tools, and debugging interfaces to discover and modify node parameters at runtime.

---

## The strategies() Method

Every node inherits `strategies()` from `BaseNode`. This method auto-discovers all fields that are `Strategy` instances.

### Signature

```python
def strategies(self) -> dict[str, Strategy]:
    """Return all Strategy-typed fields (operational policies only)."""
```

### Behavior

- Scans dataclass fields for instances inheriting from `Strategy`
- Returns a mapping of field name to strategy instance
- **Physical models (`LossRule`) are excluded** — they don't inherit from `Strategy`

### Example

```python
from dataclasses import dataclass
from typing import ClassVar
from taqsim.common import Strategy
from taqsim.node import Storage

@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"rate": (0.0, 100.0)}
    rate: float = 50.0

    def release(self, node, inflow: float, t: int, dt: float) -> float:
        return min(self.rate * dt, node.storage - node.dead_storage)

class ZeroLoss:
    """Physical model (not a Strategy)."""
    def calculate(self, node, t: int, dt: float) -> dict:
        return {}

storage = Storage(
    id="reservoir",
    capacity=1000.0,
    release_rule=FixedRelease(rate=50.0),
    loss_rule=ZeroLoss()
)

storage.strategies()
# -> {"release_rule": FixedRelease(rate=50.0)}
# Note: loss_rule is NOT included (LossRule is not a Strategy)
```

---

## Auto-Discovery Mechanism

The `strategies()` method uses dataclass field inspection to find strategies:

```python
# Actual internal logic
from dataclasses import fields

{
    f.name: getattr(self, f.name)
    for f in fields(self)
    if isinstance(getattr(self, f.name), Strategy)
}
```

### Benefits

- **No manual registration** — strategies are discovered automatically
- **Extensible** — works for any new `Strategy` subclass
- **Consistent** — all nodes use the same discovery mechanism

---

## The reset() Method

Clears node state between simulation runs. Essential for optimization workflows that run multiple simulations with different parameters.

### Signature

```python
def reset(self) -> None:
    """Reset node state for a fresh simulation run."""
```

### Node-Specific Behavior

| Node Type | Reset Behavior |
|-----------|----------------|
| `BaseNode` | Clears events via `clear_events()` |
| `Source` | Clears events only (inherits from BaseNode) |
| `Storage` | Clears events + resets `_current_storage` to `initial_storage` + resets `_received_this_step` to 0 |
| `PassThrough` | Clears events + resets `_received_this_step` to 0 |
| `Splitter` | Clears events + resets `_received_this_step` to 0 |
| `Demand` | Clears events + resets `_received_this_step` to 0 |
| `Sink` | Clears events only (inherits from BaseNode) |

### Example

```python
from taqsim import WaterSystem

# After a simulation run
system.simulate(timesteps=12)

# Reset all nodes and edges for a fresh run
system.reset()

# Run again with same or modified parameters
system.simulate(timesteps=12)
```

---

## Usage: Inspecting Node Parameters

Iterate over all nodes to discover their tunable strategies:

```python
for node_id, node in system.nodes.items():
    strategies = node.strategies()
    for name, strategy in strategies.items():
        print(f"{node_id}.{name}: {strategy.params()}")
```

### Example Output

```
reservoir.release_rule: {"rate": 50.0}
junction.split_rule: {"ratio_a": 0.6, "ratio_b": 0.4}
```

---

## Strategy Methods for Optimization

Each `Strategy` provides methods for parameter introspection, bounds, and constraints:

### params()

Returns current parameter values:

```python
strategy = FixedRelease(rate=50.0)
strategy.params()
# -> {"rate": 50.0}
```

### bounds(node)

Returns parameter bounds. Can be overridden for node-dependent bounds:

```python
# Fixed bounds via class variable
@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"rate": (0.0, 100.0)}
    rate: float = 50.0

strategy = FixedRelease()
strategy.bounds(node)
# -> {"rate": (0.0, 100.0)}

# Dynamic bounds based on node properties
@dataclass(frozen=True)
class CapacityBoundedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    rate: float = 50.0

    def bounds(self, node) -> dict[str, tuple[float, float]]:
        return {"rate": (0.0, node.capacity)}  # Bound to node's capacity
```

### constraints(node)

Returns parameter constraints. Constraints are validated at class definition time:

```python
from taqsim.constraints import SumToOne, Ordered

@dataclass(frozen=True)
class ProportionalSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("ratio_a", "ratio_b")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "ratio_a": (0.0, 1.0),
        "ratio_b": (0.0, 1.0),
    }
    __constraints__: ClassVar[tuple] = (SumToOne(params=("ratio_a", "ratio_b")),)
    ratio_a: float = 0.6
    ratio_b: float = 0.4

strategy = ProportionalSplit()
strategy.constraints(node)
# -> (SumToOne(params=('ratio_a', 'ratio_b'), target=1.0),)
```

### with_params(**kwargs)

Creates a new strategy instance with updated parameters (immutable):

```python
original = FixedRelease(rate=50.0)
modified = original.with_params(rate=75.0)

original.rate  # -> 50.0 (unchanged)
modified.rate  # -> 75.0
```

---

## Optimization Workflow

Combining introspection with reset enables parameter optimization. Since strategies are frozen dataclasses, use `with_params()` or the system's vectorization API to update parameters:

### Using System Vectorization (Recommended)

```python
from taqsim import WaterSystem

def evaluate(system: WaterSystem, vector: list[float]) -> float:
    # Create candidate with new parameters (original unchanged)
    candidate = system.with_vector(vector)

    # Run simulation
    candidate.simulate(timesteps=365)

    # Compute objective
    return compute_deficit(candidate)

# Get initial vector and bounds
base_vector = system.to_vector()
bounds = system.bounds_vector()

# Optimize
best_params = optimizer.minimize(
    lambda v: evaluate(system, v),
    x0=base_vector,
    bounds=bounds
)
```

### Using Strategy.with_params (Manual)

```python
# Strategies are immutable - use with_params() to create new instances
old_release = storage.release_rule
new_release = old_release.with_params(rate=75.0)

# Update the node (requires mutable node)
storage.release_rule = new_release
```

For full details on system-level vectorization API (`to_vector()`, `with_vector()`, `param_bounds()`, `constraint_specs()`), see [Parameter Exposure](../system/03_parameter_exposure.md).
