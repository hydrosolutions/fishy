# Edge Architecture

## Overview

The `taqsim.edge` module represents connections between nodes as pure topology. An edge defines "A connects to B" — nothing more. Edges carry no physics, no capacity constraints, and no loss calculations.

## Design Principles

### Pure Topology

Edges are structural connectors. They define the shape of the network graph but have no behavior:

- No water transport logic
- No capacity constraints
- No loss calculations
- No events
- No state

```python
# An edge is just a connection declaration
edge = Edge(id="canal_1", source="reservoir", target="farm")
```

### Separation of Concerns

Transport physics (routing, losses, delay) live in the **Reach** node type, not in edges. This cleanly separates two distinct concerns:

| Concern | Component | Responsibility |
|---------|-----------|----------------|
| **Topology** | Edge | Declares "A connects to B" |
| **Transport physics** | Reach node | Routes water, applies losses, models delay |

If your network has a canal with seepage losses and travel delay, model it as:

```
Source --edge--> Reach --edge--> Demand
```

The Reach node handles routing and losses. The edges are just the wires connecting things together.

### Why Edges Have No Physics

Earlier designs bundled capacity, loss rules, and event histories into edges. This created problems:

- Edges had dual responsibilities (topology + physics)
- The system had to call `edge.receive()` and `edge.update()` during routing
- Edge events duplicated information already tracked by nodes
- Adding transport delay required awkward edge state management

With pure-topology edges, routing is a direct pass-through: the system reads a node's output events and delivers the water straight to the target node via the edge's `source`/`target` mapping. Transport physics live in Reach nodes, which are proper nodes with full event sourcing.

## Edge Class

```python
@dataclass
class Edge:
    id: str                                    # Unique identifier (required, non-empty)
    source: str                                # Source node ID (required, non-empty)
    target: str                                # Target node ID (required, non-empty)
    tags: frozenset[str] = frozenset()         # Labels for categorization
    metadata: dict[str, Any] = {}              # Arbitrary key-value data
```

## Validation Rules

The Edge validates on creation:

- `id` cannot be empty
- `source` cannot be empty
- `target` cannot be empty

```python
# These raise ValueError:
Edge(id="", source="a", target="b")    # empty id
Edge(id="e", source="", target="b")    # empty source
Edge(id="e", source="a", target="")    # empty target
```

## Tags and Metadata

Edges support optional `tags` and `metadata` fields for annotation by intelligence layers:

```python
canal = Edge(
    id="main_canal",
    source="reservoir",
    target="city_demand",
    tags=frozenset({"canal", "primary"}),
    metadata={"length_km": 45.5},
)
```

- `tags: frozenset[str]` — Immutable set of string labels for categorization
- `metadata: dict[str, Any]` — Flexible dictionary for arbitrary key-value data

Taqsim stores these as opaque data; intelligence layers interpret them.

See [Tags and Metadata](../common/03_tags_metadata.md) for details.
