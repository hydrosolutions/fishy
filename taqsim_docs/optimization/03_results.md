# Working with Optimization Results

After running `optimize()`, you receive an `OptimizeResult` containing the Pareto-optimal solutions discovered during the search.

## OptimizeResult

The `OptimizeResult` object provides access to the optimization outcomes:

```python
result = optimize(...)
```

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `solutions` | `list[Solution]` | Pareto-optimal solutions |
| `population` | `Population` | Raw ctrl-freak Population for advanced use |

### Container Interface

`OptimizeResult` supports standard Python container operations:

```python
# Number of Pareto solutions
print(f"Found {len(result)} solutions")

# Access by index
best = result[0]
second = result[1]

# Iteration
for solution in result:
    print(solution.scores)
```

## Solution

Each `Solution` represents one Pareto-optimal configuration discovered by the optimizer.

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `scores` | `dict[str, float]` | Objective values keyed by objective name |
| `parameters` | `dict[str, float]` | Parameter values keyed by path |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `to_system()` | `WaterSystem` | Reconstruct the system with optimized parameters (unsimulated) |

### Inspecting Solutions

```python
solution = result[0]

# View objective scores
print(solution.scores)
# {'total_cost': 1250000.0, 'unmet_demand': 0.05}

# View parameter values
print(solution.parameters)
# {'pipes.main_line.diameter': 0.3, 'pumps.station_1.power': 150.0}
```

## Example Workflow

A typical workflow for analyzing and applying optimization results:

```python
result = optimize(...)

# Browse solutions
print(f"Found {len(result)} solutions")
for i, solution in enumerate(result):
    print(f"Solution {i}: {solution.scores}")

# Select and apply
best = result[0]
system = best.to_system()
system.simulate(timesteps)
# Now analyze the simulated system
```

## Advanced: Raw Population Access

For advanced analysis, access the underlying ctrl-freak `Population` object:

```python
# Access all individuals, not just Pareto front
pop = result.population
print(f"Total population: {len(pop.x)}")
print(f"Pareto front: {sum(pop.rank == 0)}")
```

The `population` attribute exposes the full evolutionary state, enabling:

- Analysis of solution diversity
- Visualization of the entire population
- Custom post-processing beyond the Pareto front
