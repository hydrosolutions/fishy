# The Node Contract

## Overview

Each node in taqsim adheres to a minimal contract: implement `update(t)` and, if accepting upstream water, satisfy the `Receives` protocol. All internal processing is private — the system and external code interact through `update()`, `receive()`, and **events**.

## The Receives Protocol

`Receives` is the sole runtime-checked protocol. `WaterSystem` uses `isinstance(node, Receives)` to determine which nodes can accept water from upstream edges.

```python
@runtime_checkable
class Receives(Protocol):
    def receive(self, amount: float, source_id: str, t: Timestep) -> float: ...
```

Returns the amount actually received.

### Which nodes satisfy Receives

| Node        | Receives |
|-------------|----------|
| Source      |          |
| PassThrough | yes      |
| Splitter    | yes      |
| Demand      | yes      |
| Storage     | yes      |
| Reach       | yes      |
| Sink        | yes      |

Source is the only node that does not receive water — it generates it.

## The update() Contract

`update(t: Timestep)` is the universal entry point called by `WaterSystem` for every node at each timestep. The system never calls internal sub-steps.

Each node type implements a private pipeline inside `update()`:

| Node        | Private Pipeline                         | Output Event     |
|-------------|------------------------------------------|------------------|
| Source      | `_generate`                              | WaterOutput      |
| PassThrough | (pass-through)                           | WaterOutput      |
| Splitter    | `_distribute` (via split_policy)         | WaterDistributed |
| Demand      | `_consume`                               | WaterOutput      |
| Storage     | `_store`, `_lose`, `_release`            | WaterOutput      |
| Reach       | route, lose, transit snapshot            | WaterOutput      |
| Sink        | (terminal — no-op)                       | —                |

## Events as the Observation Layer

Since internal steps are private, all observation happens through events:

```python
# Assert on events, not internal state
source.update(t)
events = source.events_of_type(WaterGenerated)
assert events[0].amount == 100.0
```

This is the same pattern used by Reach from the start — the refactoring converges all nodes to this approach.

## Checking Protocol Satisfaction

```python
from taqsim.node import Receives

if isinstance(node, Receives):
    node.receive(amount, source_id, t)
```

## Protocol vs BaseNode

- `BaseNode`: Provides event recording infrastructure and the `update()` contract
- `Receives`: The sole protocol — defines the ability to accept water from upstream
