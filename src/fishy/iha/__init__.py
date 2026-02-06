"""IHA (Indicators of Hydrological Alteration) computation."""

from fishy.iha.bridge import iha_from_trace
from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import (
    DateFlowLengthMismatchError,
    EdgeNotFoundError,
    EmptyTraceError,
    IHAError,
    InsufficientDataError,
    MissingStartDateError,
    NegativeFlowError,
    NonDailyFrequencyError,
    NonDailyTimestepError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, Col, IHAResult, PulseThresholds

__all__ = [
    "Col",
    "DateFlowLengthMismatchError",
    "EdgeNotFoundError",
    "EmptyTraceError",
    "IHAError",
    "IHAResult",
    "InsufficientDataError",
    "MissingStartDateError",
    "NegativeFlowError",
    "NonDailyFrequencyError",
    "NonDailyTimestepError",
    "PulseThresholds",
    "ZERO_FLOW_THRESHOLD",
    "compute_iha",
    "iha_from_trace",
    "pulse_thresholds_from_record",
]
