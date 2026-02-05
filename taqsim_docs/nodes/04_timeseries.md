# TimeSeries

## Overview

`TimeSeries` is a dataclass that provides standardized time-indexed data for water system simulation. It stores sequences of water volumes used by `Source` (inflow) and `Demand` (requirement) nodes.

## Creation

```python
from taqsim.node import TimeSeries

# From a list of floats
inflow = TimeSeries(values=[100.0, 150.0, 200.0, 175.0])

# Typical usage: monthly inflows in m3/s
monthly_inflows = TimeSeries(values=[
    10.5, 12.3, 15.0, 18.2,  # Jan-Apr
    22.1, 25.0, 20.5, 16.3,  # May-Aug
    13.2, 11.0, 10.2, 10.0   # Sep-Dec
])
```

## Validation

All values are validated on creation using numpy:

| Constraint | Error Message |
|------------|---------------|
| Non-empty | `"TimeSeries cannot be empty"` |
| Non-negative | `"TimeSeries contains negative values"` |
| Finite | `"TimeSeries contains non-finite values"` |

```python
# These raise ValueError:
TimeSeries(values=[])              # empty
TimeSeries(values=[-1.0, 2.0])     # negative
TimeSeries(values=[1.0, float('inf')])  # non-finite
TimeSeries(values=[1.0, float('nan')])  # non-finite
```

## Access

### Indexing

Access values by timestep using `__getitem__`:

```python
ts = TimeSeries(values=[100.0, 200.0, 300.0])

ts[0]  # 100.0
ts[1]  # 200.0
ts[2]  # 300.0
```

### Length

Get the number of timesteps using `__len__`:

```python
ts = TimeSeries(values=[100.0, 200.0, 300.0])

len(ts)  # 3
```

## Usage with Nodes

### Source Node

```python
from taqsim.node import Source, TimeSeries

inflow = TimeSeries(values=[10.0, 15.0, 20.0, 12.0])

source = Source(
    id="river_intake",
    inflow=inflow,
)
```

### Demand Node

```python
from taqsim.node import Demand, TimeSeries

requirement = TimeSeries(values=[5.0, 8.0, 12.0, 6.0])

demand = Demand(
    id="irrigation",
    requirement=requirement,
)

# With optional efficiency and consumption parameters
demand_with_losses = Demand(
    id="irrigation_lossy",
    requirement=requirement,
    efficiency=0.8,           # 80% delivery efficiency (20% lost in transit)
    consumption_fraction=0.7, # 70% consumed, 30% returned
)
```

## Conversion to Volume

`TimeSeries` stores flow rates. During simulation, values are converted to volumes:

```python
# In Source.generate():
amount = self.inflow[t] * dt  # flow rate * time = volume

# In Demand.consume():
required = self.requirement[t] * dt
```
