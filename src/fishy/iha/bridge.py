"""Bridge between taqsim WaterSystem and IHA computation."""

import numpy as np
from taqsim.node import Reach
from taqsim.system import WaterSystem
from taqsim.time import Frequency

from fishy._extract import reach_trace
from fishy.iha.compute import compute_iha
from fishy.iha.errors import (
    EmptyReachTraceError,
    MissingStartDateError,
    NonDailyFrequencyError,
    NotAReachError,
    ReachNotFoundError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, IHAResult, PulseThresholds


def iha_from_reach(
    system: WaterSystem,
    reach_id: str,
    *,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    pulse_thresholds: PulseThresholds | None = None,
    min_years: int = 1,
) -> IHAResult:
    """Compute IHA parameters from a taqsim Reach node's output trace.

    Args:
        system: A simulated WaterSystem with daily frequency and start_date.
        reach_id: The Reach node to extract flow data from.
        zero_flow_threshold: Threshold below which flow is considered zero.
        pulse_thresholds: Pre-computed pulse thresholds. If None, derived from record.
        min_years: Minimum complete calendar years required.

    Returns:
        IHAResult with parameters for each complete calendar year.

    Raises:
        NonDailyFrequencyError: If system frequency is not daily.
        MissingStartDateError: If system has no start_date.
        ReachNotFoundError: If reach_id is not in the system.
        NotAReachError: If the node exists but is not a Reach.
        EmptyReachTraceError: If the Reach trace has no data.
    """
    if system.frequency != Frequency.DAILY:
        raise NonDailyFrequencyError(frequency=int(system.frequency))

    if system.start_date is None:
        raise MissingStartDateError()

    if reach_id not in system.nodes:
        raise ReachNotFoundError(
            reach_id=reach_id,
            available_reach_ids=frozenset(nid for nid, n in system.nodes.items() if isinstance(n, Reach)),
        )

    node = system.nodes[reach_id]
    if not isinstance(node, Reach):
        raise NotAReachError(
            node_id=reach_id,
            actual_type=type(node).__name__,
        )

    trace = reach_trace(system, reach_id)

    if len(trace) == 0:
        raise EmptyReachTraceError(reach_id=reach_id)

    q = np.array(trace.values(), dtype=np.float64)
    timesteps = trace.timesteps()
    time_idx = system.time_index(max(timesteps) + 1)
    dates = np.array([time_idx[t] for t in timesteps], dtype="datetime64[D]")

    return compute_iha(
        q,
        dates,
        zero_flow_threshold=zero_flow_threshold,
        pulse_thresholds=pulse_thresholds,
        min_years=min_years,
    )
