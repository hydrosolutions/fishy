"""annual_indicators : DailyDischarge × IHAProfile → AnnualIHAIndicators (pure).

DailyDischarge and AnnualIHAIndicators are Polars tables, not array wrappers.
The supported profile uses complete calendar years, supplied pulse thresholds,
and explicitly within-year daily differences. It does not estimate quantiles,
interpolate missing flows, or compute multiannual dispersion. Definitions follow
TNC IHA 7.1 (2009), pp. 6–9, 50, 61. Boundary choices remain explicit.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from enum import Enum
from itertools import pairwise
from math import isfinite
from statistics import fmean, median

import polars as pl

from fishy.quantities import Flow


class CentralStatistic(Enum):
    MEAN = "mean"
    MEDIAN = "median"


class RateBoundary(Enum):
    WITHIN_YEAR = "within_year"


@dataclass(frozen=True)
class PulseThresholds:
    low: Flow
    high: Flow

    def __post_init__(self) -> None:
        if not isinstance(self.low, Flow) or not isinstance(self.high, Flow):
            raise TypeError("Pulse thresholds require Flow quantities")
        if self.low.value > self.high.value:
            raise ValueError("Pulse thresholds require low <= high")


@dataclass(frozen=True)
class IHAProfile:
    central_statistic: CentralStatistic
    pulse_thresholds: PulseThresholds
    rate_boundary: RateBoundary

    def __post_init__(self) -> None:
        if not isinstance(self.central_statistic, CentralStatistic):
            raise TypeError("central_statistic must be CentralStatistic")
        if not isinstance(self.pulse_thresholds, PulseThresholds):
            raise TypeError("pulse_thresholds must be PulseThresholds")
        if self.rate_boundary is not RateBoundary.WITHIN_YEAR:
            raise ValueError("Only explicit WITHIN_YEAR rate boundaries are supported")


_SCHEMA = {"year": pl.Int32, "parameter": pl.String, "group": pl.Int32, "value": pl.Float64, "reason": pl.String}


def _daily_values(discharge: pl.DataFrame) -> tuple[list[date], list[float]]:
    if discharge.columns != ["date", "discharge_m3_s"] or discharge.dtypes != [pl.Date, pl.Float64]:
        raise ValueError("Expected date:Date and discharge_m3_s:Float64 columns, in that order")
    if discharge.is_empty() or discharge.null_count().sum_horizontal().item() != 0:
        raise ValueError("Daily discharge must be nonempty and contain no nulls")
    dates: list[date] = discharge["date"].to_list()
    values: list[float] = discharge["discharge_m3_s"].to_list()
    if any(not isfinite(value) or value < 0 for value in values):
        raise ValueError("Discharge must be finite and nonnegative")
    if any(right - left != timedelta(days=1) for left, right in pairwise(dates)):
        raise ValueError("Dates must be ordered, unique and dense")
    if (dates[0].month, dates[0].day) != (1, 1) or (dates[-1].month, dates[-1].day) != (12, 31):
        raise ValueError("Complete calendar years are required")
    return dates, values


def _pulse_runs(dates: list[date], selected: list[bool]) -> tuple[dict[int, list[int]], dict[int, set[str]]]:
    durations: dict[int, list[int]] = {day.year: [] for day in dates}
    warnings: dict[int, set[str]] = {day.year: set() for day in dates}
    start = 0
    while start < len(selected):
        if not selected[start]:
            start += 1
            continue
        end = start + 1
        while end < len(selected) and selected[end]:
            end += 1
        if start == 0:
            warnings[dates[start].year].add("initial_pulse_omitted_unknown_start")
        else:
            durations[dates[start].year].append(end - start)
            if end == len(selected):
                warnings[dates[start].year].add("terminal_pulse_duration_truncated")
        start = end
    return durations, warnings


def annual_indicators(discharge: pl.DataFrame, profile: IHAProfile) -> pl.DataFrame:
    """Return all 33 annual indicators; undefined values are null with a reason.

    Dates must already be sorted complete consecutive calendar years. Pulse runs
    use the entire supplied horizon and belong to their start year. A run at the
    first datum is excluded; a run reaching the last datum has a truncation warning.
    Dates of extrema use a fixed leap-calendar index (March 1 is always 61).
    """
    if not isinstance(profile, IHAProfile):
        raise TypeError("profile must be IHAProfile")
    dates, values = _daily_values(discharge)
    aggregate = fmean if profile.central_statistic is CentralStatistic.MEAN else median
    low_threshold = float(profile.pulse_thresholds.low.value)
    high_threshold = float(profile.pulse_thresholds.high.value)
    if not (isfinite(low_threshold) and isfinite(high_threshold)):
        raise ValueError("Pulse thresholds exceed finite floating-point range")
    low, low_warnings = _pulse_runs(dates, [v < low_threshold for v in values])
    high, high_warnings = _pulse_runs(dates, [v > high_threshold for v in values])
    rows: list[tuple[int, str, int, float | None, str | None]] = []
    begin = 0
    while begin < len(dates):
        year = dates[begin].year
        end = begin + 1
        while end < len(dates) and dates[end].year == year:
            end += 1
        days, flows = dates[begin:end], values[begin:end]

        def emit(
            parameter: str, group: int, value: float | None, reason: str | None = None, *, year: int = year
        ) -> None:
            if value is not None and not isfinite(value):
                raise ValueError(f"Nonfinite computed indicator: {parameter}")
            rows.append((year, parameter, group, value, reason))

        for month in range(1, 13):
            emit(
                f"monthly_flow_{month:02d}",
                1,
                aggregate([v for d, v in zip(days, flows, strict=True) if d.month == month]),
            )
        minima: dict[int, float] = {}
        for window in (1, 3, 7, 30, 90):
            averages = [fmean(flows[i : i + window]) for i in range(len(flows) - window + 1)]
            minima[window] = min(averages)
            emit(f"minimum_{window}_day", 2, minima[window])
            emit(f"maximum_{window}_day", 2, max(averages))
        emit("zero_flow_days", 2, float(flows.count(0)))
        annual_mean = fmean(flows)
        emit(
            "base_flow_index",
            2,
            minima[7] / annual_mean if annual_mean else None,
            None if annual_mean else "undefined_zero_annual_mean",
        )
        for name, extreme in (("minimum", min(flows)), ("maximum", max(flows))):
            day = days[flows.index(extreme)]
            ordinal = (date(2000, day.month, day.day) - date(2000, 1, 1)).days + 1
            emit(f"{name}_flow_date", 3, float(ordinal))
        for name, runs, warnings in (("low", low, low_warnings), ("high", high, high_warnings)):
            warning = ";".join(sorted(warnings[year])) or None
            emit(f"{name}_pulse_count", 4, float(len(runs[year])), warning)
            duration_reason = warning if runs[year] else ";".join(filter(None, ("undefined_no_pulses", warning)))
            emit(f"{name}_pulse_duration", 4, aggregate(runs[year]) if runs[year] else None, duration_reason)
        differences = [right - left for left, right in pairwise(flows)]
        for name, changes in (("rise", [v for v in differences if v > 0]), ("fall", [v for v in differences if v < 0])):
            emit(
                f"{name}_rate", 5, aggregate(changes) if changes else None, None if changes else f"undefined_no_{name}s"
            )
        signs = [1 if value > 0 else -1 for value in differences if value != 0]
        emit("reversals", 5, float(sum(left != right for left, right in pairwise(signs))))
        begin = end
    return pl.DataFrame(rows, schema=_SCHEMA, orient="row")
