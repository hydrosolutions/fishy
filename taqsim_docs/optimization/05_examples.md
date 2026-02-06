# Complete Worked Examples

This guide provides complete, runnable examples demonstrating multi-objective optimization with taqsim.

## Example 1: Simple Two-Objective Optimization

A dam release optimization problem balancing two competing goals: minimize spill (wasted water) and minimize deficit (unmet demand).

### System Setup

```python
from dataclasses import dataclass
from typing import ClassVar

from taqsim import (
    Demand,
    Edge,
    Objective,
    Sink,
    Source,
    Storage,
    Strategy,
    TimeSeries,
    WaterSystem,
    minimize,
    optimize,
)
from taqsim.common import LossReason


# Define a tunable release rule
@dataclass(frozen=True)
class ProportionalRelease(Strategy):
    """Release a fixed fraction of available storage each timestep."""
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __bounds__: ClassVar[dict[str, tuple[float, float]]] = {"rate": (0.1, 50.0)}
    rate: float = 10.0

    def release(self, node: Storage, inflow: float, t: int, dt: float) -> float:
        return min(self.rate * dt, node.storage)


# Simple loss rule (no losses for this example)
@dataclass(frozen=True)
class NoLoss:
    def calculate(self, node: Storage, t: int, dt: float) -> dict[LossReason, float]:
        return {}


# Edge loss rule
@dataclass(frozen=True)
class NoEdgeLoss:
    def calculate(self, edge: Edge, flow: float, t: int, dt: float) -> dict[LossReason, float]:
        return {}


# Create the water system
system = WaterSystem(dt=1.0)

# Seasonal inflow pattern (high in spring, low in summer)
inflows = [80, 100, 120, 90, 60, 40, 30, 35, 50, 70, 85, 95]

# Constant downstream demand
demands = [50.0] * 12

# Add nodes
system.add_node(Source(id="river", inflow=TimeSeries(values=inflows)))
system.add_node(
    Storage(
        id="dam",
        capacity=500.0,
        initial_storage=200.0,
        release_policy=ProportionalRelease(rate=10.0),
        loss_rule=NoLoss(),
    )
)
system.add_node(Demand(id="city", requirement=TimeSeries(values=demands)))
system.add_node(Sink(id="ocean"))

# Connect nodes
system.add_edge(Edge(id="e1", source="river", target="dam", capacity=200.0, loss_rule=NoEdgeLoss()))
system.add_edge(Edge(id="e2", source="dam", target="city", capacity=100.0, loss_rule=NoEdgeLoss()))
system.add_edge(Edge(id="e3", source="city", target="ocean", capacity=100.0, loss_rule=NoEdgeLoss()))

system.validate()
```

### Define Objectives

```python
# Use built-in objectives
objectives = [
    minimize.spill("dam"),       # Reduce overflow (wasted water)
    minimize.deficit("city"),    # Ensure city gets enough water
]
```

### Run Optimization

```python
result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    pop_size=50,
    generations=100,
    seed=42,
)

print(f"Found {len(result)} Pareto-optimal solutions")
```

### Analyze Results

```python
# View all solutions
for i, solution in enumerate(result):
    spill = solution.scores["dam.spill"]
    deficit = solution.scores["city.deficit"]
    rate = solution.parameters["dam.release_policy.rate"]
    print(f"Solution {i}: spill={spill:.1f}, deficit={deficit:.1f}, rate={rate:.2f}")
```

---

## Example 2: Analyzing Trade-offs

The Pareto front reveals the fundamental trade-offs in your system. Each solution represents a different balance between objectives.

### Visualizing the Trade-off Curve

```python
import matplotlib.pyplot as plt

# Extract objective values
spills = [s.scores["dam.spill"] for s in result]
deficits = [s.scores["city.deficit"] for s in result]

plt.figure(figsize=(8, 6))
plt.scatter(spills, deficits, c='blue', s=50)
plt.xlabel("Total Spill (m3)")
plt.ylabel("Total Deficit (m3)")
plt.title("Pareto Front: Spill vs Deficit Trade-off")
plt.grid(True, alpha=0.3)
plt.show()
```

### Interpreting the Pareto Front

The shape of the Pareto front tells you about your system:

**Steep curve**: Small improvements in one objective cost large sacrifices in the other.

**Flat regions**: Multiple solutions achieve similar performance. Choose based on secondary factors.

**Knee points**: Solutions at the "elbow" often represent good compromises.

```python
# Find the "knee" - solutions where both objectives are moderate
def distance_from_origin(s):
    """Normalized distance from ideal (0, 0)."""
    max_spill = max(spills) if spills else 1
    max_deficit = max(deficits) if deficits else 1
    norm_spill = s.scores["dam.spill"] / max_spill
    norm_deficit = s.scores["city.deficit"] / max_deficit
    return (norm_spill ** 2 + norm_deficit ** 2) ** 0.5

knee_solution = min(result, key=distance_from_origin)
print(f"Knee solution: spill={knee_solution.scores['dam.spill']:.1f}, "
      f"deficit={knee_solution.scores['city.deficit']:.1f}")
```

### Comparing Solutions at Different Points

```python
# Sort by spill to see the progression
sorted_solutions = sorted(result.solutions, key=lambda s: s.scores["dam.spill"])

print("Trade-off progression (sorted by spill):")
print("-" * 50)
for s in sorted_solutions[:5]:  # First 5
    print(f"Spill: {s.scores['dam.spill']:6.1f} | "
          f"Deficit: {s.scores['city.deficit']:6.1f} | "
          f"Rate: {s.parameters['dam.release_policy.rate']:.2f}")
```

---

## Example 3: Selecting a Solution

After optimization, you need to select one solution to implement. Here are common selection strategies.

### Find Extremes

```python
# Minimum spill (may have high deficit)
min_spill = min(result, key=lambda s: s.scores["dam.spill"])
print(f"Min spill: spill={min_spill.scores['dam.spill']:.1f}, "
      f"deficit={min_spill.scores['city.deficit']:.1f}")

# Minimum deficit (may have high spill)
min_deficit = min(result, key=lambda s: s.scores["city.deficit"])
print(f"Min deficit: spill={min_deficit.scores['dam.spill']:.1f}, "
      f"deficit={min_deficit.scores['city.deficit']:.1f}")
```

### Find Balanced Solution

```python
# Weighted sum approach
def weighted_score(s, spill_weight=0.5, deficit_weight=0.5):
    """Lower is better."""
    max_spill = max(sol.scores["dam.spill"] for sol in result) or 1
    max_deficit = max(sol.scores["city.deficit"] for sol in result) or 1
    return (
        spill_weight * s.scores["dam.spill"] / max_spill +
        deficit_weight * s.scores["city.deficit"] / max_deficit
    )

# Equal weights
balanced = min(result, key=lambda s: weighted_score(s, 0.5, 0.5))
print(f"Balanced: spill={balanced.scores['dam.spill']:.1f}, "
      f"deficit={balanced.scores['city.deficit']:.1f}")

# Prioritize deficit (city needs are critical)
city_priority = min(result, key=lambda s: weighted_score(s, 0.2, 0.8))
print(f"City priority: spill={city_priority.scores['dam.spill']:.1f}, "
      f"deficit={city_priority.scores['city.deficit']:.1f}")
```

### Apply Constraints

```python
# Find best solution where deficit is below a threshold
max_acceptable_deficit = 100.0
feasible = [s for s in result if s.scores["city.deficit"] <= max_acceptable_deficit]

if feasible:
    # Among feasible, minimize spill
    best_feasible = min(feasible, key=lambda s: s.scores["dam.spill"])
    print(f"Best feasible: spill={best_feasible.scores['dam.spill']:.1f}, "
          f"deficit={best_feasible.scores['city.deficit']:.1f}")
else:
    print("No solution meets the deficit constraint. Consider relaxing it.")
```

### Apply the Selected Solution

```python
# Reconstruct the system with optimized parameters
selected = balanced
optimized_system = selected.to_system()

# Run a fresh simulation
optimized_system.simulate(timesteps=12)

# Analyze the results
dam = optimized_system.nodes["dam"]
city = optimized_system.nodes["city"]

print(f"\nOptimized system results:")
print(f"  Release rate: {dam.release_policy.rate:.2f}")
print(f"  Final storage: {dam.storage:.1f}")
```

---

## Example 4: Using Verbose Mode

Enable progress output to monitor optimization convergence.

```python
result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    pop_size=50,
    generations=20,
    verbose=True,  # Print progress each generation
    seed=42,
)
```

Output:

```
Gen    0 | Pareto:  12 | Best: [45.2341, 120.5678]
Gen    1 | Pareto:  15 | Best: [42.1234, 115.3421]
Gen    2 | Pareto:  18 | Best: [38.9012, 108.7654]
...
Gen   19 | Pareto:  23 | Best: [12.3456, 45.6789]
```

**Reading the output:**
- `Gen`: Current generation number
- `Pareto`: Number of non-dominated solutions found
- `Best`: Objective values of one Pareto-optimal solution

**Convergence indicators:**
- Pareto count stabilizes: The algorithm has found most trade-off solutions
- Best values stop improving: Further generations may not help

### Custom Callback for Advanced Monitoring

```python
def my_callback(population, generation):
    """Custom monitoring callback."""
    if generation % 10 == 0:
        pareto_count = sum(population.rank == 0)
        print(f"Generation {generation}: {pareto_count} Pareto solutions")
    # Return True to stop early, False to continue
    return False

result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    callback=my_callback,
    seed=42,
)
```

---

## Example 5: Parallel Optimization

For large populations or expensive fitness evaluations, parallel processing can significantly reduce optimization time.

### Basic Parallel Usage

```python
# Sequential (default)
result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    n_workers=1,  # One worker, sequential
)

# Use all available CPU cores
result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    n_workers=-1,  # All cores
)

# Fixed number of workers
result = optimize(
    system=system,
    objectives=objectives,
    timesteps=12,
    n_workers=4,  # Exactly 4 workers
)
```

### When to Use Parallel Optimization

Parallel optimization is most beneficial when:

- **Fitness evaluation is expensive**: Each simulation takes significant time
- **Population is large**: More individuals to evaluate per generation
- **Many timesteps**: Longer simulations per evaluation
- **Multi-core system**: You have CPU cores available

For small problems (quick evaluations, small populations), the overhead of process spawning may outweigh benefits.

### Troubleshooting Parallel Execution

**PicklingError**: When using `n_workers > 1`, the evaluate function and all objects it references must be picklable. Common fixes:

1. **Use top-level functions** instead of lambdas or nested functions
2. **Avoid closures** that capture unpicklable objects
3. **Ensure Strategy classes are picklable** (dataclasses usually work well)

```python
# ❌ This may fail with n_workers > 1 (closure captures local variable)
def make_evaluator(system, objectives):
    def evaluate(x):
        candidate = system.with_vector(x.tolist())
        ...
    return evaluate

# ✅ This works (top-level function, no closure)
def evaluate(x, system=system, objectives=objectives):
    candidate = system.with_vector(x.tolist())
    ...
```

**Note**: The built-in `optimize()` function handles pickling correctly. This troubleshooting applies if you're building custom evaluation functions.

---

## Troubleshooting

### No Improvement Over Generations

**Symptom:** Objective values stay the same across all generations.

**Causes and fixes:**

1. **Population too small**: Increase `pop_size` to explore more of the search space.
   ```python
   result = optimize(..., pop_size=200, ...)
   ```

2. **Not enough generations**: Give the algorithm more time to converge.
   ```python
   result = optimize(..., generations=500, ...)
   ```

3. **Narrow bounds**: If parameter bounds are very tight, there may be little room for improvement.

### All Solutions Identical

**Symptom:** Every solution in the result has the same scores and parameters.

**Causes and fixes:**

1. **Parameter bounds too narrow**: Check that bounds allow meaningful variation.
   ```python
   # Too narrow - all solutions will be similar
   __bounds__ = {"rate": (10.0, 10.5)}

   # Better - allows exploration
   __bounds__ = {"rate": (1.0, 50.0)}
   ```

2. **Objective insensitive to parameters**: Ensure the objective actually varies with parameter changes. Test manually:
   ```python
   # Test objective sensitivity
   for rate in [5.0, 25.0, 45.0]:
       test_system = system.with_vector([rate])
       test_system.simulate(12)
       print(f"rate={rate}: score={objectives[0].evaluate(test_system)}")
   ```

### Optimization Very Slow

**Symptom:** Each generation takes a long time.

**Causes and fixes:**

1. **Too many timesteps**: Use fewer timesteps for initial testing.
   ```python
   # Quick test run
   result = optimize(..., timesteps=6, pop_size=20, generations=10, ...)

   # Full run after validating setup
   result = optimize(..., timesteps=365, pop_size=100, generations=200, ...)
   ```

2. **Large population**: Reduce `pop_size` if convergence is fast.
   ```python
   result = optimize(..., pop_size=50, ...)  # Start smaller
   ```

3. **Complex system**: Simplify the system for testing, then scale up.

### Unexpected Objective Values

**Symptom:** Scores are much larger or smaller than expected.

**Causes and fixes:**

1. **Time scaling**: Remember that objectives accumulate over all timesteps.
   ```python
   # If demand=50/timestep and timesteps=365, max deficit could be 50*365=18,250
   ```

2. **Direction confusion**: Check if you're minimizing when you should maximize.
   ```python
   # This minimizes spill - lower is better
   minimize.spill("dam")

   # If you want to maximize water stored, define a custom objective
   ```

3. **Unit mismatch**: Ensure inflows, demands, and capacities use consistent units.
