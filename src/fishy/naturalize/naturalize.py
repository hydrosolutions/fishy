"""Core naturalize function for transforming water systems."""

import networkx as nx
from taqsim.edge import Edge
from taqsim.node import Demand, PassThrough, Reach, Sink, Source, Splitter, Storage
from taqsim.system import WaterSystem
from taqsim.time import Frequency

from fishy.naturalize.errors import (
    AmbiguousSplitError,
    NoNaturalPathError,
    TerminalDemandError,
)
from fishy.naturalize.natural_river_splitter import NaturalRiverSplitter
from fishy.naturalize.types import (
    NATURAL_TAG,
    EdgeId,
    NaturalizeContext,
    NaturalizeResult,
    NodeId,
)


def naturalize(system: WaterSystem) -> NaturalizeResult:
    """Transform a water system into its naturalized form.

    Removes human infrastructure (demands, storage operations, canals) to produce
    a system representing natural river flow, suitable for IHA indices calculation.

    Args:
        system: The WaterSystem to naturalize. Must have edges tagged with
            'natural' to identify the natural flow path.

    Returns:
        NaturalizeResult containing the naturalized system and audit trail.

    Raises:
        NoNaturalPathError: If no path exists from sources to sinks via natural edges.
        AmbiguousSplitError: If a splitter has multiple natural downstream edges
            but no NaturalRiverSplitter rule.
        TerminalDemandError: If a Demand on the natural path has no natural
            downstream edge.
    """
    ctx = NaturalizeContext.empty()

    # Step 1: Extract natural edges
    natural_edges = _extract_natural_edges(system)

    # Step 2: Build natural subgraph
    natural_graph = _build_natural_graph(natural_edges)

    # Step 3: Find sources and sinks
    sources = _find_sources(system)
    sinks = _find_sinks(system)

    # Step 4: Find nodes on natural paths
    natural_path_nodes = _find_natural_path_nodes(natural_graph, sources, sinks)

    # Step 5: Validate preconditions
    _validate_natural_paths_exist(natural_path_nodes, sources, sinks)
    _validate_splitters(system, natural_edges, natural_path_nodes)
    _validate_no_terminal_demands(system, natural_edges, natural_path_nodes)

    # Step 6: Transform nodes
    new_nodes, transformed = _transform_nodes(system, natural_path_nodes)
    ctx.transformed_nodes.update(transformed)

    # Track removed nodes
    original_node_ids = set(system.nodes.keys())
    retained_node_ids = set(new_nodes.keys())
    ctx.removed_nodes.update(original_node_ids - retained_node_ids)

    # Step 7: Filter edges
    new_edges = _filter_edges(natural_edges, retained_node_ids)

    # Track removed edges
    original_edge_ids = set(system.edges.keys())
    retained_edge_ids = set(new_edges.keys())
    ctx.removed_edges.update(original_edge_ids - retained_edge_ids)

    # Step 8: Build new system
    new_system = _build_system(system.frequency, new_nodes, new_edges)

    # Generate warnings
    ctx.warnings.extend(_generate_warnings(ctx, system))

    return ctx.to_result(new_system)


def _extract_natural_edges(system: WaterSystem) -> dict[EdgeId, Edge]:
    """Extract edges tagged with NATURAL_TAG."""
    return {edge_id: edge for edge_id, edge in system.edges.items() if NATURAL_TAG in edge.tags}


def _build_natural_graph(edges: dict[EdgeId, Edge]) -> nx.DiGraph:
    """Build a directed graph from natural edges."""
    graph = nx.DiGraph()
    for edge_id, edge in edges.items():
        graph.add_edge(edge.source, edge.target, edge_id=edge_id)
    return graph


def _find_sources(system: WaterSystem) -> set[NodeId]:
    """Find all Source nodes in the system."""
    return {node_id for node_id, node in system.nodes.items() if isinstance(node, Source)}


def _find_sinks(system: WaterSystem) -> set[NodeId]:
    """Find all Sink nodes in the system."""
    return {node_id for node_id, node in system.nodes.items() if isinstance(node, Sink)}


def _find_natural_path_nodes(
    graph: nx.DiGraph,
    sources: set[NodeId],
    sinks: set[NodeId],
) -> set[NodeId]:
    """Find all nodes that lie on a natural path from any source to any sink."""
    if not graph.nodes:
        return set()

    # Nodes reachable from sources (forward reachability)
    reachable_from_sources: set[NodeId] = set()
    for source in sources:
        if source in graph:
            reachable_from_sources.update(nx.descendants(graph, source))
            reachable_from_sources.add(source)

    # Nodes that can reach sinks (backward reachability)
    can_reach_sinks: set[NodeId] = set()
    for sink in sinks:
        if sink in graph:
            can_reach_sinks.update(nx.ancestors(graph, sink))
            can_reach_sinks.add(sink)

    # Intersection: nodes on paths from source to sink
    return reachable_from_sources & can_reach_sinks


def _validate_natural_paths_exist(
    natural_path_nodes: set[NodeId],
    sources: set[NodeId],
    sinks: set[NodeId],
) -> None:
    """Raise if no natural path exists from any source to any sink."""
    if not natural_path_nodes:
        raise NoNaturalPathError(
            source_ids=frozenset(sources),
            sink_ids=frozenset(sinks),
        )
    # Check that at least one source and one sink are on the natural path
    if not (natural_path_nodes & sources) or not (natural_path_nodes & sinks):
        raise NoNaturalPathError(
            source_ids=frozenset(sources),
            sink_ids=frozenset(sinks),
        )


def _validate_splitters(
    system: WaterSystem,
    natural_edges: dict[EdgeId, Edge],
    natural_path_nodes: set[NodeId],
) -> None:
    """Validate splitters on natural paths have proper configuration."""
    for node_id in natural_path_nodes:
        node = system.nodes.get(node_id)
        if not isinstance(node, Splitter):
            continue

        # Find natural edges downstream of this splitter
        natural_downstream = {edge_id for edge_id, edge in natural_edges.items() if edge.source == node_id}

        # If multiple natural downstream edges, need NaturalRiverSplitter
        if len(natural_downstream) > 1 and not _has_natural_river_splitter(node):
            raise AmbiguousSplitError(
                node_id=node_id,
                natural_edge_ids=frozenset(natural_downstream),
            )


def _validate_no_terminal_demands(
    system: WaterSystem,
    natural_edges: dict[EdgeId, Edge],
    natural_path_nodes: set[NodeId],
) -> None:
    """Validate that Demands on natural paths have natural downstream edges."""
    for node_id in natural_path_nodes:
        node = system.nodes.get(node_id)
        if not isinstance(node, Demand):
            continue

        # Find all downstream edges from this demand
        all_downstream = {edge_id for edge_id, edge in system.edges.items() if edge.source == node_id}

        # Find natural downstream edges
        natural_downstream = {edge_id for edge_id, edge in natural_edges.items() if edge.source == node_id}

        # If no natural downstream, this is a terminal demand on natural path
        if not natural_downstream:
            raise TerminalDemandError(
                node_id=node_id,
                downstream_edge_ids=frozenset(all_downstream),
            )


def _has_natural_river_splitter(node: Splitter) -> bool:
    """Check if a splitter uses NaturalRiverSplitter."""
    return isinstance(node.split_policy, NaturalRiverSplitter)


def _transform_nodes(
    system: WaterSystem,
    natural_path_nodes: set[NodeId],
) -> tuple[dict[NodeId, Source | Sink | PassThrough | Splitter | Reach], dict[NodeId, str]]:
    """Transform nodes for the naturalized system.

    Returns:
        Tuple of (new_nodes dict, transformed dict mapping node_id to original type)
    """
    new_nodes: dict[NodeId, Source | Sink | PassThrough | Splitter | Reach] = {}
    transformed: dict[NodeId, str] = {}

    for node_id in natural_path_nodes:
        node = system.nodes[node_id]

        if isinstance(node, Source):
            new_nodes[node_id] = _clone_source(node)
        elif isinstance(node, Sink):
            new_nodes[node_id] = _clone_sink(node)
        elif isinstance(node, PassThrough):
            new_nodes[node_id] = _clone_passthrough(node)
        elif isinstance(node, Reach):
            new_nodes[node_id] = _clone_reach(node)
        elif isinstance(node, Storage):
            new_nodes[node_id] = _storage_to_passthrough(node)
            transformed[node_id] = "Storage"
        elif isinstance(node, Demand):
            new_nodes[node_id] = _demand_to_passthrough(node)
            transformed[node_id] = "Demand"
        elif isinstance(node, Splitter):
            if _has_natural_river_splitter(node):
                new_nodes[node_id] = _clone_splitter(node)
            else:
                new_nodes[node_id] = _splitter_to_passthrough(node)
                transformed[node_id] = "Splitter"

    return new_nodes, transformed


def _clone_source(node: Source) -> Source:
    """Clone a Source node."""
    return Source(
        id=node.id,
        inflow=node.inflow,
        location=node.location,
        tags=node.tags,
        metadata=node.metadata,
    )


def _clone_sink(node: Sink) -> Sink:
    """Clone a Sink node."""
    return Sink(
        id=node.id,
        location=node.location,
        tags=node.tags,
        metadata=node.metadata,
    )


def _clone_passthrough(node: PassThrough) -> PassThrough:
    """Clone a PassThrough node."""
    return PassThrough(
        id=node.id,
        capacity=node.capacity,
        location=node.location,
        tags=node.tags,
        metadata=node.metadata,
    )


def _clone_splitter(node: Splitter) -> Splitter:
    """Clone a Splitter node (only called for NaturalRiverSplitter)."""
    return Splitter(
        id=node.id,
        split_policy=node.split_policy,
        location=node.location,
        tags=node.tags,
        metadata=node.metadata,
    )


def _clone_reach(node: Reach) -> Reach:
    """Clone a Reach node."""
    return Reach(
        id=node.id,
        routing_model=node.routing_model,
        loss_rule=node.loss_rule,
        location=node.location,
        tags=node.tags,
        metadata=node.metadata,
    )


def _storage_to_passthrough(node: Storage) -> PassThrough:
    """Convert a Storage node to PassThrough."""
    return PassThrough(
        id=node.id,
        capacity=None,  # No capacity limit in natural state
        location=node.location,
        tags=node.tags | frozenset({"naturalized_from_storage"}),
        metadata={**node.metadata, "original_capacity": node.capacity},
    )


def _demand_to_passthrough(node: Demand) -> PassThrough:
    """Convert a Demand node to PassThrough."""
    return PassThrough(
        id=node.id,
        capacity=None,
        location=node.location,
        tags=node.tags | frozenset({"naturalized_from_demand"}),
        metadata=dict(node.metadata),
    )


def _splitter_to_passthrough(node: Splitter) -> PassThrough:
    """Convert a Splitter node to PassThrough (single natural downstream)."""
    return PassThrough(
        id=node.id,
        capacity=None,
        location=node.location,
        tags=node.tags | frozenset({"naturalized_from_splitter"}),
        metadata=dict(node.metadata),
    )


def _filter_edges(
    natural_edges: dict[EdgeId, Edge],
    retained_node_ids: set[NodeId],
) -> dict[EdgeId, Edge]:
    """Filter natural edges to only those between retained nodes."""
    return {
        edge_id: _clone_edge(edge)
        for edge_id, edge in natural_edges.items()
        if edge.source in retained_node_ids and edge.target in retained_node_ids
    }


def _clone_edge(edge: Edge) -> Edge:
    """Clone an Edge."""
    return edge._fresh_copy()


def _build_system(
    frequency: Frequency,
    nodes: dict[NodeId, Source | Sink | PassThrough | Splitter | Reach],
    edges: dict[EdgeId, Edge],
) -> WaterSystem:
    """Build a new WaterSystem from nodes and edges."""
    system = WaterSystem(frequency=frequency)

    for node in nodes.values():
        system.add_node(node)

    for edge in edges.values():
        system.add_edge(edge)

    system.validate()
    return system


def _generate_warnings(ctx: NaturalizeContext, original: WaterSystem) -> list[str]:
    """Generate warnings about the naturalization process."""
    warnings: list[str] = []

    if ctx.removed_nodes:
        warnings.append(
            f"Removed {len(ctx.removed_nodes)} node(s) not on natural path: {', '.join(sorted(ctx.removed_nodes))}"
        )

    if ctx.removed_edges:
        non_natural_count = len(original.edges) - len([e for e in original.edges.values() if NATURAL_TAG in e.tags])
        if non_natural_count > 0:
            warnings.append(f"Removed {non_natural_count} non-natural edge(s)")

    return warnings
