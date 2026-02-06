# Frequency and Timestep

## Overview

The `Frequency` enum and `Timestep` dataclass provide frequency-aware time handling. They allow cyclical parameters defined at one frequency (e.g., monthly) to be used correctly in simulations running at a different frequency (e.g., daily).

## Frequency Enum

`Frequency` is an `IntEnum` whose integer values represent the number of periods per year:

```python
from taqsim.time import Frequency

class Frequency(IntEnum):
    DAILY = 365
    WEEKLY = 52
    MONTHLY = 12
    YEARLY = 1
```

### Values

| Member | Value | Meaning |
|--------|-------|---------|
| `DAILY` | 365 | One period per day |
| `WEEKLY` | 52 | One period per week |
| `MONTHLY` | 12 | One period per month |
| `YEARLY` | 1 | One period per year |

Because `Frequency` is an `IntEnum`, members can be used directly in arithmetic expressions.

### scale() Static Method

Converts a rate or quantity from one frequency to another:

```python
Frequency.scale(value, from_freq, to_freq) -> float
```

The formula is: `value * from_freq / to_freq`.

**Use cases:**

- Converting a monthly evaporation rate to a daily rate
- Converting a yearly budget to a weekly allocation
- Any rate conversion between temporal resolutions

```python
# 120 mm/month evaporation -> daily rate
daily_evap = Frequency.scale(120.0, Frequency.MONTHLY, Frequency.DAILY)
# 120 * 12 / 365 = ~3.945 mm/day

# 1000 m3/year -> weekly allocation
weekly = Frequency.scale(1000.0, Frequency.YEARLY, Frequency.WEEKLY)
# 1000 * 1 / 52 = ~19.23 m3/week
```

## Timestep Dataclass

`Timestep` pairs a simulation step index with the simulation's frequency:

```python
from taqsim.time import Timestep, Frequency

@dataclass(frozen=True, slots=True)
class Timestep:
    index: int
    frequency: Frequency
```

### Fields

| Field | Type | Purpose |
|-------|------|---------|
| `index` | `int` | Zero-based simulation step number |
| `frequency` | `Frequency` | Temporal resolution of the simulation |

### **index** Protocol

`Timestep` implements `__index__`, which means it can be used anywhere Python expects an integer index:

```python
t = Timestep(index=5, frequency=Frequency.DAILY)

values = [10, 20, 30, 40, 50, 60, 70]
values[t]  # 60 -- direct list indexing via __index__
```

It also implements `__int__` and `__mod__` for arithmetic compatibility.

### scale() Instance Method

Convenience wrapper around `Frequency.scale()` that defaults `to_freq` to the timestep's own frequency:

```python
t = Timestep(index=0, frequency=Frequency.DAILY)

# Convert a monthly rate to the simulation's frequency (daily)
daily_rate = t.scale(120.0, from_freq=Frequency.MONTHLY)
# Equivalent to: Frequency.scale(120.0, Frequency.MONTHLY, Frequency.DAILY)

# Or specify an explicit target frequency
weekly_rate = t.scale(120.0, from_freq=Frequency.MONTHLY, to_freq=Frequency.WEEKLY)
```

## Frequency-Aware Index Mapping

When a cyclical parameter is defined at a different frequency than the simulation, `param_at()` maps the simulation timestep to the correct parameter index.

### The Formula

```
idx = (t.index * param_freq // t.frequency) % len(value)
```

Where:

- `t.index` is the current simulation step
- `param_freq` is the `Frequency` declared for this parameter (from `__cyclical_freq__`)
- `t.frequency` is the simulation's `Frequency`
- `len(value)` is the number of values in the cyclical tuple

The integer division (`//`) maps simulation steps to parameter positions, and the modulo (`%`) wraps around when the cycle completes.

### Example: Daily Simulation with Monthly Parameters

A strategy declares 12 monthly values. The simulation runs daily (365 steps/year):

```python
@dataclass(frozen=True)
class SeasonalRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __time_varying__: ClassVar[tuple[str, ...]] = ("rate",)
    __cyclical__: ClassVar[tuple[str, ...]] = ("rate",)
    __cyclical_freq__: ClassVar[dict[str, Frequency]] = {"rate": Frequency.MONTHLY}

    rate: tuple[float, ...] = (10, 20, 30, 40, 50, 60, 70, 60, 50, 40, 30, 20)
```

For a daily simulation timestep `t`:

```
idx = (t.index * 12 // 365) % 12
```

| Simulation day (`t.index`) | Mapped month (`idx`) | Value |
|---------------------------|---------------------|-------|
| 0 | 0 | 10 |
| 30 | 0 | 10 |
| 31 | 1 | 20 |
| 60 | 1 | 20 |
| 61 | 2 | 30 |
| 364 | 11 | 20 |

Each group of ~30 daily steps maps to the same monthly parameter value.

### Example: Monthly Simulation with Weekly Parameters

A strategy declares 52 weekly values. The simulation runs monthly (12 steps/year):

```
idx = (t.index * 52 // 12) % 52
```

| Simulation month (`t.index`) | Mapped week (`idx`) | Description |
|------------------------------|--------------------| ------------|
| 0 | 0 | First week of Jan |
| 1 | 4 | First week of Feb |
| 6 | 26 | Mid-year |
| 11 | 47 | Late December |

Each monthly step picks the corresponding week's value, effectively sampling the weekly data at monthly resolution.

## When to Use scale() vs param_at()

These two mechanisms serve different purposes:

| Mechanism | Purpose | Example |
|-----------|---------|---------|
| `Frequency.scale()` / `t.scale()` | **Rate conversion** -- convert a physical rate from one unit to another | Monthly evaporation rate to daily rate |
| `param_at()` | **Value lookup** -- retrieve the correct cyclical parameter value for the current timestep | Get this month's allocation ratio during a daily simulation |

**Use `scale()` when** you have a rate expressed in one temporal unit and need it in another. The value itself changes (e.g., 120 mm/month becomes ~3.9 mm/day).

**Use `param_at()` when** you have a sequence of parameter values defined at some frequency and need to look up the right one for the current simulation step. The value does not change -- you are selecting from the sequence.

```python
# Rate conversion: physical unit change
daily_evap = t.scale(monthly_evap_rate, from_freq=Frequency.MONTHLY)

# Value lookup: selecting from cyclical params
current_ratio = self.param_at("city_fraction", t)
```

## Calendar Date Mapping

The `time_index` function bridges integer timesteps to real calendar dates. The simulation engine itself stays in integer-space — `time_index` is a pure derivation for intelligence layers that need calendar awareness (e.g., computing monthly means or day-of-year timing).

```python
from datetime import date
from taqsim.time import Frequency, time_index

time_index(start: date, frequency: Frequency, n: int) -> tuple[date, ...]
```

Given a start date, a frequency, and a count `n`, it returns `n` dates spaced according to the frequency:

| Frequency | Spacing |
|-----------|---------|
| `DAILY` | `start + timedelta(days=i)` |
| `WEEKLY` | `start + timedelta(weeks=i)` |
| `MONTHLY` | Calendar months from start (day clamped to month length) |
| `YEARLY` | Calendar years from start (day clamped to month length) |

Monthly and yearly offsets are always computed from the **original start date**, not from the previous entry. This means day-of-month is preserved when the target month is long enough, and clamped otherwise:

```python
# Monthly: Jan 31 -> Feb 29 (leap) -> Mar 31 -> Apr 30
time_index(date(2024, 1, 31), Frequency.MONTHLY, 4)
# (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 31), date(2024, 4, 30))

# Daily: 3 days from Jan 1
time_index(date(2024, 1, 1), Frequency.DAILY, 3)
# (date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3))
```

`WaterSystem` exposes this as a convenience method when `start_date` is set — see [WaterSystem Architecture](../system/01_architecture.md).
