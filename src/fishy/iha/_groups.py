"""Per-group IHA computation functions."""

import numpy as np
from numpy.typing import NDArray

from fishy.iha._util import rolling_mean, run_lengths


# Group 1: monthly means (Jan=1 .. Dec=12)
def compute_group1(q: NDArray[np.float64], months: NDArray[np.int32]) -> NDArray[np.float64]:
    result = np.empty(12, dtype=np.float64)
    for m in range(1, 13):
        mask = months == m
        result[m - 1] = np.mean(q[mask]) if np.any(mask) else np.nan
    return result


# Group 2: min/max rolling means, zero-flow days, BFI
def compute_group2(q: NDArray[np.float64], zero_flow_threshold: float) -> NDArray[np.float64]:
    result = np.empty(12, dtype=np.float64)
    windows = (1, 3, 7, 30, 90)
    min_7day = np.nan
    for i, w in enumerate(windows):
        rm = rolling_mean(q, w)
        result[i] = np.min(rm)
        result[i + 5] = np.max(rm)
        if w == 7:
            min_7day = result[i]
    result[10] = float(np.sum(q < zero_flow_threshold))
    annual_mean = np.mean(q)
    result[11] = min_7day / annual_mean if annual_mean > 1e-15 else np.nan
    return result


# Group 3: timing of annual extremes (day of year)
def compute_group3(q: NDArray[np.float64], day_of_year: NDArray[np.int32]) -> NDArray[np.float64]:
    result = np.empty(2, dtype=np.float64)
    result[0] = float(day_of_year[np.argmin(q)])
    result[1] = float(day_of_year[np.argmax(q)])
    return result


# Group 4: low/high pulse count and mean duration
def compute_group4(q: NDArray[np.float64], low_thresh: float, high_thresh: float) -> NDArray[np.float64]:
    result = np.empty(4, dtype=np.float64)

    low_runs = run_lengths(q < low_thresh)
    result[0] = float(len(low_runs))
    result[1] = float(np.mean(low_runs)) if len(low_runs) > 0 else 0.0

    high_runs = run_lengths(q > high_thresh)
    result[2] = float(len(high_runs))
    result[3] = float(np.mean(high_runs)) if len(high_runs) > 0 else 0.0

    return result


# Group 5: rise rate, fall rate, reversals
def compute_group5(q: NDArray[np.float64]) -> NDArray[np.float64]:
    result = np.empty(3, dtype=np.float64)
    diff = np.diff(q)

    pos = diff[diff > 0]
    neg = diff[diff < 0]

    result[0] = float(np.median(pos)) if len(pos) > 0 else 0.0
    result[1] = float(np.median(neg)) if len(neg) > 0 else 0.0
    result[2] = float(np.sum(np.diff(np.signbit(diff))))

    return result
