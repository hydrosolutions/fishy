# Creating Custom Objectives

## Overview

Custom objectives let you optimize for domain-specific goals beyond the built-ins. This guide covers creating, structuring, and registering custom objectives.

## Anatomy of an Objective Factory

An objective factory is a function that returns an `Objective`:

```python
from taqsim.objective import Objective

def my_objective(target_id: str, *, priority: int = 1) -> Objective:
    def evaluate(system):
        # Compute score from system state
        return score

    return Objective(
        name=f"{target_id}.my_metric",
        direction="minimize",  # or "maximize"
        evaluate=evaluate,
        priority=priority,
    )
```

## Example: Hydropower Production

Maximize energy generated from water releases through a turbine. This example demonstrates:
- **Multi-node objectives** (reservoir + turbine)
- **@lift decorator** for physics transformations
- **Trace arithmetic** for element-wise calculations

```python
from taqsim.objective import Objective, lift
from taqsim.node.events import WaterStored, WaterReceived

GRAVITY = 9.81  # m/s^2
WATER_DENSITY = 1000  # kg/m^3

@lift
def vol_to_head(volume: float) -> float:
    # Simplified: head increases with storage
    # Real reservoirs use area-volume-elevation curves
    return (volume / 1_000_000) ** 0.5 * 50  # meters

def hydropower(
    reservoir_id: str,
    turbine_id: str,
    efficiency: float = 0.85,
    *,
    priority: int = 1,
) -> Objective:
    def evaluate(system):
        reservoir = system.nodes[reservoir_id]
        turbine = system.nodes[turbine_id]

        # Storage → Head (using @lift makes this work on Traces)
        storage = reservoir.trace(WaterStored)
        head = vol_to_head(storage)  # Returns Trace, not float!

        # Flow through turbine
        flow = turbine.trace(WaterReceived)

        # Power = ρ * g * Q * H * η (element-wise Trace multiplication)
        power = head * flow * GRAVITY * WATER_DENSITY * efficiency

        return power.sum()

    return Objective(
        name=f"{turbine_id}.hydropower",
        direction="maximize",
        evaluate=evaluate,
        priority=priority,
    )
```

Usage:

```python
from taqsim.objective import maximize, minimize

# Register once (typically at module initialization)
maximize.register("hydropower", hydropower)

# Use via fluent API
objectives = [
    maximize.hydropower("reservoir", "turbine", efficiency=0.9),
    minimize.spill("reservoir"),
]
```

## Example: Storage Target

Minimize deviation from a target storage level:

```python
from taqsim.objective import Objective

def storage_target(reservoir_id: str, target: float, *, priority: int = 1) -> Objective:
    def evaluate(system):
        node = system.nodes[reservoir_id]
        final_storage = node.storage  # Derived from events
        return abs(final_storage - target)

    return Objective(
        name=f"{reservoir_id}.storage_target",
        direction="minimize",
        evaluate=evaluate,
        priority=priority,
    )
```

## Registering Custom Objectives

Register with a registry for fluent API access:

```python
from taqsim.objective import minimize, maximize

# Register with appropriate registry
maximize.register("hydropower", hydropower)
minimize.register("storage_target", storage_target)

# Now accessible via fluent API
obj = maximize.hydropower("reservoir", "turbine", efficiency=0.9)
obj = minimize.storage_target("reservoir", target=1000000)
```

## Using Trace for Complex Computations

Trace enables functional transformations:

```python
from taqsim.objective import Objective
from taqsim.node.events import WaterReleased

def peak_flow_penalty(node_id: str, threshold: float, *, priority: int = 1) -> Objective:
    def evaluate(system):
        node = system.nodes[node_id]
        releases = node.trace(WaterReleased)

        # Penalize flows exceeding threshold
        excess = releases.map(lambda q: max(0, q - threshold))
        penalties = excess ** 2  # Quadratic penalty
        return penalties.sum()

    return Objective(
        name=f"{node_id}.peak_penalty",
        direction="minimize",
        evaluate=evaluate,
        priority=priority,
    )
```

## Edge-Based Objectives

Edges also support the `.trace()` method for building objectives based on flow events:

```python
from taqsim.edge.events import WaterDelivered

def channel_utilization(edge_id: str, capacity: float, *, priority: int = 1) -> Objective:
    def evaluate(system):
        edge = system.edges[edge_id]
        transfers = edge.trace(WaterDelivered)

        # Calculate utilization as fraction of capacity
        utilization = transfers.map(lambda q: q / capacity)
        return utilization.mean()

    return Objective(
        name=f"{edge_id}.utilization",
        direction="maximize",
        evaluate=evaluate,
        priority=priority,
    )
```

## Multi-Event Objectives

Combine multiple event types:

```python
from taqsim.objective import Objective
from taqsim.node.events import WaterReceived, DeficitRecorded

def net_benefit(demand_id: str, *, priority: int = 1) -> Objective:
    def evaluate(system):
        node = system.nodes[demand_id]

        delivered = node.trace(WaterReceived)
        deficits = node.trace(DeficitRecorded, field="deficit")

        # Benefit from delivery minus penalty for deficit
        benefit = delivered.sum()
        penalty = deficits.sum() * 2  # 2x penalty for unmet demand
        return benefit - penalty

    return Objective(
        name=f"{demand_id}.net_benefit",
        direction="maximize",
        evaluate=evaluate,
        priority=priority,
    )
```

## Best Practices

1. **Validate targets** - Check that nodes/edges exist before accessing
2. **Use descriptive names** - Include target_id in the objective name
3. **Accept priority** - Allow users to weight objectives
4. **Document units** - Be clear about what the score represents
5. **Keep evaluation pure** - Don't modify system state in evaluate
