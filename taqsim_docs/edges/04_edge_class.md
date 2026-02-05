# Edge Class

## Overview

The `Edge` class represents a connection between two nodes, handling water transport with capacity constraints and losses.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | `str` | Yes | - | Unique identifier |
| `source` | `str` | Yes | - | Source node ID |
| `target` | `str` | Yes | - | Target node ID |
| `capacity` | `float` | Yes | - | Maximum flow capacity |
| `loss_rule` | `EdgeLossRule` | Yes | - | Loss calculation strategy |
| `targets` | `list[str]` | No | `[]` | Additional target nodes |

## Validation Rules

The Edge validates parameters on creation:

- `id` cannot be empty
- `source` cannot be empty
- `target` cannot be empty
- `capacity` must be positive
- `loss_rule` is required

```python
# These raise ValueError:
Edge(id="", source="a", target="b", capacity=100, loss_rule=rule)  # empty id
Edge(id="e", source="", target="b", capacity=100, loss_rule=rule)  # empty source
Edge(id="e", source="a", target="b", capacity=0, loss_rule=rule)   # zero capacity
Edge(id="e", source="a", target="b", capacity=100, loss_rule=None) # no loss rule
```

## Methods

### receive(amount, t) -> float

Accept water from the source node.

```python
received = edge.receive(100.0, t=0)
# Records WaterReceived event
# Returns amount received
```

### update(t, dt) -> float

Process accumulated flow and deliver to target.

```python
delivered = edge.update(t=0, dt=1.0)
# Returns amount delivered after losses
```

### record(event) -> None

Append an event to the event log.

```python
edge.record(WaterReceived(amount=50.0, t=0))
```

### events_of_type(event_type) -> list[T]

Filter events by type.

```python
deliveries = edge.events_of_type(WaterDelivered)
losses = edge.events_of_type(WaterLost)
```

### clear_events() -> None

Reset the event log. Primarily for testing.

```python
edge.clear_events()
assert len(edge.events) == 0
```

### trace(event_type, field="amount") -> Trace

Create a `Trace` object from events of a specific type.

```python
from taqsim.edge import WaterDelivered

trace = edge.trace(WaterDelivered)
# Returns Trace.from_events(edge.events_of_type(WaterDelivered), field="amount")
```

### reset() -> None

Reset edge to initial state for a fresh simulation run. Clears accumulated events and step accumulator.

```python
edge.reset()
# Equivalent to:
# edge.clear_events()
# edge._received_this_step = 0.0
```

## Update Cycle

The `update()` method performs these steps:

1. **Capacity Check**: If received > capacity, record `WaterLost(reason=CAPACITY_EXCEEDED)` and cap flow
2. **Loss Calculation**: Apply `loss_rule.calculate()` to determine losses
3. **Loss Scaling**: If total losses > available flow, scale proportionally
4. **Record Losses**: Create `WaterLost` event for each loss type
5. **Calculate Delivered**: delivered = received - total_losses
6. **Record Delivery**: Create `WaterDelivered` event
7. **Reset**: Clear accumulated flow for next timestep
8. **Return**: Return delivered amount

## Usage Examples

### Basic Edge

```python
from taqsim.edge import Edge, EdgeLossRule
from taqsim.common import LossReason
from dataclasses import dataclass

@dataclass
class ZeroLoss:
    def calculate(self, edge: Edge, flow: float, t: int, dt: float) -> dict[LossReason, float]:
        return {}

edge = Edge(
    id="canal_1",
    source="reservoir",
    target="farm",
    capacity=100.0,
    loss_rule=ZeroLoss()
)

# Receive water
edge.receive(80.0, t=0)

# Process and deliver
delivered = edge.update(t=0, dt=1.0)
assert delivered == 80.0
```

### Edge with Losses

```python
@dataclass
class SeepageLoss:
    fraction: float

    def calculate(self, edge: Edge, flow: float, t: int, dt: float) -> dict[LossReason, float]:
        return {LossReason.SEEPAGE: flow * self.fraction}

edge = Edge(
    id="leaky_canal",
    source="reservoir",
    target="farm",
    capacity=100.0,
    loss_rule=SeepageLoss(fraction=0.1)  # 10% loss
)

edge.receive(100.0, t=0)
delivered = edge.update(t=0, dt=1.0)
assert delivered == 90.0  # 100 - 10% loss
```

### Capacity Exceeded

```python
from taqsim.common import LossReason

edge = Edge(
    id="small_pipe",
    source="tank",
    target="outlet",
    capacity=50.0,
    loss_rule=ZeroLoss()
)

edge.receive(100.0, t=0)  # exceeds capacity
delivered = edge.update(t=0, dt=1.0)

assert delivered == 50.0  # capped at capacity

# Check for capacity exceeded via WaterLost events
capacity_losses = [
    e for e in edge.events_of_type(WaterLost)
    if e.reason == LossReason.CAPACITY_EXCEEDED
]
assert len(capacity_losses) == 1
assert capacity_losses[0].amount == 50.0  # 100 - 50 capacity
```

## Properties

### events

The append-only event log.

```python
edge.events  # list[EdgeEvent]
```

## Internal State

The edge tracks `_received_this_step` internally to accumulate flow between `receive()` calls before `update()`. This is reset to 0 after each `update()`.
