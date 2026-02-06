# Constraints

Constraints define relationships between strategy parameters that must hold after genetic operators modify values during optimization. The constraint system is bounds-aware, meaning repairs respect parameter bounds while satisfying constraint invariants.

## Constraint Protocol

All constraints implement the `Constraint` protocol:

```python
from typing import Protocol

class Constraint(Protocol):
    @property
    def params(self) -> tuple[str, ...]: ...

    def repair(
        self,
        values: dict[str, float],
        bounds: dict[str, tuple[float, float]] | None = None,
    ) -> dict[str, float]:
        """Return corrected values. Must not mutate input."""
        ...

    def satisfied(self, values: dict[str, float], tol: float = 1e-9) -> bool:
        """Check if constraint is satisfied within tolerance."""
        ...

    def is_feasible(self, bounds: dict[str, tuple[float, float]]) -> bool:
        """Check if constraint can be satisfied given bounds."""
        ...
```

## Built-in Constraint Types

### SumToOne

Parameters must sum to a target value (default 1.0). Common for split ratios and allocation weights.

```python
from taqsim.constraints import SumToOne

@dataclass(frozen=True)
class AllocationSplit(Strategy):
    __params__ = ("city", "farm", "env")
    __bounds__ = {"city": (0.1, 0.6), "farm": (0.1, 0.5), "env": (0.1, 0.4)}
    __constraints__ = (SumToOne(("city", "farm", "env")),)

    city: float = 0.5
    farm: float = 0.3
    env: float = 0.2
```

**Parameters:**

- `params`: Tuple of parameter names that must sum to target
- `target`: Target sum (default: 1.0)

**Bounds-aware repair behavior:**

1. Clamp all values to their bounds
2. Calculate current sum and required delta
3. If delta > 0 (need to increase): distribute proportionally based on headroom (distance to upper bound)
4. If delta < 0 (need to decrease): distribute proportionally based on floor-room (distance to lower bound)
5. If no room available, return best-effort (clamped values)

**Feasibility check:** Sum of lower bounds <= target <= sum of upper bounds

### Ordered

Ensures `low <= high`. Common for threshold parameters and release bands.

```python
from taqsim.constraints import Ordered

@dataclass(frozen=True)
class BandedRelease(Strategy):
    __params__ = ("min_rate", "max_rate")
    __bounds__ = {"min_rate": (0, 100), "max_rate": (50, 200)}
    __constraints__ = (Ordered(low="min_rate", high="max_rate"),)

    min_rate: float = 10.0
    max_rate: float = 80.0
```

**Bounds-aware repair strategy cascade:**

1. **Swap**: If low > high and swapped values stay in bounds, swap them
2. **Overlap**: If bounds overlap, push both to midpoint of overlap region
3. **Gap**: If low_max < high_min (valid gap), push to boundaries (low=low_max, high=high_min)
4. **Best-effort**: If low_min > high_max (impossible), minimize violation (low=low_min, high=high_max)

**Feasibility check:** low_min <= high_max

## ConstraintSpec

`ConstraintSpec` is an internal data structure that fully resolves a constraint for use in repair functions. It binds a constraint to its location in the system's parameter namespace.

```python
@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    constraint: Constraint
    prefix: str                              # e.g., "dam.release_policy"
    param_paths: dict[str, str]              # {"r1": "dam.release_policy.r1", ...}
    param_bounds: dict[str, tuple[float, float]]  # {"r1": (0.0, 1.0), ...}
```

You typically don't create `ConstraintSpec` directly. The system generates them via `system.constraint_specs()`.

## Time-Varying Constraints

When a constraint involves time-varying parameters, validation is performed **per-timestep**. Each timestep's values must independently satisfy the constraint.

### Per-Timestep Validation

For time-varying parameters, constraints are checked at each timestep `t`:

```python
from taqsim.constraints import Ordered, SumToOne

@dataclass(frozen=True)
class SeasonalThresholds(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("low", "high")
    __time_varying__: ClassVar[tuple[str, ...]] = ("low", "high")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "low": (0.0, 100.0), "high": (0.0, 100.0)
    }
    __constraints__: ClassVar[tuple] = (Ordered(low="low", high="high"),)

    low: tuple[float, ...] = (10.0, 20.0, 15.0)
    high: tuple[float, ...] = (50.0, 60.0, 55.0)
```

The `Ordered` constraint checks `low[t] <= high[t]` for each timestep:
- t=0: `10.0 <= 50.0` (satisfied)
- t=1: `20.0 <= 60.0` (satisfied)
- t=2: `15.0 <= 55.0` (satisfied)

### SumToOne with Time-Varying Parameters

```python
@dataclass(frozen=True)
class SeasonalAllocation(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("city", "farm", "env")
    __time_varying__: ClassVar[tuple[str, ...]] = ("city", "farm", "env")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "city": (0.1, 0.6), "farm": (0.1, 0.5), "env": (0.1, 0.4)
    }
    __constraints__: ClassVar[tuple] = (SumToOne(params=("city", "farm", "env")),)

    city: tuple[float, ...] = (0.5, 0.4, 0.3)
    farm: tuple[float, ...] = (0.3, 0.4, 0.4)
    env: tuple[float, ...] = (0.2, 0.2, 0.3)
```

For each timestep, the sum is validated:
- t=0: `0.5 + 0.3 + 0.2 = 1.0` (satisfied)
- t=1: `0.4 + 0.4 + 0.2 = 1.0` (satisfied)
- t=2: `0.3 + 0.4 + 0.3 = 1.0` (satisfied)

### ConstraintSpec for Time-Varying Parameters

When the system builds `ConstraintSpec` objects, it includes metadata about which parameters are time-varying:

```python
@dataclass(frozen=True, slots=True)
class ConstraintSpec:
    constraint: Constraint
    prefix: str
    param_paths: dict[str, str]
    param_bounds: dict[str, tuple[float, float]]
    time_varying_params: frozenset[str]  # params that vary over time
```

The `time_varying_params` field allows repair functions to handle time-varying parameters correctly during optimization.

### Cyclical Parameter Constraints

When all time-varying parameters in a constraint are cyclical, validation is performed **per-cycle-position** rather than per-timestep. Note that `__cyclical_freq__` is now required alongside `__cyclical__` -- see [Strategies](../nodes/05_strategies.md) for full details on declaring cyclical parameters with their frequencies.

#### Validation Behavior

Constraint validation still operates per-cycle-position (unchanged behavior). The `__cyclical_freq__` declaration affects runtime value lookup via `param_at()`, but constraint validation at construction time iterates over cycle positions directly:

```python
from taqsim.time import Frequency

@dataclass(frozen=True)
class SeasonalSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("r1", "r2")
    __time_varying__: ClassVar[tuple[str, ...]] = ("r1", "r2")
    __cyclical__: ClassVar[tuple[str, ...]] = ("r1", "r2")
    __cyclical_freq__: ClassVar[dict[str, Frequency]] = {
        "r1": Frequency.MONTHLY, "r2": Frequency.MONTHLY
    }
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "r1": (0.0, 1.0), "r2": (0.0, 1.0)
    }
    __constraints__: ClassVar[tuple] = (SumToOne(params=("r1", "r2")),)

    r1: tuple[float, ...] = (0.6, 0.5, 0.4)  # 3 monthly values
    r2: tuple[float, ...] = (0.4, 0.5, 0.6)
```

Validation checks `SumToOne` at each cycle position:
- Position 0: `0.6 + 0.4 = 1.0` ✓
- Position 1: `0.5 + 0.5 = 1.0` ✓
- Position 2: `0.4 + 0.6 = 1.0` ✓

#### Ordered Constraint with Cyclical Parameters

```python
@dataclass(frozen=True)
class SeasonalBands(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("low", "high")
    __time_varying__: ClassVar[tuple[str, ...]] = ("low", "high")
    __cyclical__: ClassVar[tuple[str, ...]] = ("low", "high")
    __cyclical_freq__: ClassVar[dict[str, Frequency]] = {
        "low": Frequency.MONTHLY, "high": Frequency.MONTHLY
    }
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "low": (0.0, 100.0), "high": (0.0, 100.0)
    }
    __constraints__: ClassVar[tuple] = (Ordered(low="low", high="high"),)

    low: tuple[float, ...] = (10.0, 20.0, 15.0)
    high: tuple[float, ...] = (50.0, 60.0, 55.0)
```

Validation checks `Ordered` at each cycle position:
- Position 0: `10.0 <= 50.0` ✓
- Position 1: `20.0 <= 60.0` ✓
- Position 2: `15.0 <= 55.0` ✓

#### Repair Behavior

The repair system operates on parameter vector indices. For cyclical parameters:
- Each cycle position is an independent entry in the parameter vector
- Constraints are repaired per-position (e.g., `r1[0] + r2[0] = 1`, `r1[1] + r2[1] = 1`, etc.)

## Integration with Optimization

### make_repair

The `make_repair` function creates a repair function for use with ctrl-freak genetic operators:

```python
from taqsim.optimization import make_repair

system = build_system()
repair = make_repair(system)

# Use with ctrl-freak operators
crossover = lambda p1, p2: repair(sbx_crossover(...)(p1, p2))
mutate = lambda x: repair(polynomial_mutation(...)(x))
```

**What make_repair does:**

1. Clips values to bounds (fast, vectorized)
2. Applies each constraint repair in order
3. Returns repaired numpy array

## Complete Example

```python
from dataclasses import dataclass
from typing import ClassVar

from taqsim import Edge, Sink, Source, Splitter, Storage, TimeSeries, WaterSystem
from taqsim.common import Strategy
from taqsim.constraints import Ordered, SumToOne
from taqsim.optimization import make_repair


@dataclass(frozen=True)
class BandedRelease(Strategy):
    """Release rule with min/max thresholds."""
    __params__: ClassVar[tuple[str, ...]] = ("low", "high")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "low": (0.0, 100.0),
        "high": (0.0, 100.0),
    }
    __constraints__: ClassVar[tuple[Ordered, ...]] = (Ordered(low="low", high="high"),)

    low: float = 10.0
    high: float = 50.0

    def release(self, node: "Storage", inflow: float, t: int, dt: float) -> float:
        return min(self.high * dt, node.storage)


@dataclass(frozen=True)
class AllocationSplit(Strategy):
    """Split water to three destinations with ratios summing to 1."""
    __params__: ClassVar[tuple[str, ...]] = ("city", "farm", "env")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "city": (0.1, 0.6),
        "farm": (0.1, 0.5),
        "env": (0.1, 0.4),
    }
    __constraints__: ClassVar[tuple[SumToOne, ...]] = (
        SumToOne(params=("city", "farm", "env")),
    )

    city: float = 0.5
    farm: float = 0.3
    env: float = 0.2

    def split(self, node: "Splitter", amount: float, t: int) -> dict[str, float]:
        ratios = {"city_sink": self.city, "farm_sink": self.farm, "env_sink": self.env}
        return {target: amount * ratios[target] for target in node.targets}


# Build system with constrained strategies
system = WaterSystem(dt=86400.0)
system.add_node(Source(id="river", inflow=TimeSeries([100.0] * 12)))
system.add_node(Storage(id="dam", capacity=1000.0, release_policy=BandedRelease()))
system.add_node(Splitter(id="junction", split_policy=AllocationSplit()))
system.add_node(Sink(id="city_sink"))
system.add_node(Sink(id="farm_sink"))
system.add_node(Sink(id="env_sink"))

# ... add edges ...
system.validate()

# Create repair function for optimization
repair = make_repair(system)

# Verify constraints are discoverable
specs = system.constraint_specs()
for spec in specs:
    print(f"{spec.prefix}: {spec.constraint}")
```

## Custom Constraints

To implement a custom constraint:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class MinDifference:
    """Ensure high - low >= min_gap."""
    low: str
    high: str
    min_gap: float

    @property
    def params(self) -> tuple[str, ...]:
        return (self.low, self.high)

    def repair(
        self,
        values: dict[str, float],
        bounds: dict[str, tuple[float, float]] | None = None,
    ) -> dict[str, float]:
        result = dict(values)
        if values[self.high] - values[self.low] < self.min_gap:
            mid = (values[self.low] + values[self.high]) / 2
            result[self.low] = mid - self.min_gap / 2
            result[self.high] = mid + self.min_gap / 2
        return result

    def satisfied(self, values: dict[str, float], tol: float = 1e-9) -> bool:
        return values[self.high] - values[self.low] >= self.min_gap - tol

    def is_feasible(self, bounds: dict[str, tuple[float, float]]) -> bool:
        return bounds[self.high][1] - bounds[self.low][0] >= self.min_gap
```

## Validation

Constraints are validated at class definition time. Referencing unknown parameters raises `TypeError`:

```python
# Raises TypeError: BadStrategy: constraint references unknown params: {'missing'}
@dataclass(frozen=True)
class BadStrategy(Strategy):
    __params__ = ("rate",)
    __constraints__ = (SumToOne(("missing",)),)
```

## Instance Validation

Beyond class-definition validation, constraints are also validated when a Strategy instance is created. If any constraint's `satisfied()` method returns `False`, a `ConstraintViolationError` is raised immediately.

### Interaction with Repair Functions

Construction-time validation and `repair()` serve different purposes:

| Context | Mechanism | Purpose |
|---------|-----------|---------|
| Strategy construction | `ConstraintViolationError` | Catch invalid user input immediately |
| GA optimization | `repair()` function | Correct values after genetic operators mutate/crossover |

The repair function remains essential for optimization workflows where genetic operators may produce invalid parameter combinations. Always use `make_repair()` to wrap GA operators.
