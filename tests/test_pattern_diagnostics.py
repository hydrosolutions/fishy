"""D.8 daily diagnostics: real calendar boundaries and exact per-case differences."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import CorrectionState, ProductionMethod, Provenance
from fishy.flows import Coverage, FlowSample, Presence
from fishy.pattern_diagnostics import (
    DiagnosticDuration,
    DiagnosticUnit,
    DiagnosticValue,
    DurationDomain,
    diagnostic_difference,
    duration_minimum,
    half_volume_timing,
    longest_below_threshold,
    seasonal_share,
)
from fishy.quantities import Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval

YEAR = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
LOCATION = Location(Reach("river", "1", WaterBody("body", "1")), CalculationSection("point", "1"), "1")
PROVENANCE = Provenance(
    "synthetic daily observations",
    "validation",
    "reference",
    "1",
    "1",
    "1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
)


def samples(values: list[int], start: datetime = YEAR.start) -> tuple[FlowSample, ...]:
    return tuple(
        FlowSample(
            LOCATION,
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            Flow(value),
            Presence.PRESENT,
            PROVENANCE,
        )
        for i, value in enumerate(values)
    )


def test_seasonal_share_actual_leap_year_and_percentage_point_errors():
    season = Interval(datetime(2024, 2, 1, tzinfo=UTC), datetime(2024, 3, 1, tzinfo=UTC))
    result = seasonal_share(samples([8] * 366), YEAR, season)
    assert result.value == Fraction(2900, 366)
    error = diagnostic_difference(result, DiagnosticValue(Fraction(5), DiagnosticUnit.PERCENT))
    assert error.signed.value == Fraction(1070, 366)
    assert error.absolute.value == error.signed.value
    assert error.relative == Fraction(214, 366)


def test_zero_volume_undefined_share_and_marker():
    zero = samples([0] * 366)
    assert seasonal_share(zero, YEAR, YEAR).undefined_reason == "zero annual volume"
    assert half_volume_timing(zero, YEAR, YEAR).value is None


def test_first_half_volume_plateau_fractional_day_and_nonwrap():
    season = Interval(YEAR.start + timedelta(days=30), YEAR.start + timedelta(days=34))
    plateau = samples([0] * 30 + [2, 0, 0, 2] + [0] * 332)
    assert half_volume_timing(plateau, YEAR, season).value == 31
    fractional = samples([0] * 30 + [1, 3, 0, 0] + [0] * 332)
    assert half_volume_timing(fractional, YEAR, season).value == Fraction(94, 3)
    crossing = Interval(YEAR.end - timedelta(days=2), YEAR.end + timedelta(days=2))
    with pytest.raises(ValueError, match="nonwrapping"):
        half_volume_timing(plateau, YEAR, crossing)


def test_strict_below_spells_do_not_join_year_edges():
    first = samples([0, 2, 0, 2] + [2] * 360 + [0, 0])
    second = samples([0, 0, 2, 2] + [2] * 360 + [0, 0])
    assert longest_below_threshold(first, YEAR, Flow(1)).value == 2
    assert longest_below_threshold(second, YEAR, Flow(1)).value == 2
    assert longest_below_threshold(second, YEAR, Flow(2)).value == 2
    assert longest_below_threshold(second, YEAR, Flow(0)).value == 0
    season = Interval(YEAR.start, YEAR.start + timedelta(days=4))
    assert longest_below_threshold(first[:4], season, Flow(1)).value == 1
    assert longest_below_threshold(second[:4], season, Flow(1)).value == 2


def test_seasonal_minimum_and_signed_error_preserve_overestimation():
    candidate = samples([8] * 366)
    reference = samples([4] * 7 + [8] * 359)
    duration = DiagnosticDuration(7)
    c = duration_minimum(candidate, YEAR, duration, DurationDomain.SEASONAL)
    r = duration_minimum(reference, YEAR, duration, DurationDomain.SEASONAL)
    assert c.value.value == 8
    assert r.value.value == 4
    assert r.window == Interval(YEAR.start, YEAR.start + timedelta(days=7))
    error = diagnostic_difference(c.value, r.value)
    assert error.signed.value == 4
    assert error.absolute.value == 4
    assert error.relative == 1
    negative = diagnostic_difference(r.value, c.value)
    assert negative.signed.value == -4
    assert negative.absolute.value == 4
    assert negative.relative == Fraction(-1, 2)


def test_annual_minimum_requires_real_predecessor_and_differs_from_seasonal():
    duration = DiagnosticDuration(3)
    actual = samples([0, 0] + [6] * 366, YEAR.start - timedelta(days=2))
    result = duration_minimum(actual, YEAR, duration, DurationDomain.ANNUAL)
    assert result.value.value == 2
    assert result.window == Interval(YEAR.start - timedelta(days=2), YEAR.start + timedelta(days=1))
    with pytest.raises(ValueError, match="context"):
        duration_minimum(actual[2:], YEAR, duration, DurationDomain.ANNUAL)
    assert duration_minimum(actual[2:], YEAR, duration, DurationDomain.SEASONAL).value.value == 6


def test_zero_reference_retains_absolute_errors_and_undefined_relative():
    result = diagnostic_difference(
        DiagnosticValue(Fraction(3), DiagnosticUnit.DISCHARGE), DiagnosticValue(Fraction(0), DiagnosticUnit.DISCHARGE)
    )
    assert result.signed.value == result.absolute.value == 3
    assert result.relative is None
    assert result.relative_undefined_reason == "zero reference denominator"
    undefined = diagnostic_difference(
        DiagnosticValue(None, DiagnosticUnit.DAYS, "zero seasonal volume"),
        DiagnosticValue(Fraction(2), DiagnosticUnit.DAYS),
    )
    assert undefined.absolute.value is None
    with pytest.raises(ValueError, match="matching units"):
        diagnostic_difference(
            DiagnosticValue(Fraction(1), DiagnosticUnit.DAYS), DiagnosticValue(Fraction(1), DiagnosticUnit.PERCENT)
        )


@pytest.mark.parametrize("fault", ["gap", "missing", "partial", "member", "duplicate", "coarse", "warmup"])
def test_public_daily_boundary_refuses_invalid_support(fault):
    data = list(samples([1] * 366))
    if fault == "gap":
        del data[100]
    elif fault == "missing":
        data[100] = replace(data[100], value=None, presence=Presence.MISSING, reasons=("unmeasured",))
    elif fault == "partial":
        data[100] = replace(data[100], coverage=Coverage.PARTIAL, reasons=("partial observation",))
    elif fault == "member":
        data[100] = replace(data[100], provenance=replace(PROVENANCE, reference_member="other"))
    elif fault == "duplicate":
        data.append(data[0])
    elif fault == "coarse":
        data[0] = replace(data[0], interval=Interval(data[0].interval.start, data[1].interval.end))
        del data[1]
    elif fault == "warmup":
        data[0] = replace(data[0], provenance=replace(PROVENANCE, excluded_warmup=(data[0].interval,)))
    with pytest.raises(ValueError):
        seasonal_share(tuple(data), YEAR, YEAR)
    with pytest.raises(ValueError):
        half_volume_timing(tuple(data), YEAR, YEAR)
    with pytest.raises(ValueError):
        longest_below_threshold(tuple(data), YEAR, Flow(2))
    with pytest.raises(ValueError):
        duration_minimum(tuple(data), YEAR, DiagnosticDuration(7), DurationDomain.SEASONAL)


def test_row_order_independent_and_incomplete_year_refused():
    data = samples([1] * 366)
    assert seasonal_share(tuple(reversed(data)), YEAR, YEAR).value == 100
    with pytest.raises(ValueError, match="complete accounting year"):
        seasonal_share(data[:4], Interval(YEAR.start, YEAR.start + timedelta(days=4)), data[0].interval)
    with pytest.raises(ValueError, match="no eligible windows"):
        duration_minimum(
            data[:4],
            Interval(YEAR.start, YEAR.start + timedelta(days=4)),
            DiagnosticDuration(7),
            DurationDomain.SEASONAL,
        )


@pytest.mark.parametrize("days", [0, -1, 1.5, True])
def test_invalid_duration_refused(days):
    with pytest.raises(ValueError):
        DiagnosticDuration(days)
