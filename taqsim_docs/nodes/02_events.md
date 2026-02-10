# Event System

## Overview

The `taqsim.node` module uses event sourcing. All events are frozen dataclasses with `slots=True` for immutability and memory efficiency.

## Common Fields

All events share:
- `t: int` - timestep when event occurred
- `amount: float` - water volume in m³

## Event Types

### WaterGenerated

Source nodes produce water.

```python
WaterGenerated(amount=100.0, t=0)
```

### WaterReceived

Node receives water from upstream.

```python
WaterReceived(amount=50.0, source_id="upstream_node", t=0)
```

### WaterStored

Water added to storage.

```python
WaterStored(amount=30.0, t=0)
```

### WaterReleased

Water released from storage.

```python
WaterReleased(amount=20.0, t=0)
```

### WaterLost

Physical losses (evaporation, seepage, overflow, inefficiency, or custom reasons).

```python
from taqsim.common import LossReason, EVAPORATION, SEEPAGE, OVERFLOW, INEFFICIENCY

# Using standard constants
WaterLost(amount=5.0, reason=EVAPORATION, t=0)
WaterLost(amount=2.0, reason=SEEPAGE, t=0)
WaterLost(amount=100.0, reason=OVERFLOW, t=0)
WaterLost(amount=20.0, reason=INEFFICIENCY, t=0)  # Delivery losses in Demand nodes

# Custom loss reasons
WaterLost(amount=10.0, reason=LossReason("infiltration"), t=0)
```

### WaterConsumed

Water physically consumed (leaving the water system). For partially consumptive
demands (e.g., cooling water where only a fraction evaporates), this records
only the portion that leaves the system. Water returned downstream appears in
`WaterOutput` instead.

```python
WaterConsumed(amount=40.0, t=0)
```

### WaterOutput

Water available for downstream routing. Used by single-output nodes (Source, Storage, Demand, PassThrough, Reach). The `WaterSystem` orchestrator routes this to the appropriate edge.

```python
WaterOutput(amount=60.0, t=0)
```

### WaterPassedThrough

Records water passing through a PassThrough node (for analysis, e.g., turbine power calculation).

```python
WaterPassedThrough(amount=100.0, t=0)
```

### WaterSpilled

Water that exceeds capacity and cannot be stored or processed.

**Emitted by:**
- `Storage` — when inflow exceeds available storage capacity (overflow)
- `PassThrough` — when flow exceeds `capacity` parameter (if set)

```python
WaterSpilled(amount=50.0, t=0)
```

### WaterDistributed

Water sent to a specific downstream target. Used by Splitter nodes to distribute to multiple targets.

```python
WaterDistributed(amount=60.0, target_id="downstream_edge", t=0)
```

### DeficitRecorded

Unmet demand or minimum flow requirement.

```python
DeficitRecorded(required=100.0, actual=80.0, deficit=20.0, t=0)
```

### WaterEnteredReach

Water entering a Reach node at the upstream end. Records the total inflow before routing and losses are applied.

**Emitted by:** `Reach`

```python
WaterEnteredReach(amount=100.0, t=0)
```

### WaterExitedReach

Water exiting a Reach node at the downstream end. Records the routed outflow after the routing model processes it but before losses.

**Emitted by:** `Reach`

```python
WaterExitedReach(amount=95.0, t=0)
```

### WaterInTransit

Snapshot of water currently stored within the Reach's routing model (e.g., water delayed in transit due to travel time). Recorded each timestep after routing.

**Emitted by:** `Reach`

```python
WaterInTransit(amount=50.0, t=0)
```

## Deriving State from Events

Current storage:

```python
def current_storage(node: BaseNode, initial: float = 0.0) -> float:
    balance = initial
    for event in node.events:
        match event:
            case WaterStored(amount=a):
                balance += a
            case WaterReleased(amount=a) | WaterLost(amount=a):
                balance -= a
    return balance
```

Total generated:

```python
total = sum(e.amount for e in node.events_of_type(WaterGenerated))
```

## Event Ordering

Within a timestep, events are recorded in `update()` execution order:

1. WaterGenerated (sources)
2. WaterReceived
3. WaterStored / WaterSpilled
4. WaterLost
5. WaterReleased
6. WaterConsumed
7. WaterPassedThrough (PassThrough nodes)
8. WaterEnteredReach (Reach nodes)
9. WaterExitedReach (Reach nodes)
10. WaterInTransit (Reach nodes)
11. WaterOutput (single-output nodes) / WaterDistributed (Splitter)

## Querying Events

```python
# All events at timestep 5
events_t5 = node.events_at(5)

# All storage events
stored = node.events_of_type(WaterStored)

# Total losses
losses = sum(e.amount for e in node.events_of_type(WaterLost))

# Losses by reason (using constants from taqsim.common)
evap = sum(
    e.amount for e in node.events_of_type(WaterLost)
    if e.reason == EVAPORATION
)

# Reach transit water
transit = node.events_of_type(WaterInTransit)
```

## NodeEvent Union Type

All event types are part of the `NodeEvent` union:

```python
NodeEvent = (
    WaterGenerated | WaterReceived | WaterStored | WaterReleased |
    WaterLost | WaterSpilled | WaterConsumed | WaterDistributed |
    WaterOutput | WaterPassedThrough | DeficitRecorded |
    WaterEnteredReach | WaterExitedReach | WaterInTransit
)
```
