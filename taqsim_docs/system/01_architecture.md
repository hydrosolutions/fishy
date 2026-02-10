# WaterSystem Architecture

## Overview

`WaterSystem` is the orchestrator that:

1. Manages nodes and edges
2. Derives topology from edge definitions
3. Validates network structure
4. Runs simulation in topological order
5. Routes water between nodes via edges

## Design Principles

See [Design Philosophy](../00_philosophy.md) for the foundational principle: **expose everything, decide nothing**.

### Separation of Concerns

| Component | Responsibility |
|-----------|----------------|
| **Nodes** | Process water, record events (know nothing about topology) |
| **Edges** | Define topology (pure connectors — know source/target IDs, no physics) |
| **WaterSystem** | Derive topology, validate, orchestrate simulation |

### Nodes Don't Know Targets

Nodes never specify their downstream connections. Instead:

1. You define edges with `source` and `target` node IDs
2. `WaterSystem.validate()` builds the graph and populates node targets
3. Nodes output via events (`WaterOutput`, `WaterDistributed`)
4. `WaterSystem` reads events and routes water through edges

### Events as Communication API

Nodes communicate output through events:

- **Single-output nodes** (Source, Storage, Demand, PassThrough): Record `WaterOutput`
- **Multi-output nodes** (Splitter): Record `WaterDistributed` for each target

`WaterSystem._route_output()` reads these events and delivers water to downstream nodes.

## Class Definition

```python
from dataclasses import dataclass, field
import networkx as nx

@dataclass
class WaterSystem:
    frequency: Frequency  # simulation frequency (e.g., Frequency.DAILY) — no default, must be explicit
    start_date: date | None = None  # optional calendar anchor for time_index()

    _nodes: dict[str, BaseNode] = field(default_factory=dict, init=False)
    _edges: dict[str, Edge] = field(default_factory=dict, init=False)
    _graph: nx.DiGraph = field(default_factory=nx.DiGraph, init=False)
    _validated: bool = field(default=False, init=False)
```

## Key Methods

### add_node(node)

Registers a node in the system.

```python
system.add_node(Source(id="river", inflow=inflow_data))
```

### add_edge(edge)

Registers an edge connecting two nodes. Edges are pure topology — they define connectivity only.

```python
system.add_edge(Edge(id="e1", source="river", target="dam"))
```

### validate()

Validates network structure and derives topology:

1. Check all edge endpoints exist
2. Build networkx graph
3. Check acyclic (DAG)
4. Check connectivity
5. Validate terminal structure (Source in_degree=0, Sink out_degree=0)
6. Check single output for non-Splitter nodes
7. Check path to sink for all nodes
8. Populate targets on all nodes via `_set_targets()`

### simulate(timesteps)

Runs the simulation:

1. Auto-validates if not validated
2. For each timestep:
   - Process nodes in topological order
   - Route output from each node to downstream via edges

### time_index(n)

Returns `n` calendar dates starting from `start_date`, spaced by the system's frequency. Raises `ValueError` if `start_date` is `None`.

```python
system = WaterSystem(frequency=Frequency.MONTHLY, start_date=date(2024, 1, 1))
dates = system.time_index(12)
# (date(2024, 1, 1), date(2024, 2, 1), ..., date(2024, 12, 1))
```

See [Frequency — Calendar Date Mapping](../common/04_frequency.md#calendar-date-mapping) for details on monthly/yearly day clamping.

## Usage Example

```python
from taqsim.node import Source, Storage, PassThrough, Splitter, Demand, Sink, TimeSeries, WaterReceived
from taqsim.edge import Edge
from taqsim.system import WaterSystem

# Create nodes (no targets specified)
# (Assume rule, losses, equal_split are pre-defined strategy implementations)
source = Source(id="river", inflow=TimeSeries([100.0] * 12))
dam = Storage(id="dam", capacity=1000, release_policy=rule, loss_rule=losses)
turbine = PassThrough(id="turbine")
junction = Splitter(id="junction", split_policy=equal_split)
farm = Demand(id="farm", requirement=TimeSeries([30.0] * 12))
city = Sink(id="city")

# Create system
system = WaterSystem(frequency=Frequency.DAILY, start_date=date(2020, 1, 1))

# Add nodes
system.add_node(source)
system.add_node(dam)
system.add_node(turbine)
system.add_node(junction)
system.add_node(farm)
system.add_node(city)

# Add edges (pure topology — just connectivity, no physics)
system.add_edge(Edge(id="e1", source="river", target="dam"))
system.add_edge(Edge(id="e2", source="dam", target="turbine"))
system.add_edge(Edge(id="e3", source="turbine", target="junction"))
system.add_edge(Edge(id="e4", source="junction", target="farm"))
system.add_edge(Edge(id="e5", source="junction", target="city"))

# Validate (derives targets from edges)
system.validate()

# Simulate 12 timesteps
system.simulate(timesteps=12)

# Analyze results via node events
total_received = sum(e.amount for e in city.events_of_type(WaterReceived))
```

## Graph Structure

The internal graph is a `networkx.DiGraph`:

- Nodes are node IDs (strings)
- Edges store `edge_id` attribute linking to the Edge object

```python
# After validation, inspect topology
system._graph.nodes()  # ['river', 'dam', 'turbine', 'junction', 'farm', 'city']
system._graph.edges()  # [('river', 'dam'), ('dam', 'turbine'), ...]
```

## Simulation Flow

```
timesteps = frequency.make_timesteps(n)  # Create Timestep objects from frequency
For each timestep ts in timesteps:
    For each node_id in topological_sort(graph):
        node.update(ts)                  # Node processes water, records events
        _route_output(node_id, ts)       # System reads events, routes via edges
```

The `Timestep` is created from the `Frequency` and carries all temporal context a node needs. Nodes no longer receive a separate `dt` argument.

**Data units**: All data (inflows, demands, capacities, release rates) is in **per-timestep units**. There is no internal scaling factor. If the simulation frequency is daily, a demand of `30.0` means 30 units per day.

### Routing Logic

Edges are pure topology, so routing is a direct pass-through:

1. Read `WaterOutput` events → route to single outgoing edge
2. Read `WaterDistributed` events → route to specified target edge
3. For each routed amount:
   - Look up `edge.target` to find the downstream node
   - `target_node.receive(amount, edge_id, ts)` — deliver directly, no edge processing

There is no `edge.receive()` or `edge.update()` call. The edge is used only to resolve which target node receives the water. Transport physics (routing delay, losses) are handled by **Reach** nodes when present in the network.

## Properties

| Property | Returns |
|----------|---------|
| `nodes` | `dict[str, BaseNode]` - All registered nodes |
| `edges` | `dict[str, Edge]` - All registered edges |

## Parameter Exposure

WaterSystem provides methods for parameter discovery and manipulation, enabling optimization workflows.

### Methods

| Method | Purpose |
|--------|---------|
| `param_schema()` | Returns list of all tunable parameters as `ParamSpec` objects |
| `to_vector()` | Flattens parameters to `list[float]` for optimization |
| `param_bounds()` | Returns `dict[str, tuple[float, float]]` of parameter bounds (raises if any bounds missing) |
| `bounds_vector()` | Returns bounds matching `to_vector()` order as `list[tuple[float, float]]` |
| `constraint_specs()` | Returns `list[ConstraintSpec]` with resolved paths and bounds for constraint repair |
| `with_vector(vector)` | Creates new system with parameters from vector (immutable) |
| `reset()` | Clears all events and resets node state for fresh simulation |

### Example

```python
# Discover parameters
schema = system.param_schema()
for spec in schema:
    print(f"{spec.path}: {spec.value}")

# Vectorize and modify
vector = system.to_vector()
new_system = system.with_vector(modified_vector)
new_system.simulate(12)

# Get bounds for optimization
bounds = system.param_bounds()  # dict[str, tuple[float, float]]
bounds_vec = system.bounds_vector()  # list matching to_vector() order

# Get constraints for repair
constraints = system.constraint_specs()  # list[ConstraintSpec]
```

See [Parameter Exposure](03_parameter_exposure.md) for complete documentation.

## Visualization

`WaterSystem.visualize()` renders the network on a geographic plot:

```python
system.visualize()                                      # Interactive display
system.visualize(save_to="map.png")                     # Save to file
system.visualize(figsize=(16, 10), save_to="map.png")   # Custom figure size
```

Features:
- Nodes plotted at (longitude, latitude) positions
- Different colors/markers per node type:
  - Source: blue triangle
  - Storage: green square
  - Demand: orange circle
  - Sink: gray triangle
  - Splitter: purple diamond
  - PassThrough: cyan hexagon
- Edges drawn as arrows
- Node IDs as labels

Raises `ValueError` if no nodes have locations set.

## Edge Length Computation

Compute geodesic distances between connected nodes:

```python
# Single edge (returns meters or None)
length = system.edge_length("pipeline_1")

# All edges with located endpoints
lengths = system.edge_lengths()  # dict[str, float]
```

Uses the Haversine formula for WGS84 great-circle distance.
Returns `None` for edges where either endpoint lacks a location.