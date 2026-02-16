"""IARI (Index of Hydrological Regime Alteration) scoring."""

from fishy.iari._deviation import bands_from_iha
from fishy.iari.compute import compute_iari
from fishy.iari.errors import (
    IARIError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonReachesError,
    ReachEvaluationError,
)
from fishy.iari.evaluate import evaluate_iari
from fishy.iari.objective import composite_iari_objective, iari_objective
from fishy.iari.types import (
    IARIResult,
    NaturalBands,
)

__all__ = [
    "IARIError",
    "IARIResult",
    "IncompatibleIHAResultsError",
    "InsufficientYearsError",
    "NaturalBands",
    "NoCommonReachesError",
    "ReachEvaluationError",
    "bands_from_iha",
    "composite_iari_objective",
    "compute_iari",
    "evaluate_iari",
    "iari_objective",
]
