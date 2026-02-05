# Multi-Objective Optimization Overview

## Purpose

Water systems involve inherent trade-offs. Releasing more water reduces spill but may increase downstream deficits. Storing water ensures future supply but risks overflow during wet periods. The `taqsim` optimization module finds balanced solutions across competing objectives using multi-objective genetic algorithms.

Typical trade-offs include:

- **Deficit vs Spill** - Aggressive releases reduce spill but may leave demands unmet
- **Storage vs Reliability** - High storage targets improve drought resilience but increase overflow risk
- **Cost vs Performance** - Infrastructure upgrades improve service but increase capital expense

## Core Concepts

### Multi-Objective Optimization

Unlike single-objective optimization (find the one best solution), multi-objective optimization finds a *set* of solutions representing different trade-off points. No single solution dominates all others across every objective.

### Pareto Optimality

A solution is **Pareto-optimal** if no other solution improves one objective without worsening another. The set of all Pareto-optimal solutions forms the **Pareto front** - a surface in objective space representing the best achievable trade-offs.

### Trade-Off Surfaces

The Pareto front reveals the cost of improving one objective in terms of another. A steep region indicates large gains in one objective for small losses in another. Flat regions indicate diminishing returns.

See `04_pareto_concepts.md` for detailed treatment of these concepts.

## Quick Start

```python
from taqsim import optimize, minimize

result = optimize(
    system=my_water_system,
    objectives=[minimize.deficit("farm"), minimize.spill("dam")],
    timesteps=12,
    pop_size=100,
    generations=200,
    seed=42,
)

print(f"Found {len(result)} Pareto-optimal solutions")
for solution in result:
    print(solution.scores)
```

## How It Works

The optimization pipeline:

1. **System Definition** - Define nodes, edges, and controllable parameters
2. **Vectorization** - Extract decision variables from strategy parameters
3. **Genetic Algorithm** - Evolve population toward Pareto front using NSGA-II
4. **Evaluation** - Simulate each candidate and compute objective scores
5. **Selection** - Non-dominated sorting preserves diverse trade-off solutions
6. **Result** - Return Pareto-optimal solutions with their parameter values and scores

```
┌──────────┐    ┌─────────────┐    ┌────────────┐    ┌─────────────┐
│  System  │ -> │ Vectorize   │ -> │     GA     │ -> │ Pareto Front│
│Definition│    │ Parameters  │    │ Evolution  │    │  Solutions  │
└──────────┘    └─────────────┘    └────────────┘    └─────────────┘
```

## When to Use

**Use multi-objective optimization when:**

- Multiple conflicting objectives exist (deficit vs spill, cost vs reliability)
- You need to understand trade-offs rather than find a single answer
- Decision-makers require options to choose from based on priorities
- System behavior is complex enough that intuition alone is insufficient

**Consider simpler approaches when:**

- A single objective dominates (use single-objective optimization)
- Objectives can be combined into a weighted sum (use scalar optimization)
- The system is simple enough to solve analytically
- Real-time decisions are needed (pre-compute lookup tables instead)
