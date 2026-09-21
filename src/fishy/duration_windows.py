"""duration_windows : FlowSamples × AssessmentPeriod × DurationWindowRule → DurationWindows (pure).

Whole supported intervals conserve volume. No subinterval constancy, physical
wrapping, boundary repetition or missing-as-zero is inferred.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import Provenance
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.quantities import Flow, FlowBounds, Volume
from fishy.spatial import Location
from fishy.time import Interval


class WindowDomain(StrEnum):
    ANNUAL = "annual"
    SEASONAL = "continuous_season"


@dataclass(frozen=True)
class ContinuousSeason:
    name: str
    start_month: int
    start_day: int
    end_month: int
    end_day: int

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("named continuous season required")
        for month, day in ((self.start_month, self.start_day), (self.end_month, self.end_day)):
            if type(month) is not int or type(day) is not int:
                raise TypeError("season boundaries require integer month/day")
            datetime(2001, month, day)  # Fixed recurring boundaries must exist every year.
        if (self.start_month, self.start_day) == (self.end_month, self.end_day):
            raise ValueError("season must be shorter than one year; end is exclusive")


@dataclass(frozen=True)
class DurationWindowRule:
    duration_days: int
    domain: WindowDomain
    accounting_start_month: int
    utc_offset_minutes: int
    season: ContinuousSeason | None
    basis: str

    def __post_init__(self) -> None:
        if type(self.duration_days) is not int or self.duration_days <= 0:
            raise ValueError("duration must be a positive integer day count")
        if not isinstance(self.domain, WindowDomain):
            raise TypeError("typed window domain required")
        if type(self.accounting_start_month) is not int or not 1 <= self.accounting_start_month <= 12:
            raise ValueError("accounting start month must be in 1..12")
        if type(self.utc_offset_minutes) is not int or not -1440 < self.utc_offset_minutes < 1440:
            raise ValueError("fixed UTC offset must be integer minutes within one day")
        if (self.domain is WindowDomain.SEASONAL) != isinstance(self.season, ContinuousSeason):
            raise ValueError("seasonal domain requires a season; annual domain forbids one")
        if not isinstance(self.basis, str) or not self.basis.strip():
            raise ValueError("duration/domain justification or hypothetical basis required")

    @property
    def timezone(self) -> timezone:
        return timezone(timedelta(minutes=self.utc_offset_minutes))

    def block(self, day: datetime) -> Interval | None:
        """Annual block containing last daily interval; season labelled by ending year."""
        local = day.astimezone(self.timezone)
        if self.domain is WindowDomain.ANNUAL:
            year = local.year - (local.month < self.accounting_start_month)
            return Interval(
                datetime(year, self.accounting_start_month, 1, tzinfo=self.timezone),
                datetime(year + 1, self.accounting_start_month, 1, tzinfo=self.timezone),
            )
        assert self.season is not None
        s = self.season
        for year in (local.year - 1, local.year):
            start = datetime(year, s.start_month, s.start_day, tzinfo=self.timezone)
            end_year = year + ((s.end_month, s.end_day) < (s.start_month, s.start_day))
            end = datetime(end_year, s.end_month, s.end_day, tzinfo=self.timezone)
            if start <= local < end:
                return Interval(start, end)
        return None

    def label(self, block: Interval) -> int:
        return (block.end - timedelta(days=1)).astimezone(self.timezone).year


@dataclass(frozen=True)
class WindowUncertaintySupport:
    """Supplied joint enclosing support, not independent marginal confidence limits."""

    meaning: str
    source: str
    dependence: str

    def __post_init__(self) -> None:
        if any(not isinstance(s, str) or not s.strip() for s in (self.meaning, self.source, self.dependence)):
            raise ValueError("joint bound propagation needs meaning, source and dependence")


@dataclass(frozen=True)
class DurationWindow:
    interval: Interval
    block: Interval
    block_year: int
    mean: Flow | None
    volume: Volume | None
    uncertainty: FlowBounds | None
    contributors: tuple[FlowSample, ...]
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class DurationWindows:
    rule: DurationWindowRule
    period: Interval
    location: Location
    provenance: Provenance
    predecessor_basis: str | None
    uncertainty_support: WindowUncertaintySupport | None
    windows: tuple[DurationWindow, ...]

    @property
    def coverage(self) -> Coverage:
        return Coverage.COMPLETE if self.windows and all(w.mean is not None for w in self.windows) else Coverage.PARTIAL

    @property
    def minimum(self) -> Flow | None:
        values = tuple(w.mean for w in self.windows if w.mean is not None)
        return min(values, key=lambda q: q.value) if values else None

    @property
    def minimum_windows(self) -> tuple[Interval, ...]:
        minimum = self.minimum
        return tuple(w.interval for w in self.windows if minimum is not None and w.mean == minimum)


def check_fixed_days(period: Interval, rule: DurationWindowRule) -> None:
    for boundary in (period.start, period.end):
        local = boundary.astimezone(rule.timezone)
        if (local.hour, local.minute, local.second, local.microsecond) != (0, 0, 0, 0):
            raise ValueError("period boundaries must be fixed-offset midnight; convert civil days explicitly")
    if period.seconds % 86400:
        raise ValueError("period must contain whole fixed 86400-second days")


def duration_windows(
    samples: tuple[FlowSample, ...],
    period: Interval,
    rule: DurationWindowRule,
    *,
    location: Location,
    provenance: Provenance,
    predecessor_basis: str | None,
    uncertainty_support: WindowUncertaintySupport | None = None,
) -> DurationWindows:
    """Evaluate every eligible daily-ending window, preserving uncovered windows."""
    if not isinstance(samples, tuple) or any(not isinstance(s, FlowSample) for s in samples):
        raise TypeError("immutable FlowSample tuple required")
    if not isinstance(rule, DurationWindowRule) or not isinstance(period, Interval):
        raise TypeError("typed period and window rule required")
    if not isinstance(location, Location) or not isinstance(provenance, Provenance):
        raise TypeError("typed location and provenance required even for empty input")
    if predecessor_basis is not None and (not isinstance(predecessor_basis, str) or not predecessor_basis.strip()):
        raise ValueError("nonempty predecessor justification required")
    if uncertainty_support is not None and not isinstance(uncertainty_support, WindowUncertaintySupport):
        raise TypeError("typed uncertainty propagation support required")
    check_fixed_days(period, rule)
    if samples:
        check_flow_intervals(samples)
    for sample in samples:
        if sample.location != location or any(
            getattr(sample.provenance, f) != getattr(provenance, f)
            for f in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("window location/member/scenario identity differs")
    ordered = sorted(samples, key=lambda s: s.interval.start)
    windows = []
    day = period.start
    while day < period.end:
        end = day + timedelta(days=1)
        start = end - timedelta(days=rule.duration_days)
        block = rule.block(day)
        if block is None or (rule.domain is WindowDomain.SEASONAL and start < block.start):
            day = end
            continue
        interval = Interval(start, end)
        parts = tuple(s for s in ordered if s.interval.start < end and start < s.interval.end)
        reasons = []
        if start < period.start and predecessor_basis is None:
            reasons.append("predecessor context has no supplied justification")
        if not parts or parts[0].interval.start != start or parts[-1].interval.end != end:
            reasons.append("missing boundary evidence or unsupported fraction of a coarse interval")
        if any(a.interval.end != b.interval.start for a, b in zip(parts, parts[1:], strict=False)):
            reasons.append("uncovered gap")
        if any(
            s.presence is not Presence.PRESENT
            or s.coverage is not Coverage.COMPLETE
            or interval_use(s) is not IntervalUse.ELIGIBLE
            for s in parts
        ):
            reasons.append("missing, partial, excluded or unsupported flow")
        mean = volume = bounds = None
        if not reasons:
            total = sum((s.value.value * s.interval.seconds for s in parts if s.value is not None), Fraction())
            volume = Volume(total)
            mean = Flow(total / interval.seconds)
            if uncertainty_support is not None and all(s.uncertainty is not None for s in parts):
                lower = sum(
                    (s.uncertainty.lower.value * s.interval.seconds for s in parts if s.uncertainty is not None),
                    Fraction(),
                )
                upper = sum(
                    (s.uncertainty.upper.value * s.interval.seconds for s in parts if s.uncertainty is not None),
                    Fraction(),
                )
                bounds = FlowBounds(
                    Flow(lower / interval.seconds),
                    Flow(upper / interval.seconds),
                    uncertainty_support.meaning,
                    uncertainty_support.source,
                    uncertainty_support.dependence,
                )
        windows.append(DurationWindow(interval, block, rule.label(block), mean, volume, bounds, parts, tuple(reasons)))
        day = end
    return DurationWindows(rule, period, location, provenance, predecessor_basis, uncertainty_support, tuple(windows))
