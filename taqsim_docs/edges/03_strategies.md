# Strategy Protocols

> **Note**: `EdgeLossRule` is a physical model representing transport losses, not an operational strategy. It does **not** inherit from `Strategy` and is not included in parameter optimization. For optimizable strategies, see [Node Strategies](../nodes/05_strategies.md).

## Overview

Strategies define configurable behaviors for edges. Each is a `Protocol` that allows custom implementations to be injected at edge creation.

## Protocol Definitions

### EdgeLossRule

Controls how transport losses are calculated.

```python
@runtime_checkable
class EdgeLossRule(Protocol):
    def calculate(
        self,
        edge: Edge,       # the edge instance (access capacity via edge.capacity)
        flow: float,      # current flow volume
        t: int,           # timestep
        dt: float         # timestep duration
    ) -> dict[LossReason, float]: ...  # {reason: amount}
```

`LossReason` is a typed string class with predefined constants:
- `EVAPORATION`
- `SEEPAGE`
- `OVERFLOW`
- `INEFFICIENCY`
- `CAPACITY_EXCEEDED`

## Custom Implementations

### Zero Loss Rule

No transport losses.

```python
from dataclasses import dataclass
from taqsim.common import LossReason
from taqsim.edge import Edge

@dataclass
class ZeroLoss:
    def calculate(
        self, edge: Edge, flow: float, t: int, dt: float
    ) -> dict[LossReason, float]:
        return {}
```

### Percentage Loss Rule

Constant percentage loss.

```python
from taqsim.common import SEEPAGE

@dataclass
class PercentageLoss:
    fraction: float  # 0.0 to 1.0
    reason: LossReason = SEEPAGE

    def calculate(
        self, edge: Edge, flow: float, t: int, dt: float
    ) -> dict[LossReason, float]:
        return {self.reason: flow * self.fraction}
```

### Fixed Rate Loss Rule

Fixed loss rate per timestep.

```python
@dataclass
class FixedRateLoss:
    rate: float  # loss per unit time
    reason: LossReason = SEEPAGE

    def calculate(
        self, edge: Edge, flow: float, t: int, dt: float
    ) -> dict[LossReason, float]:
        loss = min(self.rate * dt, flow)  # don't lose more than available
        return {self.reason: loss}
```

### Combined Loss Rule

Multiple loss mechanisms.

```python
from taqsim.common import SEEPAGE, EVAPORATION

@dataclass
class CombinedLoss:
    seepage_fraction: float = 0.02
    evap_fraction: float = 0.01

    def calculate(
        self, edge: Edge, flow: float, t: int, dt: float
    ) -> dict[LossReason, float]:
        return {
            SEEPAGE: flow * self.seepage_fraction,
            EVAPORATION: flow * self.evap_fraction,
        }
```

## Usage

```python
from taqsim.edge import Edge

# Create loss rule
loss_rule = PercentageLoss(fraction=0.05)

# Use with edge
edge = Edge(
    id="canal",
    source="reservoir",
    target="farm",
    capacity=100.0,
    loss_rule=loss_rule
)
```

## Protocol Checking

Strategies satisfy protocols via structural typing:

```python
from taqsim.edge.losses import EdgeLossRule

loss = ZeroLoss()
assert isinstance(loss, EdgeLossRule)

loss = PercentageLoss(fraction=0.05)
assert isinstance(loss, EdgeLossRule)
```

## Loss Scaling

The Edge automatically scales losses if they would exceed available flow:

```python
# If loss_rule returns losses > received flow:
# losses are proportionally scaled down to equal available flow
```

This prevents negative deliveries while preserving the relative proportions of different loss types.
