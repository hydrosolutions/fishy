# Node Architecture

## Overview

The `taqsim.node` module provides the building blocks for water system simulation using event sourcing. Nodes record events instead of mutating state directly.

## Design Principles

### Event Sourcing

Nodes record events instead of mutating state. State is derived from the event history.

Benefits:

- Audit trail: See exactly what happened
- Replay: Reconstruct any historical state
- Debugging: Trace issues through event sequence
- Testability: Assert on events, not internal state

```python
# Instead of:
node.storage = node.storage + inflow - outflow  # mutation

# We record:
node.record(WaterStored(amount=inflow, t=0))
node.record(WaterReleased(amount=outflow, t=0))

# State is derived:
current_storage = sum(stored) - sum(released) - sum(lost)
```

### The Node Contract

`Receives` is the sole runtime-checked protocol. `WaterSystem` uses `isinstance(node, Receives)` to determine which nodes can accept water from upstream edges. All other node behavior is encapsulated within `update(t)` using private pipeline methods.

See [The Node Contract](03_capabilities.md) for details.

## Node Lifecycle

```
create(id) → [update(t: Timestep) → record events]* → derive state from events
```

## BaseNode

All nodes extend `BaseNode` which provides:

```python
@dataclass
class BaseNode:
    id: str
    location: tuple[float, float] | None  # (lat, lon) in WGS84
    events: list[NodeEvent]               # append-only event log (not in __init__)
    _targets: list[str]                   # downstream node IDs (not in __init__)

    # Properties
    @property
    def targets() -> list[str]            # downstream node IDs

    # Event methods
    def record(event: NodeEvent) -> None  # append event
    def events_at(t: int) -> list         # filter by timestep
    def events_of_type[T](type[T]) -> list[T]  # filter by event class
    def trace[T](type[T], field: str) -> Trace # extract Trace from events
    def clear_events() -> None            # reset events (for testing)

    # Lifecycle
    def reset() -> None                   # clears events and resets state for fresh simulation
    def update(t: Timestep) -> None       # MUST be implemented by subclasses

    # Strategy introspection
    def strategies() -> dict[str, Strategy]  # returns all Strategy-typed fields
```

## Universal update() Pattern

All nodes implement `update(t: Timestep)` as their sole public processing method. The system calls `update()` once per timestep for each node in topological order. Internal processing is private to each node type:

- **Source**: `_generate` → WaterOutput
- **Storage**: `_store` → `_lose` → `_release` → WaterOutput
- **Demand**: `_consume` → WaterOutput
- **Splitter**: `_distribute` → WaterDistributed
- **Reach**: route → exit → lose → transit snapshot → WaterOutput
- **PassThrough**: pass-through → WaterOutput
- **Sink**: no-op

Each step records appropriate events. External code observes behavior through events, never by calling sub-steps directly.

## Data Flow

```
Source ──[edge]──> Storage ──[edge]──> Demand ──[edge]──> Sink
   │                  │                   │                 │
   ▼                  ▼                   ▼                 ▼
Generated          Received           Received          Received
Output             Stored             Consumed          (terminal)
                   Spilled            Lost (inefficiency)
                   Lost               Deficit (if short)
                   Released           Output
                   Output
```

Additional node types:
- `Splitter`: Receives water and distributes to multiple downstream targets
- `PassThrough`: Receives water, records passage (e.g., for hydropower), outputs unchanged

## Node Location

The `location` field on `BaseNode` is optional and specifies WGS84 coordinates (EPSG:4326):

- First element: latitude (-90 to +90 degrees)
- Second element: longitude (-180 to +180 degrees)

Example:
```python
source = Source(
    id="river_intake",
    inflow=TimeSeries([100.0] * 12),
    location=(31.7683, 35.2137),  # Jerusalem
)
```

Location is used by `WaterSystem` for:
- Geographic visualization via `visualize()`
- Edge length computation via `edge_length()` and `edge_lengths()`

## Tags and Metadata

Nodes support optional `tags` and `metadata` fields for annotation by intelligence layers:

```python
source = Source(
    id="river_intake",
    inflow=TimeSeries([100.0] * 12),
    tags=frozenset({"upstream", "primary"}),
    metadata={"watershed": "jordan", "capacity_mcm": 50},
)
```

- `tags: frozenset[str]` - Immutable set of string labels for categorization
- `metadata: dict[str, Any]` - Flexible dictionary for arbitrary key-value data

Taqsim stores these as opaque data; intelligence layers interpret them.

See [Tags and Metadata](../common/03_tags_metadata.md) for details.