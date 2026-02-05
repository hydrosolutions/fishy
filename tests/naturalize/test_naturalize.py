"""Tests for naturalize function."""

# conftest.py sets up sys.modules with mock taqsim modules BEFORE this file loads.
# We import the mock classes via sys.modules to get the same classes that
# naturalize.py will use for isinstance() checks.

import sys

import pytest

# Get the mock classes from sys.modules (set up by conftest.py)
_taqsim_node = sys.modules["taqsim.node"]
_taqsim_edge = sys.modules["taqsim.edge"]
_taqsim_system = sys.modules["taqsim.system"]

Source = _taqsim_node.Source
Sink = _taqsim_node.Sink
PassThrough = _taqsim_node.PassThrough
Storage = _taqsim_node.Storage
Demand = _taqsim_node.Demand
Splitter = _taqsim_node.Splitter
TimeSeries = _taqsim_node.TimeSeries

Edge = _taqsim_edge.Edge

WaterSystem = _taqsim_system.WaterSystem

# Now import from fishy.naturalize (will use same classes via sys.modules)
from fishy.naturalize import (  # noqa: E402
    NATURAL_TAG,
    AmbiguousSplitError,
    NaturalizeResult,
    NaturalRiverSplitter,
    NoNaturalPathError,
    naturalize,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def simple_linear_system() -> WaterSystem:
    """Source -> Storage -> Sink (all natural)."""
    system = WaterSystem(dt=86400.0)

    system.add_node(Source(id="source", inflow=TimeSeries(values=(100.0, 150.0))))
    system.add_node(Storage(id="storage", capacity=10000.0))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_storage",
            source="source",
            target="storage",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_sink",
            source="storage",
            target="sink",
            tags=frozenset({NATURAL_TAG}),
        )
    )

    return system


@pytest.fixture
def system_with_side_branch() -> WaterSystem:
    """Source -> Storage -> Sink (natural) + Storage -> Demand (canal)."""
    system = WaterSystem(dt=86400.0)

    system.add_node(Source(id="source"))
    system.add_node(Storage(id="storage"))
    system.add_node(Sink(id="sink"))
    system.add_node(Demand(id="demand"))

    system.add_edge(
        Edge(
            id="source_to_storage",
            source="source",
            target="storage",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_sink",
            source="storage",
            target="sink",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="storage_to_demand",
            source="storage",
            target="demand",
            tags=frozenset({"canal"}),
        )
    )

    return system


@pytest.fixture
def system_no_natural_edges() -> WaterSystem:
    """System with no natural edges."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="canal",
            source="source",
            target="sink",
            tags=frozenset({"canal"}),
        )
    )

    return system


@pytest.fixture
def system_with_demand_on_path() -> WaterSystem:
    """Source -> Demand -> Sink (all natural)."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(Demand(id="demand"))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_demand",
            source="source",
            target="demand",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="demand_to_sink",
            source="demand",
            target="sink",
            tags=frozenset({NATURAL_TAG}),
        )
    )

    return system


@pytest.fixture
def system_with_terminal_demand() -> WaterSystem:
    """Source -> Demand (terminal on natural path)."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(Demand(id="demand"))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_demand",
            source="source",
            target="demand",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="demand_to_sink",
            source="demand",
            target="sink",
            tags=frozenset({"canal"}),  # Not natural
        )
    )

    return system


@pytest.fixture
def system_with_passthrough() -> WaterSystem:
    """Source -> PassThrough -> Sink (all natural)."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(PassThrough(id="passthrough", capacity=500.0))
    system.add_node(Sink(id="sink"))

    system.add_edge(
        Edge(
            id="source_to_pt",
            source="source",
            target="passthrough",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="pt_to_sink",
            source="passthrough",
            target="sink",
            tags=frozenset({NATURAL_TAG}),
        )
    )

    return system


@pytest.fixture
def system_with_splitter_single_natural() -> WaterSystem:
    """Splitter with single natural downstream edge."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(Splitter(id="splitter"))
    system.add_node(Sink(id="sink"))
    system.add_node(Demand(id="demand"))

    system.add_edge(
        Edge(
            id="source_to_splitter",
            source="source",
            target="splitter",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_sink",
            source="splitter",
            target="sink",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_demand",
            source="splitter",
            target="demand",
            tags=frozenset({"canal"}),
        )
    )

    return system


@pytest.fixture
def system_with_natural_splitter() -> WaterSystem:
    """Splitter with NaturalRiverSplitter and multiple natural downstream edges."""
    system = WaterSystem()

    natural_rule = NaturalRiverSplitter(ratios={"sink_a": 0.6, "sink_b": 0.4})

    system.add_node(Source(id="source"))
    system.add_node(Splitter(id="splitter", split_rule=natural_rule))
    system.add_node(Sink(id="sink_a"))
    system.add_node(Sink(id="sink_b"))

    system.add_edge(
        Edge(
            id="source_to_splitter",
            source="source",
            target="splitter",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_sink_a",
            source="splitter",
            target="sink_a",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_sink_b",
            source="splitter",
            target="sink_b",
            tags=frozenset({NATURAL_TAG}),
        )
    )

    return system


@pytest.fixture
def system_with_ambiguous_splitter() -> WaterSystem:
    """Splitter with multiple natural downstream but no NaturalRiverSplitter."""
    system = WaterSystem()

    system.add_node(Source(id="source"))
    system.add_node(Splitter(id="splitter", split_rule=None))  # No rule
    system.add_node(Sink(id="sink_a"))
    system.add_node(Sink(id="sink_b"))

    system.add_edge(
        Edge(
            id="source_to_splitter",
            source="source",
            target="splitter",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_sink_a",
            source="splitter",
            target="sink_a",
            tags=frozenset({NATURAL_TAG}),
        )
    )
    system.add_edge(
        Edge(
            id="splitter_to_sink_b",
            source="splitter",
            target="sink_b",
            tags=frozenset({NATURAL_TAG}),
        )
    )

    return system


# ============================================================
# Tests
# ============================================================


class TestHappyPath:
    """Tests for successful naturalization."""

    def test_simple_linear_system(self, simple_linear_system: WaterSystem) -> None:
        """Linear system with storage should transform storage to passthrough."""
        result = naturalize(simple_linear_system)

        assert isinstance(result, NaturalizeResult)
        assert "source" in result.system.nodes
        assert "storage" in result.system.nodes
        assert "sink" in result.system.nodes
        assert result.removed_count == 0
        assert result.transformed_count == 1
        assert "storage" in result.transformed_nodes
        assert result.transformed_nodes["storage"] == "Storage"

    def test_side_branch_removed(self, system_with_side_branch: WaterSystem) -> None:
        """Non-natural side branch should be removed."""
        result = naturalize(system_with_side_branch)

        assert "demand" not in result.system.nodes
        assert "storage_to_demand" not in result.system.edges
        assert "demand" in result.removed_nodes
        assert "storage_to_demand" in result.removed_edges

    def test_passthrough_preserved(self, system_with_passthrough: WaterSystem) -> None:
        """PassThrough nodes should be preserved as-is."""
        result = naturalize(system_with_passthrough)

        assert "passthrough" in result.system.nodes
        assert "passthrough" not in result.transformed_nodes

    def test_splitter_single_natural_becomes_passthrough(
        self, system_with_splitter_single_natural: WaterSystem
    ) -> None:
        """Splitter with single natural downstream becomes PassThrough."""
        result = naturalize(system_with_splitter_single_natural)

        assert "splitter" in result.system.nodes
        assert "splitter" in result.transformed_nodes
        assert result.transformed_nodes["splitter"] == "Splitter"

    def test_natural_splitter_preserved(self, system_with_natural_splitter: WaterSystem) -> None:
        """Splitter with NaturalRiverSplitter should be preserved."""
        result = naturalize(system_with_natural_splitter)

        assert "splitter" in result.system.nodes
        assert "splitter" not in result.transformed_nodes
        # Both sinks should be preserved
        assert "sink_a" in result.system.nodes
        assert "sink_b" in result.system.nodes


class TestNodeTransformations:
    """Tests for node type transformations."""

    def test_storage_to_passthrough(self, simple_linear_system: WaterSystem) -> None:
        """Storage nodes should become PassThrough."""
        result = naturalize(simple_linear_system)

        storage_node = result.system.nodes["storage"]
        assert isinstance(storage_node, PassThrough)
        assert storage_node.capacity is None  # Natural has no capacity limit
        assert "naturalized_from_storage" in storage_node.tags

    def test_demand_on_path_to_passthrough(self, system_with_demand_on_path: WaterSystem) -> None:
        """Demand on natural path with natural downstream becomes PassThrough."""
        result = naturalize(system_with_demand_on_path)

        demand_node = result.system.nodes["demand"]
        assert isinstance(demand_node, PassThrough)
        assert "naturalized_from_demand" in demand_node.tags

    def test_source_preserved(self, simple_linear_system: WaterSystem) -> None:
        """Source nodes should be preserved as Source."""
        result = naturalize(simple_linear_system)

        source_node = result.system.nodes["source"]
        assert isinstance(source_node, Source)

    def test_sink_preserved(self, simple_linear_system: WaterSystem) -> None:
        """Sink nodes should be preserved as Sink."""
        result = naturalize(simple_linear_system)

        sink_node = result.system.nodes["sink"]
        assert isinstance(sink_node, Sink)


class TestEdgeFiltering:
    """Tests for edge filtering behavior."""

    def test_only_natural_edges_retained(self, system_with_side_branch: WaterSystem) -> None:
        """Only natural edges should be in the result."""
        result = naturalize(system_with_side_branch)

        for edge in result.system.edges.values():
            assert NATURAL_TAG in edge.tags

    def test_removed_edges_tracked(self, system_with_side_branch: WaterSystem) -> None:
        """Removed edges should be tracked in result."""
        result = naturalize(system_with_side_branch)

        assert "storage_to_demand" in result.removed_edges


class TestErrorCases:
    """Tests for error conditions."""

    def test_no_natural_path_error(self, system_no_natural_edges: WaterSystem) -> None:
        """Should raise NoNaturalPathError when no natural path exists."""
        with pytest.raises(NoNaturalPathError) as exc_info:
            naturalize(system_no_natural_edges)

        error = exc_info.value
        assert "source" in error.source_ids
        assert "sink" in error.sink_ids

    def test_terminal_demand_raises_no_path_error(self, system_with_terminal_demand: WaterSystem) -> None:
        """Terminal demand on natural path actually raises NoNaturalPathError.

        Note: A demand with no natural downstream edges cannot be "on a natural path"
        because natural_path_nodes requires the node to have a natural path TO a sink.
        If demand→sink isn't natural, demand can't reach sink via natural edges,
        so it's not on a natural path, and NoNaturalPathError is raised instead.
        """
        with pytest.raises(NoNaturalPathError):
            naturalize(system_with_terminal_demand)

    def test_ambiguous_splitter_error(self, system_with_ambiguous_splitter: WaterSystem) -> None:
        """Should raise AmbiguousSplitError for splitter without NaturalRiverSplitter."""
        with pytest.raises(AmbiguousSplitError) as exc_info:
            naturalize(system_with_ambiguous_splitter)

        error = exc_info.value
        assert error.node_id == "splitter"
        assert "splitter_to_sink_a" in error.natural_edge_ids
        assert "splitter_to_sink_b" in error.natural_edge_ids


class TestNaturalizeResult:
    """Tests for NaturalizeResult properties."""

    def test_removed_count(self, system_with_side_branch: WaterSystem) -> None:
        """removed_count should reflect removed nodes."""
        result = naturalize(system_with_side_branch)
        assert result.removed_count == 1  # demand

    def test_transformed_count(self, simple_linear_system: WaterSystem) -> None:
        """transformed_count should reflect transformed nodes."""
        result = naturalize(simple_linear_system)
        assert result.transformed_count == 1  # storage

    def test_summary_includes_transformations(self, simple_linear_system: WaterSystem) -> None:
        """summary() should include transformation details."""
        result = naturalize(simple_linear_system)
        summary = result.summary()

        assert "Naturalization Summary" in summary
        assert "storage" in summary
        assert "PassThrough" in summary

    def test_warnings_generated(self, system_with_side_branch: WaterSystem) -> None:
        """Warnings should be generated for removed nodes."""
        result = naturalize(system_with_side_branch)

        assert len(result.warnings) > 0
        assert any("demand" in w for w in result.warnings)
