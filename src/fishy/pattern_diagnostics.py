"""pattern_diagnostics : FlowSamples × DiagnosticDomain → DiagnosticValue (pure).

D.8 diagnostics describe one case, not scientific acceptance or a safeguard.
Daily means use whole UTC days. No operation wraps or fills unknown context.
"""

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from fractions import Fraction

from fishy.flows import FlowSample, daily_discharge
from fishy.pattern_calendar import half_volume_marker
from fishy.quantities import Flow, finite_number
from fishy.time import Interval


class DiagnosticUnit(StrEnum):
    PERCENT = "percent"
    DAYS = "days"
    DISCHARGE = "m3/s"


@dataclass(frozen=True)
class DiagnosticValue:
    """A diagnostic in declared units; undefined is not zero."""

    value: Fraction | None
    unit: DiagnosticUnit
    undefined_reason: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.unit, DiagnosticUnit):
            raise TypeError("diagnostic unit requires DiagnosticUnit")
        if self.value is not None:
            object.__setattr__(self, "value", finite_number(self.value))
            if self.undefined_reason is not None:
                raise ValueError("defined diagnostic cannot have an undefined reason")
        elif not isinstance(self.undefined_reason, str) or not self.undefined_reason.strip():
            raise ValueError("undefined diagnostic needs a reason")


@dataclass(frozen=True)
class DiagnosticDifference:
    """Candidate minus reference; percent inputs yield percentage-point errors.

    Relative error is a signed fraction of the reference, not a percentage.
    """

    signed: DiagnosticValue
    absolute: DiagnosticValue
    relative: Fraction | None
    relative_undefined_reason: str | None


def diagnostic_difference(candidate: DiagnosticValue, reference: DiagnosticValue) -> DiagnosticDifference:
    if candidate.unit is not reference.unit:
        raise ValueError("diagnostic difference requires matching units")
    if candidate.value is None or reference.value is None:
        reason = "; ".join(x for x in (candidate.undefined_reason, reference.undefined_reason) if x)
        missing = DiagnosticValue(None, candidate.unit, reason)
        return DiagnosticDifference(missing, missing, None, reason)
    signed = candidate.value - reference.value
    return DiagnosticDifference(
        DiagnosticValue(signed, candidate.unit),
        DiagnosticValue(abs(signed), candidate.unit),
        signed / reference.value if reference.value else None,
        None if reference.value else "zero reference denominator",
    )


def _daily_bounds(domain: Interval) -> None:
    if not isinstance(domain, Interval):
        raise TypeError("diagnostic domain requires Interval")
    for bound in (domain.start, domain.end):
        if (bound.hour, bound.minute, bound.second, bound.microsecond) != (0, 0, 0, 0):
            raise ValueError("diagnostic domain requires whole UTC days")


def _year_bounds(year: Interval) -> None:
    _daily_bounds(year)
    if year.start.day != 1 or year.end != year.start.replace(year=year.start.year + 1):
        raise ValueError("annual domain requires a complete accounting year starting on the first of a month")


def _contained(year: Interval, season: Interval) -> None:
    _daily_bounds(season)
    if season.start < year.start or season.end > year.end:
        raise ValueError("season must be contained in the nonwrapping accounting year")


def _complete_daily(samples: tuple[FlowSample, ...], domain: Interval) -> tuple[FlowSample, ...]:
    _daily_bounds(domain)
    # Reuse the physical boundary's identity, presence, coverage and resolution checks.
    daily_discharge(samples)
    ordered = tuple(sorted(samples, key=lambda sample: sample.interval.start))
    if ordered[0].interval.start != domain.start or ordered[-1].interval.end != domain.end:
        raise ValueError("samples must cover exactly the declared diagnostic domain and required context")
    if any(a.interval.end != b.interval.start for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError("diagnostic requires complete daily coverage; gaps cannot become zero")
    return ordered


def _values(samples: tuple[FlowSample, ...]) -> tuple[Fraction, ...]:
    return tuple(sample.value.value for sample in samples if sample.value is not None)


def seasonal_share(samples: tuple[FlowSample, ...], year: Interval, season: Interval) -> DiagnosticValue:
    """Seasonal volume / annual volume in percent, undefined for a zero-volume year."""
    _year_bounds(year)
    _contained(year, season)
    ordered = _complete_daily(samples, year)
    total = sum(_values(ordered), Fraction())
    if not total:
        return DiagnosticValue(None, DiagnosticUnit.PERCENT, "zero annual volume")
    seasonal = sum(
        (
            sample.value.value
            for sample in ordered
            if season.start <= sample.interval.start < season.end and sample.value is not None
        ),
        Fraction(),
    )
    return DiagnosticValue(100 * seasonal / total, DiagnosticUnit.PERCENT)


def half_volume_timing(samples: tuple[FlowSample, ...], year: Interval, season: Interval) -> DiagnosticValue:
    """First half-volume crossing, elapsed fractional days from accounting-year start.

    Daily interpolation is a timing convention, not inferred subdaily observations.
    At a plateau choose its first attaining boundary. Zero seasonal volume is undefined.
    """
    _year_bounds(year)
    _contained(year, season)
    ordered = _complete_daily(samples, year)
    start_day = (season.start - year.start).days
    end_day = (season.end - year.start).days
    marker = half_volume_marker(_values(ordered), start_day, end_day)
    if marker is None:
        return DiagnosticValue(None, DiagnosticUnit.DAYS, "zero seasonal volume")
    return DiagnosticValue(marker / 86400, DiagnosticUnit.DAYS)


class DurationDomain(StrEnum):
    ANNUAL = "annual_last_daily_interval"
    SEASONAL = "seasonal_whole_window"


@dataclass(frozen=True)
class DiagnosticDuration:
    days: int

    def __post_init__(self) -> None:
        if type(self.days) is not int or self.days < 1:
            raise ValueError("diagnostic duration requires a positive integer number of days")


@dataclass(frozen=True)
class DurationMinimum:
    value: DiagnosticValue
    window: Interval
    domain: Interval
    convention: DurationDomain


def duration_minimum(
    samples: tuple[FlowSample, ...], domain: Interval, duration: DiagnosticDuration, convention: DurationDomain
) -> DurationMinimum:
    """Minimum daily-window mean; equal minima retain the earliest window.

    Annual windows are assigned by their last day and require d-1 predecessor
    days. Seasonal windows must lie wholly inside the declared continuous season.
    No threshold, issuance gate or corrective schedule is computed.
    """
    if not isinstance(duration, DiagnosticDuration) or not isinstance(convention, DurationDomain):
        raise TypeError("duration minimum needs typed duration and domain convention")
    _daily_bounds(domain)
    days = duration.days
    if convention is DurationDomain.ANNUAL:
        _year_bounds(domain)
        required = Interval(domain.start - timedelta(days=days - 1), domain.end)
    else:
        required = domain
    ordered = _complete_daily(samples, required)
    values = _values(ordered)
    if len(values) < days:
        raise ValueError("duration exceeds season; no eligible windows")
    running = sum(values[:days], Fraction())
    best, index = running, 0
    for end in range(days, len(values)):
        running += values[end] - values[end - days]
        if running < best:
            best, index = running, end - days + 1
    return DurationMinimum(
        DiagnosticValue(best / days, DiagnosticUnit.DISCHARGE),
        Interval(ordered[index].interval.start, ordered[index + days - 1].interval.end),
        domain,
        convention,
    )


def longest_below_threshold(samples: tuple[FlowSample, ...], domain: Interval, threshold: Flow) -> DiagnosticValue:
    """Longest strictly-below run within domain; edge runs are clipped, never joined.

    This reports the run inside the declared interval, not its unknown outside
    continuation. To diagnose a longer period, supply that period and its data.
    """
    if not isinstance(threshold, Flow):
        raise TypeError("diagnostic threshold requires Flow")
    ordered = _complete_daily(samples, domain)
    longest = current = 0
    for value in _values(ordered):
        current = current + 1 if value < threshold.value else 0
        longest = max(longest, current)
    return DiagnosticValue(Fraction(longest), DiagnosticUnit.DAYS)
