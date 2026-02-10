# Naturalize Module

Transform water systems to their natural state for IHA (Indicators of Hydrological Alteration) analysis.

## Introduction

The `naturalize` module provides tools to transform a `WaterSystem` that includes human infrastructure (dams, canals, diversions) into a "naturalized" version representing what the system would look like without human intervention. This naturalized system is required for calculating IHA indices, which compare current flow regimes against natural baselines.

### Why Naturalization?

IHA analysis requires comparing:
- **Observed/Simulated flows**: Current conditions with infrastructure
- **Natural flows**: What flows would be without human intervention

The naturalized system:
- Removes human infrastructure (diversions, canals)
- Converts storage facilities to pass-through points
- Preserves natural river bifurcations
- Maintains the natural drainage network topology

## Quick Start

```python
from fishy import naturalize, NATURAL_TAG
from taqsim.system import WaterSystem
from taqsim.edge import Edge
from taqsim.time import Frequency

# Create your system with edges tagged as 'natural' where appropriate
system = WaterSystem(frequency=Frequency.DAILY)
# ... add nodes and edges ...

# Ensure natural flow path edges are tagged
edge = Edge(
    id="river_reach",
    source="upstream",
    target="downstream",
    tags=frozenset({NATURAL_TAG}),  # Mark as natural
)
system.add_edge(edge)

# Naturalize the system
result = naturalize(system)

# Use the naturalized system for IHA
natural_system = result.system
print(result.summary())
```

## Tagging Your System

### The NATURAL_TAG Constant

Use `NATURAL_TAG` (value: `"natural"`) to mark edges that represent natural flow paths:

```python
from fishy import NATURAL_TAG

# Natural river reach
river_edge = Edge(
    id="main_river",
    source="upstream",
    target="downstream",
    tags=frozenset({NATURAL_TAG}),
)

# Man-made canal (not tagged)
canal_edge = Edge(
    id="irrigation_canal",
    source="reservoir",
    target="farm",
    tags=frozenset({"canal", "irrigation"}),  # No NATURAL_TAG
)
```

### The NATURAL_SPLIT_RATIOS Constant

Use `NATURAL_SPLIT_RATIOS` (value: `"natural_split_ratios"`) as a metadata key on Splitter nodes that have both natural and non-natural downstream edges. This tells the naturalization engine what ratios to use when rebuilding the splitter for the naturalized system.

```python
from fishy import NATURAL_SPLIT_RATIOS
from taqsim.node import Splitter

splitter = Splitter(
    id="junction",
    split_policy=operational_rule,
    metadata={NATURAL_SPLIT_RATIOS: {"main_channel": 0.6, "side_channel": 0.4}},
)
```

The ratio keys must match the target node IDs of the natural downstream edges from this splitter.

### What Gets Tagged

| Edge Type | Tagged Natural? | Reason |
|-----------|----------------|--------|
| Main river channel | Yes | Primary natural flow path |
| Natural distributary | Yes | Natural bifurcation |
| Irrigation canal | No | Human infrastructure |
| Diversion channel | No | Artificial routing |
| Spillway | Context-dependent | May be natural overflow path |

## NaturalRiverSplitter

When rivers naturally bifurcate (like delta distributaries), use `NaturalRiverSplitter` to define the natural split ratios.

### Fixed Ratios

For stable bifurcations with constant split ratios:

```python
from fishy import NaturalRiverSplitter

# 60% flows to main channel, 40% to secondary
splitter_rule = NaturalRiverSplitter(
    ratios={
        "main_channel": 0.6,
        "secondary_channel": 0.4,
    }
)

splitter = Splitter(
    id="delta_junction",
    split_rule=splitter_rule,
)
```

### Time-Varying Ratios

For seasonal variations in split ratios:

```python
# Different ratios for wet vs dry season (monthly)
splitter_rule = NaturalRiverSplitter(
    ratios={
        "main": (0.7, 0.7, 0.6, 0.5, 0.5, 0.5, 0.5, 0.5, 0.6, 0.7, 0.7, 0.7),
        "side": (0.3, 0.3, 0.4, 0.5, 0.5, 0.5, 0.5, 0.5, 0.4, 0.3, 0.3, 0.3),
    }
)
```

### Cyclical Ratios

For repeating patterns:

```python
# Quarterly pattern that repeats
splitter_rule = NaturalRiverSplitter(
    ratios={
        "main": (0.7, 0.6, 0.5, 0.6),
        "side": (0.3, 0.4, 0.5, 0.4),
    },
    cyclical=True,  # Wraps around: t=4 uses t=0 ratios
)
```

## Mixed Splitters

When a Splitter has both natural and non-natural downstream edges (e.g., a river bifurcation that also feeds a canal), you cannot assign `NaturalRiverSplitter` as the split policy directly — the operational system needs its own split rule. Instead, annotate the Splitter with `NATURAL_SPLIT_RATIOS` metadata.

### Topology

```
Source → Reach → Splitter → Reach A → Sink A  (natural)
                           → Reach B → Sink B  (natural)
                           → Canal (Demand)     (non-natural)
```

### Usage

```python
from fishy import NATURAL_SPLIT_RATIOS, NATURAL_TAG, naturalize
from taqsim.node import Splitter

# The operational splitter uses whatever rule you need
splitter = Splitter(
    id="junction",
    split_policy=my_operational_rule,
    metadata={NATURAL_SPLIT_RATIOS: {"reach_a": 0.6, "reach_b": 0.4}},
)

# During naturalization:
# - The canal edge and Demand are removed
# - The Splitter is rebuilt with NaturalRiverSplitter(ratios={"reach_a": 0.6, "reach_b": 0.4})
result = naturalize(system)
```

### Ratio Keys

The keys in the `NATURAL_SPLIT_RATIOS` dict must be the **direct downstream target node IDs** on natural edges from the splitter — not the final sink IDs.

### Time-Varying Ratios

Time-varying ratios use the same tuple format as `NaturalRiverSplitter`:

```python
metadata={NATURAL_SPLIT_RATIOS: {
    "reach_a": (0.7, 0.6, 0.5, 0.6),
    "reach_b": (0.3, 0.4, 0.5, 0.4),
}}
```

### Precedence

If a Splitter has **both** a `NaturalRiverSplitter` policy **and** `NATURAL_SPLIT_RATIOS` metadata, the policy wins (existing path, metadata ignored).

## Understanding the Result

The `naturalize()` function returns a `NaturalizeResult` with:

```python
result = naturalize(system)

# The naturalized system
natural_system = result.system

# Audit trail
result.removed_nodes      # frozenset of removed node IDs
result.removed_edges      # frozenset of removed edge IDs
result.transformed_nodes  # {node_id: original_type} for nodes that changed type
result.warnings          # tuple of warning messages

# Convenience properties
result.removed_count      # Number of removed nodes
result.transformed_count  # Number of transformed nodes
result.summary()          # Human-readable summary string
```

### Example Output

```
Naturalization Summary:
  Removed nodes: 2
  Removed edges: 3
  Transformed nodes: 1
  Transformations:
    reservoir: Storage -> PassThrough
  Warnings: 2
    - Removed 2 node(s) not on natural path: farm, city
    - Removed 3 non-natural edge(s)
```

## Transformation Rules

| Original Node | On Natural Path? | Transformation |
|---------------|-----------------|----------------|
| Source | Yes | Preserved as Source |
| Sink | Yes | Preserved as Sink |
| PassThrough | Yes | Preserved as PassThrough |
| Storage | Yes | -> PassThrough (no capacity) |
| Demand | Yes (with natural downstream) | -> PassThrough |
| Demand | Yes (terminal) | **Error: TerminalDemandError** |
| Splitter (NaturalRiverSplitter) | Yes | Preserved as Splitter |
| Splitter (single natural downstream) | Yes | -> PassThrough |
| Splitter (mixed, with NATURAL_SPLIT_RATIOS) | Yes | Preserved as Splitter (policy rebuilt from metadata) |
| Splitter (multiple natural, no rule) | Yes | **Error: AmbiguousSplitError** |
| Reach | Yes | Preserved as Reach |
| Any node | No | Removed |

## Error Handling

### NoNaturalPathError

Raised when no path exists from any Source to any Sink via natural edges.

```python
from fishy.naturalize import NoNaturalPathError

try:
    result = naturalize(system)
except NoNaturalPathError as e:
    print(f"Sources: {e.source_ids}")
    print(f"Sinks: {e.sink_ids}")
    # Fix: Tag edges on natural path with NATURAL_TAG
```

### AmbiguousSplitError

Raised when a Splitter has multiple natural downstream edges but no `NaturalRiverSplitter`.

```python
from fishy.naturalize import AmbiguousSplitError

try:
    result = naturalize(system)
except AmbiguousSplitError as e:
    print(f"Splitter: {e.node_id}")
    print(f"Natural edges: {e.natural_edge_ids}")
    # Fix: Add NaturalRiverSplitter, add NATURAL_SPLIT_RATIOS metadata, or remove NATURAL_TAG from all but one edge
```

### TerminalDemandError

Raised when a Demand node on the natural path has no natural downstream edge.

```python
from fishy.naturalize import TerminalDemandError

try:
    result = naturalize(system)
except TerminalDemandError as e:
    print(f"Demand: {e.node_id}")
    print(f"Downstream edges: {e.downstream_edge_ids}")
    # Fix: Tag downstream edge as natural, or remove NATURAL_TAG from upstream
```

### NoNaturalReachError

Raised when a connected natural path contains no Reach node. Every natural path from Source to Sink must include at least one Reach to model the physical river channel.

```python
from fishy.naturalize import NoNaturalReachError

try:
    result = naturalize(system)
except NoNaturalReachError as e:
    print(f"Sources: {e.source_ids}")
    print(f"Sinks: {e.sink_ids}")
    print(f"Path nodes: {e.path_node_ids}")
    # Fix: Add a Reach node on the natural path
```

### InvalidNaturalSplitRatiosError

Raised when a Splitter has `NATURAL_SPLIT_RATIOS` metadata that is malformed (wrong type, ratios don't sum to 1.0, keys don't match downstream targets).

```python
from fishy.naturalize import InvalidNaturalSplitRatiosError

try:
    result = naturalize(system)
except InvalidNaturalSplitRatiosError as e:
    print(f"Splitter: {e.node_id}")
    print(f"Reason: {e.reason}")
    # Fix: Ensure ratios are a dict, sum to 1.0, and keys match natural downstream targets
```

## Complete Example

### Original System

```
                    +-----[canal]----> farm (Demand)
                    |
source --[natural]--+ reservoir --[natural]--> junction --[natural]--> ocean
(Source)             (Storage)                 (Splitter)               (Sink)
                                                   |
                                                   +--[canal]----> city (Demand)
```

### After Naturalization

```
source --[natural]--> reservoir --[natural]--> junction --[natural]--> ocean
(Source)             (PassThrough)            (PassThrough)            (Sink)
```

### Code

```python
from fishy import naturalize, NATURAL_TAG, NaturalRiverSplitter
from taqsim.system import WaterSystem
from taqsim.node import Source, Storage, Splitter, Demand, Sink
from taqsim.edge import Edge
from taqsim.time import Frequency

# Build original system
system = WaterSystem(frequency=Frequency.DAILY)

system.add_node(Source(id="source", inflow=inflow_ts))
system.add_node(Storage(id="reservoir", capacity=10000.0))
system.add_node(Splitter(id="junction", split_rule=some_rule))
system.add_node(Demand(id="farm", requirement=farm_req))
system.add_node(Demand(id="city", requirement=city_req))
system.add_node(Sink(id="ocean"))

# Natural path edges
system.add_edge(Edge(id="e1", source="source", target="reservoir",
                     tags=frozenset({NATURAL_TAG})))
system.add_edge(Edge(id="e2", source="reservoir", target="junction",
                     tags=frozenset({NATURAL_TAG})))
system.add_edge(Edge(id="e3", source="junction", target="ocean",
                     tags=frozenset({NATURAL_TAG})))

# Canal edges (not natural)
system.add_edge(Edge(id="e4", source="reservoir", target="farm",
                     tags=frozenset({"canal"})))
system.add_edge(Edge(id="e5", source="junction", target="city",
                     tags=frozenset({"canal"})))

# Naturalize
result = naturalize(system)

print(result.summary())
# Output:
# Naturalization Summary:
#   Removed nodes: 2
#   Removed edges: 2
#   Transformed nodes: 2
#   Transformations:
#     junction: Splitter -> PassThrough
#     reservoir: Storage -> PassThrough
#   Warnings: 2
#     - Removed 2 node(s) not on natural path: city, farm
#     - Removed 2 non-natural edge(s)

# Use for IHA
natural_system = result.system
natural_system.simulate(timesteps=365)
# ... calculate IHA indices ...
```

### Mixed Splitter Example

```
source --[natural]--> reach --[natural]--> junction --[natural]--> reach_a --[natural]--> ocean_a
(Source)             (Reach)              (Splitter)              (Reach)               (Sink)
                                              |
                                              +--[natural]--> reach_b --[natural]--> ocean_b
                                              |              (Reach)               (Sink)
                                              |
                                              +--[canal]----> irrigation (Demand)
```

```python
from fishy import naturalize, NATURAL_TAG, NATURAL_SPLIT_RATIOS
from taqsim.node import Source, Reach, Splitter, Demand, Sink
from taqsim.edge import Edge
from taqsim.system import WaterSystem
from taqsim.time import Frequency

system = WaterSystem(frequency=Frequency.DAILY)

system.add_node(Source(id="source", inflow=inflow_ts))
system.add_node(Reach(id="reach"))
system.add_node(Splitter(
    id="junction",
    split_policy=operational_rule,
    metadata={NATURAL_SPLIT_RATIOS: {"reach_a": 0.6, "reach_b": 0.4}},
))
system.add_node(Reach(id="reach_a"))
system.add_node(Reach(id="reach_b"))
system.add_node(Sink(id="ocean_a"))
system.add_node(Sink(id="ocean_b"))
system.add_node(Demand(id="irrigation", requirement=irr_req))

# Natural edges
for eid, src, tgt in [
    ("e1", "source", "reach"),
    ("e2", "reach", "junction"),
    ("e3", "junction", "reach_a"),
    ("e4", "junction", "reach_b"),
    ("e5", "reach_a", "ocean_a"),
    ("e6", "reach_b", "ocean_b"),
]:
    system.add_edge(Edge(id=eid, source=src, target=tgt, tags=frozenset({NATURAL_TAG})))

# Canal edge
system.add_edge(Edge(id="e7", source="junction", target="irrigation", tags=frozenset({"canal"})))

result = naturalize(system)
# junction is preserved as Splitter with NaturalRiverSplitter(ratios={"reach_a": 0.6, "reach_b": 0.4})
# irrigation node and canal edge removed
```

## Integration with IHA

The typical workflow. Note that the naturalized system must contain at least one Reach node on each natural path, as IHA flow extraction operates on Reach nodes.

```
+------------------+     +--------------+     +--------------+
|  WaterSystem     | --> | naturalize() | --> | IHA Indices  |
| (with infra)     |     |              |     | (via Reach)  |
+------------------+     +--------------+     +--------------+
         |                     |                    |
         |                     |                    v
         |                     |            Natural baseline
         |                     v
         |              NaturalizeResult
         |              - system (natural)
         |              - audit trail
         |
         v
    Simulate both systems
    Compare flow regimes (at Reach nodes)
```
