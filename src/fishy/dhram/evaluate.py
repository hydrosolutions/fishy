"""DHRAM evaluation orchestrator for taqsim WaterSystem pairs."""

import logging
from collections.abc import Sequence

import numpy as np
from taqsim.system import WaterSystem
from taqsim.time import Frequency

from fishy._extract import edge_trace
from fishy.dhram.compute import compute_dhram
from fishy.dhram.errors import EdgeEvaluationError, NoCommonEdgesError
from fishy.dhram.types import DHRAMResult, ThresholdVariant
from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import MissingStartDateError, NonDailyFrequencyError
from fishy.iha.types import ZERO_FLOW_THRESHOLD

logger = logging.getLogger(__name__)

NATURAL_TAG: str = "natural"


def _natural_edge_ids(system: WaterSystem) -> frozenset[str]:
    return frozenset(eid for eid, edge in system.edges.items() if NATURAL_TAG in edge.tags)


def _extract_flow(system: WaterSystem, edge_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Extract flow array and date array from a system edge."""
    trace = edge_trace(system, edge_id)
    q = np.array(trace.values(), dtype=np.float64)
    timesteps = trace.timesteps()
    time_idx = system.time_index(max(timesteps) + 1)
    dates = np.array([time_idx[t] for t in timesteps], dtype="datetime64[D]")
    return q, dates


def evaluate_dhram(
    natural: WaterSystem,
    impacted: WaterSystem,
    *,
    edge_ids: Sequence[str] | None = None,
    threshold_variant: ThresholdVariant = ThresholdVariant.EMPIRICAL,
    flow_cessation: bool = False,
    subdaily_oscillation: bool = False,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    min_years: int = 1,
) -> dict[str, DHRAMResult]:
    """Evaluate DHRAM classification for each shared natural-tagged edge.

    Args:
        natural: Simulated WaterSystem representing natural conditions.
        impacted: Simulated WaterSystem representing impacted conditions.
        edge_ids: Specific edges to evaluate. If None, uses all shared natural-tagged edges.
        threshold_variant: Empirical (default) or simplified thresholds.
        flow_cessation: Whether anthropogenic flow cessation is present.
        subdaily_oscillation: Whether sub-daily oscillations exceed threshold.
        zero_flow_threshold: Threshold below which flow is considered zero.
        min_years: Minimum complete years required in each series.

    Returns:
        Dict mapping edge_id to DHRAMResult for each successfully evaluated edge.

    Raises:
        NonDailyFrequencyError: If either system is not daily.
        MissingStartDateError: If either system has no start_date.
        NoCommonEdgesError: If no shared natural-tagged edges are found.
        EdgeEvaluationError: If ALL edges fail evaluation.
    """
    # Validate prerequisites
    if natural.frequency != Frequency.DAILY:
        raise NonDailyFrequencyError(frequency=int(natural.frequency))
    if impacted.frequency != Frequency.DAILY:
        raise NonDailyFrequencyError(frequency=int(impacted.frequency))
    if natural.start_date is None:
        raise MissingStartDateError()
    if impacted.start_date is None:
        raise MissingStartDateError()

    # Resolve edge selection
    if edge_ids is not None:
        selected = list(edge_ids)
    else:
        nat_edges = _natural_edge_ids(natural)
        imp_edges = _natural_edge_ids(impacted)
        common = nat_edges & imp_edges
        if not common:
            raise NoCommonEdgesError(
                natural_edge_ids=nat_edges,
                impacted_edge_ids=imp_edges,
            )
        selected = sorted(common)

    if not selected:
        nat_edges = _natural_edge_ids(natural)
        imp_edges = _natural_edge_ids(impacted)
        raise NoCommonEdgesError(
            natural_edge_ids=nat_edges,
            impacted_edge_ids=imp_edges,
        )

    # Per-edge pipeline
    results: dict[str, DHRAMResult] = {}
    errors: dict[str, Exception] = {}

    for eid in selected:
        try:
            # Extract natural flow and derive pulse thresholds
            nat_q, nat_dates = _extract_flow(natural, eid)
            thresholds = pulse_thresholds_from_record(nat_q)

            # Compute IHA for both using same pulse thresholds
            nat_iha = compute_iha(
                nat_q,
                nat_dates,
                zero_flow_threshold=zero_flow_threshold,
                pulse_thresholds=thresholds,
                min_years=min_years,
            )

            imp_q, imp_dates = _extract_flow(impacted, eid)
            imp_iha = compute_iha(
                imp_q,
                imp_dates,
                zero_flow_threshold=zero_flow_threshold,
                pulse_thresholds=thresholds,
                min_years=min_years,
            )

            # Compute DHRAM
            result = compute_dhram(
                nat_iha,
                imp_iha,
                threshold_variant=threshold_variant,
                flow_cessation=flow_cessation,
                subdaily_oscillation=subdaily_oscillation,
                min_years=min_years,
            )
            results[eid] = result

        except Exception as exc:
            logger.warning("DHRAM evaluation failed for edge '%s': %s", eid, exc)
            errors[eid] = exc

    if not results:
        raise EdgeEvaluationError(edge_errors=errors)

    return results
