"""Tests for naturalize function."""

import pytest
from taqsim.node import PassThrough, Reach, Sink, Source, Splitter
from taqsim.system import WaterSystem

from fishy.naturalize import (
    NATURAL_TAG,
    AmbiguousSplitError,
    InvalidNaturalSplitRatiosError,
    NaturalizeResult,
    NaturalRiverSplitter,
    NoNaturalPathError,
    NoNaturalReachError,
    naturalize,
)


class TestHappyPath:
    """Tests for successful naturalization."""

    def test_simple_linear_system(self, simple_linear_system: WaterSystem) -> None:
        """Linear system with storage should transform storage to passthrough."""
        result = naturalize(simple_linear_system)

        assert isinstance(result, NaturalizeResult)
        assert "source" in result.system.nodes
        assert "reach" in result.system.nodes
        assert "storage" in result.system.nodes
        assert "sink" in result.system.nodes
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

    def test_reach_on_natural_path_preserved(self, system_with_reach_on_natural_path: WaterSystem) -> None:
        """Reach on natural path should be preserved as Reach (physical channel)."""
        result = naturalize(system_with_reach_on_natural_path)

        assert "reach" in result.system.nodes
        assert isinstance(result.system.nodes["reach"], Reach)
        assert "reach" not in result.transformed_nodes

    def test_reach_off_natural_path_removed(self, system_with_reach_off_natural_path: WaterSystem) -> None:
        """Reach used as canal (off natural path) should be removed."""
        result = naturalize(system_with_reach_off_natural_path)

        assert "natural_reach" in result.system.nodes
        assert "canal_reach" not in result.system.nodes
        assert "canal_reach" in result.removed_nodes

    def test_mixed_splitter_preserved_as_splitter(self, system_with_mixed_splitter: WaterSystem) -> None:
        """Mixed splitter with NATURAL_SPLIT_RATIOS stays as Splitter."""
        result = naturalize(system_with_mixed_splitter)

        assert "splitter" in result.system.nodes
        assert isinstance(result.system.nodes["splitter"], Splitter)
        # Non-natural demand removed
        assert "demand" not in result.system.nodes

    def test_mixed_splitter_gets_natural_river_splitter_policy(self, system_with_mixed_splitter: WaterSystem) -> None:
        """Mixed splitter's policy is rebuilt as NaturalRiverSplitter from metadata."""
        result = naturalize(system_with_mixed_splitter)

        splitter = result.system.nodes["splitter"]
        assert isinstance(splitter, Splitter)
        assert isinstance(splitter.split_policy, NaturalRiverSplitter)
        assert splitter.split_policy.ratios["reach_a"] == 0.6
        assert splitter.split_policy.ratios["reach_b"] == 0.4

    def test_mixed_splitter_not_in_transformed(self, system_with_mixed_splitter: WaterSystem) -> None:
        """Mixed splitter should NOT appear in transformed_nodes (stays a Splitter)."""
        result = naturalize(system_with_mixed_splitter)

        assert "splitter" not in result.transformed_nodes


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

    def test_mixed_splitter_non_natural_edges_removed(self, system_with_mixed_splitter: WaterSystem) -> None:
        """Canal edge and demand node removed from mixed splitter system."""
        result = naturalize(system_with_mixed_splitter)

        # All remaining edges should be natural
        for edge in result.system.edges.values():
            assert NATURAL_TAG in edge.tags

        # Canal edge removed
        assert "splitter_to_demand" in result.removed_edges


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
        """Terminal demand on natural path actually raises NoNaturalPathError."""
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

    def test_no_reach_on_natural_path_raises(self, system_without_reach_on_natural_path: WaterSystem) -> None:
        """Should raise NoNaturalReachError when natural path has no Reach node."""
        with pytest.raises(NoNaturalReachError) as exc_info:
            naturalize(system_without_reach_on_natural_path)

        error = exc_info.value
        assert "source" in error.source_ids
        assert "sink" in error.sink_ids
        assert "source" in error.path_node_ids
        assert "storage" in error.path_node_ids
        assert "sink" in error.path_node_ids

    def test_mixed_splitter_without_metadata_raises_ambiguous(
        self, system_with_mixed_splitter_no_metadata: WaterSystem
    ) -> None:
        """Mixed splitter without NATURAL_SPLIT_RATIOS raises AmbiguousSplitError."""
        with pytest.raises(AmbiguousSplitError):
            naturalize(system_with_mixed_splitter_no_metadata)

    def test_mixed_splitter_bad_ratios_sum_raises(self, system_with_mixed_splitter_bad_sum: WaterSystem) -> None:
        """Mixed splitter with ratios not summing to 1.0 raises InvalidNaturalSplitRatiosError."""
        with pytest.raises(InvalidNaturalSplitRatiosError, match="sum to 1.0"):
            naturalize(system_with_mixed_splitter_bad_sum)

    def test_mixed_splitter_wrong_targets_raises(self, system_with_mixed_splitter_wrong_targets: WaterSystem) -> None:
        """Mixed splitter with mismatched ratio keys raises InvalidNaturalSplitRatiosError."""
        with pytest.raises(InvalidNaturalSplitRatiosError, match="do not match"):
            naturalize(system_with_mixed_splitter_wrong_targets)

    def test_ambiguous_error_mentions_metadata(self, system_with_ambiguous_splitter: WaterSystem) -> None:
        """AmbiguousSplitError message should mention NATURAL_SPLIT_RATIOS."""
        with pytest.raises(AmbiguousSplitError) as exc_info:
            naturalize(system_with_ambiguous_splitter)

        assert "NATURAL_SPLIT_RATIOS" in str(exc_info.value)


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
