"""Error types for IHA computation failures."""

from dataclasses import dataclass


class IHAError(Exception):
    """Base error for IHA computation failures."""


@dataclass
class InsufficientDataError(IHAError):
    """Raised when the input timeseries spans too few complete calendar years.

    Args:
        n_days: Number of days in input.
        n_years: Number of complete calendar years found.
        min_years: Minimum required.
    """

    n_days: int
    n_years: int
    min_years: int

    def __str__(self) -> str:
        return (
            f"Insufficient data: found {self.n_years} complete calendar year(s) "
            f"from {self.n_days} days of data, but at least {self.min_years} required."
        )


@dataclass
class DateFlowLengthMismatchError(IHAError):
    """Raised when date and flow arrays have different lengths.

    Args:
        n_dates: Length of the date array.
        n_flows: Length of the flow array.
    """

    n_dates: int
    n_flows: int

    def __str__(self) -> str:
        return f"Date and flow arrays have different lengths: {self.n_dates} dates vs {self.n_flows} flow values."


@dataclass
class NonDailyTimestepError(IHAError):
    """Raised when the timeseries contains non-daily gaps.

    Args:
        position: Index where the gap was found.
        gap_days: Actual gap in days.
    """

    position: int
    gap_days: int

    def __str__(self) -> str:
        return (
            f"Non-daily timestep detected at position {self.position}: "
            f"gap of {self.gap_days} day(s). IHA requires continuous daily data."
        )


@dataclass
class NegativeFlowError(IHAError):
    """Raised when the flow data contains negative values.

    Args:
        n_negative: Count of negative values.
        min_value: Most negative value found.
    """

    n_negative: int
    min_value: float

    def __str__(self) -> str:
        return (
            f"Flow data contains {self.n_negative} negative value(s) "
            f"(minimum: {self.min_value:.6g}). IHA requires non-negative flows."
        )


@dataclass
class MissingStartDateError(IHAError):
    """Raised when a WaterSystem has no start_date set."""

    def __str__(self) -> str:
        return "WaterSystem has no start_date. IHA requires calendar dates for year extraction."


@dataclass
class NonDailyFrequencyError(IHAError):
    """Raised when a WaterSystem does not use daily frequency."""

    frequency: int

    def __str__(self) -> str:
        return f"WaterSystem frequency is {self.frequency}, but IHA requires daily (365)."


@dataclass
class ReachNotFoundError(IHAError):
    """Raised when the requested reach_id is not in the system."""

    reach_id: str
    available_reach_ids: frozenset[str]

    def __str__(self) -> str:
        return f"Reach '{self.reach_id}' not found in system. Available reaches: {sorted(self.available_reach_ids)}"


@dataclass
class NotAReachError(IHAError):
    """Raised when the specified node exists but is not a Reach."""

    node_id: str
    actual_type: str

    def __str__(self) -> str:
        return f"Node '{self.node_id}' is a {self.actual_type}, not a Reach."


@dataclass
class EmptyReachTraceError(IHAError):
    """Raised when a Reach node's trace contains no data."""

    reach_id: str

    def __str__(self) -> str:
        return f"Reach '{self.reach_id}' has an empty trace (no flow data recorded)."
