"""Shared flow-extraction utilities for taqsim WaterSystem."""

from taqsim.node import Reach, WaterOutput
from taqsim.objective import Trace
from taqsim.system import WaterSystem


def reach_trace(system: WaterSystem, reach_id: str) -> Trace:
    """Extract flow Trace from a Reach node's WaterOutput events."""
    node = system.nodes[reach_id]
    if not isinstance(node, Reach):
        raise TypeError(f"Node '{reach_id}' is {type(node).__name__}, not Reach")
    return Trace.from_events(node.events_of_type(WaterOutput))  # type: ignore[arg-type]
