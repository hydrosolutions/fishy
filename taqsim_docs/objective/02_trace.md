# Trace

## Overview

`Trace` is a time-indexed series of float values. It provides a functional interface for transforming and aggregating simulation data.

```python
@dataclass(frozen=True, slots=True)
class Trace:
    _data: dict[int, float]  # timestep -> value
```

## Construction

### Node and Edge `.trace()` Method

The simplest way to build a Trace is using the `.trace()` method available on both nodes and edges:

```python
# From a node
spill_trace = node.trace(WaterSpilled)
deficit_trace = node.trace(DeficitRecorded, field="deficit")

# From an edge
flow_trace = edge.trace(WaterDelivered)
```

This is the recommended approach for most use cases.

### from_events

For more control, build a Trace directly from events:

```python
from taqsim.objective import Trace
from taqsim.node.events import WaterSpilled

# Sum amounts at each timestep (default behavior)
spill_trace = Trace.from_events(node.events_of_type(WaterSpilled))

# Use a different field
deficit_trace = Trace.from_events(events, field="deficit")

# Custom reduce function (e.g., take max instead of sum)
peak_trace = Trace.from_events(events, reduce=max)
```

### from_dict

Create from raw data:

```python
trace = Trace.from_dict({0: 100.0, 1: 150.0, 2: 120.0})
```

### constant

Create a constant trace over timesteps:

```python
target = Trace.constant(1000.0, range(12))
target = Trace.constant(500.0, [0, 3, 6, 9])
```

### empty

Create an empty trace:

```python
trace = Trace.empty()
```

## Transformation

### map

Apply a function to all values:

```python
squared = trace.map(lambda x: x ** 2)
normalized = trace.map(lambda x: x / 1000)
```

### filter

Keep entries matching a predicate:

```python
# Keep only positive values
positive = trace.filter(lambda t, v: v > 0)

# Keep specific timesteps
subset = trace.filter(lambda t, v: t in [0, 1, 2])
```

## Arithmetic

Traces support standard arithmetic. Operations between two Traces use intersection semantics (only common timesteps).

### Binary operations

```python
a = Trace.from_dict({0: 10, 1: 20, 2: 30})
b = Trace.from_dict({1: 5, 2: 10, 3: 15})

a + b  # {1: 25, 2: 40} - intersection of timesteps
a - b  # {1: 15, 2: 20}
a * b  # {1: 100, 2: 300}
a / b  # {1: 4.0, 2: 3.0}
```

### Scalar operations

```python
trace + 10   # Add 10 to all values
trace - 5    # Subtract 5 from all values
trace * 2    # Double all values
trace / 100  # Divide all values by 100
10 + trace   # Also works in reverse
```

### Unary operations

```python
-trace       # Negate all values
trace ** 2   # Square all values
```

## Cumulative Operations

### cumsum

Compute running cumulative sum with optional initial value:

```python
deltas = Trace.from_dict({0: 10, 1: -3, 2: 5})
cumulative = deltas.cumsum()           # {0: 10, 1: 7, 2: 12}
cumulative = deltas.cumsum(initial=50) # {0: 60, 1: 57, 2: 62}
```

Reconstruct storage level from delta events:

```python
net_change = stored - released - lost - spilled
storage = net_change.cumsum(initial=dam.initial_storage)
```

## Aggregation

Reduce a Trace to a single value:

```python
trace.sum()   # Sum of all values
trace.mean()  # Average value
trace.max()   # Maximum value
trace.min()   # Minimum value
```

Note: `mean()`, `max()`, and `min()` raise `ValueError` on empty traces.

## Access

### Indexing

```python
value = trace[5]  # Get value at timestep 5
```

### Length

```python
len(trace)  # Number of entries
```

### Iteration

```python
for t in trace:
    print(f"t={t}: {trace[t]}")
```

### Extracting data

```python
trace.timesteps()  # [0, 1, 2] - sorted timestep list
trace.values()     # [100, 150, 120] - values in timestep order
trace.items()      # [(0, 100), (1, 150), (2, 120)] - (t, v) pairs
trace.to_dict()    # {0: 100, 1: 150, 2: 120} - raw dict copy
```

## HasTimestep Protocol

Events must have a `t: int` attribute to work with `from_events`:

```python
@runtime_checkable
class HasTimestep(Protocol):
    t: int
```

All taqsim events implement this protocol.
