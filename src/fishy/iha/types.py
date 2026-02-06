"""Type definitions for the IHA module."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

ZERO_FLOW_THRESHOLD: float = 0.001


class Col:
    """Column index namespace for the 33 IHA parameters.

    Plain integer class attributes (numba-compatible, no IntEnum).
    """

    # Group 1 (0-11): Monthly means
    JAN = 0
    FEB = 1
    MAR = 2
    APR = 3
    MAY = 4
    JUN = 5
    JUL = 6
    AUG = 7
    SEP = 8
    OCT = 9
    NOV = 10
    DEC = 11

    # Group 2 (12-23): Extreme magnitude/duration
    MIN_1DAY = 12
    MIN_3DAY = 13
    MIN_7DAY = 14
    MIN_30DAY = 15
    MIN_90DAY = 16
    MAX_1DAY = 17
    MAX_3DAY = 18
    MAX_7DAY = 19
    MAX_30DAY = 20
    MAX_90DAY = 21
    ZERO_FLOW_DAYS = 22
    BASE_FLOW_INDEX = 23

    # Group 3 (24-25): Timing
    DATE_OF_MIN = 24
    DATE_OF_MAX = 25

    # Group 4 (26-29): Pulses
    LOW_PULSE_COUNT = 26
    LOW_PULSE_DURATION = 27
    HIGH_PULSE_COUNT = 28
    HIGH_PULSE_DURATION = 29

    # Group 5 (30-32): Rate of change
    RISE_RATE = 30
    FALL_RATE = 31
    REVERSALS = 32

    N_PARAMS: int = 33

    GROUPS: tuple[slice, ...] = (
        slice(0, 12),
        slice(12, 24),
        slice(24, 26),
        slice(26, 30),
        slice(30, 33),
    )

    NAMES: tuple[str, ...] = (
        "jan",
        "feb",
        "mar",
        "apr",
        "may",
        "jun",
        "jul",
        "aug",
        "sep",
        "oct",
        "nov",
        "dec",
        "min_1day",
        "min_3day",
        "min_7day",
        "min_30day",
        "min_90day",
        "max_1day",
        "max_3day",
        "max_7day",
        "max_30day",
        "max_90day",
        "zero_flow_days",
        "base_flow_index",
        "date_of_min",
        "date_of_max",
        "low_pulse_count",
        "low_pulse_duration",
        "high_pulse_count",
        "high_pulse_duration",
        "rise_rate",
        "fall_rate",
        "reversals",
    )


@dataclass(frozen=True)
class PulseThresholds:
    """Thresholds for detecting low and high flow pulses.

    Args:
        low: Flow value below which a low pulse is detected.
        high: Flow value above which a high pulse is detected.
    """

    low: float
    high: float

    def __post_init__(self) -> None:
        if self.low < 0:
            raise ValueError(f"low threshold must be >= 0, got {self.low}")
        if self.high < 0:
            raise ValueError(f"high threshold must be >= 0, got {self.high}")
        if self.low >= self.high:
            raise ValueError(f"low threshold must be less than high threshold, got low={self.low}, high={self.high}")


@dataclass(frozen=True)
class IHAResult:
    """Result of computing IHA parameters across multiple years.

    Args:
        values: Matrix of shape (n_years, 33) with one column per IHA parameter.
        years: Array of shape (n_years,) with the year label for each row.
        zero_flow_threshold: Threshold used to count zero-flow days.
        pulse_thresholds: Thresholds used for pulse detection, or None if
            derived from the series itself.
    """

    values: NDArray[np.float64]
    years: NDArray[np.intp]
    zero_flow_threshold: float
    pulse_thresholds: PulseThresholds | None

    def group(self, g: int) -> NDArray[np.float64]:
        """Return columns for IHA group g (1-indexed).

        Args:
            g: Group number, 1 through 5.

        Returns:
            Sub-matrix of shape (n_years, n_params_in_group).

        Raises:
            ValueError: If g is not in [1, 5].
        """
        if g < 1 or g > 5:
            raise ValueError(f"group must be between 1 and 5, got {g}")
        return self.values[:, Col.GROUPS[g - 1]]

    def param(self, col: int) -> NDArray[np.float64]:
        """Return a single parameter across all years.

        Args:
            col: Column index, 0 through 32 (use Col constants).

        Returns:
            Array of shape (n_years,).

        Raises:
            ValueError: If col is not in [0, 32].
        """
        if col < 0 or col > 32:
            raise ValueError(f"col must be between 0 and 32, got {col}")
        return self.values[:, col]

    def year_row(self, year: int) -> NDArray[np.float64]:
        """Return all 33 parameters for a single year.

        Args:
            year: The year to retrieve.

        Returns:
            Array of shape (33,).

        Raises:
            ValueError: If year is not present in self.years.
        """
        mask = self.years == year
        if not np.any(mask):
            raise ValueError(f"year {year} not found in results (available: {self.years.tolist()})")
        return self.values[mask][0]
