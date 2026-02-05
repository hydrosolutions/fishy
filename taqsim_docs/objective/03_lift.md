# lift Decorator

## Purpose

The `@lift` decorator transforms a scalar function into one that works on both scalars and Traces. This enables reusable physics transformations.

## Signature

```python
def lift(fn: Callable[[float], float]) -> Callable[[Trace | float], Trace | float]
```

## When to Use

Use `@lift` when you have a physics formula or transformation that:

1. Operates on scalar values
2. Needs to be applied across a time series
3. Should work with both raw floats and Traces

## Basic Example

```python
from taqsim.objective import lift, Trace

@lift
def to_megaliters(cubic_meters: float) -> float:
    return cubic_meters / 1000

# Works on scalars
to_megaliters(5000)  # 5.0

# Works on Traces
volumes = Trace.from_dict({0: 1000, 1: 2000, 2: 3000})
to_megaliters(volumes)  # Trace: {0: 1.0, 1: 2.0, 2: 3.0}
```

## Physics Example: Hydropower

The `@lift` decorator only lifts single-argument functions. For multi-parameter physics formulas, use `Trace.map()` or Trace arithmetic instead:

```python
from taqsim.objective import Trace

GRAVITY = 9.81  # m/s^2
WATER_DENSITY = 1000  # kg/m^3

# Using Trace arithmetic for multi-parameter formulas
def compute_power(flow_trace: Trace, head_m: float = 50, efficiency: float = 0.85) -> Trace:
    """P = rho * g * Q * H * eta"""
    return flow_trace * WATER_DENSITY * GRAVITY * head_m * efficiency

# Apply to release trace
power_trace = compute_power(release_trace)
total_energy = power_trace.sum()
```

Note: `@lift` only works with single-argument functions (signature `Callable[[float], float]`). For formulas with multiple parameters, use Trace's built-in arithmetic operations or `map()`.

## Composing Lifted Functions

Lifted functions compose naturally:

```python
@lift
def celsius_to_kelvin(c: float) -> float:
    return c + 273.15

@lift
def saturation_vapor_pressure(temp_k: float) -> float:
    """Approximate SVP in kPa"""
    return 0.611 * math.exp(17.27 * (temp_k - 273.15) / (temp_k - 35.85))

# Chain transformations
temp_c = Trace.from_dict({0: 20, 1: 25, 2: 30})
temp_k = celsius_to_kelvin(temp_c)
svp = saturation_vapor_pressure(temp_k)
```

## Alternative: Using map

For simple transformations, `Trace.map()` is often clearer:

```python
# Using lift
@lift
def double(x: float) -> float:
    return x * 2

doubled = double(trace)

# Using map (simpler for one-off use)
doubled = trace.map(lambda x: x * 2)
```

Use `@lift` when the transformation is reusable or semantically meaningful. Use `map` for ad-hoc transformations.
