# Design Philosophy

## Core Principle

Taqsim follows a single design rule: **expose everything, decide nothing**.

The simulation engine is intentionally "dumb." It routes water through a network, records every operation as an immutable event, and exposes all internal state for external analysis. It never interprets what the data means or makes policy decisions.

## What Taqsim Does

| Capability | Description |
|------------|-------------|
| **Routes water** | Moves water through DAG topology in topological order |
| **Records events** | Every water movement becomes an immutable, queryable event |
| **Exposes parameters** | All tunable values discoverable via `param_schema()` |
| **Provides traces** | Converts event streams to time-indexed series |
| **Stores annotations** | Tags and metadata attached to any component |

## What Taqsim Does NOT Do

| Anti-capability | Why not |
|-----------------|---------|
| **Optimize** | That's the optimizer's job (`taqsim.optimization`) |
| **Interpret events** | External layers derive meaning from raw events |
| **Make policy decisions** | Strategies encode logic; taqsim just executes them |
| **Validate business rules** | Tags/metadata are opaque; interpretation is external |
| **Aggregate or report** | Traces enable aggregation; taqsim doesn't prescribe how |

## The Boundary

```
┌─────────────────────────────────────────────────────────────┐
│                    INTELLIGENCE LAYERS                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Optimizer   │  │ Visualizer  │  │ Decision Support    │  │
│  │ (NSGA-II)   │  │ (plots)     │  │ (rules, policies)   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │            │
│         ▼                ▼                     ▼            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    QUERY INTERFACE                    │  │
│  │  • Events (.events_of_type())                         │  │
│  │  • Traces (.trace(), @lift)                           │  │
│  │  • Parameters (param_schema(), to_vector())           │  │
│  │  • Annotations (tags, metadata)                       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ expose
                              │
┌─────────────────────────────┴───────────────────────────────┐
│                         TAQSIM CORE                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    WaterSystem                          ││
│  │  • Topology (DAG)                                       ││
│  │  • Simulation loop (topological order)                  ││
│  │  • Water routing (edges)                                ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐  │
│  │  Nodes    │ │   Edges   │ │ Strategies│ │   Events    │  │
│  │  (6 types)│ │ (routing) │ │ (behavior)│ │ (14 types)  │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Exposure Mechanisms

### 1. Event Sourcing

Every water movement is an immutable event. Taqsim records 14 event types (11 node events, 3 edge events) with no interpretation:

```python
# Taqsim records this event...
WaterLost(amount=50.0, reason=EVAPORATION, t=5)

# ...but never decides if 50.0 is "too much" or "acceptable"
# That judgment belongs to external analysis
```

See: [Node Events](nodes/02_events.md), [Edge Events](edges/02_events.md)

### 2. Traces

Traces transform event streams into time-indexed series for analysis:

```python
# Taqsim provides the trace...
spill = dam.trace(WaterSpilled)

# ...external code interprets it
if spill.sum() > threshold:
    print("Excessive spill detected")
```

See: [Trace API](objective/02_trace.md), [@lift decorator](objective/03_lift.md)

### 3. Parameter Exposure

All tunable parameters are discoverable and vectorizable:

```python
# Taqsim exposes parameters...
schema = system.param_schema()
vector = system.to_vector()
bounds = system.bounds_vector()

# ...optimizers use them
result = nsga2(fitness_fn, bounds, ...)
```

See: [Parameter Exposure](system/03_parameter_exposure.md)

### 4. Tags and Metadata

Opaque annotations that taqsim stores but never interprets:

```python
# Taqsim stores these...
node = Storage(id="dam", tags=frozenset({"critical", "regulated"}), ...)

# ...external systems give them meaning
critical_nodes = [n for n in system.nodes.values() if "critical" in n.tags]
```

See: [Tags and Metadata](common/03_tags_metadata.md)

## Why This Matters

### For Users

- **Predictability**: Taqsim behavior is deterministic and auditable
- **Flexibility**: Any analysis or optimization approach works
- **Debuggability**: Full event history enables root cause analysis

### For Developers

- **Testability**: Pure functions with no hidden state
- **Composability**: Layers stack cleanly without coupling
- **Maintainability**: Core stays simple; complexity lives in layers

## Common Misconceptions

| Misconception | Reality |
|---------------|---------|
| "Taqsim is incomplete" | No, it's intentionally minimal. Add intelligence externally. |
| "Events are logging" | No, events ARE the state. There's no hidden internal state. |
| "Traces are reports" | No, traces are queryable data. Reporting is external. |
| "Metadata affects simulation" | No, metadata is opaque. Simulation ignores it entirely. |
