# Network Validation

## Overview

`WaterSystem.validate()` performs comprehensive validation before simulation. All errors are collected and reported together.

## Validation Rules

### 1. Edge Endpoint Existence

All edge `source` and `target` must reference existing nodes.

```python
# Error: Edge 'e1': source node 'nonexistent' does not exist
```

### 2. Directed Acyclic Graph (DAG)

The network must be acyclic. Water cannot flow in loops.

```python
# Error: Network contains cycles
```

### 3. Connectivity

All nodes must be part of a single connected component (weakly connected).

```python
# Error: Network is not connected
```

### 4. Terminal Structure

- **Source nodes**: Must have `in_degree=0` (no incoming edges)
- **Sink nodes**: Must have `out_degree=0` (no outgoing edges)

```python
# Error: Source 'river' must have in_degree=0, got 1
# Error: Sink 'ocean' must have out_degree=0, got 1
```

### 5. Single Output for Non-Splitters

Source, Storage, Demand, and PassThrough must have exactly one outgoing edge.

```python
# Error: Non-splitter node 'dam' must have exactly 1 outgoing edge, got 2
```

Use a Splitter when you need to distribute to multiple targets.

### 6. Path to Sink

Every node (except Sinks) must have a path to at least one Sink.

```python
# Error: Node 'orphan_reservoir' has no path to any Sink
```

## ValidationError

All validation errors raise `ValidationError` with a descriptive message:

```python
from taqsim.system import ValidationError

try:
    system.validate()
except ValidationError as e:
    print(e)
```

## Target Derivation

After validation passes, `WaterSystem` populates targets on all nodes:

```python
def _set_targets(self) -> None:
    for node_id, node in self._nodes.items():
        if isinstance(node, Sink):
            continue

        # Find outgoing edges for this node
        outgoing_edges = [edge for edge in self._edges.values() if edge.source == node_id]

        target_edge_ids = [e.id for e in outgoing_edges]
        node._set_targets(target_edge_ids)
```

- **Single-output nodes**: `targets = ["edge_id"]`
- **Splitter**: `targets = ["edge1_id", "edge2_id", ...]`
- **Sink**: `targets = []` (terminal)

## Re-Validation

Adding nodes or edges invalidates the system:

```python
system.validate()
assert system._validated is True

system.add_node(new_node)
assert system._validated is False  # Invalidated

system.validate()  # Must re-validate
```

## Auto-Validation

`simulate()` auto-validates if not already validated:

```python
system.add_node(source)
system.add_node(sink)
system.add_edge(edge)

# No explicit validate() needed
system.simulate(timesteps=10)  # Calls validate() internally
```
