"""annual_sanitary_profile : NaturalDailyRecord × SeasonalWindows → HypotheticalProfile.

Pure hypothetical annual selection, separate from issued duties and ecological entry.
Nomination and imports retain their own methods; no member comparison is performed.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum
from fractions import Fraction
from itertools import groupby

from fishy.evidence import Completeness, Computability, EvidenceFindings, NumericalValidity, Provenance, ReferenceKind
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.quantities import Flow
from fishy.spatial import Location
from fishy.time import Interval


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("identity and interpretation must be nonempty text")


@dataclass(frozen=True)
class SeasonWindow:
    """Inclusive month/day endpoints, with no cross-year wrapping."""

    start: tuple[int, int]
    end: tuple[int, int]

    def __post_init__(self) -> None:
        for endpoint in (self.start, self.end):
            if not isinstance(endpoint, tuple) or len(endpoint) != 2 or any(type(v) is not int for v in endpoint):
                raise TypeError("window endpoints require integer month/day tuples")
            date(2000, *endpoint)
        if self.start > self.end:
            raise ValueError("cross-year windows require another profile")

    def dates(self, year: int) -> tuple[date, date]:
        return date(year, *self.start), date(year, *self.end)


@dataclass(frozen=True)
class SeasonalWindows:
    summer: SeasonWindow
    winter: SeasonWindow

    def __post_init__(self) -> None:
        if not isinstance(self.summer, SeasonWindow) or not isinstance(self.winter, SeasonWindow):
            raise TypeError("two declared SeasonWindow records required")
        if max(self.summer.start, self.winter.start) <= min(self.summer.end, self.winter.end):
            raise ValueError("summer and winter windows overlap")


@dataclass(frozen=True)
class ProfileAttribution:
    identifier: str
    location: Location
    reference_period: Interval
    provenance: Provenance
    evidence: EvidenceFindings
    fixed_offset: timezone

    def __post_init__(self) -> None:
        _text(self.identifier)
        for value, kind in (
            (self.location, Location),
            (self.reference_period, Interval),
            (self.provenance, Provenance),
            (self.evidence, EvidenceFindings),
        ):
            if not isinstance(value, kind):
                raise TypeError("profile requires typed attribution and evidence")
        if not isinstance(self.fixed_offset, timezone):
            raise TypeError("calendar requires datetime.timezone, not a DST timezone")
        scope = self.evidence.scope
        if (scope.product, scope.reach, scope.member, scope.period) != (
            self.identifier,
            self.location.reach.identifier,
            self.provenance.reference_member,
            self.reference_period,
        ) or self.evidence.provenance != self.provenance:
            raise ValueError("profile evidence identity or period mismatch")


class ProfileMethod(StrEnum):
    ANNUAL_SELECTION = "hypothetical annual-mean nearest supported 95% analogue"
    NOMINATED_YEAR = "independently nominated hypothetical year"
    IMPORTED = "imported seasonal estimate"


@dataclass(frozen=True)
class AnnualRank:
    year: int
    mean: Flow
    rank: Fraction
    probability: Fraction


@dataclass(frozen=True)
class SeasonalMinimum:
    window: SeasonWindow
    value: Flow
    dates: tuple[date, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.window, SeasonWindow) or not isinstance(self.value, Flow):
            raise TypeError("seasonal estimate requires a window and Flow")
        if not isinstance(self.dates, tuple) or any(type(d) is not date for d in self.dates):
            raise TypeError("minimum dates require an immutable tuple of dates")
        if len(set(self.dates)) != len(self.dates):
            raise ValueError("duplicate minimum dates")
        if any(not self.window.start <= (d.month, d.day) <= self.window.end for d in self.dates):
            raise ValueError("minimum date outside its window")


@dataclass(frozen=True)
class HypotheticalProfile:
    attribution: ProfileAttribution
    method: ProfileMethod
    interpretation: str | None
    windows: SeasonalWindows | None
    presence: Presence
    reasons: tuple[str, ...]
    summer: SeasonalMinimum | None = None
    winter: SeasonalMinimum | None = None
    selected_year: int | None = None
    annual_ranks: tuple[AnnualRank, ...] = ()
    tied_candidates: tuple[AnnualRank, ...] = ()
    samples: tuple[FlowSample, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.attribution, ProfileAttribution) or not isinstance(self.method, ProfileMethod):
            raise TypeError("profile requires attribution and method")
        if self.interpretation is not None:
            _text(self.interpretation)
        if self.windows is not None and not isinstance(self.windows, SeasonalWindows):
            raise TypeError("windows require SeasonalWindows")
        if self.presence not in (Presence.PRESENT, Presence.MISSING, Presence.UNSUPPORTED):
            raise ValueError("invalid profile availability")
        if not isinstance(self.reasons, tuple) or any(not isinstance(r, str) or not r.strip() for r in self.reasons):
            raise ValueError("reasons must be immutable nonempty text")
        if self.presence is Presence.PRESENT:
            if self.windows is None or self.interpretation is None:
                raise ValueError("available profile requires interpretation and windows")
            for result, window in ((self.summer, self.windows.summer), (self.winter, self.windows.winter)):
                if not isinstance(result, SeasonalMinimum) or result.window != window:
                    raise ValueError("available profile requires both matching seasonal estimates")
                for day in result.dates:
                    start = datetime.combine(day, time(), self.attribution.fixed_offset)
                    if (
                        start < self.attribution.reference_period.start
                        or start + timedelta(days=1) > self.attribution.reference_period.end
                    ):
                        raise ValueError("minimum date outside reference period")
                    if self.selected_year is not None and day.year != self.selected_year:
                        raise ValueError("minimum date differs from selected year")
        elif self.summer is not None or self.winter is not None or not self.reasons:
            raise ValueError("unavailable profile retains reasons, not invented values")
        if self.method is not ProfileMethod.ANNUAL_SELECTION and (self.annual_ranks or self.tied_candidates):
            raise ValueError("nomination/import cannot claim empirical selection")

    @property
    def completeness(self) -> Completeness:
        """Member calculation coverage, not full-year operating-schedule coverage."""
        return Completeness.COMPLETE if self.presence is Presence.PRESENT else Completeness.INCOMPLETE

    @property
    def selected_rank(self) -> AnnualRank | None:
        return next((r for r in self.annual_ranks if r.year == self.selected_year), None)

    def value_on(self, day: date) -> Flow | None:
        """Recurring month/day candidate, not an issued schedule or year extension.

        The date selects a month/day only. The selected historical year remains
        the statistic's source, not a forecast for the requested date's year.
        No value is supplied outside the two declared windows.
        """
        for result in (self.summer, self.winter):
            if result is not None and result.window.start <= (day.month, day.day) <= result.window.end:
                return result.value
        return None


def _daily(samples: tuple[FlowSample, ...], attribution: ProfileAttribution) -> dict[date, Flow]:
    if (
        attribution.evidence.numerical_validity is NumericalValidity.INVALID
        or attribution.evidence.computability is Computability.NOT_COMPUTABLE
    ):
        raise ValueError("profile numerical evidence is invalid or not computable")
    if not isinstance(samples, tuple) or any(not isinstance(s, FlowSample) for s in samples):
        raise TypeError("daily evidence must be immutable FlowSample records")
    check_flow_intervals(samples)
    values = {}
    for sample in samples:
        if sample.location != attribution.location or any(
            getattr(sample.provenance, field) != getattr(attribution.provenance, field)
            for field in ("scenario", "reference_member", "reference_kind")
        ):
            raise ValueError("daily evidence location or reference identity mismatch")
        if (
            sample.interval.start < attribution.reference_period.start
            or sample.interval.end > attribution.reference_period.end
        ):
            raise ValueError("daily evidence outside reference period")
        if (
            sample.presence is not Presence.PRESENT
            or sample.coverage is not Coverage.COMPLETE
            or interval_use(sample) is not IntervalUse.ELIGIBLE
            or sample.value is None
        ):
            raise ValueError("daily evidence is unavailable, partial or excluded")
        local = sample.interval.start.astimezone(attribution.fixed_offset)
        if local.time() != time() or sample.interval.seconds != 86400:
            raise ValueError("daily means require complete fixed-offset calendar days")
        values[local.date()] = sample.value
    return values


def _minimum(values: dict[date, Flow], window: SeasonWindow, year: int) -> SeasonalMinimum:
    start, end = window.dates(year)
    days = tuple(start + timedelta(days=i) for i in range((end - start).days + 1))
    if any(d not in values for d in days):
        raise ValueError("missing day in declared season")
    value = min((values[d] for d in days), key=lambda f: f.value)
    return SeasonalMinimum(window, value, tuple(d for d in days if values[d] == value))


def annual_sanitary_profile(
    samples: tuple[FlowSample, ...], attribution: ProfileAttribution, windows: SeasonalWindows
) -> HypotheticalProfile:
    """Select by exact annual midrank; reject invalid years before checking support."""
    if not isinstance(windows, SeasonalWindows):
        raise TypeError("declare seasonal windows before annual selection")
    if attribution.provenance.reference_member is None or attribution.provenance.reference_kind not in (
        ReferenceKind.PRESENT_CLIMATE_NATURAL,
        ReferenceKind.NATURALISED_HISTORICAL,
        ReferenceKind.FUTURE_CLIMATE_STRESS,
    ):
        raise ValueError("annual selection requires an identified natural-flow reconstruction")
    values = _daily(samples, attribution)
    start = attribution.reference_period.start.astimezone(attribution.fixed_offset)
    end = attribution.reference_period.end.astimezone(attribution.fixed_offset)
    if (start.month, start.day, end.month, end.day) != (1, 1, 1, 1) or start.time() != time() or end.time() != time():
        raise ValueError("reference period must contain complete calendar years")
    if len(values) != (end.date() - start.date()).days:
        raise ValueError("missing day: complete calendar years required")
    means = []
    for year in range(start.year, end.year):
        windows.summer.dates(year)
        windows.winter.dates(year)
        annual = [v.value for d, v in values.items() if d.year == year]
        means.append((year, Flow(sum(annual, Fraction()) / len(annual))))
    ordered = sorted(means, key=lambda pair: pair[1].value, reverse=True)
    ranks = []
    occupied = 1
    for _, members in groupby(ordered, key=lambda pair: pair[1].value):
        group = tuple(members)
        rank = Fraction(2 * occupied + len(group) - 1, 2)
        ranks.extend(AnnualRank(y, mean, rank, rank / (len(means) + 1)) for y, mean in group)
        occupied += len(group)
    ranks = tuple(sorted(ranks, key=lambda r: r.year))
    target = Fraction(19, 20)
    interpretation = ProfileMethod.ANNUAL_SELECTION.value
    if not min(r.probability for r in ranks) <= target <= max(r.probability for r in ranks):
        return HypotheticalProfile(
            attribution,
            ProfileMethod.ANNUAL_SELECTION,
            interpretation,
            windows,
            Presence.UNSUPPORTED,
            ("target 0.95 outside actual unrounded plotting-position support",),
            annual_ranks=ranks,
            samples=samples,
        )
    distance = min(abs(r.probability - target) for r in ranks)
    tied = tuple(r for r in ranks if abs(r.probability - target) == distance)
    selected = min(tied, key=lambda r: (-r.probability, r.year))
    return HypotheticalProfile(
        attribution,
        ProfileMethod.ANNUAL_SELECTION,
        interpretation,
        windows,
        Presence.PRESENT,
        ("hypothetical nearest analogue, not a population quantile or issued duty",),
        _minimum(values, windows.summer, selected.year),
        _minimum(values, windows.winter, selected.year),
        selected.year,
        ranks,
        tied,
        samples,
    )


def nominated_sanitary_profile(
    samples: tuple[FlowSample, ...],
    attribution: ProfileAttribution,
    year: int,
    windows: SeasonalWindows | None,
    interpretation: str | None,
) -> HypotheticalProfile:
    """Calculate a separately nominated year's minima, requiring only its seasonal days."""
    if type(year) is not int or not 1 <= year <= 9999:
        raise ValueError("nomination requires a calendar year")
    if windows is None or interpretation is None:
        return HypotheticalProfile(
            attribution,
            ProfileMethod.NOMINATED_YEAR,
            interpretation,
            windows,
            Presence.MISSING,
            ("nomination interpretation or seasonal windows missing",),
            selected_year=year,
        )
    values = _daily(samples, attribution)
    if any(d.year != year for d in values):
        raise ValueError("nominated samples must belong to the nominated year")
    return HypotheticalProfile(
        attribution,
        ProfileMethod.NOMINATED_YEAR,
        interpretation,
        windows,
        Presence.PRESENT,
        ("independent hypothetical nomination; no empirical annual selection",),
        _minimum(values, windows.summer, year),
        _minimum(values, windows.winter, year),
        year,
        samples=samples,
    )


def imported_sanitary_profile(
    attribution: ProfileAttribution,
    method_description: str | None,
    windows: SeasonalWindows | None,
    summer: SeasonalMinimum | None,
    winter: SeasonalMinimum | None,
) -> HypotheticalProfile:
    """Retain imported method and evidence, with no annual-record-length gate."""
    if (
        attribution.evidence.numerical_validity is NumericalValidity.INVALID
        or attribution.evidence.computability is Computability.NOT_COMPUTABLE
    ):
        return HypotheticalProfile(
            attribution,
            ProfileMethod.IMPORTED,
            method_description,
            windows,
            Presence.UNSUPPORTED,
            ("import numerical evidence is invalid or not computable",),
        )
    if windows is None or method_description is None or summer is None or winter is None:
        return HypotheticalProfile(
            attribution,
            ProfileMethod.IMPORTED,
            method_description,
            windows,
            Presence.MISSING,
            ("import method, windows or seasonal estimates missing",),
        )
    return HypotheticalProfile(
        attribution,
        ProfileMethod.IMPORTED,
        method_description,
        windows,
        Presence.PRESENT,
        ("imported estimate; not a result of empirical annual selection",),
        summer,
        winter,
    )
