"""Type definitions for the naturalize module."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from taqsim.system import WaterSystem

# Constants
NATURAL_TAG: str = "natural"
NATURAL_SPLIT_RATIOS: str = "natural_split_ratios"

# Type aliases
NodeId = str
EdgeId = str
NodeType = str


@dataclass(frozen=True)
class NaturalizeResult:
    """Result of naturalizing a water system.

    Contains the naturalized system plus an audit trail of all transformations.

    Args:
        system: The naturalized WaterSystem with human infrastructure removed.
        removed_nodes: IDs of nodes that were completely removed.
        removed_edges: IDs of edges that were removed.
        transformed_nodes: Mapping of node_id -> original node type for nodes that changed type.
        warnings: Any warnings generated during naturalization.
    """

    system: "WaterSystem"
    removed_nodes: frozenset[NodeId]
    removed_edges: frozenset[EdgeId]
    transformed_nodes: Mapping[NodeId, NodeType]
    warnings: tuple[str, ...]

    @property
    def removed_count(self) -> int:
        """Total number of nodes removed."""
        return len(self.removed_nodes)

    @property
    def transformed_count(self) -> int:
        """Total number of nodes that changed type."""
        return len(self.transformed_nodes)

    def summary(self) -> str:
        """Human-readable summary of naturalization changes."""
        lines = [
            "Naturalization Summary:",
            f"  Removed nodes: {self.removed_count}",
            f"  Removed edges: {len(self.removed_edges)}",
            f"  Transformed nodes: {self.transformed_count}",
        ]
        if self.transformed_nodes:
            lines.append("  Transformations:")
            for node_id, original_type in sorted(self.transformed_nodes.items()):
                lines.append(f"    {node_id}: {original_type} -> PassThrough")
        if self.warnings:
            lines.append(f"  Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                lines.append(f"    - {warning}")
        return "\n".join(lines)


@dataclass
class NaturalizeContext:
    """Mutable builder for collecting naturalization changes.

    Used internally during naturalization to accumulate changes before
    building the final immutable NaturalizeResult.
    """

    removed_nodes: set[NodeId] = field(default_factory=set)
    removed_edges: set[EdgeId] = field(default_factory=set)
    transformed_nodes: dict[NodeId, NodeType] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "NaturalizeContext":
        """Create an empty context."""
        return cls()

    def to_result(self, system: "WaterSystem") -> NaturalizeResult:
        """Convert mutable context to immutable result."""
        return NaturalizeResult(
            system=system,
            removed_nodes=frozenset(self.removed_nodes),
            removed_edges=frozenset(self.removed_edges),
            transformed_nodes=dict(self.transformed_nodes),  # Shallow copy as Mapping
            warnings=tuple(self.warnings),
        )
