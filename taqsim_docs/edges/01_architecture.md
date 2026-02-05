# Edge Architecture

## Overview

The `taqsim.edge` module represents connections between nodes, managing water transport with capacity constraints and losses. Like nodes, edges use event sourcing.

## Design Principles

### Event Sourcing

Edges record events instead of mutating state. State is derived from the event history.

Benefits:

- Audit trail: See exactly what flowed through
- Replay: Reconstruct any historical state
- Debugging: Trace flow issues through event sequence
- Testability: Assert on events, not internal state

```python
# Instead of:
edge.delivered = edge.received - edge.losses  # mutation

# We record:
edge.record(WaterReceived(amount=100.0, t=0))
edge.record(WaterLost(amount=5.0, reason=LossReason.SEEPAGE, t=0))
edge.record(WaterDelivered(amount=95.0, t=0))

# State is derived:
events = edge.events_of_type(WaterDelivered)  # returns list[WaterDelivered]
total_delivered = sum(e.amount for e in events)
```

### Strategy Pattern

Configurable behaviors via protocols:

- `EdgeLossRule` - customizable loss calculation for transport losses (required)

## Edge vs Node

| Aspect | Node | Edge |
|--------|------|------|
| Purpose | Process water | Transport water |
| Events | Water* prefix | Water* prefix |
| Losses | Storage-based | Flow-based |
| State | Complex (storage, generation) | Simple (received, delivered) |

## Edge Class

```python
@dataclass
class Edge:
    id: str                                    # Unique identifier (required, non-empty)
    source: str                                # Source node ID (required, non-empty)
    target: str                                # Target node ID (required, non-empty)
    capacity: float                            # Max flow capacity (required, positive)
    loss_rule: EdgeLossRule | None = None      # Loss calculation rule (required)
    targets: list[str] = field(default_factory=list)  # Additional targets

    events: list[EdgeEvent]                    # Event history (auto-managed)
    _received_this_step: float                 # Step accumulator (auto-managed)
```

## Edge Lifecycle

```
Edge(id, source, target, capacity, loss_rule) -> [receive(amount, t) -> update(t, dt)]* -> derive state from events
```

## Data Flow

```
receive(amount) -> capacity check -> loss calculation -> deliver
      |                  |                 |               |
      v                  v                 v               v
WaterReceived    WaterLost            WaterLost      WaterDelivered
                 (CAPACITY_EXCEEDED)  (via loss_rule)
```

## Edge Interface

Key methods:

- `receive(amount, t)` - Accept flow from upstream node, returns amount received
- `update(t, dt)` - Process flow and record events, returns delivered amount
- `reset()` - Clears events and step accumulator for fresh simulation run
- `record(event)` - Append an EdgeEvent to the event history
- `events_of_type(event_type)` - Returns list of events matching the given type
- `trace(event_type, field)` - Returns a Trace object from events of given type
- `clear_events()` - Clears all events from history

## Update Cycle

1. **Receive**: Edge accumulates water via `receive()` calls
2. **Capacity Check**: Excess flow is recorded as `WaterLost(reason=CAPACITY_EXCEEDED)` if over capacity
3. **Loss Calculation**: Apply `EdgeLossRule.calculate()` to compute transport losses
4. **Loss Scaling**: If total losses exceed available flow, scale proportionally
5. **Delivery**: Record final delivered amount as `WaterDelivered`
6. **Reset**: Clear accumulated flow for next timestep
7. **Return**: Return delivered amount to caller

## EdgeLossRule Protocol

```python
@runtime_checkable
class EdgeLossRule(Protocol):
    def calculate(self, edge: Edge, flow: float, t: int, dt: float) -> dict[LossReason, float]: ...
```

The loss rule receives the edge, current flow, timestep, and dt, returning a dictionary mapping loss reasons to amounts.

## Tags and Metadata

Edges support optional `tags` and `metadata` fields for annotation by intelligence layers:

```python
canal = Edge(
    id="main_canal",
    source="reservoir",
    target="city_demand",
    capacity=200.0,
    loss_rule=canal_loss_rule,
    tags=frozenset({"canal", "primary"}),
    metadata={"length_km": 45.5},
)
```

- `tags: frozenset[str]` - Immutable set of string labels for categorization
- `metadata: dict[str, Any]` - Flexible dictionary for arbitrary key-value data

Taqsim stores these as opaque data; intelligence layers interpret them.

See [Tags and Metadata](../common/03_tags_metadata.md) for details.