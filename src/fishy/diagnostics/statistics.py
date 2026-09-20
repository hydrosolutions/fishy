"""summarize_indicators : AnnualIHAIndicators × DispersionConvention → IHASummary (pure).

TNC IHA 7.1 §5.3 defines timing means by quarterly unwrapping and timing
CV as SD/366. The standard-deviation denominator is an explicit numerical
convention, not attributed to an unspecified historical implementation.
"""

from enum import StrEnum
from math import isfinite
from statistics import fmean, pstdev, stdev

import polars as pl


class DispersionConvention(StrEnum):
    SAMPLE = "sample_n_minus_one"
    POPULATION = "population_n"


def summarize_indicators(annual: pl.DataFrame, *, dispersion: DispersionConvention) -> pl.DataFrame:
    """Preserve unsupported components; never skip missing years in summaries."""
    if not isinstance(dispersion, DispersionConvention):
        raise TypeError("Dispersion convention must be explicit")
    required = {"year": pl.Int32, "parameter": pl.String, "group": pl.Int32, "value": pl.Float64, "reason": pl.String}
    if annual.schema != required or annual.is_empty():
        raise ValueError("Expected nonempty annual IHA table")
    if annual.select("year", "parameter").is_duplicated().any():
        raise ValueError("Duplicate annual parameter")
    years = set(annual["year"].to_list())
    rows = []
    for frame in annual.partition_by("parameter", maintain_order=True):
        parameter = frame["parameter"][0]
        groups = frame["group"].unique().to_list()
        if len(groups) != 1:
            raise ValueError("Parameter group changes across years")
        group = groups[0]
        raw = frame["value"].to_list()
        if any(value is not None and not isfinite(value) for value in raw):
            raise ValueError("Nonfinite annual indicator")
        mean = sd = cv = None
        warnings = [str(reason) for reason in frame["reason"].to_list() if reason]
        if set(frame["year"].to_list()) != years or any(value is None for value in raw):
            warnings.append("incomplete_annual_parameter")
        else:
            values = [float(value) for value in raw]
            if group == 3:
                if any(not 1 <= value <= 366 for value in values):
                    raise ValueError("Timing indicators require fixed366 calendar days")
                quarters = [0 if value <= 91 else 1 if value <= 183 else 2 if value <= 275 else 3 for value in values]
                counts = [quarters.count(q) for q in range(4)]
                if counts.count(max(counts)) != 1:
                    warnings.append("undefined_dominant_quarter_tie")
                    values = []
                else:
                    dominant = counts.index(max(counts))
                    if counts[(dominant + 2) % 4] / len(values) > 0.1:
                        warnings.append("widely_distributed_extreme_dates")
                    if dominant == 0:
                        values = [value - 366 if value >= 276 else value for value in values]
                    elif dominant == 3:
                        values = [value + 366 if value <= 91 else value for value in values]
            if values:
                mean = fmean(values)
                if dispersion is DispersionConvention.SAMPLE and len(values) < 2:
                    warnings.append("sample_dispersion_requires_two_years")
                else:
                    sd = stdev(values) if dispersion is DispersionConvention.SAMPLE else pstdev(values)
                    if group == 3:
                        cv = sd / 366
                        if sd > 180:
                            warnings.append("timing_standard_deviation_above_180_days")
                    elif mean != 0:
                        cv = sd / mean
                    else:
                        warnings.append("undefined_zero_mean_cv")
                if group == 3:
                    if mean < 0:
                        mean += 366
                    elif mean > 366:
                        mean -= 366
                    if mean == 0:
                        mean = None
                        warnings.append("undefined_timing_day_zero")
        rows.append((parameter, group, mean, sd, cv, ";".join(dict.fromkeys(warnings)) or None))
    return pl.DataFrame(
        rows,
        schema={
            "parameter": pl.String,
            "group": pl.Int32,
            "mean": pl.Float64,
            "standard_deviation": pl.Float64,
            "coefficient_of_variation": pl.Float64,
            "reason": pl.String,
        },
        orient="row",
    )
