"""Shared flow-extraction utilities for taqsim WaterSystem."""

from taqsim.node import WaterReceived
from taqsim.objective import Trace
from taqsim.system import WaterSystem


def edge_trace(system: WaterSystem, edge_id: str) -> Trace:
    """Extract flow Trace for an edge from WaterReceived events on its target node."""
    edge = system.edges[edge_id]
    target_node = system.nodes[edge.target]
    received = [e for e in target_node.events_of_type(WaterReceived) if e.source_id == edge_id]
    return Trace.from_events(received)  # type: ignore[arg-type]
