"""Source-defined annual IHA witnesses and explicit boundary cases."""

from datetime import date, timedelta

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from fishy.diagnostics.iha import CentralStatistic, IHAProfile, PulseThresholds, RateBoundary, annual_indicators
from fishy.quantities import Flow


def daily(values, year=2001):
    return pl.DataFrame(
        {"date": [date(year, 1, 1) + timedelta(days=i) for i in range(len(values))], "discharge_m3_s": values},
        schema={"date": pl.Date, "discharge_m3_s": pl.Float64},
    )


def profile(stat=CentralStatistic.MEAN, low=10.0, high=300.0):
    return IHAProfile(stat, PulseThresholds(Flow(low), Flow(high)), RateBoundary.WITHIN_YEAR)


def value(result, parameter, year=2001):
    return result.filter((pl.col("parameter") == parameter) & (pl.col("year") == year))["value"].item()


def reason(result, parameter, year=2001):
    return result.filter((pl.col("parameter") == parameter) & (pl.col("year") == year))["reason"].item()


def test_all_33_independent_monotonic_witness():
    result = annual_indicators(daily(list(range(1, 366))), profile())
    expected = []
    start = 1
    for month, count in enumerate([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], 1):
        expected.append((2001, f"monthly_flow_{month:02d}", 1, start + (count - 1) / 2, None))
        start += count
    for window in (1, 3, 7, 30, 90):
        expected.extend(
            [
                (2001, f"minimum_{window}_day", 2, (window + 1) / 2, None),
                (2001, f"maximum_{window}_day", 2, 365 - (window - 1) / 2, None),
            ]
        )
    expected.extend(
        [
            (2001, "zero_flow_days", 2, 0.0, None),
            (2001, "base_flow_index", 2, 4 / 183, None),
            (2001, "minimum_flow_date", 3, 1.0, None),
            (2001, "maximum_flow_date", 3, 366.0, None),
            (2001, "low_pulse_count", 4, 0.0, "initial_pulse_omitted_unknown_start"),
            (2001, "low_pulse_duration", 4, None, "undefined_no_pulses;initial_pulse_omitted_unknown_start"),
            (2001, "high_pulse_count", 4, 1.0, "terminal_pulse_duration_truncated"),
            (2001, "high_pulse_duration", 4, 65.0, "terminal_pulse_duration_truncated"),
            (2001, "rise_rate", 5, 1.0, None),
            (2001, "fall_rate", 5, None, "undefined_no_falls"),
            (2001, "reversals", 5, 0.0, None),
        ]
    )
    assert_frame_equal(result, pl.DataFrame(expected, schema=result.schema, orient="row"))


def test_mean_median_and_rolling_always_mean():
    flows = [1.0] * 365
    flows[5] = 101.0
    mean = annual_indicators(daily(flows), profile())
    med = annual_indicators(daily(flows), profile(CentralStatistic.MEDIAN))
    assert value(mean, "monthly_flow_01") == pytest.approx(131 / 31)
    assert value(med, "monthly_flow_01") == 1
    assert value(med, "maximum_3_day") == pytest.approx(103 / 3)
    assert value(mean, "maximum_3_day") == value(med, "maximum_3_day")


def test_leap_day_and_earliest_extreme_ties():
    flows = [1.0] * 366
    flows[59] = flows[60] = 5.0
    result = annual_indicators(daily(flows, 2000), profile())
    assert value(result, "maximum_flow_date", 2000) == 60
    assert value(result, "monthly_flow_02", 2000) == pytest.approx(33 / 29)
    nonleap = [1.0] * 365
    nonleap[59] = 5
    assert value(annual_indicators(daily(nonleap), profile()), "maximum_flow_date") == 61


def test_no_rolling_wrap_or_cross_year():
    flows = [1.0] * 730
    flows[364:367] = [101.0] * 3
    result = annual_indicators(daily(flows), profile())
    assert value(result, "maximum_3_day", 2001) == pytest.approx(103 / 3)
    assert value(result, "maximum_3_day", 2002) == pytest.approx(203 / 3)


def test_cross_year_pulses_strict_threshold_and_truncation():
    flows = [5.0] * 730
    flows[:2] = [0.0] * 2
    flows[363:368] = [11.0] * 5
    flows[20:22] = [10.0, 0.0]
    flows[-2:] = [0.0] * 2
    result = annual_indicators(daily(flows), profile(low=1, high=10))
    assert value(result, "high_pulse_count", 2001) == 1
    assert value(result, "high_pulse_duration", 2001) == 5
    assert value(result, "high_pulse_count", 2002) == 0
    assert value(result, "low_pulse_count", 2001) == 1
    assert value(result, "low_pulse_duration", 2001) == 1
    assert reason(result, "low_pulse_count", 2001) == "initial_pulse_omitted_unknown_start"
    assert value(result, "low_pulse_duration", 2002) == 2
    assert reason(result, "low_pulse_duration", 2002) == "terminal_pulse_duration_truncated"


def test_duration_and_rate_mean_median_plateaus_reversals():
    flows = [5.0] * 365
    flows[:8] = [5, 6, 6, 9, 7, 7, 6, 5]
    flows[20:21] = [11.0]
    flows[30:32] = [11.0] * 2
    flows[40:48] = [11.0] * 8
    mean = annual_indicators(daily(flows), profile(low=1, high=10))
    med = annual_indicators(daily(flows), profile(CentralStatistic.MEDIAN, low=1, high=10))
    assert value(mean, "high_pulse_duration") == pytest.approx(11 / 3)
    assert value(med, "high_pulse_duration") == 2
    assert value(mean, "rise_rate") == pytest.approx(22 / 5)
    assert value(mean, "fall_rate") == pytest.approx(-22 / 6)
    assert value(med, "rise_rate") == 6
    assert value(med, "fall_rate") == -4
    assert value(mean, "reversals") == 7


def test_reversal_and_rate_year_reset():
    flows = [1.0] * 365 + [9.0] * 365
    flows[363:365] = [2, 3]
    flows[365:368] = [9, 8, 7]
    result = annual_indicators(daily(flows), profile())
    assert value(result, "rise_rate", 2001) == 1
    assert value(result, "fall_rate", 2002) == -1
    assert value(result, "reversals", 2001) == 0
    assert value(result, "reversals", 2002) == 1


def test_zero_series_retains_undefined_values():
    result = annual_indicators(daily([0.0] * 365), profile())
    assert value(result, "zero_flow_days") == 365
    assert value(result, "base_flow_index") is None
    assert reason(result, "base_flow_index") == "undefined_zero_annual_mean"
    assert value(result, "rise_rate") is None
    assert value(result, "fall_rate") is None
    assert value(result, "reversals") == 0
    assert value(result, "minimum_flow_date") == 1
    assert value(result, "high_pulse_duration") is None


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1.0, None])
def test_invalid_discharge_rejected(bad):
    flows = [1.0] * 365
    flows[10] = bad
    with pytest.raises(ValueError):
        annual_indicators(daily(flows), profile())


@pytest.mark.parametrize("kind", ["missing", "duplicate", "unsorted", "partial", "empty", "dtype"])
def test_invalid_dates_or_schema_rejected(kind):
    frame = daily([1.0] * 365)
    if kind == "missing":
        frame = frame.filter(pl.col("date") != date(2001, 5, 2))
    elif kind == "duplicate":
        frame = pl.concat([frame, frame.tail(1)])
    elif kind == "unsorted":
        frame = frame.reverse()
    elif kind == "partial":
        frame = frame.head(364)
    elif kind == "empty":
        frame = frame.head(0)
    else:
        frame = frame.with_columns(pl.col("discharge_m3_s").cast(pl.Int64))
    with pytest.raises(ValueError):
        annual_indicators(frame, profile())


@pytest.mark.parametrize("low,high", [(-1, 2), (3, 2), (0, float("inf")), (float("nan"), 2)])
def test_invalid_thresholds(low, high):
    with pytest.raises(ValueError):
        PulseThresholds(Flow(low), Flow(high))


def test_profile_requires_explicit_types():
    with pytest.raises(TypeError):
        IHAProfile("mean", PulseThresholds(Flow(1), Flow(2)), RateBoundary.WITHIN_YEAR)  # ty: ignore[invalid-argument-type]
    with pytest.raises(ValueError):
        IHAProfile(CentralStatistic.MEAN, PulseThresholds(Flow(1), Flow(2)), "within_year")  # ty: ignore[invalid-argument-type]


def test_collapsed_thresholds_constant_series():
    thresholds = PulseThresholds(Flow(0), Flow(0))
    result = annual_indicators(
        daily([0.0] * 365), IHAProfile(CentralStatistic.MEAN, thresholds, RateBoundary.WITHIN_YEAR)
    )
    assert value(result, "low_pulse_count") == 0
    assert value(result, "high_pulse_count") == 0
    assert reason(result, "low_pulse_count") is None


@pytest.mark.parametrize("low,high", [(False, 2.0), (0.0, True)])
def test_boolean_thresholds_rejected(low, high):
    with pytest.raises(TypeError):
        PulseThresholds(Flow(low), Flow(high))


def test_wrong_profile_rejected_explicitly():
    with pytest.raises(TypeError, match="IHAProfile"):
        annual_indicators(daily([1.0] * 365), None)  # ty: ignore[invalid-argument-type]


def test_threshold_flow_units_are_normalized():
    thresholds = PulseThresholds(Flow(1000, "l/s"), Flow(2000, "l/s"))
    assert thresholds == PulseThresholds(Flow(1), Flow(2))
    result = annual_indicators(
        daily([1.5] * 365), IHAProfile(CentralStatistic.MEAN, thresholds, RateBoundary.WITHIN_YEAR)
    )
    assert value(result, "low_pulse_count") == 0
    assert value(result, "high_pulse_count") == 0


def test_raw_thresholds_are_rejected():
    with pytest.raises(TypeError, match="Flow"):
        PulseThresholds(1.0, 2.0)  # ty: ignore[invalid-argument-type]
