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

### Capability Protocols

Nodes implement capability protocols defined in `protocols.py`:

| Protocol | Method | Description |
|----------|--------|-------------|
| Generates | `generate(t, dt) -> float` | Produce water |
| Receives | `receive(amount, source_id, t) -> float` | Accept water from upstream |
| Stores | `store(amount, t, dt) -> tuple[float, float]` | Buffer water (returns stored, spilled) |
| Loses | `lose(t, dt) -> float` | Physical losses |
| Consumes | `consume(amount, t, dt) -> tuple[float, float]` | Consume water (returns withdrawn, remaining) |

Node types and their capabilities:

```
Source      = Generates
Splitter    = Receives + distribute()
Storage     = Receives + Stores + Loses + release()
Demand      = Receives + Consumes
Sink        = Receives
PassThrough = Receives
```

Note: `distribute()` and `release()` are node-specific methods, not protocols.

## Node Lifecycle

```
create(id) → [update(t, dt) → record events]* → derive state from events
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
    def update(t: int, dt: float) -> None # MUST be implemented by subclasses

    # Strategy introspection
    def strategies() -> dict[str, Strategy]  # returns all Strategy-typed fields
```

## Universal update() Pattern

All nodes implement `update(t, dt)` which:

1. Generate water (if source)
2. Receive from upstream edges
3. Store/release (if has storage)
4. Consume (if demand)
5. Calculate losses
6. Distribute downstream

Each step records appropriate events.

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