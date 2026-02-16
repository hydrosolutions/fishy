"""IARI objective factory for taqsim optimization."""

import numpy as np
from taqsim.objective import Objective
from taqsim.system import WaterSystem

from fishy.iari._deviation import compute_deviations
from fishy.iari.types import NaturalBands
from fishy.iha.bridge import iha_from_reach
from fishy.iha.types import ZERO_FLOW_THRESHOLD


def iari_objective(
    bands: NaturalBands,
    reach_id: str,
    *,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    min_years: int = 1,
    priority: int = 1,
) -> Objective:
    """Build a taqsim Objective that minimizes IARI at a Reach.

    Args:
        bands: Pre-computed natural IQR bands (frozen, picklable).
        reach_id: ID of the Reach node to evaluate.
        zero_flow_threshold: Flow below which days count as zero-flow.
        min_years: Minimum complete calendar years required for IHA.
        priority: Objective priority for the optimizer.

    Returns:
        taqsim Objective that minimizes IARI deviation at the given Reach.
    """

    def evaluate(system: WaterSystem) -> float:
        iha = iha_from_reach(
            system,
            reach_id,
            pulse_thresholds=bands.pulse_thresholds,
            zero_flow_threshold=zero_flow_threshold,
            min_years=min_years,
        )
        deviations = compute_deviations(iha.values, bands)
        per_year = np.mean(deviations, axis=1)
        return float(np.mean(per_year))

    return Objective(
        name=f"{reach_id}.iari",
        direction="minimize",
        evaluate=evaluate,
        priority=priority,
    )


def composite_iari_objective(
    bands_by_reach: dict[str, NaturalBands],
    *,
    weights: dict[str, float] | None = None,
    name: str = "iari",
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    min_years: int = 1,
    priority: int = 1,
) -> Objective:
    """Build a taqsim Objective that minimizes weighted-average IARI across Reaches.

    Args:
        bands_by_reach: Mapping of reach ID to pre-computed natural IQR bands.
        weights: Optional per-reach weights. Keys must match bands_by_reach exactly.
            If None, equal weights are used. All values must be positive.
        name: Objective name for the optimizer.
        zero_flow_threshold: Flow below which days count as zero-flow.
        min_years: Minimum complete calendar years required for IHA.
        priority: Objective priority for the optimizer.

    Returns:
        taqsim Objective that minimizes weighted-average IARI deviation.

    Raises:
        ValueError: If bands_by_reach is empty, weights keys do not match, or
            weights are not positive.
    """
    if not bands_by_reach:
        raise ValueError("bands_by_reach must not be empty")

    reach_ids = sorted(bands_by_reach)

    if weights is not None:
        extra = set(weights) - set(bands_by_reach)
        missing = set(bands_by_reach) - set(weights)
        if extra or missing:
            parts: list[str] = []
            if extra:
                parts.append(f"extra={sorted(extra)}")
            if missing:
                parts.append(f"missing={sorted(missing)}")
            raise ValueError(f"weights keys must match bands_by_reach keys: {', '.join(parts)}")
        if any(w <= 0 for w in weights.values()):
            raise ValueError("all weights must be positive")
        total_weight = sum(weights.values())
        normalized = {rid: weights[rid] / total_weight for rid in reach_ids}
    else:
        n = len(reach_ids)
        normalized = dict.fromkeys(reach_ids, 1.0 / n)

    def evaluate(system: WaterSystem) -> float:
        total = 0.0
        for rid in reach_ids:
            bands = bands_by_reach[rid]
            iha = iha_from_reach(
                system,
                rid,
                pulse_thresholds=bands.pulse_thresholds,
                zero_flow_threshold=zero_flow_threshold,
                min_years=min_years,
            )
            deviations = compute_deviations(iha.values, bands)
            per_year = np.mean(deviations, axis=1)
            total += normalized[rid] * float(np.mean(per_year))
        return total

    return Objective(
        name=name,
        direction="minimize",
        evaluate=evaluate,
        priority=priority,
    )
