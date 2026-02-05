# Built-in Objectives

## Overview

Taqsim provides two built-in objective factories for common water system optimization goals. These objectives measure outcomes that can be influenced through operational strategies (release rules, allocation decisions).

Access them via the `minimize` registry.

## minimize.spill

Minimize water spilled from a node.

```python
from taqsim.objective import minimize

obj = minimize.spill("reservoir_1")
obj = minimize.spill("city_intake")  # PassThrough with capacity
obj = minimize.spill("reservoir_1", priority=2)
```

**What it measures:** Sum of `WaterSpilled` event amounts at the specified node.

**Applicable nodes:**
- `Storage` — overflow when inflow exceeds reservoir capacity
- `PassThrough` — flow exceeding the `capacity` parameter (if set)

**Use case:** Reduce wasteful overflow from storage nodes. Spills indicate the reservoir exceeded capacity—this can be avoided by releasing water earlier to make room for inflows.

## minimize.deficit

Minimize unmet demand at a node.

```python
from taqsim.objective import minimize

obj = minimize.deficit("city_demand")
```

**What it measures:** Sum of `DeficitRecorded` event deficits at the specified node.

**Use case:** Ensure demand nodes receive their required water. Deficits indicate supply fell short of requirements—this can be reduced by allocating more water to this demand.

## Priority Parameter

All built-in objectives accept a `priority` parameter for multi-objective weighting:

```python
objectives = [
    minimize.deficit("municipal", priority=3),   # Highest priority
    minimize.deficit("irrigation", priority=1),  # Lower priority
    minimize.spill("dam", priority=2),
]
```

Higher priority objectives carry more weight in optimization.

## Error Handling

Objectives raise `ValueError` if the target node doesn't exist:

```python
obj = minimize.spill("nonexistent")
obj.evaluate(system)  # ValueError: Node 'nonexistent' not found
```

## Why Only These Two?

Objectives should measure outcomes that are **controllable through operational strategies**. Physical infrastructure properties like losses (evaporation, seepage, pipe inefficiency) are fixed by the system design—a GA optimizing release schedules cannot change them.

The `maximize` registry has no built-in objectives for the same reason. Custom maximization objectives (like hydropower production) should be registered explicitly.

For custom objectives that combine events or compute derived metrics, see [Creating Custom Objectives](./05_custom.md).
