"""Exact D6/D7/D9 calendar witnesses and complete-year boundary coverage."""

from datetime import UTC, date, datetime
from fractions import Fraction

import pytest

from fishy.pattern_calendar import (
    AccountingYear,
    half_volume_marker,
    map_calendar,
    normalize_shares,
    shift_year,
)


def _year(year: int) -> AccountingYear:
    return AccountingYear(year, 1, 0)


def _constant(year: AccountingYear, volume: int) -> tuple[Fraction, ...]:
    return (Fraction(volume),) * year.days


def test_accounting_year_fixed_offset_and_dates() -> None:
    year = AccountingYear(2023, 10, 330)
    assert year.days == 366
    assert year.interval.seconds == 366 * 86400
    assert year.interval.start == datetime(2023, 9, 30, 18, 30, tzinfo=UTC)
    assert year.dates[0] == date(2023, 10, 1)
    assert year.dates[-1] == date(2024, 9, 30)
    assert AccountingYear(2023, 1, -840).interval.seconds == 365 * 86400


@pytest.mark.parametrize("fields", [(2023, 0, 0), (2023, 13, 0), (2023, 1, 841), (2023, 1, -841), (9999, 1, 0)])
def test_invalid_calendars(fields: tuple[int, int, int]) -> None:
    with pytest.raises(ValueError):
        AccountingYear(*fields)


def test_calendar_rejects_boolean_fields() -> None:
    with pytest.raises(TypeError):
        AccountingYear(True, 1, 0)


def test_d6_february_first_day_splits_exactly() -> None:
    source, target = _year(2023), _year(2024)
    volumes = tuple(Fraction(day == 31) for day in range(source.days))
    mapped = map_calendar(source, volumes, target)
    assert mapped[31:33] == (Fraction(28, 29), Fraction(1, 29))
    assert sum(mapped, Fraction()) == 1
    assert sum(mapped[:31], Fraction()) == sum(mapped[60:], Fraction()) == 0


@pytest.mark.parametrize("source_year,target_year,start_month", [(2023, 2024, 1), (2024, 2023, 1), (2022, 2023, 10)])
def test_every_month_and_annual_total_conserved(source_year: int, target_year: int, start_month: int) -> None:
    source, target = AccountingYear(source_year, start_month, 0), AccountingYear(target_year, start_month, 0)
    volumes = tuple(Fraction(index % 13, 7) for index in range(source.days))
    mapped = map_calendar(source, volumes, target)
    for month in range(1, 13):
        expected = sum((v for d, v in zip(source.dates, volumes, strict=True) if d.month == month), Fraction())
        actual = sum((v for d, v in zip(target.dates, mapped, strict=True) if d.month == month), Fraction())
        assert actual == expected
    assert sum(mapped, Fraction()) == sum(volumes, Fraction())
    assert all(value >= 0 for value in mapped)


def test_mapping_rejects_incomplete_or_incompatible_calendar() -> None:
    with pytest.raises(ValueError, match="complete"):
        map_calendar(_year(2023), (Fraction(1),), _year(2024))
    with pytest.raises(ValueError, match="same month"):
        map_calendar(_year(2023), _constant(_year(2023), 1), AccountingYear(2024, 10, 0))


def test_d7_markers_and_median_shift() -> None:
    # Positive volume on days 99 and 100 has its half crossing at day 100.
    a = tuple(Fraction(day in (99, 100)) for day in range(365))
    b = tuple(Fraction(day in (103, 104)) for day in range(365))
    left = half_volume_marker(a, 90, 120)
    right = half_volume_marker(b, 90, 120)
    assert left == 100 * 86400
    assert right == 104 * 86400
    assert left is not None and right is not None
    median = (left + right) / 2
    assert median == 102 * 86400
    assert (median - left, median - right) == (2 * 86400, -2 * 86400)


def test_marker_first_plateau_boundary_fractional_day_and_absent_volume() -> None:
    assert half_volume_marker((Fraction(2), Fraction(0), Fraction(0), Fraction(2)), 0, 4) == 86400
    assert half_volume_marker((Fraction(0), Fraction(3), Fraction(1)), 0, 3) == Fraction(5, 3) * 86400
    assert half_volume_marker((Fraction(0), Fraction(0)), 0, 2) is None
    with pytest.raises(ValueError, match="must not cross"):
        half_volume_marker((Fraction(1), Fraction(1)), 1, 0)


@pytest.mark.parametrize("seconds,reason", [(1, "left"), (-1, "right")])
def test_d8_unknown_edges_never_wrap_or_zero_fill(seconds: int, reason: str) -> None:
    source = _year(2023)
    result = shift_year(source, _constant(source, 1), _year(2024), Fraction(seconds))
    assert result.shares is None
    assert result.reason is not None and reason in result.reason
    assert result.introduced is None and result.displaced is None


@pytest.mark.parametrize("direction", [-1, 1])
def test_fractional_overlap_and_original_source_scaling(direction: int) -> None:
    source = target = _year(2023)
    # Twice-as-large adjacent daily volumes must introduce 1/365, not
    # half of an independently normalised adjacent-year share.
    adjacent = _year(2023 - direction)
    kwargs = {"left_volumes" if direction == 1 else "right_volumes": _constant(adjacent, 2)}
    result = shift_year(source, _constant(source, 1), target, Fraction(direction * 43200), **kwargs)
    assert result.reason is None and result.shares is not None
    edge = 0 if direction == 1 else -1
    assert result.shares[edge] == Fraction(3, 2 * 365)
    assert result.introduced == Fraction(1, 365)
    assert result.displaced == Fraction(1, 2 * 365)
    assert sum(result.shares, Fraction()) == 1 + Fraction(1, 2 * 365)
    assert sum(normalize_shares(result.shares), Fraction()) == 1


def test_adjacent_year_is_calendar_mapped_before_translation() -> None:
    # The previous February differs in length. A 334-day delay exposes all
    # previous-year March..December plus most of its February.
    source, target = _year(2024), _year(2025)
    previous = _year(2023)
    prior = tuple(Fraction(day == 31) * 2 for day in range(previous.days))
    core = tuple(Fraction(day == 0) for day in range(source.days))
    result = shift_year(source, core, target, Fraction(334 * 86400), left_volumes=prior)
    assert result.reason is None and result.shares is not None
    # Prior target is leap 2024, origin -366: Feb 1 maps to output -1,
    # Feb 2 maps to output 0. Only 2/29 of original core total enters.
    assert result.shares[0] == Fraction(2, 29)
    assert result.introduced == Fraction(2, 29)
    assert result.displaced == 0


def test_zero_shift_needs_no_context() -> None:
    source = _year(2023)
    result = shift_year(source, _constant(source, 3), source, Fraction())
    assert result.shares == (Fraction(1, 365),) * 365
    assert result.introduced == result.displaced == 0


def test_zero_retained_total_is_unsupported() -> None:
    source = _year(2023)
    volumes = (Fraction(),) * 364 + (Fraction(1),)
    result = shift_year(source, volumes, source, Fraction(86400), left_volumes=_constant(_year(2022), 0))
    assert result.shares is None
    assert result.reason == "zero retained design-interval volume"


def test_shift_beyond_available_context_is_unsupported() -> None:
    source = _year(2023)
    result = shift_year(
        source, _constant(source, 1), source, Fraction(367 * 86400), left_volumes=_constant(_year(2022), 1)
    )
    assert result.reason == "shift requires context beyond the adjacent year"


def test_incomplete_adjacent_context_is_not_accepted() -> None:
    source = _year(2023)
    with pytest.raises(ValueError, match="complete"):
        shift_year(source, _constant(source, 1), source, Fraction(86400), left_volumes=(Fraction(1),))


def test_d9_individual_renormalisation_before_averaging() -> None:
    a = normalize_shares((Fraction(1, 2), Fraction(), Fraction(), Fraction()))
    b = normalize_shares((Fraction(1, 4),) * 4)
    assert tuple((x + y) / 2 for x, y in zip(a, b, strict=True)) == (
        Fraction(5, 8),
        Fraction(1, 8),
        Fraction(1, 8),
        Fraction(1, 8),
    )


def test_zero_and_negative_values_refused() -> None:
    with pytest.raises(ValueError, match="zero-volume"):
        normalize_shares((Fraction(), Fraction()))
    with pytest.raises(ValueError, match="nonnegative"):
        normalize_shares((Fraction(-1), Fraction(2)))
    source = _year(2023)
    assert shift_year(source, _constant(source, 0), source, Fraction()).reason == "zero source volume"
