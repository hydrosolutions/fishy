# Multi-Objective Optimization and Pareto Concepts

## The Problem of Multiple Objectives

Real water systems rarely have a single goal. Operators must balance competing demands:

- **Minimize water deficit** (meet all demands)
- **Minimize spillage** (don't waste water)
- **Minimize pumping costs** (energy efficiency)
- **Maximize storage** (buffer for dry periods)

These objectives often conflict. Reducing deficit might mean keeping reservoirs fuller, which increases spill risk during wet periods. Minimizing pumping costs might mean tolerating higher deficits during peak demand.

**The fundamental challenge**: You cannot optimize all objectives simultaneously.


## Why Not Just Combine Objectives?

A tempting approach is to combine multiple objectives into one:

```
Total Score = w1 * deficit + w2 * spill + w3 * cost
```

This has serious limitations:

### Incommensurable Units

How do you add cubic meters of water to dollars of cost? The weights become arbitrary conversion factors that obscure real trade-offs.

### Weight Sensitivity

Small changes in weights can dramatically shift the "optimal" solution. The choice of weights embeds value judgments that may not be transparent.

### Non-Convex Fronts

Weighted sums can only find solutions on convex portions of the trade-off surface. Important compromise solutions may be invisible:

```
      ↑ Objective 2
      │
      │  A●
      │     ╲
      │      ●B  ← This solution cannot be found
      │     ╱      by any weighted sum
      │  C●
      │
      └──────────────→ Objective 1
```

A weighted sum draws a straight line and finds where it touches the front. Point B lies in a concave region - no straight line can reach it.


## Pareto Optimality Explained

Instead of collapsing objectives into one, Pareto optimality preserves the full trade-off structure.

### Dominance

Solution A **dominates** solution B if:
1. A is at least as good as B on **every** objective
2. A is strictly better than B on **at least one** objective

Example with two objectives (both minimized):

| Solution | Deficit | Spill |
|----------|---------|-------|
| A        | 100     | 50    |
| B        | 150     | 80    |
| C        | 120     | 40    |

- A dominates B (better on both)
- A does not dominate C (C has less spill)
- C does not dominate A (A has less deficit)

### Non-Dominated Solutions

A solution is **non-dominated** (or Pareto optimal) if no other solution dominates it. In the example above, both A and C are non-dominated.

Non-dominated solutions represent genuine trade-offs: to improve on one objective, you must sacrifice on another.

### The Pareto Front

The **Pareto front** is the set of all non-dominated solutions. It forms a surface (or curve in 2D) representing the boundary of achievable performance:

```
      ↑ spill (minimize)
      │
      │  ╭──────╮  ← Pareto front
      │ ╱        ╲    (non-dominated solutions)
 high │●          ╲
      │            ●
      │             ╲
  low │              ●
      │
      └────────────────→ deficit (minimize)
           low      high


      Solutions ON the front: optimal trade-offs
      Solutions INSIDE: dominated (can be improved)
      Solutions OUTSIDE: infeasible
```

Every point on the Pareto front represents a different balance of priorities. Moving along the front means accepting more of one objective to get less of another.


## Interpreting Pareto Results

### Trade-Off Analysis

The shape of the front reveals the cost of trade-offs:

```
Steep section:              Flat section:
Large spill reduction       Large deficit reduction
for small deficit increase  for small spill increase

     ↑                          ↑
     │●                         │
     │ ●                        │●────●────●
     │  ●                       │
     │   ●                      │
     └────→                     └────────────→
```

**Knee points** - where the front bends sharply - often represent attractive compromises. Beyond the knee, you pay a lot in one objective for marginal gains in another.

### No Single "Best"

A key insight: **the Pareto front does not contain a single best solution**. Every point on the front is equally "optimal" in the Pareto sense.

Selecting a final solution requires human judgment about priorities:
- Risk-averse operators might prefer low-deficit solutions
- Cost-conscious operators might accept higher deficits to reduce expenses
- Regulations might impose hard constraints that narrow choices

The Pareto front provides options; stakeholders provide values.

### Decision Support

Multi-objective optimization transforms the problem from "find the answer" to "understand the trade-offs." This supports better decisions by:

1. **Revealing hidden trade-offs** that weren't obvious
2. **Quantifying costs** of different priorities
3. **Enabling informed negotiation** among stakeholders


## NSGA-II: Finding the Pareto Front

NSGA-II (Non-dominated Sorting Genetic Algorithm II) is a popular algorithm for multi-objective optimization.

### Core Ideas

**Population-based search**: Instead of tracking one solution, maintain a population of candidates. This allows exploring multiple parts of the front simultaneously.

**Evolutionary operators**: Generate new solutions by combining and mutating existing ones. Good solutions survive and reproduce.

**Pareto ranking**: Sort solutions into "fronts" based on dominance:
- Front 1: Non-dominated by anyone
- Front 2: Non-dominated except by Front 1
- Front 3: Non-dominated except by Fronts 1-2
- ...and so on

```
      ↑
      │  ●  ●      ← Front 1 (best)
      │    ●  ●
      │  ●    ●    ← Front 2
      │      ●
      │    ●   ●   ← Front 3
      │
      └──────────→
```

**Crowding distance**: Among solutions in the same front, prefer those in less crowded regions. This maintains diversity and spreads solutions across the entire front.

### Algorithm Flow

```
1. Initialize random population
2. Evaluate all objectives for each solution
3. Repeat for N generations:
   a. Select parents (prefer lower fronts, then higher crowding)
   b. Create offspring via crossover and mutation
   c. Combine parents and offspring
   d. Rank by Pareto dominance
   e. Select survivors (fill by front, use crowding to break ties)
4. Return final Front 1 as Pareto approximation
```

### Practical Considerations

- **Population size**: Larger populations explore more but cost more evaluations
- **Generations**: More generations refine the front but increase runtime
- **Crossover/mutation rates**: Control exploration vs exploitation balance

The result is not the true Pareto front (which may be infinite) but an approximation: a finite set of high-quality trade-off solutions.


## Summary

| Concept | Definition |
|---------|------------|
| Dominance | A dominates B if A is at least as good everywhere and strictly better somewhere |
| Non-dominated | Not dominated by any other solution |
| Pareto front | Set of all non-dominated solutions |
| Trade-off | Improvement on one objective requires sacrifice on another |
| NSGA-II | Genetic algorithm that finds Pareto front approximations |

The Pareto approach shifts optimization from finding "the answer" to mapping "the possibilities." This supports transparent, informed decision-making in complex systems with competing goals.
