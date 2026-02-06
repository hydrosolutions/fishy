"""IHA computation orchestrator."""

import numpy as np
from numpy.typing import NDArray

from fishy.iha._groups import compute_group1, compute_group2, compute_group3, compute_group4, compute_group5
from fishy.iha._util import dates_to_components, extract_year_slices
from fishy.iha.errors import (
    DateFlowLengthMismatchError,
    InsufficientDataError,
    NegativeFlowError,
    NonDailyTimestepError,
)
from fishy.iha.types import ZERO_FLOW_THRESHOLD, Col, IHAResult, PulseThresholds


def pulse_thresholds_from_record(q: NDArray[np.float64]) -> PulseThresholds:
    """Derive pulse thresholds from the 25th and 75th percentiles of the full record.

    Args:
        q: Full flow record.

    Returns:
        PulseThresholds with low=Q25, high=Q75.

    Raises:
        ValueError: If Q25 >= Q75 (e.g. constant flow).
    """
    low = float(np.percentile(q, 25))
    high = float(np.percentile(q, 75))
    return PulseThresholds(low=low, high=high)


def compute_iha(
    q: NDArray[np.float64],
    dates: NDArray[np.datetime64],
    *,
    zero_flow_threshold: float = ZERO_FLOW_THRESHOLD,
    pulse_thresholds: PulseThresholds | None = None,
    min_years: int = 1,
) -> IHAResult:
    """Compute the 33 IHA parameters for each complete calendar year.

    Args:
        q: Daily flow values.
        dates: Daily dates as datetime64[D]. Must be same length as q.
        zero_flow_threshold: Threshold below which flow is considered zero.
        pulse_thresholds: External thresholds for Group 4 pulse analysis.
            If None, derived from the 25th/75th percentiles of the full record.
        min_years: Minimum number of complete calendar years required.

    Returns:
        IHAResult containing (n_years, 33) parameter matrix.

    Raises:
        DateFlowLengthMismatchError: If q and dates have different lengths.
        NegativeFlowError: If any flow value is negative.
        NonDailyTimestepError: If dates are not continuous daily.
        InsufficientDataError: If fewer than min_years complete years found.
    """
    # 1. Validate lengths match
    if len(q) != len(dates):
        raise DateFlowLengthMismatchError(n_dates=len(dates), n_flows=len(q))

    # 2. Validate no negatives
    neg_mask = q < 0
    if np.any(neg_mask):
        raise NegativeFlowError(n_negative=int(np.sum(neg_mask)), min_value=float(np.min(q)))

    # 3. Validate daily continuity
    if len(dates) > 1:
        diffs = np.diff(dates).astype(np.int64)
        bad = np.flatnonzero(diffs != 1)
        if len(bad) > 0:
            pos = int(bad[0])
            raise NonDailyTimestepError(position=pos, gap_days=int(diffs[pos]))

    # 4. Extract year slices
    year_slices = extract_year_slices(dates)

    # 5. Check min_years
    if len(year_slices) < min_years:
        raise InsufficientDataError(n_days=len(q), n_years=len(year_slices), min_years=min_years)

    # 6. Resolve pulse thresholds
    if pulse_thresholds is None:
        pulse_thresholds = pulse_thresholds_from_record(q)

    # 7. Extract date components (vectorized, once for all)
    _, months, day_of_year = dates_to_components(dates)

    # 8. Allocate output and loop over years
    n_years = len(year_slices)
    values = np.empty((n_years, Col.N_PARAMS), dtype=np.float64)
    years = np.empty(n_years, dtype=np.intp)

    for i, (year, start, end) in enumerate(year_slices):
        years[i] = year
        q_year = q[start:end]
        months_year = months[start:end]
        doy_year = day_of_year[start:end]

        values[i, Col.GROUPS[0]] = compute_group1(q_year, months_year)
        values[i, Col.GROUPS[1]] = compute_group2(q_year, zero_flow_threshold)
        values[i, Col.GROUPS[2]] = compute_group3(q_year, doy_year)
        values[i, Col.GROUPS[3]] = compute_group4(q_year, pulse_thresholds.low, pulse_thresholds.high)
        values[i, Col.GROUPS[4]] = compute_group5(q_year)

    # 9. Return result
    return IHAResult(
        values=values,
        years=years,
        zero_flow_threshold=zero_flow_threshold,
        pulse_thresholds=pulse_thresholds,
    )
