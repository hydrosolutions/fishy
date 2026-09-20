"""DatedFlowEvidence → SourceDefinedHydrologicalDiagnostics (public operations).

Daily DHRAM descriptor calculation remains blocked by unresolved historical
source definitions; only its supplied-summary scoring operation is exported.
"""

from fishy.diagnostics.dhram import (
    AlterationRisk,
    HydrologicalChanges,
    SupplementaryEvidence,
    SupplementaryFinding,
    classify_dhram,
)
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
    DHRAMComparison,
    IARIComparison,
    IndicatorRecord,
    MonthlyIARIComparison,
    RegimeAttribution,
    assess_dhram,
    compare_iari,
    compare_monthly_iari,
    flow_indicators,
)
from fishy.diagnostics.statistics import DispersionConvention, summarize_indicators

__all__ = [
    "AlterationRisk",
    "BasinPrecipitationSPI12",
    "CentralStatistic",
    "ComparisonBasis",
    "DHRAMComparison",
    "MonthlyIARIComparison",
    "RegimeAttribution",
    "assess_dhram",
    "compare_monthly_iari",
    "DispersionConvention",
    "HydrologicalChanges",
    "HydrologicalRegimeClass",
    "IARIComparison",
    "IARIResult",
    "IHAProfile",
    "IndicatorRecord",
    "PulseThresholds",
    "QuantileEstimator",
    "RateBoundary",
    "SummaryStatistic",
    "SupplementaryEvidence",
    "SupplementaryFinding",
    "annual_indicators",
    "classify_dhram",
    "compare_iari",
    "flow_indicators",
    "iari",
    "monthly_iari",
    "summarize_indicators",
]
