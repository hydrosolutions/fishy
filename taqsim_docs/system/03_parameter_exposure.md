# Parameter Exposure

## Overview

Parameter exposure enables genetic algorithm (GA) optimization by providing a standardized interface to discover, read, and modify tunable parameters across a `WaterSystem`. The system treats operational strategies as optimizable while keeping physical models fixed.

## Semantic Distinction

Not all configurable objects are optimizable. The system distinguishes between:

| Type | Category | Optimizable | Examples |
|------|----------|-------------|----------|
| **Operational Policy** | Strategy | Yes | `ReleaseRule`, `SplitRule` |
| **Physical Model** | Rule | No | `LossRule`, `EdgeLossRule` |

### Why the Distinction?

- **Operational policies** represent decisions: how much water to release, how to split flow. These are tunable parameters a GA can optimize.
- **Physical models** represent reality: evaporation rates, seepage coefficients. These are measured properties of the physical system, not optimization variables.

Only classes that inherit from `Strategy` expose parameters for optimization.

## Strategy Base Class

Located in `src/taqsim/common.py`:

```python
class Strategy:
    __params__: ClassVar[tuple[str, ...]] = ()
    __bounds__: ClassVar[dict[str, ParamBounds]] = {}
    __constraints__: ClassVar[tuple[Constraint, ...]] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        valid = set(cls.__params__)
        for c in cls.__constraints__:
            invalid = set(c.params) - valid
            if invalid:
                raise TypeError(f"{cls.__name__}: constraint references unknown params: {invalid}")

    def params(self) -> dict[str, ParamValue]:
        """Return current parameter values."""
        return {name: getattr(self, name) for name in self.__params__}

    def bounds(self, node: BaseNode) -> dict[str, ParamBounds]:
        """Return parameter bounds, optionally derived from node properties."""
        return dict(self.__bounds__)

    def constraints(self, node: BaseNode) -> tuple[Constraint, ...]:
        """Return constraints for this strategy."""
        return self.__constraints__

    def with_params(self, **kwargs: ParamValue) -> Self:
        """Create new instance with updated parameters (immutable)."""
        invalid = set(kwargs) - set(self.__params__)
        if invalid:
            raise ValueError(f"Unknown parameters: {invalid}")
        return replace(self, **kwargs)
```

### Class Variables

| Variable | Type | Description |
|----------|------|-------------|
| `__params__` | `tuple[str, ...]` | Names of optimizable fields |
| `__bounds__` | `dict[str, ParamBounds]` | Static bounds for parameters (param name -> (low, high)) |
| `__constraints__` | `tuple[Constraint, ...]` | Constraints between parameters (e.g., SumToOne, Ordered) |

### Methods

| Method | Return Type | Description |
|--------|-------------|-------------|
| `__init_subclass__` | `None` | Validates that all constraint params reference valid `__params__` entries |
| `params()` | `dict[str, ParamValue]` | Returns current parameter values as a dictionary |
| `bounds(node)` | `dict[str, ParamBounds]` | Returns parameter bounds, can be overridden for node-dependent bounds |
| `constraints(node)` | `tuple[Constraint, ...]` | Returns constraints, can be overridden for node-dependent constraints |
| `with_params(**kwargs)` | `Self` | Creates new instance with updated parameters (immutable) |

### Implementing a Strategy

Concrete strategies must:

1. Inherit from `Strategy`
2. Be frozen dataclasses
3. Declare `__params__` listing optimizable field names
4. Optionally declare `__bounds__` for parameter bounds
5. Optionally declare `__constraints__` for parameter constraints

```python
from dataclasses import dataclass
from typing import ClassVar
from taqsim.common import Strategy, ParamBounds
from taqsim.node import Storage

@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, ParamBounds]] = {"rate": (0.0, 100.0)}
    rate: float = 50.0

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        available = node.storage - node.dead_storage
        return min(self.rate * dt, available)
```

### Non-Optimizable Fields

Fields not listed in `__params__` are excluded from optimization:

```python
@dataclass(frozen=True)
class ThresholdRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate", "threshold")
    __bounds__: ClassVar[dict[str, ParamBounds]] = {
        "rate": (0.0, 100.0),
        "threshold": (0.0, 1.0),
    }
    rate: float = 50.0
    threshold: float = 0.8
    name: str = "threshold_release"  # NOT in __params__ - excluded
```

### Constraints

Constraints express relationships between parameters that must hold after GA operations (crossover, mutation). They are validated at subclass creation time:

```python
from taqsim.constraints import SumToOne

@dataclass(frozen=True)
class ProportionalSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("ratio_a", "ratio_b")
    __bounds__: ClassVar[dict[str, ParamBounds]] = {
        "ratio_a": (0.0, 1.0),
        "ratio_b": (0.0, 1.0),
    }
    __constraints__: ClassVar[tuple[Constraint, ...]] = (
        SumToOne(params=("ratio_a", "ratio_b")),
    )
    ratio_a: float = 0.6
    ratio_b: float = 0.4
```

If a constraint references a parameter not in `__params__`, a `TypeError` is raised at class definition time:

```python
# This raises TypeError: MyStrategy: constraint references unknown params: {'invalid_param'}
@dataclass(frozen=True)
class MyStrategy(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __constraints__: ClassVar[tuple[Constraint, ...]] = (
        SumToOne(params=("rate", "invalid_param")),
    )
    rate: float = 0.5
```

### Node-Dependent Bounds

Override the `bounds()` method for bounds that depend on node properties:

```python
@dataclass(frozen=True)
class CapacityBasedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    rate: float = 50.0

    def bounds(self, node: BaseNode) -> dict[str, ParamBounds]:
        # Bound rate to node's capacity
        return {"rate": (0.0, node.capacity)}
```

## ParamSpec Dataclass

Each tunable parameter is described by a `ParamSpec`:

```python
@dataclass(frozen=True, slots=True)
class ParamSpec:
    path: str    # e.g., "dam.release_rule.rate"
    value: float # scalar value
```

| Field | Description | Example |
|-------|-------------|---------|
| `path` | Dot-separated path to parameter | `"dam.release_rule.rate"` |
| `value` | Current scalar value | `50.0` |

## WaterSystem Vectorization API

### param_schema()

Discover all tunable parameters:

```python
system = build_system()
schema = system.param_schema()

for spec in schema:
    print(f"{spec.path} = {spec.value}")
```

Output:
```
dam.release_rule.rate = 50.0
junction.split_rule.ratio_a = 0.6
junction.split_rule.ratio_b = 0.4
```

### to_vector()

Flatten parameters to a list of floats:

```python
vector = system.to_vector()
# [50.0, 0.6, 0.4]
```

### param_bounds()

Collect bounds for all tunable parameters:

```python
system = build_system()
bounds = system.param_bounds()

for path, (low, high) in bounds.items():
    print(f"{path}: [{low}, {high}]")
```

Output:
```
dam.release_rule.rate: [0.0, 100.0]
junction.split_rule.ratio_a: [0.0, 1.0]
junction.split_rule.ratio_b: [0.0, 1.0]
```

### bounds_vector()

Get bounds in optimizer-friendly format:

```python
bounds = system.bounds_vector()
lower = [b[0] for b in bounds]
upper = [b[1] for b in bounds]

# Use with scipy.optimize
from scipy.optimize import minimize

result = minimize(
    objective,
    x0=system.to_vector(),
    bounds=bounds,
    method='L-BFGS-B'
)
```

### with_vector(vector)

Create a new system with modified parameters (immutable):

```python
new_vector = [100.0, 0.7, 0.3]
new_system = system.with_vector(new_vector)

# Original unchanged
assert system.to_vector() == [50.0, 0.6, 0.4]
# New system has updated values
assert new_system.to_vector() == [100.0, 0.7, 0.3]
```

Raises `ValueError` if vector length doesn't match schema.

### Validation on Parameter Updates

Both `with_params()` and `with_vector()` create new Strategy instances, which triggers construction-time validation:

```python
strategy = FixedRelease(rate=50.0)
strategy.with_params(rate=150.0)  # Raises BoundViolationError

# In GA context, always repair first
repair = make_repair(system)
safe_vector = repair(candidate_vector)
new_system = system.with_vector(safe_vector)
```

### reset()

Clear state for fresh simulation:

```python
system.simulate(12)
# Events accumulated, storage changed

system.reset()
# Events cleared, storage back to initial value
# Topology and strategies preserved
```

## Multiple Parameter Handling

When a strategy has multiple related parameters (like split ratios), each is exposed as a separate scalar `ParamSpec`:

```python
@dataclass(frozen=True)
class ProportionalSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("ratio_a", "ratio_b")
    __bounds__: ClassVar[dict[str, ParamBounds]] = {
        "ratio_a": (0.0, 1.0),
        "ratio_b": (0.0, 1.0),
    }
    __constraints__: ClassVar[tuple[Constraint, ...]] = (
        SumToOne(params=("ratio_a", "ratio_b")),
    )
    ratio_a: float = 0.6
    ratio_b: float = 0.4
```

Schema output:

| path | value |
|------|-------|
| `junction.split_rule.ratio_a` | `0.6` |
| `junction.split_rule.ratio_b` | `0.4` |

Vector: `[0.6, 0.4]`

Constraints ensure related parameters maintain valid relationships after GA operations.

## GA Optimization Loop Pattern

The vectorization API enables a standard optimization loop:

```python
from taqsim import WaterSystem

def build_system() -> WaterSystem:
    # ... create and configure system
    pass

def evaluate(system: WaterSystem) -> float:
    # ... calculate fitness score
    pass

def evolve(population: list[list[float]], scores: list[float]) -> list[list[float]]:
    # ... GA selection, crossover, mutation
    pass

# Initialize
system = build_system()
base_vector = system.to_vector()
population = [mutate(base_vector) for _ in range(100)]

# Optimization loop
for generation in range(100):
    scores = []

    for vec in population:
        # Create candidate (original unchanged)
        candidate = system.with_vector(vec)

        # Run simulation
        candidate.simulate(12)

        # Evaluate fitness
        scores.append(evaluate(candidate))

    # Evolve population
    population = evolve(population, scores)

# Best solution
best_idx = scores.index(max(scores))
best_system = system.with_vector(population[best_idx])
```

### Key Properties

1. **Immutable**: `with_vector()` never modifies the original system
2. **Isolated**: Each candidate runs independently
3. **Resettable**: Use `reset()` if reusing a system instance
4. **Consistent**: Schema order is deterministic (sorted by path)

## Constraint-Aware Optimization

### constraint_specs()

Discover constraint specifications for repair functions:

```python
specs = system.constraint_specs()
for spec in specs:
    print(f"{spec.prefix}: {spec.constraint}")
```

### make_repair

For genetic algorithms using ctrl-freak operators, use `make_repair` to create a bounds-and-constraint-aware repair function:

```python
from taqsim.optimization import make_repair

repair = make_repair(system)

# Wrap GA operators
crossover = lambda p1, p2: repair(sbx_crossover(...)(p1, p2))
mutate = lambda x: repair(polynomial_mutation(...)(x))
```

The repair function:
1. Clips values to parameter bounds
2. Applies constraint repairs (e.g., SumToOne, Ordered)
3. Returns a valid numpy array

See [Constraints](../common/02_constraints.md) for full documentation on constraint types and custom implementations.

## Time-Varying Parameters

Time-varying parameters are expanded in the vector representation.

### Path Expansion

For a time-varying parameter with N timesteps, `param_schema()` returns N `ParamSpec` objects with indexed paths:

```python
# Strategy: rate = (50.0, 60.0, 70.0)
schema = system.param_schema()
# [
#   ParamSpec(path="dam.release_rule.rate[0]", value=50.0),
#   ParamSpec(path="dam.release_rule.rate[1]", value=60.0),
#   ParamSpec(path="dam.release_rule.rate[2]", value=70.0),
# ]
```

### Vector Flattening

`to_vector()` flattens tuples into consecutive elements:

```python
vector = system.to_vector()  # [50.0, 60.0, 70.0]
```

### Tuple Reconstruction

`with_vector()` reconstructs tuples from indexed values:

```python
new_system = system.with_vector([55.0, 65.0, 75.0])
# dam.release_rule.rate = (55.0, 65.0, 75.0)
```

### Bounds Expansion

Bounds are replicated for each timestep index:

```python
bounds = system.bounds_vector()
# [(0.0, 100.0), (0.0, 100.0), (0.0, 100.0)]
```

### Length Validation

Before simulation, the system validates that time-varying parameters have sufficient length:

```python
# If rate has 3 values but simulate(5) is called:
# Raises InsufficientLengthError
```
