"""IHA (Indicators of Hydrological Alteration) computation."""

from fishy.iha.compute import compute_iha, pulse_thresholds_from_record
from fishy.iha.errors import (
    DateFlowLengthMismatchError,
    IHAError,
    InsufficientDataError,
    NegativeFlowError,
    NonDailyTimestepError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, Col, IHAResult, PulseThresholds

__all__ = [
    "Col",
    "DateFlowLengthMismatchError",
    "IHAError",
    "IHAResult",
    "InsufficientDataError",
    "NegativeFlowError",
    "NonDailyTimestepError",
    "PulseThresholds",
    "ZERO_FLOW_THRESHOLD",
    "compute_iha",
    "pulse_thresholds_from_record",
]
