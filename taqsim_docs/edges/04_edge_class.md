# Edge Class

## Overview

The `Edge` class represents a topological connection between two nodes. It carries no behavior — no water transport, no capacity constraints, no loss calculations, no events.

## Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `id` | `str` | Yes | - | Unique identifier |
| `source` | `str` | Yes | - | Source node ID |
| `target` | `str` | Yes | - | Target node ID |
| `tags` | `frozenset[str]` | No | `frozenset()` | Labels for categorization |
| `metadata` | `dict[str, Any]` | No | `{}` | Arbitrary key-value data |

## Validation Rules

The Edge validates parameters on creation:

- `id` cannot be empty
- `source` cannot be empty
- `target` cannot be empty

```python
# These raise ValueError:
Edge(id="", source="a", target="b")    # empty id
Edge(id="e", source="", target="b")    # empty source
Edge(id="e", source="a", target="")    # empty target
```

## Methods

### _fresh_copy() -> Edge

Creates a new `Edge` instance with identical field values. Used internally by `WaterSystem.with_vector()` to produce an independent copy of the system's topology when creating a new system with modified parameters.

```python
copy = edge._fresh_copy()
# copy.id == edge.id
# copy.source == edge.source
# copy.target == edge.target
# copy.tags == edge.tags
# copy.metadata == edge.metadata
```

## Usage Examples

### Basic Edge

```python
from taqsim.edge import Edge

edge = Edge(id="canal_1", source="reservoir", target="farm")
```

### Edge with Annotations

```python
edge = Edge(
    id="main_canal",
    source="reservoir",
    target="distribution_node",
    tags=frozenset({"canal", "primary"}),
    metadata={"length_km": 45.5, "material": "concrete"},
)
```

### Modeling Transport Physics

To model transport losses and routing delay, place a **Reach** node between source and target:

```python
from taqsim.node import Source, Reach, Demand
from taqsim.edge import Edge

# Nodes
source = Source(id="river", inflow=inflow_data)
canal = Reach(id="canal", routing_model=muskingum, loss_rule=seepage)
farm = Demand(id="farm", requirement=demand_data)

# Edges — pure topology
e1 = Edge(id="e1", source="river", target="canal")
e2 = Edge(id="e2", source="canal", target="farm")
```

The Reach node handles all transport physics. The edges just define connectivity.
