# Strategy Protocols

## Overview

Strategies define configurable behaviors for nodes. Each is a `Protocol` that allows custom implementations to be injected at node creation.

## Strategy Base Class

Operational strategies inherit from the `Strategy` mixin class, which provides parameter introspection for optimization.

### Declaration Pattern

```python
from dataclasses import dataclass
from typing import ClassVar
from taqsim.common import Strategy
from taqsim.node import Storage

@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    rate: float = 50.0

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        available = node.storage - node.dead_storage
        return min(self.rate * dt, available)
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `Strategy` base | Enables parameter discovery via `node.strategies()` |
| `@dataclass(frozen=True)` | Immutable instances for safe optimization |
| `__params__` | Declares which fields are tunable parameters |
| `__bounds__` | Declares fixed bounds for tunable parameters (optional) |
| `__constraints__` | Declares constraints between parameters (optional) |

### Methods Provided

- `params() -> dict[str, float]` — Returns current parameter values
- `bounds(node) -> dict[str, tuple[float, float]]` — Returns parameter bounds (may depend on node)
- `constraints(node) -> tuple[Constraint, ...]` — Returns parameter constraints
- `with_params(**kwargs) -> Self` — Creates new instance with updated values

### Note on Physical Models

`LossRule` implementations do **not** inherit from `Strategy`. They are physical models representing infrastructure, not operational policies. Only `ReleaseRule` and `SplitRule` are optimizable.

## Protocol Definitions

### ReleaseRule

Controls how storage nodes release water.

```python
@runtime_checkable
class ReleaseRule(Protocol):
    def release(
        self,
        node: Storage,  # the storage node (provides storage, dead_storage, capacity)
        inflow: float,  # inflow this timestep
        t: int,         # timestep
        dt: float       # timestep duration
    ) -> float: ...     # amount to release
```

### SplitRule

Determines how water is distributed among downstream nodes.

```python
@runtime_checkable
class SplitRule(Protocol):
    def split(
        self,
        node: Splitter,           # the splitter node (provides targets)
        amount: float,            # total amount to distribute
        t: int                    # timestep
    ) -> dict[str, float]: ...   # {downstream_node_id: amount}
```

The returned dict keys are **downstream node IDs** (not edge IDs). For example, if a splitter routes water to nodes "irrigation" and "thermal":

```python
def split(self, node: Splitter, amount: float, t: int) -> dict[str, float]:
    return {"irrigation": amount * 0.6, "thermal": amount * 0.4}
```

### LossRule

Calculates physical losses from storage.

```python
@runtime_checkable
class LossRule(Protocol):
    def calculate(
        self,
        node: Storage,  # the storage node (provides storage, capacity)
        t: int,         # timestep
        dt: float       # timestep duration
    ) -> dict[LossReason, float]: ...  # {reason: amount}
```

`LossReason` is a `str` subclass with standard constants:

- `EVAPORATION`
- `SEEPAGE`
- `OVERFLOW`
- `INEFFICIENCY`
- `CAPACITY_EXCEEDED`

Users can create custom loss reasons: `LossReason("infiltration")`

Import from `taqsim.common` or `taqsim.node`:
```python
from taqsim.common import LossReason, EVAPORATION, SEEPAGE, OVERFLOW, INEFFICIENCY, CAPACITY_EXCEEDED
# or (CAPACITY_EXCEEDED not exported from taqsim.node)
from taqsim.node import LossReason, EVAPORATION, SEEPAGE, OVERFLOW, INEFFICIENCY
```

## Parameter Bounds

Strategies can declare bounds for their tunable parameters to support optimization algorithms.

### Fixed Bounds

Use the `__bounds__` class variable for parameters with fixed bounds:

```python
@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "rate": (0.0, 100.0),  # min=0, max=100
    }
    rate: float = 50.0

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        return min(self.rate * dt, node.storage - node.dead_storage)
```

### Dynamic Bounds

Override the `bounds(node)` method for node-dependent constraints:

```python
@dataclass(frozen=True)
class CapacityBoundedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    rate: float = 50.0

    def bounds(self, node: Storage) -> dict[str, tuple[float, float]]:
        # Rate cannot exceed node capacity
        return {"rate": (0.0, node.capacity)}

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        return min(self.rate * dt, node.storage - node.dead_storage)
```

## Constraints

Strategies can declare constraints on their parameters using `__constraints__`:

```python
from typing import ClassVar
from taqsim.common import Strategy
from taqsim.constraints import SumToOne

@dataclass(frozen=True)
class MySplitRule(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("ratio_a", "ratio_b")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"ratio_a": (0, 1), "ratio_b": (0, 1)}
    __constraints__: ClassVar[tuple[SumToOne, ...]] = (SumToOne(("ratio_a", "ratio_b")),)

    ratio_a: float = 0.6
    ratio_b: float = 0.4
```

Constraints are validated at class definition - referencing unknown parameters raises `TypeError`.

For dynamic constraints based on node properties, override `constraints()`:

```python
def constraints(self, node: BaseNode) -> tuple[Constraint, ...]:
    return (SumToOne(("ratio_a", "ratio_b")),)
```

See [Constraints](../common/02_constraints.md) for details.

## Custom Implementations

### Equal Split Rule

```python
from dataclasses import dataclass
from taqsim.node import Splitter

@dataclass
class EqualSplit:
    def split(self, node: Splitter, amount: float, t: int) -> dict[str, float]:
        targets = node.targets
        if not targets:
            return {}
        share = amount / len(targets)
        return {target: share for target in targets}
```

### Proportional Split Rule

```python
@dataclass
class ProportionalSplit:
    weights: dict[str, float]

    def split(self, node: Splitter, amount: float, t: int) -> dict[str, float]:
        targets = node.targets
        total_weight = sum(self.weights.get(tgt, 0) for tgt in targets)
        if total_weight == 0:
            return {tgt: 0 for tgt in targets}
        return {
            target: amount * (self.weights.get(target, 0) / total_weight)
            for target in targets
        }
```

### Fixed Release Rule

```python
@dataclass
class FixedRelease:
    rate: float  # constant release rate

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        available = node.storage - node.dead_storage
        return min(self.rate * dt, available)
```

### Percentage Release Rule

```python
@dataclass
class PercentageRelease:
    fraction: float  # 0.0 to 1.0

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        available = node.storage - node.dead_storage
        return available * self.fraction
```

### Zero Loss Rule

```python
from taqsim.common import LossReason
from taqsim.node import Storage

@dataclass
class ZeroLoss:
    def calculate(self, node: Storage, t: int, dt: float) -> dict[LossReason, float]:
        return {}
```

### Evaporation Loss Rule

```python
from taqsim.common import EVAPORATION

@dataclass
class EvaporationLoss:
    rate: float  # evaporation rate per timestep

    def calculate(self, node: Storage, t: int, dt: float) -> dict[LossReason, float]:
        loss = min(self.rate * dt, node.storage)
        return {EVAPORATION: loss}
```

### Combined Loss Rule

```python
from taqsim.common import EVAPORATION, SEEPAGE

@dataclass
class CombinedLoss:
    evap_rate: float
    seepage_rate: float

    def calculate(self, node: Storage, t: int, dt: float) -> dict[LossReason, float]:
        return {
            EVAPORATION: self.evap_rate * dt,
            SEEPAGE: self.seepage_rate * dt
        }
```

## Usage

```python
from taqsim.node import Source, Storage, TimeSeries

# Create strategies
split = EqualSplit()
release = FixedRelease(rate=5.0)
loss = ZeroLoss()

# Use with nodes
source = Source(
    id="river",
    inflow=TimeSeries(values=[10.0, 15.0]),
    targets=["dam"],
    split_rule=split
)

storage = Storage(
    id="dam",
    capacity=1000.0,
    release_rule=release,
    loss_rule=loss,
    split_rule=split,
    targets=["downstream"]
)
```

## Protocol Checking

Strategies satisfy protocols via structural typing:

```python
from taqsim.node import SplitRule, ReleaseRule, LossRule

split = EqualSplit()
assert isinstance(split, SplitRule)

release = FixedRelease(rate=5.0)
assert isinstance(release, ReleaseRule)

loss = ZeroLoss()
assert isinstance(loss, LossRule)
```

## Construction-Time Validation

Strategies validate their parameters at construction time, failing fast if values are invalid.

### Bound Validation

If a parameter value falls outside its declared bounds, `BoundViolationError` is raised:

```python
@dataclass(frozen=True)
class FixedRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"rate": (0.0, 100.0)}
    rate: float = 50.0

# Valid construction
valid = FixedRelease(rate=50.0)

# Invalid - raises BoundViolationError
FixedRelease(rate=150.0)  # BoundViolationError: Parameter 'rate' value 150.0 outside bounds [0.0, 100.0]
```

### Constraint Validation

If constraint conditions are not satisfied, `ConstraintViolationError` is raised:

```python
@dataclass(frozen=True)
class AllocationSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("city", "farm")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"city": (0.0, 1.0), "farm": (0.0, 1.0)}
    __constraints__: ClassVar[tuple] = (SumToOne(params=("city", "farm")),)
    city: float = 0.6
    farm: float = 0.4

# Valid - ratios sum to 1.0
valid = AllocationSplit(city=0.6, farm=0.4)

# Invalid - raises ConstraintViolationError
AllocationSplit(city=0.6, farm=0.6)  # ConstraintViolationError: SumToOne violated
```

### Validation Order

1. **Bounds first**: All parameter bounds are checked
2. **Constraints second**: All constraints are validated
3. **Fail fast**: First violation raises an error

## Time-Varying Parameters

Some operational strategies have parameters that vary over time. For example, a release rate might differ in wet vs dry seasons, or allocation ratios might shift monthly.

### Declaration

Use `__time_varying__` to declare which parameters vary over time:

```python
@dataclass(frozen=True)
class SeasonalRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __time_varying__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"rate": (0.0, 100.0)}

    rate: tuple[float, ...] = (50.0, 60.0, 70.0)  # 3 timesteps

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        return min(self.rate[t] * dt, node.storage)
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `__time_varying__` | Declares which `__params__` vary over time |
| `tuple[float, ...]` field | Time-varying params stored as tuples |
| `self.rate[t]` | Access value for current timestep |

### Bounds Validation

Each element in a time-varying tuple is validated against bounds:

```python
# Valid - all elements within (0.0, 100.0)
SeasonalRelease(rate=(50.0, 60.0, 70.0))

# Invalid - 150.0 exceeds upper bound at index 2
SeasonalRelease(rate=(50.0, 60.0, 150.0))  # Raises BoundViolationError for rate[2]
```

### Constraints

Constraints on time-varying parameters are validated per-timestep. Use `__constraints__` directly - the `__post_init__` validation handles time-varying parameters automatically:

```python
from taqsim.constraints import Ordered, SumToOne

@dataclass(frozen=True)
class SeasonalSplit(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("r1", "r2")
    __time_varying__: ClassVar[tuple[str, ...]] = ("r1", "r2")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "r1": (0.0, 1.0), "r2": (0.0, 1.0)
    }
    __constraints__: ClassVar[tuple] = (SumToOne(params=("r1", "r2")),)

    r1: tuple[float, ...] = (0.6, 0.5, 0.4)
    r2: tuple[float, ...] = (0.4, 0.5, 0.6)
```

For each timestep `t`, `r1[t] + r2[t]` must equal 1.0.

The `Ordered` constraint also works with time-varying parameters:

```python
@dataclass(frozen=True)
class SeasonalBands(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("low", "high")
    __time_varying__: ClassVar[tuple[str, ...]] = ("low", "high")
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {
        "low": (0.0, 100.0), "high": (0.0, 100.0)
    }
    __constraints__: ClassVar[tuple] = (Ordered(low="low", high="high"),)

    low: tuple[float, ...] = (10.0, 20.0, 15.0)
    high: tuple[float, ...] = (50.0, 60.0, 55.0)

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        return min(self.high[t] * dt, max(self.low[t] * dt, node.storage * 0.1))
```

At construction, `low[t] <= high[t]` is validated for every timestep.

## Cyclical Time-Varying Parameters

Some parameters repeat in cycles, such as monthly allocation ratios that apply across multiple years. The `__cyclical__` declaration enables short tuples to work for longer simulations.

### Declaration

```python
@dataclass(frozen=True)
class SeasonalAllocation(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("city_fraction",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"city_fraction": (0.0, 1.0)}
    __time_varying__: ClassVar[tuple[str, ...]] = ("city_fraction",)
    __cyclical__: ClassVar[tuple[str, ...]] = ("city_fraction",)

    city_fraction: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.3, 0.4)  # 12 monthly values
```

### Key Elements

| Element | Purpose |
|---------|---------|
| `__cyclical__` | Declares which time-varying params repeat cyclically |
| Must be subset of `__time_varying__` | Cyclical params must also be declared time-varying |
| Implicit cycle length | Cycle length equals tuple length |

### Behavior

- **Access pattern**: `value[t % len(value)]` for cyclical params
- **Simulation validation**: Cyclical params skip length validation (no InsufficientLengthError)
- **Constraint validation**: For cyclical-only strategies, validates constraints at each cycle position

### Example: Monthly Allocation for Multi-Year Simulation

```python
# 12 monthly values work for 120-month (10-year) simulation
system.simulate(120)  # No error - city_fraction cycles through its 12 values
```

### Comparison: Time-Varying vs Cyclical

| Aspect | Time-Varying | Cyclical |
|--------|--------------|----------|
| Tuple length | Must match simulation timesteps | Any length (cycles) |
| Access pattern | `value[t]` | `value[t % len(value)]` |
| Length validation | Raises InsufficientLengthError if too short | Skipped |
| Use case | Unique value per timestep | Repeating patterns (seasonal, weekly) |

## Strategy Tags and Metadata

Strategies support class-level tags and metadata via `ClassVar` declarations:

```python
@dataclass(frozen=True)
class SeasonalRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __tags__: ClassVar[frozenset[str]] = frozenset({"operational", "seasonal"})
    __metadata__: ClassVar[Mapping[str, object]] = {"version": 2}

    rate: tuple[float, ...] = (50.0, 60.0, 70.0)

# Access via methods
strategy = SeasonalRelease()
strategy.tags()      # frozenset({'operational', 'seasonal'})
strategy.metadata()  # {'version': 2}
```

| Element | Purpose |
|---------|---------|
| `__tags__` | Class-level frozenset of string labels |
| `__metadata__` | Class-level mapping of key-value data |
| `tags()` | Accessor method returning `__tags__` |
| `metadata()` | Accessor method returning `__metadata__` |

Note: Strategy tags/metadata are type-level (defined at class definition), not instance-level like nodes and edges.

See [Tags and Metadata](../common/03_tags_metadata.md) for details.