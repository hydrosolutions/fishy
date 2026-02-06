"""Test fixtures for naturalize module tests."""

import pytest
from taqsim.edge import Edge
from taqsim.node import (
    Demand,
    PassThrough,
    Sink,
    Source,
    Storage,
    TimeSeries,
)
from taqsim.system import WaterSystem

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
