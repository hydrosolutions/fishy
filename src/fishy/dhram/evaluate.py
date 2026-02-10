"""DHRAM evaluation orchestrator for taqsim WaterSystem pairs."""

import logging
from collections.abc import Sequence

import numpy as np
from taqsim.node import Reach
from taqsim.system import WaterSystem
from taqsim.time import Frequency

from fishy._extract import reach_trace
from fishy.dhram.compute import compute_dhram
from fishy.dhram.errors import NoCommonReachesError, ReachEvaluationError
from fishy.dhram.types import DHRAMResult, ThresholdVariant
from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import MissingStartDateError, NonDailyFrequencyError
from fishy.iha.types import ZERO_FLOW_THRESHOLD

logger = logging.getLogger(__name__)

NATURAL_TAG: str = "natural"


def _natural_reach_ids(system: WaterSystem) -> frozenset[str]:
    """Find Reach nodes that have both natural incoming and natural outgoing edges."""
    natural_edges = {eid: e for eid, e in system.edges.items() if NATURAL_TAG in e.tags}
    has_natural_incoming = {e.target for e in natural_edges.values()}
    has_natural_outgoing = {e.source for e in natural_edges.values()}
    candidates = has_natural_incoming & has_natural_outgoing
    return frozenset(nid for nid in candidates if isinstance(system.nodes[nid], Reach))


def _extract_reach_flow(system: WaterSystem, reach_id: str) -> tuple[np.ndarray, np.ndarray]:
    """Extract flow array and date array from a Reach node's WaterOutput events."""
    trace = reach_trace(system, reach_id)
    q = np.array(trace.values(), dtype=np.float64)
    timesteps = trace.timesteps()
    time_idx = system.time_index(max(timesteps) + 1)
    dates = np.array([time_idx[t] for t in timesteps], dtype="datetime64[D]")
    return q, dates


def evaluate_dhram(
    natural: WaterSystem,
    impacted: WaterSystem,
    *,
    reach_ids: Sequence[str] | None = None,
    threshold_variant: ThresholdVariant = ThresholdVariant.EMPIRICAL,
    flow_cessation: bool = False,
    subdaily_oscillation: bool = False,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    min_years: int = 1,
) -> dict[str, DHRAMResult]:
    """Evaluate DHRAM classification for each shared natural Reach node.

    Args:
        natural: Simulated WaterSystem representing natural conditions.
        impacted: Simulated WaterSystem representing impacted conditions.
        reach_ids: Specific Reach nodes to evaluate. If None, uses all shared natural Reaches.
        threshold_variant: Empirical (default) or simplified thresholds.
        flow_cessation: Whether anthropogenic flow cessation is present.
        subdaily_oscillation: Whether sub-daily oscillations exceed threshold.
        zero_flow_threshold: Threshold below which flow is considered zero.
        min_years: Minimum complete years required in each series.

    Returns:
        Dict mapping reach_id to DHRAMResult for each successfully evaluated Reach.

    Raises:
        NonDailyFrequencyError: If either system is not daily.
        MissingStartDateError: If either system has no start_date.
        NoCommonReachesError: If no shared natural Reach nodes are found.
        ReachEvaluationError: If ALL Reaches fail evaluation.
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

    # Resolve reach selection
    if reach_ids is not None:
        selected = list(reach_ids)
    else:
        nat_reaches = _natural_reach_ids(natural)
        imp_reaches = _natural_reach_ids(impacted)
        common = nat_reaches & imp_reaches
        if not common:
            raise NoCommonReachesError(
                natural_reach_ids=nat_reaches,
                impacted_reach_ids=imp_reaches,
            )
        selected = sorted(common)

    if not selected:
        nat_reaches = _natural_reach_ids(natural)
        imp_reaches = _natural_reach_ids(impacted)
        raise NoCommonReachesError(
            natural_reach_ids=nat_reaches,
            impacted_reach_ids=imp_reaches,
        )

    # Per-reach pipeline
    results: dict[str, DHRAMResult] = {}
    errors: dict[str, Exception] = {}

    for rid in selected:
        try:
            # Extract natural flow and derive pulse thresholds
            nat_q, nat_dates = _extract_reach_flow(natural, rid)
            thresholds = pulse_thresholds_from_record(nat_q)

            # Compute IHA for both using same pulse thresholds
            nat_iha = compute_iha(
                nat_q,
                nat_dates,
                zero_flow_threshold=zero_flow_threshold,
                pulse_thresholds=thresholds,
                min_years=min_years,
            )

            imp_q, imp_dates = _extract_reach_flow(impacted, rid)
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
            results[rid] = result

        except Exception as exc:
            logger.warning("DHRAM evaluation failed for reach '%s': %s", rid, exc)
            errors[rid] = exc

    if not results:
        raise ReachEvaluationError(reach_errors=errors)

    return results
