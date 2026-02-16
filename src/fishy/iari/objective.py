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
