"""Test fixtures for naturalize module tests."""

import sys
from dataclasses import dataclass, field
from types import ModuleType
from typing import Protocol, runtime_checkable

import pytest

# Create proper mock modules BEFORE any class definitions
# This is necessary because taqsim isn't actually installed
# and isinstance() checks need the actual class types
_mock_taqsim = ModuleType("taqsim")
_mock_taqsim_node = ModuleType("taqsim.node")
_mock_taqsim_edge = ModuleType("taqsim.edge")
_mock_taqsim_system = ModuleType("taqsim.system")

# Install in sys.modules FIRST (will assign classes after defining them)
sys.modules["taqsim"] = _mock_taqsim
sys.modules["taqsim.node"] = _mock_taqsim_node
sys.modules["taqsim.edge"] = _mock_taqsim_edge
sys.modules["taqsim.system"] = _mock_taqsim_system

# ============================================================
# Mock taqsim types for testing
# These mirror the taqsim API based on documentation
# ============================================================


@dataclass
class TimeSeries:
    """Mock TimeSeries - stores time-indexed values."""

    values: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("TimeSeries cannot be empty")
        if any(v < 0 for v in self.values):
            raise ValueError("TimeSeries cannot contain negative values")

    def __getitem__(self, t: int) -> float:
        return self.values[t]

    def __len__(self) -> int:
        return len(self.values)


@runtime_checkable
class SplitRule(Protocol):
    """Protocol for split rules."""

    def split(self, node: "Splitter", amount: float, t: int) -> dict[str, float]: ...


@runtime_checkable
class ReleaseRule(Protocol):
    """Protocol for release rules."""

    def release(self, node: "Storage", inflow: float, t: int, dt: float) -> float: ...


@runtime_checkable
class LossRule(Protocol):
    """Protocol for loss rules."""

    def calculate(self, node: "Storage", t: int, dt: float) -> dict[str, float]: ...


@runtime_checkable
class EdgeLossRule(Protocol):
    """Protocol for edge loss rules."""

    def calculate(self, edge: "Edge", flow: float, t: int, dt: float) -> dict[str, float]: ...


@dataclass
class BaseNode:
    """Base class for all nodes."""

    id: str
    location: tuple[float, float] | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class Source(BaseNode):
    """Water source node."""

    inflow: TimeSeries = field(default_factory=lambda: TimeSeries(values=(100.0,)))


@dataclass
class Sink(BaseNode):
    """Terminal node where water exits the system."""

    pass


@dataclass
class PassThrough(BaseNode):
    """Transparent junction node."""

    capacity: float | None = None


@dataclass
class Storage(BaseNode):
    """Reservoir/storage node."""

    capacity: float = 10000.0
    initial_storage: float = 5000.0
    dead_storage: float = 0.0
    release_rule: ReleaseRule | None = None
    loss_rule: LossRule | None = None


@dataclass
class Demand(BaseNode):
    """Consumption node."""

    requirement: TimeSeries = field(default_factory=lambda: TimeSeries(values=(50.0,)))
    efficiency: float = 1.0
    consumption_fraction: float = 1.0


@dataclass
class Splitter(BaseNode):
    """Distribution node that routes to multiple targets."""

    split_rule: SplitRule | None = None


@dataclass
class Edge:
    """Connection between nodes."""

    id: str
    source: str
    target: str
    capacity: float = 1000.0
    loss_rule: EdgeLossRule | None = None
    tags: frozenset[str] = field(default_factory=frozenset)
    metadata: dict[str, object] = field(default_factory=dict)


class WaterSystem:
    """Mock WaterSystem for testing."""

    def __init__(self, dt: float = 86400.0) -> None:
        self.dt = dt
        self.nodes: dict[str, BaseNode] = {}
        self.edges: dict[str, Edge] = {}

    def add_node(self, node: BaseNode) -> None:
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        self.edges[edge.id] = edge

    def validate(self) -> None:
        """Validate the system structure."""
        # Check all edge endpoints exist
        for edge in self.edges.values():
            if edge.source not in self.nodes:
                raise ValueError(f"Edge {edge.id} source '{edge.source}' not found")
            if edge.target not in self.nodes:
                raise ValueError(f"Edge {edge.id} target '{edge.target}' not found")


# Now assign the mock classes to the module attributes
# This must happen AFTER class definitions but BEFORE any imports of fishy.naturalize
_mock_taqsim_node.Source = Source
_mock_taqsim_node.Sink = Sink
_mock_taqsim_node.PassThrough = PassThrough
_mock_taqsim_node.Storage = Storage
_mock_taqsim_node.Demand = Demand
_mock_taqsim_node.Splitter = Splitter
_mock_taqsim_node.TimeSeries = TimeSeries

_mock_taqsim_edge.Edge = Edge

_mock_taqsim_system.WaterSystem = WaterSystem


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def natural_tag() -> str:
    """The NATURAL_TAG constant."""
    return "natural"


@pytest.fixture
def make_timeseries():
    """Factory for creating TimeSeries."""

    def _make(values: list[float]) -> TimeSeries:
        return TimeSeries(values=tuple(values))

    return _make


@pytest.fixture
def simple_linear_system(natural_tag: str) -> WaterSystem:
    """Simple linear system: Source -> Storage -> Sink (all natural).

    source --[natural]--> storage --[natural]--> sink
    """
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0, 150.0, 120.0)),
        )
    )
    system.add_node(
        Storage(
            id="storage",
            capacity=10000.0,
            initial_storage=5000.0,
        )
    )
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_storage",
            source="source",
            target="storage",
            tags=frozenset({natural_tag}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_sink",
            source="storage",
            target="sink",
            tags=frozenset({natural_tag}),
        )
    )

    return system


@pytest.fixture
def system_with_side_branch(natural_tag: str) -> WaterSystem:
    """System with natural path and side branch to demand.

    source --[natural]--> storage --[natural]--> sink
                              |
                              +--[canal]--> demand
    """
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0,)),
        )
    )
    system.add_node(
        Storage(
            id="storage",
            capacity=10000.0,
        )
    )
    system.add_node(Sink(id="sink"))
    system.add_node(
        Demand(
            id="demand",
            requirement=TimeSeries(values=(50.0,)),
        )
    )

    system.add_edge(
        Edge(
            id="source_to_storage",
            source="source",
            target="storage",
            tags=frozenset({natural_tag}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_sink",
            source="storage",
            target="sink",
            tags=frozenset({natural_tag}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_demand",
            source="storage",
            target="demand",
            tags=frozenset({"canal"}),  # Not natural
        )
    )

    return system


@pytest.fixture
def system_no_natural_edges() -> WaterSystem:
    """System with no natural edges - should fail naturalization."""
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0,)),
        )
    )
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_sink",
            source="source",
            target="sink",
            tags=frozenset({"canal"}),  # Not natural
        )
    )

    return system


@pytest.fixture
def system_disconnected_natural(natural_tag: str) -> WaterSystem:
    """System where natural edges don't form a complete path.

    source --[natural]--> passthrough    sink (disconnected)
    """
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0,)),
        )
    )
    system.add_node(PassThrough(id="passthrough"))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_passthrough",
            source="source",
            target="passthrough",
            tags=frozenset({natural_tag}),
        )
    )
    # No edge to sink - path is incomplete

    return system


@pytest.fixture
def system_with_terminal_demand(natural_tag: str) -> WaterSystem:
    """System with a demand on the natural path that has no natural downstream.

    source --[natural]--> demand (terminal - no natural downstream)
    """
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0,)),
        )
    )
    system.add_node(
        Demand(
            id="demand",
            requirement=TimeSeries(values=(50.0,)),
        )
    )
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_demand",
            source="source",
            target="demand",
            tags=frozenset({natural_tag}),
        )
    )
    system.add_edge(
        Edge(
            id="demand_to_sink",
            source="demand",
            target="sink",
            tags=frozenset({"canal"}),  # Not natural - demand is terminal on natural path
        )
    )

    return system


@pytest.fixture
def system_with_demand_on_path(natural_tag: str) -> WaterSystem:
    """System with a demand on the natural path that has natural downstream.

    source --[natural]--> demand --[natural]--> sink
    """
    system = WaterSystem(dt=86400.0)

    system.add_node(
        Source(
            id="source",
            inflow=TimeSeries(values=(100.0,)),
        )
    )
    system.add_node(
        Demand(
            id="demand",
            requirement=TimeSeries(values=(50.0,)),
        )
    )
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_demand",
            source="source",
            target="demand",
            tags=frozenset({natural_tag}),
        )
    )
    system.add_edge(
        Edge(
            id="demand_to_sink",
            source="demand",
            target="sink",
            tags=frozenset({natural_tag}),  # Natural downstream
        )
    )

    return system
