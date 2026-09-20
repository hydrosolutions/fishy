"""IARI : annual IHA parameters × reference parameters → hydrological alteration.

ISPRA (2011), version 1.1, chapter 1, equations 1–5 and Table 1.4.
The daily profile summarizes five recent years before measuring distance to the
reference interquartile band. Named quantile estimators are explicit choices,
not claims of equivalence to the unspecified historical IMSL implementation.
The monthly profile consumes monthly mean discharges, not daily observations.
No-data spot measurements and expert Phase 2 judgments are not computed here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from math import floor, isfinite
from statistics import mean, median

import polars as pl


class SummaryStatistic(Enum):
    """Source-permitted current-period summary."""

    MEAN = "mean"
    MEDIAN = "median"


class QuantileEstimator(Enum):
    """Explicit sample-quantile convention; neither implies IMSL identity."""

    LINEAR = "linear_type_7"
    WEIBULL = "weibull_type_6"


class HydrologicalRegimeClass(Enum):
    """Numerical classes from ISPRA Table 1.4, not biological or legal status."""

    ELEVATO = "elevato"
    BUONO = "buono"
    NON_BUONO = "non_buono"


@dataclass(frozen=True)
class BasinPrecipitationSPI12:
    """Supplied standardized basin areal precipitation index at 12 months."""

    value: float

    def __post_init__(self) -> None:
        if not isfinite(self.value):
            raise ValueError("SPI must be finite")


@dataclass(frozen=True)
class IARIResult:
    """Attributable component scores and complete numerical index, when supported."""

    scores: pl.DataFrame
    total: float | None
    classification: HydrologicalRegimeClass | None
    reason: str | None
    summary: SummaryStatistic
    quantile: QuantileEstimator
    source_profile: str


def classify_iari(value: float) -> HydrologicalRegimeClass:
    """Apply closed upper bounds of ISPRA Table 1.4."""
    if not isfinite(value) or value < 0:
        raise ValueError("IARI must be finite and nonnegative")
    if value <= 0.05:
        return HydrologicalRegimeClass.ELEVATO
    if value <= 0.15:
        return HydrologicalRegimeClass.BUONO
    return HydrologicalRegimeClass.NON_BUONO


def _quantile(values: list[float], probability: float, estimator: QuantileEstimator) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if estimator is QuantileEstimator.LINEAR:
        position = (n - 1) * probability
    elif estimator is QuantileEstimator.WEIBULL:
        position = (n + 1) * probability - 1
    else:
        raise TypeError("quantile must be a QuantileEstimator")
    position = max(0.0, min(float(n - 1), position))
    lower = floor(position)
    upper = min(lower + 1, n - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def _summary(values: list[float], statistic: SummaryStatistic) -> float:
    if statistic is SummaryStatistic.MEAN:
        return mean(values)
    if statistic is SummaryStatistic.MEDIAN:
        return median(values)
    raise TypeError("summary must be a SummaryStatistic")


def _distance(value: float, lower: float, upper: float) -> tuple[float | None, str | None]:
    if lower <= value <= upper:
        return 0.0, None
    if lower == upper:
        return None, "outside_zero_width_reference_iqr"
    return min(abs(value - lower), abs(value - upper)) / (upper - lower), None


def _years(frame: pl.DataFrame, minimum: int) -> list[int]:
    years = sorted(frame["year"].unique().to_list())
    if not years or any(year is None for year in years):
        raise ValueError("years must be present")
    if len(years) < minimum or years != list(range(years[0], years[-1] + 1)):
        raise ValueError(f"requires at least {minimum} contiguous years")
    return years


def _schema(frame: pl.DataFrame, required: Mapping[str, pl.DataType | type[pl.DataType]]) -> None:
    for column, dtype in required.items():
        if column not in frame.columns or frame.schema[column] != dtype:
            raise ValueError(f"{column} must have dtype {dtype}")


def _result(
    rows: list[dict],
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
    profile: str,
    correction: float = 1.0,
) -> IARIResult:
    scores = pl.DataFrame(
        rows,
        schema={
            "parameter": pl.String,
            "group": pl.Int32,
            "reference_q25": pl.Float64,
            "reference_q75": pl.Float64,
            "characteristic": pl.Float64,
            "score": pl.Float64,
            "reason": pl.String,
        },
    )
    values = scores["score"].to_list()
    if any(value is None for value in values):
        return IARIResult(scores, None, None, "unsupported_required_parameters", summary, quantile, profile)
    total = correction * mean(values)
    return IARIResult(scores, total, classify_iari(total), None, summary, quantile, profile)


def _score_row(
    parameter: str,
    group: int,
    reference: Sequence[float | None],
    impacted: Sequence[float | None],
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
) -> dict:
    row = {
        "parameter": parameter,
        "group": group,
        "reference_q25": None,
        "reference_q75": None,
        "characteristic": None,
        "score": None,
        "reason": None,
    }
    if any(value is None for value in (*reference, *impacted)):
        row["reason"] = "unsupported_input_parameter"
        return row
    natural = [float(value) for value in reference if value is not None]
    current = [float(value) for value in impacted if value is not None]
    lower, upper = _quantile(natural, 0.25, quantile), _quantile(natural, 0.75, quantile)
    characteristic = _summary(current, summary)
    score, reason = _distance(characteristic, lower, upper)
    row.update(reference_q25=lower, reference_q75=upper, characteristic=characteristic, score=score, reason=reason)
    return row


def _choices(summary: SummaryStatistic, quantile: QuantileEstimator) -> None:
    if not isinstance(summary, SummaryStatistic) or not isinstance(quantile, QuantileEstimator):
        raise TypeError("summary and quantile require explicit enum choices")


def _finite(values: list[float | None], *, nonnegative: bool = False) -> None:
    if any(value is not None and (not isfinite(value) or (nonnegative and value < 0)) for value in values):
        raise ValueError("input values must be finite and within their domain")


def spi_correction(spi: BasinPrecipitationSPI12) -> float:
    """ISPRA Table 1.3, preserving the asymmetric signed interval endpoints."""
    if not isinstance(spi, BasinPrecipitationSPI12):
        raise TypeError("SPI must identify the basin precipitation 12-month basis")
    value = spi.value
    if value > 2 or value <= -2:
        return 0.5
    if value > 1 or value <= -1:
        return 0.75
    return 1.0


def monthly_iari(
    reference: pl.DataFrame,
    impacted: pl.DataFrame,
    *,
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
    spi: BasinPrecipitationSPI12 | None = None,
) -> IARIResult:
    """Assess supplied monthly mean discharges using ISPRA equations 3–5.

    Tables contain year:Int32, month:Int32, discharge_m3_s:Float64. Supply
    at least 20 contiguous reference years. Supply at least five contiguous
    impacted years (only the last five are summarized), or exactly one year
    with an explicit basin SPI12. Two to four years are rejected: select the
    current year explicitly rather than silently averaging them.
    """
    _choices(summary, quantile)
    schema = {"year": pl.Int32, "month": pl.Int32, "discharge_m3_s": pl.Float64}
    for frame in (reference, impacted):
        _schema(frame, schema)
        _finite(frame["discharge_m3_s"].to_list(), nonnegative=True)
        if frame.select("year", "month").null_count().row(0) != (0, 0):
            raise ValueError("monthly identity cannot be null")
        if frame.select("year", "month").is_duplicated().any():
            raise ValueError("duplicate monthly identity")
        for group in frame.partition_by("year"):
            if sorted(group["month"].to_list()) != list(range(1, 13)):
                raise ValueError("each year requires all twelve monthly means")
    _years(reference, 20)
    years = _years(impacted, 1)
    if len(years) == 1:
        if spi is None:
            raise ValueError("single current year requires basin precipitation SPI12")
        correction = spi_correction(spi)
    elif len(years) >= 5:
        if spi is not None:
            raise ValueError("SPI correction does not apply to five-year summaries")
        correction = 1.0
        impacted = impacted.filter(pl.col("year") >= years[-5])
    else:
        raise ValueError("supply one current year with SPI or at least five years")
    rows = [
        _score_row(
            f"month_{month:02d}",
            1,
            reference.filter(pl.col("month") == month)["discharge_m3_s"].to_list(),
            impacted.filter(pl.col("month") == month)["discharge_m3_s"].to_list(),
            summary,
            quantile,
        )
        for month in range(1, 13)
    ]
    return _result(rows, summary, quantile, "ISPRA_2011_v1.1_monthly", correction)


# ISPRA Table 1.2 parameter membership; IDs shared with annual_indicators.
_PARAMETER_GROUPS = {
    **{f"monthly_flow_{month:02d}": 1 for month in range(1, 13)},
    **{f"{extreme}_{window}_day": 2 for extreme in ("minimum", "maximum") for window in (1, 3, 7, 30, 90)},
    "zero_flow_days": 2,
    "base_flow_index": 2,
    "minimum_flow_date": 3,
    "maximum_flow_date": 3,
    "low_pulse_count": 4,
    "low_pulse_duration": 4,
    "high_pulse_count": 4,
    "high_pulse_duration": 4,
    "rise_rate": 5,
    "fall_rate": 5,
    "reversals": 5,
}


def _annual_table(frame: pl.DataFrame, minimum: int) -> list[int]:
    _schema(
        frame, {"year": pl.Int32, "parameter": pl.String, "group": pl.Int32, "value": pl.Float64, "reason": pl.String}
    )
    if frame.select("year", "parameter", "group").null_count().row(0) != (0, 0, 0):
        raise ValueError("annual parameter identities cannot be null")
    years = _years(frame, minimum)
    _finite(frame["value"].to_list())
    if frame.select("year", "parameter").is_duplicated().any():
        raise ValueError("duplicate annual parameter")
    for year in frame.partition_by("year"):
        membership = dict(year.select("parameter", "group").iter_rows())
        if membership != _PARAMETER_GROUPS:
            raise ValueError("each year requires the exact 33 IHA parameters and groups")
    for parameter, value, reason in frame.select("parameter", "value", "reason").iter_rows():
        if value is None and not reason:
            raise ValueError("unsupported annual values require a reason")
        if value is not None:
            if parameter == "fall_rate" and value > 0:
                raise ValueError("fall_rate must be nonpositive")
            if parameter != "fall_rate" and value < 0:
                raise ValueError("annual parameter outside nonnegative domain")
            if parameter in ("minimum_flow_date", "maximum_flow_date") and not 1 <= value <= 366:
                raise ValueError("timing requires a fixed leap-calendar day in 1..366")
    return years


def _quarter(value: float) -> int:
    if value <= 91:
        return 1
    if value <= 183:
        return 2
    if value <= 275:
        return 3
    return 4


def _dominant_quarter(values: list[float]) -> int | None:
    counts = [sum(_quarter(value) == quarter for value in values) for quarter in (1, 2, 3, 4)]
    largest = max(counts)
    if counts.count(largest) != 1:
        return None
    return counts.index(largest) + 1


def _unwrap_timing(values: list[float]) -> tuple[list[float] | None, str | None]:
    """IHA 7.1 quarterly unwrapping; retain ambiguous-axis unsupported reason.

    Returned values intentionally retain the unwrapped axis for statistics.
    The caller must wrap final dates (<0 add366; >366 subtract366) and reject
    resulting day zero. More than ten percent opposite-quarter dates warns.
    """
    if not values or any(not isfinite(value) or not 1 <= value <= 366 for value in values):
        raise ValueError("timing requires nonempty finite leap-calendar dates")
    dominant = _dominant_quarter(values)
    if dominant is None:
        return None, "unsupported_tied_dominant_quarters"
    opposite = {1: 3, 2: 4, 3: 1, 4: 2}[dominant]
    reason = (
        "circular_opposite_quarter_over_ten_percent"
        if sum(_quarter(value) == opposite for value in values) / len(values) > 0.1
        else None
    )
    shifted = [
        value - 366
        if dominant == 1 and _quarter(value) == 4
        else value + 366
        if dominant == 4 and _quarter(value) == 1
        else value
        for value in values
    ]
    return shifted, reason


def _timing_row(
    parameter: str,
    reference: Sequence[float | None],
    impacted: Sequence[float | None],
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
) -> dict:
    if any(value is None for value in (*reference, *impacted)):
        return _score_row(parameter, 3, reference, impacted, summary, quantile)
    natural = [float(value) for value in reference if value is not None]
    current = [float(value) for value in impacted if value is not None]
    dominant = _dominant_quarter(natural)
    other = _dominant_quarter(current)
    if dominant is None or other is None or (dominant != other and {dominant, other} != {2, 3}):
        return {
            "parameter": parameter,
            "group": 3,
            "reference_q25": None,
            "reference_q75": None,
            "characteristic": None,
            "score": None,
            "reason": "unsupported_ambiguous_circular_timing_axis",
        }

    natural_axis, natural_warning = _unwrap_timing(natural)
    current_axis, current_warning = _unwrap_timing(current)
    assert natural_axis is not None and current_axis is not None
    # Different q2/q3 dominant quarters both use the identity transformation.
    result = _score_row(parameter, 3, natural_axis, current_axis, summary, quantile)
    warnings = [reason for reason in (result["reason"], natural_warning, current_warning) if reason]
    result["reason"] = "; ".join(dict.fromkeys(warnings)) if warnings else None
    if any(result[key] == 0 for key in ("reference_q25", "reference_q75", "characteristic")):
        result.update(score=None, reason="unsupported_circular_day_zero")
    return result


def iari(
    reference: pl.DataFrame,
    impacted: pl.DataFrame,
    *,
    summary: SummaryStatistic,
    quantile: QuantileEstimator,
) -> IARIResult:
    """Assess all 33 annual IHA parameters under ISPRA's sufficient-data route.

    Reference requires at least twenty contiguous complete annual parameter
    sets. The current characteristic uses the last five contiguous annual sets.
    Identified reconstructed references may overlap the impacted dates.
    Reference identity and comparison basis belong to the calling boundary.
    Null parameters prevent a complete index but do
    not suppress independently supported component scores.

    Timing is supported on a shared unique dominant-quarter axis (IHA 7.1,
    pp.62–63). Tied or differently transformed dominant quarters remain unsupported rather
    than guessing a circular interval. Timing output statistics retain the
    shared unwrapped day axis so that their distance can be audited.
    """
    _choices(summary, quantile)
    _annual_table(reference, 20)
    impacted_years = _annual_table(impacted, 5)
    selected_years = impacted_years[-5:]
    impacted = impacted.filter(pl.col("year").is_in(selected_years))
    rows = []
    for parameter, group in _PARAMETER_GROUPS.items():
        natural = reference.filter(pl.col("parameter") == parameter)["value"].to_list()
        current = impacted.filter(pl.col("parameter") == parameter)["value"].to_list()
        if group == 3:
            row = _timing_row(parameter, natural, current, summary, quantile)
        else:
            row = _score_row(parameter, group, natural, current, summary, quantile)
        input_reasons = []
        for label, table in (("reference", reference), ("impacted", impacted)):
            for year, reason in table.filter(pl.col("parameter") == parameter).select("year", "reason").iter_rows():
                if reason:
                    input_reasons.append(f"{label}:{year}:{reason}")
        reasons = [row["reason"]] if row["reason"] else []
        reasons.extend(input_reasons)
        row["reason"] = "; ".join(reasons) if reasons else None
        rows.append(row)
    return _result(rows, summary, quantile, "ISPRA_2011_v1.1_daily")
