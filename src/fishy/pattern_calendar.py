"""calendar_alignment : AccountingYear × DailyVolumes × AccountingYear → DailyShares.

Exact conservative month mapping and non-wrapping translation for D.6.
Tuple carriers are internal numerical operators, not accepted reference products.
"""

from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction

from fishy.time import Interval


@dataclass(frozen=True)
class AccountingYear:
    """A Gregorian year starting on month day one, with fixed-offset days.

    ``year`` names the calendar year in which the accounting year starts.
    """

    year: int
    start_month: int
    utc_offset_minutes: int

    def __post_init__(self) -> None:
        for value in (self.year, self.start_month, self.utc_offset_minutes):
            if type(value) is not int:
                raise TypeError("accounting calendar fields must be integers")
        if not 1 <= self.year <= 9998:
            raise ValueError("accounting year must lie in 1..9998")
        if not 1 <= self.start_month <= 12:
            raise ValueError("start_month must lie in 1..12")
        if abs(self.utc_offset_minutes) > 14 * 60:
            raise ValueError("fixed UTC offset must not exceed 14 hours")
        # Also check that UTC-normalised endpoints are representable.
        try:
            _ = self.interval
        except OverflowError as error:
            raise ValueError("accounting interval exceeds datetime bounds") from error

    @property
    def interval(self) -> Interval:
        zone = timezone(timedelta(minutes=self.utc_offset_minutes))
        return Interval(
            datetime(self.year, self.start_month, 1, tzinfo=zone),
            datetime(self.year + 1, self.start_month, 1, tzinfo=zone),
        )

    @property
    def days(self) -> int:
        return (date(self.year + 1, self.start_month, 1) - date(self.year, self.start_month, 1)).days

    @property
    def dates(self) -> tuple[date, ...]:
        start = date(self.year, self.start_month, 1)
        return tuple(start + timedelta(days=day) for day in range(self.days))


def _check_values(values: tuple[Fraction, ...]) -> None:
    if not isinstance(values, tuple) or any(not isinstance(value, Fraction) for value in values):
        raise TypeError("daily values must be a tuple of exact Fractions")
    if not values or any(value < 0 for value in values):
        raise ValueError("daily values must be nonempty and nonnegative")


def normalize_shares(values: tuple[Fraction, ...]) -> tuple[Fraction, ...]:
    """Normalise one contribution before equal-year averaging; refuse zero totals."""
    _check_values(values)
    total = sum(values, Fraction())
    if total == 0:
        raise ValueError("zero-volume contribution cannot supply a positive-target shape")
    return tuple(value / total for value in values)


def _month_lengths(year: AccountingYear) -> tuple[int, ...]:
    return tuple(
        monthrange(year.year + (year.start_month - 1 + step) // 12, (year.start_month - 1 + step) % 12 + 1)[1]
        for step in range(12)
    )


def map_calendar(source: AccountingYear, volumes: tuple[Fraction, ...], target: AccountingYear) -> tuple[Fraction, ...]:
    """Distribute each source day by normalised-month overlap, without scaling.

    Values may be raw volumes or shares. Monthly and annual totals are preserved;
    the mapped values are a transformation, not newly observed daily detail.
    """
    _check_values(volumes)
    if len(volumes) != source.days:
        raise ValueError("daily values must cover the complete source accounting year")
    if source.start_month != target.start_month:
        raise ValueError("source and target accounting years must start in the same month")
    result: list[Fraction] = []
    offset = 0
    for source_days, target_days in zip(_month_lengths(source), _month_lengths(target), strict=True):
        mapped = [Fraction() for _ in range(target_days)]
        for day in range(source_days):
            start = Fraction(day * target_days, source_days)
            end = Fraction((day + 1) * target_days, source_days)
            for receiving_day in range(start.numerator // start.denominator, -(-end.numerator // end.denominator)):
                overlap = min(end, receiving_day + 1) - max(start, receiving_day)
                mapped[receiving_day] += volumes[offset + day] * overlap * Fraction(source_days, target_days)
        result.extend(mapped)
        offset += source_days
    return tuple(result)


def half_volume_marker(shares: tuple[Fraction, ...], start_day: int, end_day: int) -> Fraction | None:
    """First half-volume crossing in [start_day, end_day), in elapsed seconds.

    Linear within-day interpolation is a timing convention. An exact plateau
    uses its first attaining boundary. No seasonal volume means no marker.
    """
    _check_values(shares)
    if type(start_day) is not int or type(end_day) is not int:
        raise TypeError("season boundaries must be integer day offsets")
    if not 0 <= start_day < end_day <= len(shares):
        raise ValueError("season must be nonempty and must not cross the accounting boundary")
    half = sum(shares[start_day:end_day], Fraction()) / 2
    if half == 0:
        return None
    cumulative = Fraction()
    for day in range(start_day, end_day):
        value = shares[day]
        if cumulative + value >= half:
            return (Fraction(day) + (half - cumulative) / value) * 86400
        cumulative += value
    raise AssertionError("positive seasonal half-volume crossing must exist")


@dataclass(frozen=True)
class ShiftResult:
    """Aligned shares and edge accounts, all relative to original source total.

    Successful shares are not renormalised: the caller must normalise each
    retained contribution separately before equal-year averaging.
    """

    shares: tuple[Fraction, ...] | None
    introduced: Fraction | None
    displaced: Fraction | None
    reason: str | None

    def __post_init__(self) -> None:
        if self.reason is not None:
            if not self.reason or any(value is not None for value in (self.shares, self.introduced, self.displaced)):
                raise ValueError("unsupported shifts require a reason and no numerical result")
        elif self.shares is None or self.introduced is None or self.displaced is None:
            raise ValueError("supported shifts require shares and both edge accounts")
        else:
            _check_values(self.shares)
            if sum(self.shares, Fraction()) <= 0 or self.introduced < 0 or self.displaced < 0:
                raise ValueError("supported shift must retain positive volume and nonnegative edge accounts")


def _translated(values: tuple[Fraction, ...], origin: int, shift_days: Fraction, output: list[Fraction]) -> Fraction:
    retained = Fraction()
    for day, value in enumerate(values):
        start = max(Fraction(), Fraction(origin + day) + shift_days)
        end = min(Fraction(len(output)), Fraction(origin + day + 1) + shift_days)
        if end <= start:
            continue
        for receiving_day in range(start.numerator // start.denominator, -(-end.numerator // end.denominator)):
            volume = value * (min(end, receiving_day + 1) - max(start, receiving_day))
            output[receiving_day] += volume
            retained += volume
    return retained


def shift_year(
    source: AccountingYear,
    volumes: tuple[Fraction, ...],
    target: AccountingYear,
    shift_seconds: Fraction,
    *,
    left_volumes: tuple[Fraction, ...] | None = None,
    right_volumes: tuple[Fraction, ...] | None = None,
) -> ShiftResult:
    """Translate mapped volumes, requiring complete context on the exposed side.

    Positive shifts delay the pattern and require the previous source year.
    Adjacent volumes are mapped to adjacent target years and divided by the
    ORIGINAL source total, never independently normalised. Unknown edges are
    unsupported even if the known source edges have zero flow.
    """
    if not isinstance(shift_seconds, Fraction):
        raise TypeError("shift_seconds must be an exact Fraction")
    mapped = map_calendar(source, volumes, target)
    total = sum(volumes, Fraction())
    if total == 0:
        return ShiftResult(None, None, None, "zero source volume")
    shares = tuple(value / total for value in mapped)
    shift_days = shift_seconds / 86400
    context: tuple[Fraction, ...] = ()
    origin = 0
    if shift_days:
        direction = -1 if shift_days > 0 else 1
        adjacent_volumes = left_volumes if direction == -1 else right_volumes
        if adjacent_volumes is None:
            side = "left" if direction == -1 else "right"
            return ShiftResult(None, None, None, f"missing {side} adjacent-year context")
        if not (1 <= source.year + direction <= 9998 and 1 <= target.year + direction <= 9998):
            return ShiftResult(None, None, None, "adjacent calendar is outside supported datetime bounds")
        adjacent_source = AccountingYear(source.year + direction, source.start_month, source.utc_offset_minutes)
        adjacent_target = AccountingYear(target.year + direction, target.start_month, target.utc_offset_minutes)
        if abs(shift_days) > adjacent_target.days:
            return ShiftResult(None, None, None, "shift requires context beyond the adjacent year")
        context = tuple(value / total for value in map_calendar(adjacent_source, adjacent_volumes, adjacent_target))
        origin = -adjacent_target.days if direction == -1 else target.days
    output = [Fraction() for _ in range(target.days)]
    retained = _translated(shares, 0, shift_days, output)
    introduced = _translated(context, origin, shift_days, output)
    if sum(output, Fraction()) == 0:
        return ShiftResult(None, None, None, "zero retained design-interval volume")
    return ShiftResult(tuple(output), introduced, Fraction(1) - retained, None)
