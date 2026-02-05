# Loss Reasons

## Overview

`LossReason` is a `str` subclass that provides typed, extensible loss categorization for both nodes and edges.

## Design

Unlike a traditional enum, `LossReason` is a string subclass allowing:
- User-defined loss reasons without library modification
- String compatibility (can be used as dict keys, JSON serialization)
- Type safety via type hints

## Built-in Constants

```python
from taqsim.common import EVAPORATION, SEEPAGE, OVERFLOW, INEFFICIENCY, CAPACITY_EXCEEDED

# Use directly in loss rules
return {EVAPORATION: 10.0, SEEPAGE: 5.0}
```

| Constant | Value | Description |
|----------|-------|-------------|
| EVAPORATION | "evaporation" | Surface water evaporation |
| SEEPAGE | "seepage" | Ground infiltration |
| OVERFLOW | "overflow" | Spillage/overflow losses |
| INEFFICIENCY | "inefficiency" | Operational inefficiency losses |
| CAPACITY_EXCEEDED | "capacity_exceeded" | Losses due to exceeding capacity limits |

## Creating Custom Loss Reasons

### Method 1: Direct Instantiation
```python
from taqsim.common import LossReason

INFILTRATION = LossReason("infiltration")
ILLEGAL_EXTRACTION = LossReason("illegal_extraction")

# Use in loss rule
return {INFILTRATION: 5.0}
```

### Method 2: Module Constants
```python
# my_project/constants.py
from taqsim.common import LossReason

CANAL_LEAKAGE = LossReason("canal_leakage")
MEASUREMENT_ERROR = LossReason("measurement_error")
```

## Summarizing Losses

The `summarize_losses()` utility aggregates losses by reason:

```python
from taqsim.common import summarize_losses
from taqsim.node import WaterLost

losses = node.events_of_type(WaterLost)
summary = summarize_losses(losses)
# {"evaporation": 125.5, "seepage": 45.0}
```

## Type Safety

While `LossReason` is a string, type checkers can still provide hints:

```python
def my_loss_rule(storage: float) -> dict[LossReason, float]:
    return {EVAPORATION: storage * 0.01}  # Type-safe
```
