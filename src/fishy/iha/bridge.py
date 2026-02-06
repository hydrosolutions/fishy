"""Bridge between taqsim WaterSystem and IHA computation."""

import numpy as np
from taqsim.edge import WaterDelivered
from taqsim.system import WaterSystem
from taqsim.time import Frequency

from fishy.iha.compute import compute_iha
from fishy.iha.errors import (
    EdgeNotFoundError,
    EmptyTraceError,
    MissingStartDateError,
    NonDailyFrequencyError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, IHAResult, PulseThresholds


def iha_from_trace(
    system: WaterSystem,
    edge_id: str,
    *,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    pulse_thresholds: PulseThresholds | None = None,
    min_years: int = 1,
) -> IHAResult:
    """Compute IHA parameters from a taqsim edge trace.

    Args:
        system: A simulated WaterSystem with daily frequency and start_date.
        edge_id: The edge to extract flow data from.
        zero_flow_threshold: Threshold below which flow is considered zero.
        pulse_thresholds: Pre-computed pulse thresholds. If None, derived from record.
        min_years: Minimum complete calendar years required.

    Returns:
        IHAResult with parameters for each complete calendar year.

    Raises:
        NonDailyFrequencyError: If system frequency is not daily.
        MissingStartDateError: If system has no start_date.
        EdgeNotFoundError: If edge_id is not in the system.
        EmptyTraceError: If the edge trace has no data.
    """
    if system.frequency != Frequency.DAILY:
        raise NonDailyFrequencyError(frequency=int(system.frequency))

    if system.start_date is None:
        raise MissingStartDateError()

    if edge_id not in system.edges:
        raise EdgeNotFoundError(
            edge_id=edge_id,
            available_edge_ids=frozenset(system.edges.keys()),
        )

    edge = system.edges[edge_id]
    trace = edge.trace(WaterDelivered)

    if len(trace) == 0:
        raise EmptyTraceError(edge_id=edge_id)

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
