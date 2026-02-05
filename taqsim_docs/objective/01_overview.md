# Objective System Overview

## Purpose

The `taqsim.objective` module provides declarative optimization objectives for genetic algorithm (GA) optimization. Instead of manually computing fitness scores, you declare what to optimize and the system handles evaluation.

## Core Concepts

### Objective

An `Objective` encapsulates what to optimize:

```python
@dataclass(frozen=True, slots=True)
class Objective:
    name: str                                    # Human-readable identifier
    direction: Literal["minimize", "maximize"]   # Optimization direction
    evaluate: Callable[[WaterSystem], float]     # Computes score from simulation
    priority: int = 1                            # For multi-objective weighting
```

### Trace

A `Trace` is a time-indexed series of values. It bridges simulation events and objective computation, supporting arithmetic operations and aggregations.

### lift

The `@lift` decorator transforms scalar functions to work on Traces, enabling custom physics transformations.

## Quick Example

```python
from taqsim.objective import minimize

# Use built-in objectives via the registry
objectives = [
    minimize.spill("reservoir_1"),      # Minimize water spilled
    minimize.deficit("city_demand"),    # Minimize unmet demand
]

# Objectives evaluate against a simulated system
system.simulate(timesteps=12)
scores = [obj.evaluate(system) for obj in objectives]
```

## Registries

Taqsim provides two objective registries: `minimize` and `maximize`.

### minimize (built-in objectives)

- `minimize.spill` - minimize water spilled (controllable via release timing)
- `minimize.deficit` - minimize unmet demand (controllable via allocation)

```python
from taqsim.objective import minimize

obj1 = minimize.spill("reservoir")
obj2 = minimize.deficit("city_demand", priority=2)
```

### maximize (custom objectives)

The `maximize` registry starts empty. Register custom objectives to use the fluent API:

```python
from taqsim.objective import maximize

# After defining and registering hydropower (see 05_custom.md)
maximize.register("hydropower", hydropower)
obj = maximize.hydropower("reservoir", "turbine", efficiency=0.9)
```

## Custom Objectives

Create custom objectives by defining an evaluate function:

```python
from taqsim.objective import Objective
from taqsim.node.events import WaterReleased

def hydropower(turbine_id: str, efficiency: float = 0.85) -> Objective:
    def evaluate(system):
        node = system.nodes[turbine_id]
        releases = node.trace(WaterReleased)
        power = releases.map(lambda q: q * 9.81 * 50 * efficiency)  # P = Q * g * h * eta
        return power.sum()

    return Objective(
        name=f"{turbine_id}.hydropower",
        direction="maximize",
        evaluate=evaluate,
    )
```
