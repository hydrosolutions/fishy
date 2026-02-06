"""Internal DHRAM computation helpers."""

import math

import numpy as np
from numpy.typing import NDArray

from fishy.dhram.types import (
    CLASS_BOUNDARIES,
    WFD_LABELS,
    IndicatorDetail,
    ScoringThresholds,
)
from fishy.iha.types import Col

_DAYS_PER_YEAR = 365.25
_TWO_PI = 2.0 * math.pi
_NEAR_ZERO = 1e-10


def circular_mean_doy(doy_values: NDArray[np.float64]) -> float:
    """Compute the circular mean of day-of-year values."""
    theta = _TWO_PI * doy_values / _DAYS_PER_YEAR
    x_mean = float(np.mean(np.cos(theta)))
    y_mean = float(np.mean(np.sin(theta)))
    mean_angle = math.atan2(y_mean, x_mean)
    mean_doy = mean_angle * _DAYS_PER_YEAR / _TWO_PI
    if mean_doy < 0:
        mean_doy += _DAYS_PER_YEAR
    return mean_doy


def circular_distance_days(doy_a: float, doy_b: float) -> float:
    """Shortest arc distance in days between two circular DOY values."""
    diff = abs(doy_a - doy_b)
    if diff > _DAYS_PER_YEAR / 2:
        diff = _DAYS_PER_YEAR - diff
    return diff


def safe_percent_change(natural: float, impacted: float) -> float:
    """Absolute percentage change with zero-denominator handling.

    Returns:
        0.0 if both are near-zero, 100.0 if natural is near-zero but impacted is not,
        otherwise |impacted - natural| / |natural| * 100.
    """
    if abs(natural) < _NEAR_ZERO:
        if abs(impacted) < _NEAR_ZERO:
            return 0.0
        return 100.0
    return abs(impacted - natural) / abs(natural) * 100.0


def compute_cv(values: NDArray[np.float64]) -> float:
    """Coefficient of variation (%) using population std (ddof=0).

    Returns 0.0 if mean is near-zero.
    """
    mean = float(np.mean(values))
    if abs(mean) < _NEAR_ZERO:
        return 0.0
    std = float(np.std(values, ddof=0))
    return std / abs(mean) * 100.0


def extract_dhram_group_params(iha_values: NDArray[np.float64], group: int) -> NDArray[np.float64]:
    """Extract the IHA parameters for a given DHRAM group.

    Args:
        iha_values: Array of shape (n_years, 33).
        group: 1-based group index (1-5).

    Returns:
        Subarray for the group. For group 2, excludes zero_flow_days and BFI
        (returns only columns 12-21, not 22-23).
    """
    s = Col.GROUPS[group - 1]
    if group == 2:
        # Exclude zero_flow_days (col 22) and BFI (col 23)
        return iha_values[:, s.start : s.start + 10]
    return iha_values[:, s]


def _compute_group_indicators(
    natural_params: NDArray[np.float64],
    impacted_params: NDArray[np.float64],
    group: int,
    thresholds_a: ScoringThresholds,
    thresholds_b: ScoringThresholds,
) -> tuple[IndicatorDetail, IndicatorDetail]:
    """Compute the two indicators (Xa, Xb) for one IHA group."""
    n_params = natural_params.shape[1]
    is_timing = group == 3

    # Per-parameter mean change
    mean_changes = np.empty(n_params)
    for j in range(n_params):
        nat_col = natural_params[:, j]
        imp_col = impacted_params[:, j]
        if is_timing:
            nat_mean = circular_mean_doy(nat_col)
            imp_mean = circular_mean_doy(imp_col)
            mean_changes[j] = circular_distance_days(nat_mean, imp_mean) / _DAYS_PER_YEAR * 100.0
        else:
            nat_mean = float(np.mean(nat_col))
            imp_mean = float(np.mean(imp_col))
            mean_changes[j] = safe_percent_change(nat_mean, imp_mean)

    # Per-parameter CV change (always linear, even for timing)
    cv_changes = np.empty(n_params)
    for j in range(n_params):
        nat_cv = compute_cv(natural_params[:, j])
        imp_cv = compute_cv(impacted_params[:, j])
        cv_changes[j] = safe_percent_change(nat_cv, imp_cv)

    # Average across parameters
    avg_mean_change = float(np.mean(mean_changes))
    avg_cv_change = float(np.mean(cv_changes))

    # Score
    points_a = thresholds_a.score(avg_mean_change)
    points_b = thresholds_b.score(avg_cv_change)

    indicator_a = IndicatorDetail(
        name=f"{group}a",
        group=group,
        statistic="mean",
        value=avg_mean_change,
        points=points_a,
        thresholds=thresholds_a,
    )
    indicator_b = IndicatorDetail(
        name=f"{group}b",
        group=group,
        statistic="cv",
        value=avg_cv_change,
        points=points_b,
        thresholds=thresholds_b,
    )
    return indicator_a, indicator_b


def compute_summary_indicators(
    natural_values: NDArray[np.float64],
    impacted_values: NDArray[np.float64],
    thresholds: tuple[ScoringThresholds, ...],
) -> tuple[IndicatorDetail, ...]:
    """Compute all 10 DHRAM summary indicators (Stages 2+3).

    Args:
        natural_values: IHA values array of shape (n_years_nat, 33).
        impacted_values: IHA values array of shape (n_years_imp, 33).
        thresholds: Tuple of 10 ScoringThresholds (one per indicator).

    Returns:
        Tuple of 10 IndicatorDetail objects in order 1a, 1b, ..., 5a, 5b.
    """
    indicators: list[IndicatorDetail] = []
    for g in range(1, 6):
        nat_params = extract_dhram_group_params(natural_values, g)
        imp_params = extract_dhram_group_params(impacted_values, g)
        idx = (g - 1) * 2
        a, b = _compute_group_indicators(nat_params, imp_params, g, thresholds[idx], thresholds[idx + 1])
        indicators.append(a)
        indicators.append(b)
    return tuple(indicators)


def classify(total_points: int) -> int:
    """Map total impact points to DHRAM class (1-5)."""
    for i in range(len(CLASS_BOUNDARIES) - 1, -1, -1):
        if total_points >= CLASS_BOUNDARIES[i]:
            return i + 1
    return 1


def apply_supplementary(
    preliminary_class: int,
    *,
    flow_cessation: bool,
    subdaily_oscillation: bool,
) -> int:
    """Apply supplementary question adjustments to the preliminary class."""
    adjustment = int(flow_cessation) + int(subdaily_oscillation)
    return min(preliminary_class + adjustment, 5)


def wfd_label(dhram_class: int) -> str:
    """Map DHRAM class (1-5) to WFD status label."""
    return WFD_LABELS[dhram_class - 1]
