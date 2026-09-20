"""DatedFlowEvidence → SourceDefinedHydrologicalDiagnostics (public operations).

Supported profiles calculate IHA and IARI independently of a simulator.
"""

from fishy.diagnostics.iari import (
    BasinPrecipitationSPI12,
    HydrologicalRegimeClass,
    IARIResult,
    QuantileEstimator,
    SummaryStatistic,
    iari,
    monthly_iari,
)
from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary, annual_indicators
from fishy.diagnostics.records import (
    ComparisonBasis,
    IARIComparison,
    IndicatorRecord,
    MonthlyIARIComparison,
    RegimeAttribution,
    compare_iari,
    compare_monthly_iari,
    flow_indicators,
)
from fishy.diagnostics.statistics import DispersionConvention, summarize_indicators

__all__ = [
    "BasinPrecipitationSPI12",
    "CentralStatistic",
    "ComparisonBasis",
    "MonthlyIARIComparison",
    "RegimeAttribution",
    "compare_monthly_iari",
    "DispersionConvention",
    "HydrologicalRegimeClass",
    "IARIComparison",
    "IARIResult",
    "IHAProfile",
    "IndicatorRecord",
    "PulseThresholds",
    "QuantileEstimator",
    "RateBoundary",
    "SummaryStatistic",
    "annual_indicators",
    "compare_iari",
    "flow_indicators",
    "iari",
    "monthly_iari",
    "summarize_indicators",
]
