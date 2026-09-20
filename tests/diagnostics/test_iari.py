"""Numerical witnesses for ISPRA IARI equations, not official admissibility."""

import math

import polars as pl
import pytest

from fishy.diagnostics.iari import (
    BasinPrecipitationSPI12,
    HydrologicalRegimeClass,
    QuantileEstimator,
    SummaryStatistic,
    classify_iari,
    monthly_iari,
    spi_correction,
)


def monthly(values, first_year=1980):
    return pl.DataFrame(
        [(year, month, value) for year, value in enumerate(values, first_year) for month in range(1, 13)],
        schema={"year": pl.Int32, "month": pl.Int32, "discharge_m3_s": pl.Float64},
        orient="row",
    )


def assess(reference, impacted, **kwargs):
    return monthly_iari(reference, impacted, summary=SummaryStatistic.MEAN, quantile=QuantileEstimator.LINEAR, **kwargs)


@pytest.mark.parametrize(
    "value, expected",
    [
        (0, HydrologicalRegimeClass.ELEVATO),
        (0.05, HydrologicalRegimeClass.ELEVATO),
        (math.nextafter(0.05, 1), HydrologicalRegimeClass.BUONO),
        (0.15, HydrologicalRegimeClass.BUONO),
        (math.nextafter(0.15, 1), HydrologicalRegimeClass.NON_BUONO),
    ],
)
def test_classification_closed_upper_bounds(value, expected):
    assert classify_iari(value) is expected


@pytest.mark.parametrize("value", [-1, math.inf, math.nan])
def test_classification_rejects_invalid(value):
    with pytest.raises(ValueError):
        classify_iari(value)


def test_monthly_distance_and_five_year_summary_order():
    # Natural 1..20 has linear quartiles 5.75,15.25. Current mean=10,
    # inside band, although annual outside-band distances average >0.
    result = assess(monthly(range(1, 21)), monthly([0, 0, 0, 0, 50], 2000))
    assert result.total == 0
    assert result.scores["characteristic"].to_list() == [10.0] * 12


def test_monthly_mean_and_median_are_distinct_explicit_profiles():
    reference, impact = monthly(range(1, 21)), monthly([0, 0, 0, 0, 50], 2000)
    result = monthly_iari(reference, impact, summary=SummaryStatistic.MEDIAN, quantile=QuantileEstimator.LINEAR)
    assert result.total == pytest.approx(5.75 / 9.5)


def test_named_quantiles_are_disclosed_and_differ():
    reference, impact = monthly(range(1, 21)), monthly([0] * 5, 2000)
    linear = assess(reference, impact)
    weibull = monthly_iari(reference, impact, summary=SummaryStatistic.MEAN, quantile=QuantileEstimator.WEIBULL)
    assert linear.total == pytest.approx(5.75 / 9.5)
    assert weibull.total == pytest.approx(5.25 / 10.5)
    assert weibull.quantile is QuantileEstimator.WEIBULL


def test_zero_width_exact_equality_remains_zero():
    assert assess(monthly([0] * 20), monthly([0] * 5, 2000)).total == 0


def test_zero_width_outside_retains_unsupported():
    result = assess(monthly([0] * 20), monthly([1] * 5, 2000))
    assert result.total is None
    assert result.classification is None
    assert result.scores["reason"].to_list() == ["outside_zero_width_reference_iqr"] * 12


def test_null_month_keeps_supported_other_scores():
    impact = monthly([10] * 5, 2000).with_columns(
        pl.when((pl.col("year") == 2004) & (pl.col("month") == 1))
        .then(None)
        .otherwise(pl.col("discharge_m3_s"))
        .alias("discharge_m3_s")
    )
    result = assess(monthly(range(1, 21)), impact)
    assert result.total is None
    assert result.scores["score"].to_list() == [None] + [0.0] * 11


@pytest.mark.parametrize(
    "spi, expected",
    [
        (-2.01, 0.5),
        (-2, 0.5),
        (-1.99, 0.75),
        (-1, 0.75),
        (-0.99, 1),
        (1, 1),
        (1.01, 0.75),
        (2, 0.75),
        (2.01, 0.5),
    ],
)
def test_spi_signed_boundaries_and_application_to_index(spi, expected):
    index = BasinPrecipitationSPI12(spi)
    assert spi_correction(index) == expected
    result = assess(monthly(range(1, 21)), monthly([0], 2000), spi=index)
    assert result.total == pytest.approx(expected * 5.75 / 9.5)


def test_single_year_requires_spi():
    with pytest.raises(ValueError, match="SPI12"):
        assess(monthly(range(1, 21)), monthly([0], 2000))


def test_five_years_disallow_spi():
    with pytest.raises(ValueError, match="does not apply"):
        assess(monthly(range(1, 21)), monthly([0] * 5, 2000), spi=BasinPrecipitationSPI12(0))


@pytest.mark.parametrize("count", [2, 3, 4])
def test_no_silent_two_to_four_year_averaging(count):
    with pytest.raises(ValueError, match="one current year"):
        assess(monthly(range(1, 21)), monthly([0] * count, 2000), spi=BasinPrecipitationSPI12(0))


def test_missing_month_cannot_be_omitted_from_total():
    with pytest.raises(ValueError, match="twelve"):
        assess(monthly(range(1, 21)).slice(1), monthly([10] * 5, 2000))


def test_duplicate_month_rejected():
    reference = monthly(range(1, 21))
    with pytest.raises(ValueError, match="duplicate"):
        assess(pl.concat([reference, reference.head(1)]), monthly([10] * 5, 2000))


def test_reference_contiguous_twenty_year_requirement():
    with pytest.raises(ValueError, match="20 contiguous"):
        assess(monthly(range(1, 20)), monthly([10] * 5, 2000))
    reference = monthly(range(1, 22)).filter(pl.col("year") != 1990)
    with pytest.raises(ValueError, match="20 contiguous"):
        assess(reference, monthly([10] * 5, 2010))


def test_only_last_five_recent_years_are_summarized():
    assert assess(monthly(range(1, 21)), monthly([1000, 10, 10, 10, 10, 10], 2000)).total == 0


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_discharge_rejected(value):
    with pytest.raises(ValueError):
        assess(monthly(range(1, 21)), monthly([value] * 5, 2000))


# Independent complete membership fixture, not a production mapping import.
MEMBERSHIP = {
    **{f"monthly_flow_{m:02d}": 1 for m in range(1, 13)},
    **{f"{kind}_{n}_day": 2 for kind in ("minimum", "maximum") for n in (1, 3, 7, 30, 90)},
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


def annual(values, first_year=1980):
    rows = []
    for year, value in enumerate(values, first_year):
        for parameter, group in MEMBERSHIP.items():
            v = 120.0 if group == 3 else (-float(value) if parameter == "fall_rate" else float(value))
            rows.append((year, parameter, group, v, None))
    return pl.DataFrame(
        rows,
        schema={"year": pl.Int32, "parameter": pl.String, "group": pl.Int32, "value": pl.Float64, "reason": pl.String},
        orient="row",
    )


def assess_daily(reference, impacted, summary=SummaryStatistic.MEAN):
    from fishy.diagnostics.iari import iari

    return iari(reference, impacted, summary=summary, quantile=QuantileEstimator.LINEAR)


def test_daily_parameter_weighting_not_equal_group_weight():
    result = assess_daily(annual(range(1, 21)), annual([0] * 5, 2000))
    # 31 non-timing parameters identical distance; two timing scores are zero.
    assert result.total == pytest.approx((31 / 33) * (5.75 / 9.5))
    assert result.scores.height == 33


def test_daily_characteristic_precedes_distance():
    reference, impact = annual(range(1, 21)), annual([0, 0, 0, 0, 50], 2000)
    assert assess_daily(reference, impact).total == 0
    assert assess_daily(reference, impact, SummaryStatistic.MEDIAN).total == pytest.approx((31 / 33) * (5.75 / 9.5))


def test_daily_null_propagates_but_other_parameters_remain_supported():
    impact = annual([10] * 5, 2000).with_columns(
        pl.when(pl.col("parameter") == "base_flow_index").then(None).otherwise(pl.col("value")).alias("value"),
        pl.when(pl.col("parameter") == "base_flow_index")
        .then(pl.lit("undefined_base_flow"))
        .otherwise(pl.col("reason"))
        .alias("reason"),
    )
    result = assess_daily(annual(range(1, 21)), impact)
    assert result.total is None
    assert result.scores["score"].null_count() == 1
    assert result.scores.filter(pl.col("parameter") == "monthly_flow_01")["score"].item() == 0


@pytest.mark.parametrize("alteration", ["missing", "wrong_group", "duplicate"])
def test_daily_full_membership_required(alteration):
    reference, impact = annual(range(1, 21)), annual([10] * 5, 2000)
    if alteration == "missing":
        impact = impact.slice(1)
    elif alteration == "wrong_group":
        impact = impact.with_columns(pl.lit(1, dtype=pl.Int32).alias("group"))
    else:
        impact = pl.concat([impact, impact.head(1)])
    with pytest.raises(ValueError):
        assess_daily(reference, impact)


def test_daily_reference_and_current_coverage_allow_reconstructed_overlap():
    assert assess_daily(annual(range(1, 21)), annual([10] * 5, 1999)).total == 0
    with pytest.raises(ValueError, match="5 contiguous"):
        assess_daily(annual(range(1, 21)), annual([10] * 4, 2000))


def timing(frame, days):
    first_year = frame["year"].min()
    return frame.with_columns(
        pl.when(pl.col("group") == 3)
        .then(pl.col("year").replace_strict({first_year + i: float(day) for i, day in enumerate(days)}))
        .otherwise(pl.col("value"))
        .alias("value")
    )


def test_shared_quarter_axis_supports_winter_wrap():
    reference = timing(annual(range(1, 21)), [360] * 8 + [10] * 12)
    impact = timing(annual([10] * 5, 2000), [360, 10, 10, 10, 10])
    result = assess_daily(reference, impact)
    dates = result.scores.filter(pl.col("group") == 3)
    # q1 is dominant in both: 360 unwraps to -6, so quartiles -6,10.
    assert dates["reference_q25"].to_list() == [-6.0, -6.0]
    assert dates["characteristic"].to_list() == [6.8, 6.8]
    assert result.total == 0


def test_tied_quarters_do_not_guess_timing_axis():
    reference = timing(annual(range(1, 21)), [10] * 10 + [120] * 10)
    result = assess_daily(reference, annual([10] * 5, 2000))
    assert result.total is None
    assert result.scores["score"].null_count() == 2


def test_different_quarters_do_not_silently_mix_axes():
    reference = timing(annual(range(1, 21)), [10] * 20)
    result = assess_daily(reference, annual([10] * 5, 2000))
    assert result.total is None


def test_quarters_two_and_three_share_identity_axis():
    reference = timing(annual(range(1, 21)), [120] * 10 + [140] * 10)
    impact = timing(annual([10] * 5, 2000), [200] * 5)
    result = assess_daily(reference, impact)
    dates = result.scores.filter(pl.col("group") == 3)
    assert dates["score"].to_list() == [3.0, 3.0]
    assert result.total == pytest.approx(6 / 33)


def test_input_parameter_reasons_are_retained():
    impact = annual([10] * 5, 2000).with_columns(
        pl.when(pl.col("parameter") == "low_pulse_duration")
        .then(pl.lit("terminal_pulse_duration_truncated"))
        .otherwise(pl.col("reason"))
        .alias("reason")
    )
    result = assess_daily(annual(range(1, 21)), impact)
    reason = result.scores.filter(pl.col("parameter") == "low_pulse_duration")["reason"].item()
    assert reason is not None and "terminal_pulse_duration_truncated" in reason


def test_real_annual_indicators_to_daily_iari_path():
    from datetime import date, timedelta

    from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary, annual_indicators
    from fishy.quantities import Flow

    start, end = date(1980, 1, 1), date(2005, 1, 1)
    dates = [start + timedelta(days=i) for i in range((end - start).days)]
    # A stationary deterministic seasonal record. Fixed leap-calendar indexing
    # gives invariant extreme dates and no arbitrary ties across year lengths.
    values = [
        5 + 4 * math.cos(2 * math.pi * (date(2000, day.month, day.day).timetuple().tm_yday - 100) / 366)
        for day in dates
    ]
    daily = pl.DataFrame(
        {"date": dates, "discharge_m3_s": values}, schema={"date": pl.Date, "discharge_m3_s": pl.Float64}
    )
    indicators = annual_indicators(
        daily, IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(2), Flow(8)), RateBoundary.WITHIN_YEAR)
    )
    result = assess_daily(
        indicators.filter(pl.col("year") < 2000), indicators.filter(pl.col("year") >= 2000), SummaryStatistic.MEDIAN
    )
    assert result.total == 0
    assert result.classification is HydrologicalRegimeClass.ELEVATO


def test_monthly_result_preserves_spi_correction_and_selected_years():
    reference = monthly(range(1, 21))
    impacted = monthly([25], 2000)
    spi = BasinPrecipitationSPI12(-2)
    result = monthly_iari(
        reference, impacted, summary=SummaryStatistic.MEAN, quantile=QuantileEstimator.LINEAR, spi=spi
    )
    assert result.precipitation_spi is spi
    assert result.correction_factor == 0.5
    assert result.reference_years == tuple(range(1980, 2000))
    assert result.impacted_years == (2000,)
