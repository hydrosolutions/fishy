"""Error types for naturalization failures."""

from dataclasses import dataclass


class NaturalizationError(Exception):
    """Base error for naturalization failures."""


@dataclass
class NoNaturalPathError(NaturalizationError):
    """Raised when no natural path exists from any source to any sink.

    Args:
        source_ids: IDs of source nodes in the system.
        sink_ids: IDs of sink nodes in the system.
    """

    source_ids: frozenset[str]
    sink_ids: frozenset[str]

    def __str__(self) -> str:
        sources = ", ".join(sorted(self.source_ids)) or "(none)"
        sinks = ", ".join(sorted(self.sink_ids)) or "(none)"
        return (
            f"No natural path exists from sources [{sources}] to sinks [{sinks}]. "
            f"Ensure edges on the natural flow path are tagged with 'natural'."
        )


@dataclass
class NoNaturalReachError(NaturalizationError):
    """Raised when a connected natural path contains no Reach node.

    Args:
        path_node_ids: IDs of nodes on the Reach-less natural path component.
        source_ids: IDs of source nodes in the component.
        sink_ids: IDs of sink nodes in the component.
    """

    path_node_ids: frozenset[str]
    source_ids: frozenset[str]
    sink_ids: frozenset[str]

    def __str__(self) -> str:
        sources = ", ".join(sorted(self.source_ids)) or "(none)"
        sinks = ", ".join(sorted(self.sink_ids)) or "(none)"
        nodes = ", ".join(sorted(self.path_node_ids))
        return (
            f"Natural path from sources [{sources}] to sinks [{sinks}] "
            f"contains no Reach node. Nodes on path: [{nodes}]. "
            f"Add a Reach node to model the physical river channel."
        )


@dataclass
class AmbiguousSplitError(NaturalizationError):
    """Raised when a splitter on the natural path has multiple natural downstream edges but no NaturalRiverSplitter.

    Args:
        node_id: ID of the problematic splitter node.
        natural_edge_ids: IDs of the natural edges downstream of this splitter.
    """

    node_id: str
    natural_edge_ids: frozenset[str]

    def __str__(self) -> str:
        edges = ", ".join(sorted(self.natural_edge_ids))
        return (
            f"Splitter '{self.node_id}' has multiple natural downstream edges [{edges}] "
            f"but no NaturalRiverSplitter rule. Either assign a NaturalRiverSplitter to define "
            f"natural flow ratios, or remove the 'natural' tag from all but one downstream edge."
        )


@dataclass
class TerminalDemandError(NaturalizationError):
    """Raised when a Demand node on the natural path has no downstream natural edges.

    A terminal Demand would consume all water, preventing natural flow from reaching sinks.

    Args:
        node_id: ID of the terminal demand node.
        downstream_edge_ids: IDs of any downstream edges (none will be tagged natural).
    """

    node_id: str
    downstream_edge_ids: frozenset[str]

    def __str__(self) -> str:
        if self.downstream_edge_ids:
            edges = ", ".join(sorted(self.downstream_edge_ids))
            return (
                f"Demand '{self.node_id}' is on the natural path but has no natural downstream edges. "
                f"Downstream edges [{edges}] are not tagged 'natural'. Either tag one as 'natural' "
                f"or remove this node from the natural path."
            )
        return (
            f"Demand '{self.node_id}' is on the natural path but is terminal (no downstream edges). "
            f"Demands cannot be terminal nodes on natural paths as they would consume all flow."
        )
