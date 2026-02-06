# Capability Protocols

## Overview

Capabilities are defined as `Protocol` classes. Nodes implement capabilities by having the required methods.

## Protocol Definitions

### Generates

```python
@runtime_checkable
class Generates(Protocol):
    def generate(self, t: int, dt: float) -> float: ...
```

Returns water volume generated.

### Receives

```python
@runtime_checkable
class Receives(Protocol):
    def receive(self, amount: float, source_id: str, t: int) -> float: ...
```

Returns amount actually received.

### Stores

```python
@runtime_checkable
class Stores(Protocol):
    @property
    def storage(self) -> float: ...

    @property
    def capacity(self) -> float: ...

    def store(self, amount: float, t: int, dt: float) -> tuple[float, float]: ...
```

Returns `(stored, released)`.

### Loses

```python
@runtime_checkable
class Loses(Protocol):
    def lose(self, t: int, dt: float) -> float: ...
```

Returns amount lost.

### Consumes

```python
@runtime_checkable
class Consumes(Protocol):
    def consume(self, amount: float, t: int, dt: float) -> tuple[float, float]: ...
```

Returns `(consumed, remaining)`.

## Composition Table

| Node Type   | Generates | Receives | Stores | Loses | Consumes |
|-------------|-----------|----------|--------|-------|----------|
| Source      | ✓         |          |        |       |          |
| PassThrough |           | ✓        |        |       |          |
| Splitter    |           | ✓        |        |       |          |
| Storage     |           | ✓        | ✓      | ✓     |          |
| Demand      |           | ✓        |        |       | ✓        |
| Sink        |           | ✓        |        |       |          |

> **Note**: Topology (targets, distribution) is handled by `WaterSystem`, not by nodes.
> The `Gives` protocol has been removed. Splitter uses `split_policy` internally
> but targets are derived from edges by the orchestrator.

## Checking Protocol Satisfaction

```python
from taqsim.node import Stores, Generates

if isinstance(node, Stores):
    stored, released = node.store(water, t, dt)

if isinstance(node, Generates):
    water = node.generate(t, dt)
```

## Implementing a Capability

Example: implementing `Stores` for a reservoir:

```python
from taqsim.node import BaseNode, WaterStored, WaterReleased, WaterLost

@dataclass
class Reservoir(BaseNode):
    _capacity: float = 0.0
    _initial_storage: float = 0.0

    @property
    def storage(self) -> float:
        stored = sum(e.amount for e in self.events_of_type(WaterStored))
        released = sum(e.amount for e in self.events_of_type(WaterReleased))
        lost = sum(e.amount for e in self.events_of_type(WaterLost))
        return self._initial_storage + stored - released - lost

    @property
    def capacity(self) -> float:
        return self._capacity

    def store(self, amount: float, t: int, dt: float) -> tuple[float, float]:
        available_space = self.capacity - self.storage
        stored = min(amount, available_space)
        released = amount - stored

        self.record(WaterStored(amount=stored, t=t))
        self.record(WaterReleased(amount=released, t=t))

        return stored, released

# Reservoir satisfies Stores protocol
assert isinstance(Reservoir(id="dam"), Stores)
```

## Protocol vs BaseNode

- `BaseNode`: Provides event recording infrastructure
- Protocols: Define behavioral contracts

A class can:
1. Extend `BaseNode` for event recording
2. Implement protocols for specific capabilities
3. Be checked with `isinstance(obj, Protocol)` at runtime
