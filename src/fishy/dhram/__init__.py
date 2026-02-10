"""DHRAM (Dundee Hydrological Regime Alteration Method) classification."""

from fishy.dhram.compute import compute_dhram
from fishy.dhram.errors import (
    DHRAMError,
    IncompatibleIHAResultsError,
    InsufficientYearsError,
    NoCommonReachesError,
    ReachEvaluationError,
)
from fishy.dhram.evaluate import evaluate_dhram
from fishy.dhram.types import (
    CLASS_BOUNDARIES,
    DHRAM_GROUP_SIZES,
    EMPIRICAL_THRESHOLDS,
    INDICATOR_NAMES,
    MAX_POINTS,
    N_INDICATORS,
    SIMPLIFIED_THRESHOLDS,
    WFD_LABELS,
    DHRAMResult,
    IndicatorDetail,
    ScoringThresholds,
    ThresholdVariant,
)

__all__ = [
    "CLASS_BOUNDARIES",
    "DHRAM_GROUP_SIZES",
    "DHRAMError",
    "DHRAMResult",
    "EMPIRICAL_THRESHOLDS",
    "INDICATOR_NAMES",
    "IncompatibleIHAResultsError",
    "IndicatorDetail",
    "InsufficientYearsError",
    "MAX_POINTS",
    "N_INDICATORS",
    "NoCommonReachesError",
    "ReachEvaluationError",
    "SIMPLIFIED_THRESHOLDS",
    "ScoringThresholds",
    "ThresholdVariant",
    "WFD_LABELS",
    "compute_dhram",
    "evaluate_dhram",
]
