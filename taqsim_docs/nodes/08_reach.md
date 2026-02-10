# Reach

## Purpose

The Reach node models physical transport processes within a water channel, canal, or river segment. It handles:

- **Routing delay**: Water entering the reach may take multiple timesteps to exit, modeled by a `RoutingModel`
- **Attenuation**: Peak flows may be dampened as water travels through the reach
- **Transit losses**: Losses (seepage, evaporation from open channels) applied to routed outflow via a `ReachLossRule`

Reach separates transport physics from connectivity. Edges define topology (which nodes connect); Reach nodes model what happens to water during transport.

## Init Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `routing_model` | `RoutingModel` | Yes | Physical routing model (delay, attenuation) |
| `loss_rule` | `ReachLossRule` | Yes | Transit loss calculation |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

Both `routing_model` and `loss_rule` are required. Construction raises `ValueError` if either is `None`.

## Properties

| Property | Type | Description |
|----------|------|-------------|
| `water_in_transit` | `float` | Volume of water currently stored within the routing model's internal state |

```python
reach = Reach(id="canal", routing_model=NoRouting(), loss_rule=NoReachLoss())
reach.water_in_transit  # 0.0 for NoRouting
```

## Update Pipeline

Each timestep, the Reach processes water in six stages:

```
receive -> enter -> route -> exit -> lose -> transit snapshot -> output
```

### 1. Receive

Water arrives via `receive(amount, source_id, t)`. Multiple upstream nodes may deliver water in a single timestep. Each delivery records a `WaterReceived` event and accumulates into `_received_this_step`.

### 2. Enter

The accumulated inflow is recorded as `WaterEnteredReach(amount, t)`.

### 3. Route

The routing model transforms the current state and inflow into an outflow and new state:

```python
outflow, new_state = routing_model.route(reach, inflow, state, t)
```

The routing model owns its internal state representation. Simple models (e.g., `NoRouting`) use `None` and return inflow as outflow immediately. Delay-based models maintain a buffer of in-transit volumes.

### 4. Exit

The routed outflow is recorded as `WaterExitedReach(amount, t)` — the volume exiting the channel before transit losses are applied.

### 5. Lose

Transit losses are calculated against the routed outflow:

```python
losses = loss_rule.calculate(reach, outflow, t)
```

If total losses exceed outflow, they are scaled proportionally so net outflow is never negative. Each non-zero loss records a `WaterLost(amount, reason, t)` event.

### 6. Transit Snapshot and Output

A `WaterInTransit(amount, t)` event captures the current volume in transit (from `routing_model.storage(state)`).

If net outflow (outflow minus losses) is positive, a `WaterOutput(amount, t)` event is recorded for downstream routing.

## Events

| Event | Fields | When |
|-------|--------|------|
| `WaterReceived` | `amount, source_id, t` | Each delivery from upstream |
| `WaterEnteredReach` | `amount, t` | Start of update (total inflow) |
| `WaterExitedReach` | `amount, t` | Routed outflow before losses |
| `WaterLost` | `amount, reason, t` | Per loss reason after routing |
| `WaterInTransit` | `amount, t` | Snapshot of water in routing state |
| `WaterOutput` | `amount, t` | Net outflow for downstream |

## Default Implementations

### NoRouting

Pass-through routing. No delay, no attenuation. Outflow equals inflow, zero water in transit.

```python
from taqsim.node import NoRouting

@dataclass(frozen=True)
class NoRouting:
    def initial_state(self, reach: Reach) -> None:
        return None

    def route(self, reach: Reach, inflow: float, state: None, t: Timestep) -> tuple[float, None]:
        return (inflow, None)

    def storage(self, state: None) -> float:
        return 0.0
```

### NoReachLoss

No transit losses. Returns an empty loss dictionary.

```python
from taqsim.node import NoReachLoss

@dataclass(frozen=True)
class NoReachLoss:
    def calculate(self, reach: Reach, flow: float, t: Timestep) -> dict[LossReason, float]:
        return {}
```

## Strategy Protocols

### RoutingModel

Physical model for transport routing. **Not** a `Strategy` -- not optimizable.

```python
@runtime_checkable
class RoutingModel(Protocol):
    def initial_state(self, reach: Reach) -> Any: ...
    def route(self, reach: Reach, inflow: float, state: Any, t: Timestep) -> tuple[float, Any]: ...
    def storage(self, state: Any) -> float: ...
```

| Method | Purpose |
|--------|---------|
| `initial_state(reach)` | Returns the initial routing state |
| `route(reach, inflow, state, t)` | Returns `(outflow, new_state)` |
| `storage(state)` | Returns volume of water in transit |

### ReachLossRule

Physical model for transit losses. **Not** a `Strategy` -- not optimizable.

```python
@runtime_checkable
class ReachLossRule(Protocol):
    def calculate(self, reach: Reach, flow: float, t: Timestep) -> dict[LossReason, float]: ...
```

Receives the routed **outflow** (post-routing), not the raw inflow. Losses are applied after routing.

## Example: Reach in a Network

```python
from taqsim.node import Source, Reach, Sink, NoRouting, NoReachLoss, TimeSeries
from taqsim.edge import Edge

source = Source(id="river", inflow=TimeSeries([100.0] * 12))
channel = Reach(id="canal", routing_model=NoRouting(), loss_rule=NoReachLoss())
outlet = Sink(id="outlet")

# Edges define topology; Reach handles transport physics
# source -> canal -> outlet
```

## Reset

Calling `reset()` reinitializes the routing state via `routing_model.initial_state(reach)` and clears the received counter.
