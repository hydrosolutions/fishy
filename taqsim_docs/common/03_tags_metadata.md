# Tags and Metadata

## Overview

Tags and metadata provide a mechanism for intelligence layers to annotate and query simulation components without Taqsim core interpreting these values. This enables clean separation of concerns:

- **Taqsim core**: Stores tags and metadata as opaque data
- **Intelligence layers**: Interpret and use these annotations for filtering, categorization, and decision-making

## Field Definitions

### Tags

`tags: frozenset[str]` - An immutable set of string labels for categorization.

- Immutable (`frozenset`) to prevent accidental modification
- Use for categorical classification (e.g., "primary", "backup", "seasonal")
- Supports set operations for filtering (intersection, union)

### Metadata

`metadata: dict[str, Any]` - A flexible dictionary for arbitrary key-value pairs.

- Mutable dictionary for extensibility
- Use for structured data (e.g., `{"priority": 1, "owner": "agency_a"}`)
- Values can be any type (strings, numbers, nested dicts, lists)

## Usage on Nodes

All node types (`Source`, `Storage`, `Demand`, `Splitter`, `PassThrough`, `Sink`) inherit `tags` and `metadata` from `BaseNode`:

```python
from taqsim.node import Source, Storage, Sink
from taqsim.node.timeseries import TimeSeries

# Source with tags and metadata
source = Source(
    id="river_intake",
    inflow=TimeSeries([100.0] * 12),
    tags=frozenset({"upstream", "primary"}),
    metadata={"watershed": "jordan", "capacity_mcm": 50},
)

# Storage with operational tags
storage = Storage(
    id="main_reservoir",
    capacity=1000.0,
    release_rule=my_release_rule,
    loss_rule=my_loss_rule,
    tags=frozenset({"reservoir", "regulated"}),
    metadata={"built_year": 1985, "operator": "NWC"},
)

# Sink with classification
sink = Sink(
    id="sea_outlet",
    tags=frozenset({"terminal", "environmental"}),
    metadata={"ecosystem": "dead_sea"},
)
```

## Usage on Edges

Edges also support `tags` and `metadata`:

```python
from taqsim.edge import Edge

# Canal edge with infrastructure metadata
canal = Edge(
    id="main_canal",
    source="reservoir",
    target="city_demand",
    capacity=200.0,
    loss_rule=canal_loss_rule,
    tags=frozenset({"canal", "concrete", "primary"}),
    metadata={"length_km": 45.5, "year_built": 1972},
)

# River edge with natural flow characteristics
river = Edge(
    id="river_segment",
    source="upstream",
    target="downstream",
    capacity=500.0,
    loss_rule=river_loss_rule,
    tags=frozenset({"river", "natural"}),
    metadata={"average_velocity_mps": 1.2},
)
```

## Usage on Strategies

Strategies use class-level tags and metadata via `ClassVar` declarations:

```python
from dataclasses import dataclass
from typing import ClassVar, Mapping
from taqsim.common import Strategy

@dataclass(frozen=True)
class SeasonalRelease(Strategy):
    __params__: ClassVar[tuple[str, ...]] = ("rate",)
    __tags__: ClassVar[frozenset[str]] = frozenset({"operational", "seasonal"})
    __metadata__: ClassVar[Mapping[str, object]] = {
        "description": "Monthly varying release rates",
        "version": 2,
    }

    rate: tuple[float, ...] = (50.0, 60.0, 70.0)

# Access via methods
strategy = SeasonalRelease()
print(strategy.tags())      # frozenset({'operational', 'seasonal'})
print(strategy.metadata())  # {'description': 'Monthly varying release rates', 'version': 2}
```

Note: Strategy tags/metadata are type-level (defined at class definition), not instance-level.

## Intelligence Layer Examples

### Filtering Nodes by Tags

```python
def get_primary_sources(system: WaterSystem) -> list[Source]:
    """Find all primary water sources."""
    return [
        node for node in system.nodes.values()
        if isinstance(node, Source) and "primary" in node.tags
    ]

def get_regulated_storage(system: WaterSystem) -> list[Storage]:
    """Find all regulated reservoirs."""
    return [
        node for node in system.nodes.values()
        if isinstance(node, Storage) and "regulated" in node.tags
    ]
```

### Filtering Edges by Metadata

```python
def get_long_canals(system: WaterSystem, min_length_km: float) -> list[Edge]:
    """Find canals longer than a threshold."""
    return [
        edge for edge in system.edges.values()
        if "canal" in edge.tags
        and edge.metadata.get("length_km", 0) >= min_length_km
    ]
```

### Aggregating by Tags

```python
def group_edges_by_type(system: WaterSystem) -> dict[str, list[Edge]]:
    """Group edges by their infrastructure type tag."""
    groups: dict[str, list[Edge]] = {}
    for edge in system.edges.values():
        for tag in edge.tags:
            if tag in ("canal", "river", "pipeline"):
                groups.setdefault(tag, []).append(edge)
    return groups
```

## Best Practices

### Tags

- Use tags for **categorical classification**
- Keep tag names short and consistent across the system
- Use lowercase with underscores (e.g., `"primary_supply"`, `"backup"`)
- Common tag categories:
  - Role: `"primary"`, `"secondary"`, `"backup"`
  - Type: `"reservoir"`, `"canal"`, `"river"`, `"pipeline"`
  - Status: `"regulated"`, `"natural"`, `"seasonal"`
  - Priority: `"critical"`, `"essential"`, `"discretionary"`

### Metadata

- Use metadata for **values and structured data**
- Prefer descriptive key names (e.g., `"length_km"` over `"len"`)
- Include units in key names when relevant
- Common metadata fields:
  - Physical: `"length_km"`, `"capacity_mcm"`, `"area_km2"`
  - Administrative: `"owner"`, `"operator"`, `"agency_code"`
  - Temporal: `"year_built"`, `"last_inspection"`, `"commissioning_date"`
  - Technical: `"material"`, `"efficiency"`, `"loss_coefficient"`

### Separation of Concerns

Taqsim intentionally does **not** interpret tags or metadata:

- The simulation engine treats them as opaque storage
- Intelligence layers (optimization, visualization, reporting) give them meaning
- This allows different use cases without modifying core Taqsim code
