# optimize() API Reference

## Function Signature

```python
def optimize(
    system: WaterSystem,
    objectives: list[Objective],
    timesteps: int,
    *,
    pop_size: int = 100,
    generations: int = 200,
    seed: int | None = None,
    warm_start: bool = False,
    verbose: bool = False,
    callback: Callable[[Population, int], bool] | None = None,
    n_workers: int = 1,
) -> OptimizeResult:
```

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `system` | `WaterSystem` | required | Validated water system with tunable parameters |
| `objectives` | `list[Objective]` | required | One or more objectives from `minimize`/`maximize` registries |
| `timesteps` | `int` | required | Number of simulation timesteps per evaluation |
| `pop_size` | `int` | `100` | Population size for NSGA-II (minimum 4) |
| `generations` | `int` | `200` | Number of generations to evolve |
| `seed` | `int \| None` | `None` | Random seed for reproducibility |
| `warm_start` | `bool` | `False` | Reserved for future warm-start support |
| `verbose` | `bool` | `False` | Print generation progress to stdout |
| `callback` | `Callable[[Population, int], bool] \| None` | `None` | Per-generation callback; return `True` to stop early |
| `n_workers` | `int` | `1` | Number of parallel workers. Use `1` for sequential, `-1` for all CPU cores. |

## Returns

**`OptimizeResult`** - Container for optimization results:

```python
@dataclass(frozen=True, slots=True)
class OptimizeResult:
    solutions: list[Solution]  # Pareto-optimal solutions
    population: Population     # Final NSGA-II population

    def __len__(self) -> int: ...
    def __getitem__(self, idx: int) -> Solution: ...
```

Each `Solution` contains:

| Attribute | Type | Description |
|-----------|------|-------------|
| `scores` | `dict[str, float]` | Objective name to score mapping |
| `parameters` | `dict[str, float]` | Parameter path to value mapping |
| `to_system()` | method | Returns configured (unsimulated) `WaterSystem` |

## Parameter Details

### system

The `WaterSystem` must be validated before optimization:

```python
from taqsim.common import Frequency

system = WaterSystem(frequency=Frequency.MONTHLY)
system.validate()  # Required
result = optimize(system, objectives, timesteps=12)
```

The system must also expose tunable parameters via strategies with bounds. If `system.param_schema()` returns an empty list, optimization will fail.

**Note:** The optimizer works with compact parameter vectors that are frequency-agnostic. The `frequency` on `WaterSystem` affects simulation behavior only -- it does not change the shape or contents of the parameter vectors that the optimizer evolves. Cyclical parameters are stored in their compact (single-cycle) form in the vector; the system handles tiling at simulation time.

### objectives

Objectives are created from the `minimize` and `maximize` registries:

```python
from taqsim.objective import minimize, maximize

objectives = [
    minimize.spill("reservoir_1"),
    minimize.deficit("city_demand"),
]
```

At least one objective is required. For multi-objective optimization, NSGA-II finds Pareto-optimal trade-offs.

### timesteps

Number of simulation steps per candidate evaluation. This directly affects computational cost. Choose based on:

- Seasonal patterns to capture
- Required temporal resolution
- Available compute budget

### pop_size

Population size for the genetic algorithm. Constraints and recommendations:

- **Minimum**: 4 (enforced)
- **Typical range**: 50-200
- **Higher values**: Better exploration, slower convergence
- **Lower values**: Faster convergence, risk of premature convergence

### generations

Number of evolutionary generations. Guidelines:

- **Typical range**: 100-500
- **Simple problems**: 100-200 generations
- **Complex landscapes**: 300-500 generations
- **Diminishing returns**: Progress usually plateaus; use `callback` to detect convergence

### seed

Random seed for full reproducibility. When set:

- Initialization is deterministic
- Crossover and mutation use derived sub-seeds
- Results are reproducible across runs

```python
# Reproducible optimization
result1 = optimize(system, objectives, timesteps=12, seed=42)
result2 = optimize(system, objectives, timesteps=12, seed=42)
# result1 and result2 are identical
```

### n_workers

Controls parallel evaluation of the fitness function:

- **`1`** (default): Sequential execution. Use for debugging or when `evaluate` is not picklable.
- **`-1`**: Use all available CPU cores.
- **`n > 1`**: Use exactly `n` worker processes.

```python
# Sequential (default)
result = optimize(system, objectives, timesteps=12, n_workers=1)

# Use all CPU cores
result = optimize(system, objectives, timesteps=12, n_workers=-1)

# Fixed 4 workers
result = optimize(system, objectives, timesteps=12, n_workers=4)
```

**Note:** Parallel execution requires the evaluate function to be picklable. If you encounter `PicklingError`, try using top-level functions instead of lambdas or closures.

## Error Handling

| Exception | Condition |
|-----------|-----------|
| `ValidationError` | System not validated (`system.validate()` not called) |
| `ValueError` | No tunable parameters in system |
| `ValueError` | Empty objectives list |
| `ValueError` | `pop_size < 4` |
| `ValueError` | `n_workers` is 0 or less than -1 |

```python
from taqsim.system import ValidationError

try:
    result = optimize(system, objectives, timesteps=12)
except ValidationError:
    system.validate()
    result = optimize(system, objectives, timesteps=12)
except ValueError as e:
    print(f"Configuration error: {e}")
```

## Performance

Total fitness evaluations = `pop_size` x `generations` x `timesteps` simulations.

| pop_size | generations | timesteps | Total evaluations |
|----------|-------------|-----------|-------------------|
| 50 | 100 | 12 | 60,000 |
| 100 | 200 | 12 | 240,000 |
| 100 | 200 | 52 | 1,040,000 |
| 200 | 500 | 52 | 5,200,000 |

For expensive simulations, consider:

1. Reducing `timesteps` during exploration
2. Using `verbose=True` to monitor convergence
3. Implementing early stopping via `callback`
4. **Using `n_workers=-1` for parallel evaluation on multi-core systems**

```python
def early_stop(pop: Population, gen: int) -> bool:
    # Stop if best solution hasn't improved in 20 generations
    return gen > 50 and pop.stagnation_count > 20

result = optimize(
    system, objectives, timesteps=12,
    generations=500, callback=early_stop
)
```

## Example

```python
from taqsim.system import WaterSystem
from taqsim.common import Frequency
from taqsim.objective import minimize
from taqsim.optimization import optimize

# Build and validate system
system = WaterSystem(frequency=Frequency.MONTHLY)
system.validate()

# Define objectives
objectives = [
    minimize.spill("reservoir"),
    minimize.deficit("city_demand"),
]

# Run optimization
result = optimize(
    system,
    objectives,
    timesteps=12,
    pop_size=100,
    generations=200,
    seed=42,
    verbose=True,
)

# Access results
print(f"Found {len(result)} Pareto-optimal solutions")

for solution in result.solutions:
    print(f"Scores: {solution.scores}")
    print(f"Parameters: {solution.parameters}")

# Get configured system from best solution
best_system = result[0].to_system()
best_system.simulate(12)
```
