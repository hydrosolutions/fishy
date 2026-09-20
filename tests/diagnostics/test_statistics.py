"""Source timing rules and independently calculated dispersion witnesses."""

import math

import polars as pl
import pytest

from fishy.diagnostics.statistics import DispersionConvention, summarize_indicators


def annual(values, group=1, parameter="monthly_flow_01"):
    return pl.DataFrame(
        {
            "year": list(range(2000, 2000 + len(values))),
            "parameter": [parameter] * len(values),
            "group": [group] * len(values),
            "value": values,
            "reason": [None] * len(values),
        },
        schema={"year": pl.Int32, "parameter": pl.String, "group": pl.Int32, "value": pl.Float64, "reason": pl.String},
    )


def test_sample_and_population_conventions_discriminate():
    sample = summarize_indicators(annual([1.0, 3.0, 5.0]), dispersion=DispersionConvention.SAMPLE)
    population = summarize_indicators(annual([1.0, 3.0, 5.0]), dispersion=DispersionConvention.POPULATION)
    assert sample["mean"][0] == 3
    assert sample["standard_deviation"][0] == 2
    assert sample["coefficient_of_variation"][0] == pytest.approx(2 / 3)
    assert population["standard_deviation"][0] == pytest.approx(math.sqrt(8 / 3))


def test_winter_circular_unwrap_and_source_timing_cv():
    result = summarize_indicators(
        annual([365.0, 1.0, 2.0], 3, "minimum_flow_date"), dispersion=DispersionConvention.SAMPLE
    )
    # Dominant Q1 unwraps365 to -1, hence mean2/3, sampleSD=sqrt(7/3).
    assert result["mean"][0] == pytest.approx(2 / 3)
    assert result["coefficient_of_variation"][0] == pytest.approx(math.sqrt(7 / 3) / 366)


def test_dominant_quarter_tie_not_arbitrary_linear_or_trig_average():
    result = summarize_indicators(annual([1.0, 365.0], 3, "maximum_flow_date"), dispersion=DispersionConvention.SAMPLE)
    assert result["mean"][0] is None
    assert "quarter_tie" in result["reason"][0]


def test_zero_mean_cv_and_missing_annual_value_remain_undefined():
    result = summarize_indicators(annual([0.0, 0.0]), dispersion=DispersionConvention.SAMPLE)
    assert result["mean"][0] == 0 and result["standard_deviation"][0] == 0
    assert result["coefficient_of_variation"][0] is None
    result = summarize_indicators(annual([1.0, None]), dispersion=DispersionConvention.SAMPLE)
    assert result["mean"][0] is None


def test_one_year_does_not_hide_missing_sample_dispersion():
    result = summarize_indicators(annual([3.0]), dispersion=DispersionConvention.SAMPLE)
    assert result["mean"][0] == 3 and result["standard_deviation"][0] is None


def test_omitted_year_not_dropped_from_parameter_summary():
    frame = pl.concat([annual([1.0, 3.0]), annual([4.0], parameter="monthly_flow_02")])
    result = summarize_indicators(frame, dispersion=DispersionConvention.SAMPLE)
    assert result.filter(pl.col("parameter") == "monthly_flow_02")["mean"][0] is None
