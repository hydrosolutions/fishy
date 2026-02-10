# Node Types

## Overview

Seven node types compose the water system. Each combines specific capabilities. Nodes process water and record events but **do not know their targets** — topology is derived from edges by `WaterSystem`.

| Node        | Receives | Pipeline (private)                    | Output Event     |
|-------------|----------|---------------------------------------|------------------|
| Source      |          | `_generate`                           | WaterOutput      |
| PassThrough | yes      | (pass-through)                        | WaterOutput      |
| Splitter    | yes      | `_distribute` (via split_policy)      | WaterDistributed |
| Demand      | yes      | `_consume`                            | WaterOutput      |
| Storage     | yes      | `_store`, `_lose`, `_release`         | WaterOutput      |
| Reach       | yes      | route, lose, transit snapshot         | WaterOutput      |
| Sink        | yes      | (terminal)                            | —                |

---

## Source

Water entry point. Generates inflow from a TimeSeries.

### Pipeline

- `_generate`: Produces water from `inflow` TimeSeries

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `inflow` | `TimeSeries` | Yes | Inflow rates per timestep |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Events Recorded

- `WaterGenerated(amount, t)` — when water is generated
- `WaterOutput(amount, t)` — water available for downstream

### Update Cycle

1. Generate water: `amount = inflow[t] * dt`
2. Record `WaterOutput` for routing

### Example

```python
from taqsim.node import Source, TimeSeries

source = Source(
    id="river_intake",
    inflow=TimeSeries(values=[100.0, 150.0, 120.0])
)
```

---

## PassThrough

Transparent node for turbines, measurement points, or junctions. Passes 100% of received water downstream.

### Capabilities

- **Receives**: Accepts water from upstream

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `capacity` | `float \| None` | No | Maximum flow capacity per timestep. None = unlimited (default) |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Capacity Limiting

When `capacity` is set, the PassThrough node limits flow to the specified value:

- Flow up to capacity passes through normally
- Excess flow above capacity is recorded as `WaterSpilled`
- Only flow within capacity continues downstream

**Use cases:**
- **Hydropower turbines**: Max flow through turbine (excess bypasses, generates no power)
- **City infrastructure intake**: Max flow distribution network handles (excess = overflow risk)
- **Canal sections**: Measurement points with known capacity limits
- **Aqueducts/pipelines**: Transport infrastructure with throughput limits

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives
- `WaterPassedThrough(amount, t)` — flow within capacity
- `WaterSpilled(amount, t)` — flow exceeding capacity (when capacity is set)
- `WaterOutput(amount, t)` — water available for downstream

### Update Cycle

1. Record `WaterPassedThrough` for the accumulated amount
2. Record `WaterOutput` for routing
3. Reset counter

### Example

```python
from taqsim.node import PassThrough

turbine = PassThrough(id="hydropower_turbine")
```

### Example with Capacity

```python
from taqsim.node import PassThrough

# Hydropower turbine with max 500 m³/timestep capacity
turbine = PassThrough(id="hydropower_turbine", capacity=500.0)

# City intake with limited distribution capacity
city_intake = PassThrough(id="city_intake", capacity=1000.0)
```

---

## Splitter

Distribution node. Receives water and splits among multiple targets using a split rule.

### Capabilities

- **Receives**: Accepts water from upstream

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `split_policy` | `SplitPolicy` | Yes | Distribution rule |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

> **Note**: Targets are derived from edges by `WaterSystem` and populated via `_set_targets()` during validation.

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives
- `WaterDistributed(amount, target_id, t)` — for each target edge

### Update Cycle

1. Apply split rule to distribute water
2. Record `WaterDistributed` for each target
3. Reset counter

### Example

```python
from taqsim.node import Splitter

splitter = Splitter(
    id="canal_junction",
    split_policy=proportional_split
)
```

---

## Demand

Consumption node. Receives water, consumes requirement, passes remainder downstream.

### Pipeline

- **Receives**: Accepts water from upstream via `receive()`
- `_consume`: Withdraws water to meet requirement

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `requirement` | `TimeSeries` | Yes | Demand rates per timestep |
| `consumption_fraction` | `float` | No | Fraction of met demand consumed (0.0-1.0, default: 1.0) |
| `efficiency` | `float` | No | Delivery efficiency (0.0-1.0 exclusive-inclusive, default: 1.0) |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Consumption Fraction

Controls how much of the met demand is physically consumed (leaves the system) vs returned downstream:

- `1.0` (default): Fully consumptive (irrigation, drinking water) - all met demand leaves system
- `0.0`: Fully non-consumptive (hydropower, cooling return) - all met demand returns downstream
- `0.0-1.0`: Partially consumptive (cooling tower with evaporative loss)

**Example**: With `consumption_fraction=0.3`, if demand receives 100 m³ and requirement is 80 m³:
- Met demand: 80 m³
- Consumed: 80 × 0.3 = 24 m³ (recorded as `WaterConsumed`)
- Returned: 80 × 0.7 = 56 m³
- Excess: 100 - 80 = 20 m³
- Total output: 56 + 20 = 76 m³ (recorded as `WaterOutput`)

### Efficiency

Models delivery losses (conveyance, distribution, application inefficiencies). To deliver a given amount to the demand point, the system must withdraw more water:

- `1.0` (default): No delivery losses
- `0.8`: 80% efficient - to deliver 80 m³, must withdraw 100 m³ (20 m³ lost)

Losses are recorded as `WaterLost` events with reason `INEFFICIENCY`.

**Combined example**: With `efficiency=0.8` and `consumption_fraction=0.5`:
- Requirement: 80 m³, Available: 100 m³
- Withdrawal: 100 m³ (to deliver 80)
- Loss: 20 m³ (recorded as WaterLost)
- Delivered: 80 m³
- Consumed: 40 m³ (50% of delivered)
- Returned: 40 m³ (in WaterOutput)

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives
- `WaterConsumed(amount, t)` — physically consumed portion of met demand
- `WaterLost(amount, reason, t)` — delivery losses when efficiency < 1.0
- `DeficitRecorded(required, actual, deficit, t)` — if demand not met
- `WaterOutput(amount, t)` — remaining water for downstream

### Deficit Tracking

When received water is less than required, a `DeficitRecorded` event captures:
- `required`: demand for the timestep
- `actual`: amount consumed
- `deficit`: unmet demand

### Update Cycle

1. Consume up to requirement: `consumed = min(received, requirement[t] * dt)`
2. Record deficit if `consumed < required`
3. Record `WaterOutput` for remaining water
4. Reset counter

### Example

```python
from taqsim.node import Demand, TimeSeries

city = Demand(
    id="city_water",
    requirement=TimeSeries(values=[50.0, 60.0, 55.0])
)
```

---

## Storage

Reservoir node. Receives, stores, loses, releases, and outputs water.

### Pipeline

- **Receives**: Accepts water from upstream via `receive()`
- `_store`: Buffers water up to capacity
- `_lose`: Physical losses (evaporation, seepage)
- `_release`: Controlled release via release_policy

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `capacity` | `float` | Yes | Maximum storage volume [m³] |
| `initial_storage` | `float` | No | Starting volume (default: 0) [m³] |
| `dead_storage` | `float` | No | Volume of water that cannot be released (default: 0.0) [m³] |
| `release_policy` | `ReleasePolicy` | Yes | Release calculation |
| `loss_rule` | `LossRule` | Yes | Loss calculation |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Validation

- `capacity` must be positive
- `initial_storage` must be >= 0 and <= capacity
- `dead_storage` cannot be negative
- `dead_storage` cannot exceed capacity

### Note on Dead Storage

Water below the dead storage level cannot be released (it is below the lowest outlet), but losses still apply to the full storage volume. Water at dead level can still evaporate or seep.

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives
- `WaterStored(amount, t)` — amount added to storage
- `WaterSpilled(amount, t)` — overflow when capacity exceeded
- `WaterLost(amount, reason, t)` — per loss type (evaporation, seepage)
- `WaterReleased(amount, t)` — controlled release
- `WaterOutput(amount, t)` — released + spilled for downstream

### Spillway Handling

When inflow exceeds available capacity:
1. Store up to capacity
2. Record `WaterSpilled` for overflow
3. Spilled water joins released water in `WaterOutput`

### Loss Handling

Losses are scaled if they exceed current storage:
```python
if total_loss > current_storage:
    scale = current_storage / total_loss
    losses = {reason: amount * scale for reason, amount in losses.items()}
```

### Storage Property

Access current storage level:
```python
reservoir.storage  # returns current volume
```

### Update Cycle

1. Store inflow (record spill if overflow)
2. Calculate and apply losses
3. Calculate and apply release
4. Record `WaterOutput` for (released + spilled)
5. Reset counter

### Example

```python
from taqsim.node import Storage

reservoir = Storage(
    id="main_dam",
    capacity=10000.0,
    initial_storage=5000.0,
    release_policy=fixed_release,
    loss_rule=evaporation_loss
)

# Check current storage
print(reservoir.storage)  # 5000.0
```

---

## Reach

Transport node. Models physical transport processes: routing delay, attenuation, and transit losses. Water enters the reach, is routed through (potentially with delay), losses are applied to the routed outflow, and the net outflow continues downstream.

### Pipeline

- **Receives**: Accepts water from upstream via `receive()`
- Route: Transforms inflow through routing_model (delay, attenuation)
- Lose: Transit losses applied to routed outflow via loss_rule

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `routing_model` | `RoutingModel` | Yes | Routing physics (delay, attenuation) |
| `loss_rule` | `ReachLossRule` | Yes | Transit loss calculation |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Properties

- `water_in_transit` — current volume of water stored within the routing model's internal state

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives
- `WaterEnteredReach(amount, t)` — total inflow entering the channel this timestep
- `WaterLost(amount, reason, t)` — transit losses (per loss reason)
- `WaterInTransit(amount, t)` — snapshot of water currently in transit after routing
- `WaterOutput(amount, t)` — net outflow available for downstream

### Loss Handling

Losses are applied to the routed outflow. If total losses exceed the outflow, they are scaled proportionally:
```python
if total_loss > outflow:
    scale = outflow / total_loss
    losses = {reason: amount * scale for reason, amount in losses.items()}
```

### Update Cycle

1. Record `WaterEnteredReach` for accumulated inflow
2. Route: transform (state, inflow) into (outflow, new_state) via `routing_model.route()`
3. Lose: calculate and apply transit losses via `loss_rule.calculate()`
4. Record `WaterInTransit` snapshot
5. Record `WaterOutput` for net outflow (outflow minus losses)
6. Reset counter

### Example

```python
from taqsim.node import Reach, NoRouting, NoReachLoss

# Simple pass-through reach (no delay, no losses)
channel = Reach(
    id="main_channel",
    routing_model=NoRouting(),
    loss_rule=NoReachLoss()
)

# Check water currently in transit
print(channel.water_in_transit)  # 0.0
```

---

## Sink

Terminal node. Receives water and exits the system. Represents system boundaries (ocean, aquifer, etc.).

### Capabilities

- **Receives**: Accepts water from upstream

### Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `id` | `str` | Yes | Unique identifier |
| `location` | `tuple[float, float]` | No | (lat, lon) in WGS84 |

### Events Recorded

- `WaterReceived(amount, source_id, t)` — when water arrives

### Update Cycle

No-op. Sink is passive; it only records received water.

### Example

```python
from taqsim.node import Sink

sink = Sink(id="ocean_outflow")
```
