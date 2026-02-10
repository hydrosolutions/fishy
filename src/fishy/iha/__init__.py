"""IHA (Indicators of Hydrological Alteration) computation."""

from fishy.iha.bridge import iha_from_reach
from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import (
    DateFlowLengthMismatchError,
    EmptyReachTraceError,
    IHAError,
    InsufficientDataError,
    MissingStartDateError,
    NegativeFlowError,
    NonDailyFrequencyError,
    NonDailyTimestepError,
    NotAReachError,
    ReachNotFoundError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, Col, IHAResult, PulseThresholds

__all__ = [
    "Col",
    "DateFlowLengthMismatchError",
    "EmptyReachTraceError",
    "IHAError",
    "IHAResult",
    "InsufficientDataError",
    "MissingStartDateError",
    "NegativeFlowError",
    "NonDailyFrequencyError",
    "NonDailyTimestepError",
    "NotAReachError",
    "PulseThresholds",
    "ReachNotFoundError",
    "ZERO_FLOW_THRESHOLD",
    "compute_iha",
    "iha_from_reach",
    "pulse_thresholds_from_record",
]
