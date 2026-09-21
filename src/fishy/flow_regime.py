"""flow_regime : AttributedRegimeStatistics × AssessmentContext → IndicatorResult (pure).

BAFU HYDMOD-F (2011), §§3.4–3.6, 5.2, 5.4–5.7. Swiss regime
estimates require an explicitly supplied regime attribution, never a country guess.
Quantiles use declared linear order-statistic interpolation; CV uses sample SD.
Circular dates follow the printed JD/365 equation, including Gregorian leap days.
"""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from fractions import Fraction
from math import cos, hypot, isfinite, pi, sin, sqrt

from fishy.evidence import Completeness
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.hydrological_condition import (
    AssessmentContext,
    AssessmentState,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    Metric,
)
from fishy.quantities import Area, Flow, finite_number

SOURCE = "BAFU 2011 HYDMOD-F"

# Columns are the original Swiss regime types 1–16. Decimal transcription is exact.
R_QUANTILES = tuple(
    zip(
        map(
            Fraction,
            [
                "18",
                "16.3",
                "17.5",
                "21.1",
                "19.3",
                "25.9",
                "31.5",
                "39.5",
                "40.4",
                "42.8",
                "44.9",
                "49.1",
                "27.7",
                "44.5",
                "52.8",
                "39.8",
            ],
        ),
        map(
            Fraction,
            [
                "19.8",
                "18.3",
                "20.2",
                "23.9",
                "21.6",
                "28.8",
                "35.1",
                "43.4",
                "44.8",
                "47.7",
                "48.2",
                "54.2",
                "32.2",
                "49.8",
                "62.0",
                "45.6",
            ],
        ),
        map(
            Fraction,
            [
                "21.9",
                "20.6",
                "23.8",
                "27.7",
                "24.7",
                "32.7",
                "39.8",
                "48.7",
                "49.9",
                "53.5",
                "52.3",
                "60.8",
                "38.4",
                "56.8",
                "75.1",
                "53.5",
            ],
        ),
        strict=True,
    )
)
SPECIFIC_MEAN = tuple(
    map(Fraction, ["51", "61", "54", "48", "43", "42", "49", "36", "27", "16", "21", "16", "52", "51", "35", "31"])
)
SPECIFIC_LOW = tuple(
    map(
        Fraction,
        ["3.2", "5.1", "6.5", "6.4", "7", "7.5", "6.8", "4.8", "4.1", "4.4", "4.4", "2.7", "8.4", "5.5", "5.2", "9.2"],
    )
)
REGIME_CV = tuple(
    map(Fraction, ["22", "19", "19", "13", "18", "22", "30", "35", "38", "30", "37", "38", "19", "38", "34", "21"])
)
PARDE_COEFFICIENTS = tuple(
    tuple(map(Fraction, row.split()))
    for row in (
        "0.07 0.13 0.18 0.24 0.21 0.33 0.44 0.59 0.96 1.14 1.07 1.39 0.29 0.33 0.52 0.91",
        "0.06 0.12 0.17 0.2 0.2 0.34 0.52 0.71 1.11 1.33 1.21 1.52 0.25 0.31 0.46 0.9",
        "0.07 0.17 0.21 0.2 0.26 0.49 0.81 1.06 1.27 1.3 1.45 1.54 0.29 0.56 0.72 0.99",
        "0.17 0.37 0.46 0.4 0.62 0.99 1.44 1.65 1.25 1.16 1.61 1.28 0.59 1.26 1.48 1.14",
        "0.76 1.08 1.35 1.41 1.69 2.16 1.9 1.59 1.03 1.05 1.07 0.95 1.79 2.18 1.8 1.33",
        "2 2.19 2.44 2.68 2.64 2.29 1.73 1.34 1.12 1.02 0.85 0.84 2.49 1.73 1.42 1.09",
        "3.21 2.86 2.58 2.34 2.15 1.61 1.34 1.12 0.94 0.77 0.64 0.55 1.79 0.99 0.86 0.81",
        "3.09 2.52 2.04 1.58 1.6 1.15 1.08 0.97 0.79 0.67 0.51 0.35 1.22 0.73 0.55 0.74",
        "1.61 1.46 1.25 1.2 1.1 0.89 0.85 0.79 0.84 0.69 0.64 0.48 1.13 1.18 1 0.92",
        "0.57 0.57 0.67 0.85 0.71 0.7 0.66 0.7 0.7 0.75 0.77 0.75 1.04 1.36 1.45 1.21",
        "0.19 0.29 0.37 0.51 0.48 0.58 0.66 0.8 0.89 0.96 1.02 0.97 0.7 0.91 1.13 1.15",
        "0.11 0.19 0.23 0.33 0.29 0.43 0.56 0.66 1.11 1.17 1.19 1.42 0.39 0.44 0.59 0.82",
    )
)


def _source(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("source attribution is required")


@dataclass(frozen=True)
class RegimeReference:
    swiss_type: int
    source: str

    def __post_init__(self) -> None:
        if type(self.swiss_type) is not int or not 1 <= self.swiss_type <= 16:
            raise ValueError("Swiss regime type must be 1–16")
        _source(self.source)


def _area_km2(area: Area) -> Fraction:
    if not isinstance(area, Area) or area.value <= 0:
        raise ValueError("catchment area must be a positive Area")
    return area.value / 1_000_000


@dataclass(frozen=True)
class RunoffDepth:
    """Prepared catchment-average raster depth over a declared elapsed duration."""

    millimetres: Fraction
    seconds: Fraction
    source: str

    def __post_init__(self) -> None:
        for name in ("millimetres", "seconds"):
            object.__setattr__(self, name, finite_number(getattr(self, name)))
        if self.millimetres < 0 or self.seconds <= 0:
            raise ValueError("runoff depth must be nonnegative and duration positive")
        _source(self.source)


def raster_discharge(depth: RunoffDepth, area: Area) -> Flow:
    """§§3.4.1–2: depth × area / duration, for monthly or annual rasters."""
    return Flow(depth.millimetres * _area_km2(area) * 1000 / depth.seconds)


@dataclass(frozen=True)
class MonthlyRegime:
    monthly_means: tuple[Flow | None, ...]
    source: str
    inputs: tuple[object, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.monthly_means, tuple) or len(self.monthly_means) != 12:
            raise ValueError("monthly regime requires January–December")
        if any(v is not None and not isinstance(v, Flow) for v in self.monthly_means):
            raise TypeError("monthly means require Flow")
        _source(self.source)


def monthly_from_parde(mean: Flow, coefficients: tuple[Fraction, ...], source: str) -> MonthlyRegime:
    if len(coefficients) != 12:
        raise ValueError("twelve Parde coefficients required")
    factors = tuple(finite_number(v) for v in coefficients)
    if any(v < 0 for v in factors):
        raise ValueError("negative Parde coefficient")
    return MonthlyRegime(tuple(Flow(mean.value * v) for v in factors), source, (mean, factors))


def regime_mean_flow(regime: RegimeReference, area: Area) -> MonthlyRegime:
    mean = Flow(SPECIFIC_MEAN[regime.swiss_type - 1] * _area_km2(area), "l/s")
    monthly = monthly_from_parde(
        mean, tuple(row[regime.swiss_type - 1] for row in PARDE_COEFFICIENTS), SOURCE + " Tables 2–3"
    )
    return MonthlyRegime(
        monthly.monthly_means,
        monthly.source,
        (regime, area, *monthly.inputs),
        ("rough Swiss regime estimate; local suitability is supplied evidence",),
    )


def monthly_from_raster(depths: tuple[RunoffDepth, ...], area: Area) -> MonthlyRegime:
    return MonthlyRegime(
        tuple(raster_discharge(d, area) for d in depths), SOURCE + " §3.4.1 raster route", (depths, area)
    )


def _daily(samples: tuple[FlowSample, ...]) -> tuple[FlowSample, ...]:
    if not samples:
        return ()
    check_flow_intervals(samples)
    for sample in samples:
        start = sample.interval.start
        if sample.interval.seconds != 86400 or any((start.hour, start.minute, start.second, start.microsecond)):
            raise ValueError("whole UTC daily means required; no subdaily or coarse substitution")
    return tuple(sorted(samples, key=lambda s: s.interval.start))


def _supported(sample: FlowSample) -> bool:
    return (
        sample.presence is Presence.PRESENT
        and sample.coverage is Coverage.COMPLETE
        and interval_use(sample) is IntervalUse.ELIGIBLE
    )


def _complete_years(samples: tuple[FlowSample, ...]) -> dict[int, tuple[FlowSample, ...]]:
    ordered = _daily(samples)
    years: dict[int, tuple[FlowSample, ...]] = {}
    for year in sorted({s.interval.start.year for s in ordered}):
        group = tuple(s for s in ordered if s.interval.start.year == year)
        days = (date(year + 1, 1, 1) - date(year, 1, 1)).days
        if len(group) == days and all(_supported(s) for s in group):
            years[year] = group
    return years


def monthly_from_observations(samples: tuple[FlowSample, ...]) -> MonthlyRegime:
    ordered = _daily(samples)
    retained: list[FlowSample] = []
    excluded = 0
    for year, month in sorted({(s.interval.start.year, s.interval.start.month) for s in ordered}):
        group = tuple(s for s in ordered if (s.interval.start.year, s.interval.start.month) == (year, month))
        if len(group) == monthrange(year, month)[1] and all(_supported(s) for s in group):
            retained.extend(group)
        else:
            excluded += 1
    monthly: list[Flow | None] = []
    for month in range(1, 13):
        values = [s.value.value for s in retained if s.interval.start.month == month and s.value is not None]
        monthly.append(Flow(sum(values, Fraction()) / len(values)) if values else None)
    return MonthlyRegime(
        tuple(monthly),
        SOURCE + " §3.4.1 daily observations",
        (samples,),
        (
            f"{excluded} incomplete months excluded; only complete calendar months used",
            "source recommends ≥5 years; numerical support is not scientific acceptance",
        ),
    )


@dataclass(frozen=True)
class MeanFlowEstimate:
    value: Flow | None
    source: str
    selected_years: tuple[int, ...]
    excluded_years: tuple[int, ...]
    inputs: tuple[object, ...]
    coverage: Completeness
    reasons: tuple[str, ...]


def annual_mean_from_observations(samples: tuple[FlowSample, ...]) -> MeanFlowEstimate:
    """§3.4.2 pools complete years, retaining leap-day weight and excluded records."""
    years = _complete_years(samples)
    values = [s.value.value for group in years.values() for s in group if s.value is not None]
    value = Flow(sum(values, Fraction()) / len(values)) if values else None
    all_years = (
        set(range(min(s.interval.start.year for s in samples), max(s.interval.start.year for s in samples) + 1))
        if samples
        else set()
    )
    excluded = tuple(sorted(all_years - set(years)))
    return MeanFlowEstimate(
        value,
        SOURCE + " §3.4.2",
        tuple(years),
        excluded,
        (samples,),
        Completeness.INCOMPLETE if excluded or not values else Completeness.COMPLETE,
        ("only complete calendar years; pooled daily means; source recommends ≥5 years",),
    )


def _input_coverage(inputs: tuple[object, ...]) -> Completeness:
    """Retain partial observation windows through derived scalar records."""
    for value in inputs:
        if isinstance(value, tuple):
            if value and all(isinstance(item, FlowSample) for item in value):
                samples = _daily(tuple(item for item in value if isinstance(item, FlowSample)))
                years = _complete_years(samples)
                if sum(map(len, years.values())) != len(samples):
                    return Completeness.INCOMPLETE
                if any(a.interval.end != b.interval.start for a, b in zip(samples, samples[1:], strict=False)):
                    return Completeness.INCOMPLETE
            if _input_coverage(value) is Completeness.INCOMPLETE:
                return Completeness.INCOMPLETE
        elif isinstance(value, (MonthlyRegime, LowFlowStatistics, SeasonalityPoint, LowFlowDuration)):
            if _input_coverage(value.inputs) is Completeness.INCOMPLETE:
                return Completeness.INCOMPLETE
    return Completeness.COMPLETE


def _result(
    indicator: Indicator,
    context: AssessmentContext,
    classification: int | None,
    metrics: tuple[Metric, ...],
    section: str,
    inputs: tuple[object, ...],
    reasons: tuple[str, ...] = (),
) -> IndicatorResult:
    return IndicatorResult(
        indicator=indicator,
        context=context,
        state=AssessmentState.ASSESSED if classification is not None else AssessmentState.UNDETERMINED,
        classification=HydrologyClass(classification) if classification is not None else None,
        metrics=metrics,
        source=SOURCE + " " + section,
        reasons=reasons,
        inputs=inputs,
        coverage=_input_coverage(inputs),
    )


def assess_mean_flow(
    context: AssessmentContext,
    reference: MonthlyRegime | None,
    influenced: MonthlyRegime | None,
    regime: RegimeReference | None,
) -> IndicatorResult:
    inputs = (reference, influenced, regime)
    if (
        reference is None
        or influenced is None
        or any(v is None for v in (*reference.monthly_means, *influenced.monthly_means))
    ):
        return _result(
            Indicator.MEAN_FLOW,
            context,
            None,
            (),
            "§5.2",
            inputs,
            ("monthly reference or influenced evidence missing",),
        )
    r = tuple(v.value for v in reference.monthly_means if v is not None)
    b = tuple(v.value for v in influenced.monthly_means if v is not None)
    denominator = sum(r)
    if denominator == 0:
        return _result(Indicator.MEAN_FLOW, context, None, (), "§5.2", inputs, ("zero reference denominator",))
    reduction = 100 * sum(abs(a - c) for a, c in zip(r, b, strict=True)) / denominator
    metrics = (Metric("R", reduction, "%"),)

    def classify(quantiles: tuple[Fraction, ...]) -> int:
        return next(
            (
                i
                for i, (q, limit) in enumerate(zip(quantiles, (30, 45, 60), strict=True), 1)
                if reduction < q or reduction < limit
            ),
            4 if reduction < 85 else 5,
        )

    if regime is None:
        possibilities = {classify(quantiles) for quantiles in R_QUANTILES}
        classification = possibilities.pop() if len(possibilities) == 1 else None
        reasons = ("regime reference unavailable; class determined only if all source types agree",)
    else:
        classification = classify(R_QUANTILES[regime.swiss_type - 1])
        reasons = reference.reasons + influenced.reasons
    return _result(Indicator.MEAN_FLOW, context, classification, metrics, "§5.2 Table 10 Fig.17", inputs, reasons)


@dataclass(frozen=True)
class Percent:
    value: Fraction

    def __post_init__(self) -> None:
        value = finite_number(self.value)
        if value < 0:
            raise ValueError("percentage must be nonnegative")
        object.__setattr__(self, "value", value)


@dataclass(frozen=True)
class LowFlowStatistics:
    q347: Flow | None
    coefficient_of_variation: Percent | None
    source: str
    annual_q347: tuple[tuple[int, Flow], ...] = ()
    inputs: tuple[object, ...] = ()
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.q347 is not None and not isinstance(self.q347, Flow):
            raise TypeError("Q347 requires interval-mean Flow")
        if self.coefficient_of_variation is not None and not isinstance(self.coefficient_of_variation, Percent):
            raise TypeError("CV requires Percent")
        _source(self.source)


def regime_low_flow(regime: RegimeReference, area: Area) -> LowFlowStatistics:
    i = regime.swiss_type - 1
    return LowFlowStatistics(
        Flow(SPECIFIC_LOW[i] * _area_km2(area), "l/s"),
        Percent(REGIME_CV[i]),
        SOURCE + " Tables 6–7",
        inputs=(regime, area),
        reasons=("rough Swiss regime estimate; local suitability is supplied evidence",),
    )


class FlushingTreatment(StrEnum):
    ABSENT = "documented_no_flushing"
    SUBTRACT = "subtract_supplied_daily_flushing_component"
    UNKNOWN = "unknown_flushing_component"


@dataclass(frozen=True)
class FlushingCorrection:
    treatment: FlushingTreatment
    source: str
    daily_components: tuple[FlowSample, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.treatment, FlushingTreatment):
            raise TypeError("typed flushing treatment required")
        if self.treatment is not FlushingTreatment.SUBTRACT and self.daily_components:
            raise ValueError("only subtraction accepts flushing components")
        _source(self.source)


def _quantile(values: list[Fraction]) -> Fraction:
    ordered = sorted(values)
    index = Fraction(len(ordered) - 1, 20)
    lower = index.numerator // index.denominator
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def low_flow_from_observations(samples: tuple[FlowSample, ...], flushing: FlushingCorrection) -> LowFlowStatistics:
    """Pooled 5% Q347; separate annual 5% quantiles feed sample-SD CV, not Q347."""
    years = _complete_years(samples)
    inputs: tuple[object, ...] = (samples, flushing)
    if flushing.treatment is FlushingTreatment.UNKNOWN:
        return LowFlowStatistics(
            None, None, SOURCE + " §3.6.1", inputs=inputs, reasons=("flushing correction unknown",)
        )
    components = _daily(flushing.daily_components)
    if components and samples and components[0].location != samples[0].location:
        raise ValueError("flushing component has incompatible location")
    by_interval = {s.interval: s for s in components}
    if flushing.treatment is FlushingTreatment.SUBTRACT and set(by_interval) != {s.interval for s in samples}:
        return LowFlowStatistics(
            None, None, SOURCE + " §3.6.1", inputs=inputs, reasons=("daily flushing coverage incomplete",)
        )
    annual = []
    pooled: list[Fraction] = []
    for year, group in years.items():
        values: list[Fraction] = []
        for sample in group:
            assert sample.value is not None
            amount = sample.value.value
            if flushing.treatment is FlushingTreatment.SUBTRACT:
                component = by_interval[sample.interval]
                for field in ("scenario", "reference_member"):
                    if getattr(component.provenance, field) != getattr(sample.provenance, field):
                        raise ValueError(f"flushing component {field} differs from total discharge")
                if not _supported(component) or component.value is None:
                    return LowFlowStatistics(
                        None, None, SOURCE + " §3.6.1", inputs=inputs, reasons=("unsupported flushing component",)
                    )
                amount -= component.value.value
                if amount < 0:
                    raise ValueError("flushing component exceeds total daily discharge")
            values.append(amount)
        annual.append((year, Flow(_quantile(values))))
        pooled.extend(values)
    if not pooled:
        return LowFlowStatistics(None, None, SOURCE + " §3.6.1", inputs=inputs, reasons=("no complete calendar years",))
    annual_values = [v.value for _, v in annual]
    mean = sum(annual_values) / len(annual_values)
    cv = None
    if len(annual_values) >= 2 and mean > 0:
        variance = sum((v - mean) ** 2 for v in annual_values) / (len(annual_values) - 1)
        cv = Percent(finite_number(100 * sqrt(float(variance)) / float(mean)))
    return LowFlowStatistics(
        Flow(_quantile(pooled)),
        cv,
        SOURCE + " §§3.6.1–2",
        tuple(annual),
        inputs,
        (
            f"{len(years)} complete years; source recommends ten years for Q347",
            "linear quantile (n−1)p; sample SD (n−1); incomplete years excluded",
        ),
    )


class TroughApplicability(StrEnum):
    ABSENT = "no_hydropeaking"
    PRESENT = "hydropeaking_present"
    UNKNOWN = "hydropeaking_unknown"


@dataclass(frozen=True)
class TroughDischarge:
    """Supplied Q_Sunk statistic of instantaneous minima, not an interval-mean Flow."""

    cubic_metres_per_second: Fraction
    source: str

    def __post_init__(self) -> None:
        value = finite_number(self.cubic_metres_per_second)
        if value < 0:
            raise ValueError("negative trough discharge")
        object.__setattr__(self, "cubic_metres_per_second", value)
        _source(self.source)


def low_flow_thresholds(reference: Flow) -> tuple[Fraction, ...]:
    """Fig.22 linear interpolation; source explicitly applies extreme anchors outside."""
    anchors = ((50, (20, 40, 65)), (200, (25, 45, 70)), (500, (35, 55, 80)), (1000, (45, 65, 85)))
    q = reference.value * 1000
    if q <= 50:
        return tuple(Fraction(v) for v in anchors[0][1])
    if q >= 1000:
        return tuple(Fraction(v) for v in anchors[-1][1])
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:], strict=False):
        if x0 <= q <= x1:
            return tuple(Fraction(a) + (q - x0) * (b - a) / (x1 - x0) for a, b in zip(y0, y1, strict=True))
    raise AssertionError("unreachable anchor interval")


def assess_low_flow_magnitude(
    context: AssessmentContext,
    reference: LowFlowStatistics | None,
    influenced: LowFlowStatistics | None,
    trough_applicability: TroughApplicability,
    trough: TroughDischarge | None = None,
) -> IndicatorResult:
    if not isinstance(trough_applicability, TroughApplicability):
        raise TypeError("typed trough applicability required")
    if trough is not None and trough_applicability is not TroughApplicability.PRESENT:
        raise ValueError("trough supplied without hydropeaking applicability")
    inputs = (reference, influenced, trough_applicability, trough)
    if reference is None or influenced is None or reference.q347 is None or influenced.q347 is None:
        return _result(Indicator.LOW_FLOW_MAGNITUDE, context, None, (), "§5.5", inputs, ("Q347 evidence missing",))
    if reference.q347.value == 0:
        return _result(Indicator.LOW_FLOW_MAGNITUDE, context, None, (), "§5.5", inputs, ("zero reference denominator",))
    if trough_applicability is TroughApplicability.UNKNOWN or (
        trough_applicability is TroughApplicability.PRESENT and trough is None
    ):
        return _result(
            Indicator.LOW_FLOW_MAGNITUDE, context, None, (), "§5.5", inputs, ("lower trough evidence unresolved",)
        )
    b = min(influenced.q347.value, trough.cubic_metres_per_second) if trough else influenced.q347.value
    delta = 100 * (reference.q347.value - b) / reference.q347.value
    thresholds = low_flow_thresholds(reference.q347)
    metrics = (
        Metric("relative_Q347_reduction", delta, "%"),
        Metric("effective_low_flow", b, "m3/s"),
        *(Metric(f"class_{i}_upper_threshold", t, "%") for i, t in enumerate(thresholds, 2)),
    )
    cv = reference.coefficient_of_variation
    if delta < 0 or (cv is not None and delta < cv.value):
        classification = 1
    elif cv is None:
        return _result(
            Indicator.LOW_FLOW_MAGNITUDE,
            context,
            None,
            metrics,
            "§5.5 Fig.22",
            inputs,
            ("CV required to determine best qualifying class",),
        )
    else:
        classification = next((i for i, limit in enumerate(thresholds, 2) if delta < limit), 5)
    if cv is not None:
        metrics += (Metric("CV_Q347", cv.value, "%"),)
    return _result(
        Indicator.LOW_FLOW_MAGNITUDE,
        context,
        classification,
        metrics,
        "§5.5 Fig.22",
        inputs,
        reference.reasons + influenced.reasons,
    )


@dataclass(frozen=True)
class SeasonalityPoint:
    """Mean cos/sin coordinates in the source JD/365 circle; x points at January."""

    x: float
    y: float
    source: str
    inputs: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.x, self.y)) or hypot(self.x, self.y) > 1 + 1e-12:
            raise ValueError("seasonality point must lie in the unit disk")
        _source(self.source)


def circular_timing(dates: tuple[date, ...], source: str) -> SeasonalityPoint | None:
    if not dates:
        return None
    angles = [2 * pi * d.timetuple().tm_yday / 365 for d in dates]
    return SeasonalityPoint(
        sum(cos(a) for a in angles) / len(angles), sum(sin(a) for a in angles) / len(angles), source, (dates,)
    )


class Extremum(StrEnum):
    MAXIMUM = "annual_maximum"
    MINIMUM = "annual_minimum"


class ExtremumTie(StrEnum):
    EARLIEST = "earliest_date"
    LATEST = "latest_date"
    UNRESOLVED = "unresolved"


def seasonality_from_observations(
    samples: tuple[FlowSample, ...], extremum: Extremum, ties: ExtremumTie
) -> SeasonalityPoint | None:
    if not isinstance(extremum, Extremum) or not isinstance(ties, ExtremumTie):
        raise TypeError("typed extremum and tie convention required")
    dates: list[date] = []
    years = _complete_years(samples)
    for group in years.values():
        values = [s.value.value for s in group if s.value is not None]
        target = (max if extremum is Extremum.MAXIMUM else min)(values)
        candidates = [s.interval.start.date() for s in group if s.value is not None and s.value.value == target]
        if len(candidates) > 1 and ties is ExtremumTie.UNRESOLVED:
            return None
        dates.append(candidates[-1] if ties is ExtremumTie.LATEST else candidates[0])
    point = circular_timing(tuple(dates), SOURCE + " §§3.5.4,3.6.4; JD/365; complete years only")
    return SeasonalityPoint(point.x, point.y, point.source, (samples, extremum, ties)) if point else None


@dataclass(frozen=True)
class ReferenceEllipse:
    """Specialist-supplied 75% reference zone; axes in the source cos/sin plane."""

    centre: SeasonalityPoint
    semimajor: float
    semiminor: float
    rotation_radians: float
    regime: RegimeReference
    source: str

    def __post_init__(self) -> None:
        if not all(isfinite(v) for v in (self.semimajor, self.semiminor, self.rotation_radians)):
            raise ValueError("finite ellipse geometry required")
        if not 0 < self.semiminor <= self.semimajor <= 1:
            raise ValueError("ellipse semiaxes must satisfy 0 < minor <= major <= 1")
        _source(self.source)


def ellipse_distance(point: SeasonalityPoint, ellipse: ReferenceEllipse) -> float:
    """Distance to the filled reference zone; exterior closest point via monotone bisection."""
    dx, dy = point.x - ellipse.centre.x, point.y - ellipse.centre.y
    c, s = cos(ellipse.rotation_radians), sin(ellipse.rotation_radians)
    x, y = abs(c * dx + s * dy), abs(-s * dx + c * dy)
    a, b = ellipse.semimajor, ellipse.semiminor
    if (x / a) ** 2 + (y / b) ** 2 <= 1:
        return 0.0

    def equation(t: float) -> float:
        return (a * x / (t + a * a)) ** 2 + (b * y / (t + b * b)) ** 2

    low, high = 0.0, max(a * x, b * y, 1.0)
    while equation(high) > 1:
        high *= 2
    for _ in range(100):
        middle = (low + high) / 2
        if equation(middle) > 1:
            low = middle
        else:
            high = middle
    t = (low + high) / 2
    return hypot(x - a * a * x / (t + a * a), y - b * b * y / (t + b * b))


def assess_seasonality(
    context: AssessmentContext,
    indicator: Indicator,
    influenced: SeasonalityPoint | None,
    reference: SeasonalityPoint | ReferenceEllipse | None,
) -> IndicatorResult:
    if indicator not in (Indicator.FLOOD_SEASONALITY, Indicator.LOW_FLOW_SEASONALITY):
        raise ValueError("seasonality indicator required")
    inputs = (influenced, reference)
    if influenced is None or reference is None:
        return _result(
            indicator, context, None, (), "§§5.4,5.6", inputs, ("seasonality evidence missing or unresolved",)
        )
    if isinstance(reference, ReferenceEllipse):
        distance = ellipse_distance(influenced, reference)
        thresholds = (0.25, 0.5, 0.75, 1.0)
        route = "ellipse"
    else:
        distance = hypot(influenced.x - reference.x, influenced.y - reference.y)
        thresholds = (0.3, 0.6, 0.9, 1.2)
        route = "direct"
    classification = next((i for i, limit in enumerate(thresholds, 1) if distance <= limit), 5)
    return _result(
        indicator,
        context,
        classification,
        (Metric("seasonality_distance", distance, "1"),),
        "§§5.4,5.6 Fig.21 " + route,
        inputs,
        ("floating geometry precision 1e-12; specialist geometry is not a local suitability finding",),
    )


@dataclass(frozen=True)
class LowFlowDuration:
    mean_days: Fraction
    annual_longest: tuple[tuple[int, int], ...]
    source: str
    inputs: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        value = finite_number(self.mean_days)
        if value < 0:
            raise ValueError("negative duration")
        object.__setattr__(self, "mean_days", value)
        if any(type(year) is not int or type(days) is not int or days < 0 for year, days in self.annual_longest):
            raise ValueError("invalid annual spell record")
        _source(self.source)


def low_flow_duration(samples: tuple[FlowSample, ...], threshold: Flow) -> LowFlowDuration | None:
    """Whole cross-year spells belong to start year (§3.6.3); equality follows §5.7.1.

    An unfinished terminal spell or unsupported interval cannot certify a longest
    spell. Supply a subsequent above-threshold day to resolve terminal censoring.
    """
    ordered = _daily(samples)
    years = _complete_years(samples)
    if not years or not ordered or any(not _supported(s) for s in ordered):
        return None
    if any(a.interval.end != b.interval.start for a, b in zip(ordered, ordered[1:], strict=False)):
        return None
    if ordered[0].value is not None and ordered[0].value.value <= threshold.value:
        return None  # No observation establishes the start of this left-censored spell.
    longest = dict.fromkeys(years, 0)
    run = 0
    start_year = 0
    for sample in ordered:
        assert sample.value is not None
        if sample.value.value <= threshold.value:
            if run == 0:
                start_year = sample.interval.start.year
            run += 1
        elif run:
            if start_year in longest:
                longest[start_year] = max(longest[start_year], run)
            run = 0
    if run and start_year in longest:
        return None
    annual = tuple(sorted(longest.items()))
    return LowFlowDuration(
        Fraction(sum(longest.values()), len(longest)), annual, SOURCE + " §§3.6.3,5.7", (samples, threshold)
    )


def assess_low_flow_duration(context: AssessmentContext, duration: LowFlowDuration | None) -> IndicatorResult:
    if duration is None:
        return _result(
            Indicator.LOW_FLOW_DURATION,
            context,
            None,
            (),
            "§5.7",
            (duration,),
            ("duration evidence incomplete or terminal spell unresolved",),
        )
    classification = next((i for i, limit in enumerate((20, 35, 50, 65), 1) if duration.mean_days < limit), 5)
    return _result(
        Indicator.LOW_FLOW_DURATION,
        context,
        classification,
        (
            Metric("mean_annual_longest_spell", duration.mean_days, "days"),
            *(Metric(f"longest_spell_{year}", days, "days") for year, days in duration.annual_longest),
        ),
        "§5.7 Fig.23",
        (duration,),
    )


def _check_assessment_samples(context: AssessmentContext, samples: tuple[FlowSample, ...]) -> None:
    for sample in samples:
        if sample.location != context.location:
            raise ValueError("observation location differs from assessment; supply an attributable transfer first")
        for field in ("scenario", "reference_member", "reference_kind"):
            if getattr(sample.provenance, field) != getattr(context.provenance, field):
                raise ValueError(f"observation {field} differs from assessment")
        if sample.interval.start < context.period.start or sample.interval.end > context.period.end:
            raise ValueError("influenced observation lies outside assessment period")


def _check_reference_samples(context: AssessmentContext, samples: tuple[FlowSample, ...]) -> None:
    if samples:
        check_flow_intervals(samples)
    for sample in samples:
        if sample.location != context.location:
            raise ValueError("reference location differs from assessment; supply explicit A4 transfer first")
        # Historic/reference periods and reference kinds may differ from the managed
        # assessment. The selected reference ensemble member must not be swapped.
        if sample.provenance.reference_member != context.provenance.reference_member:
            raise ValueError("reference reference_member differs from assessment")


def _observation_window(result: IndicatorResult, samples: tuple[FlowSample, ...]) -> IndicatorResult:
    ordered = _daily(samples)
    if (
        not ordered
        or ordered[0].interval.start != result.context.period.start
        or ordered[-1].interval.end != result.context.period.end
    ):
        return replace(
            result,
            coverage=Completeness.INCOMPLETE,
            reasons=(*result.reasons, "observation window does not cover the full assessment period"),
        )
    return result


def assess_mean_flow_observations(
    context: AssessmentContext,
    reference: tuple[FlowSample, ...],
    influenced: tuple[FlowSample, ...],
    regime: RegimeReference | None,
) -> IndicatorResult:
    """Prepare complete-month statistics and retain every original interval."""
    _check_assessment_samples(context, influenced)
    _check_reference_samples(context, reference)
    result = assess_mean_flow(
        context, monthly_from_observations(reference), monthly_from_observations(influenced), regime
    )
    return _observation_window(result, influenced)


def assess_low_flow_observations(
    context: AssessmentContext,
    reference: tuple[FlowSample, ...],
    influenced: tuple[FlowSample, ...],
    reference_flushing: FlushingCorrection,
    influenced_flushing: FlushingCorrection,
    trough_applicability: TroughApplicability,
    trough: TroughDischarge | None = None,
) -> IndicatorResult:
    """Source Q347/CV preparation and Fig.22 assessment, independent of prescriptions."""
    _check_assessment_samples(context, influenced)
    _check_reference_samples(context, reference)
    result = assess_low_flow_magnitude(
        context,
        low_flow_from_observations(reference, reference_flushing),
        low_flow_from_observations(influenced, influenced_flushing),
        trough_applicability,
        trough,
    )
    return _observation_window(result, influenced)


def assess_seasonality_observations(
    context: AssessmentContext,
    indicator: Indicator,
    influenced: tuple[FlowSample, ...],
    reference: tuple[FlowSample, ...] | ReferenceEllipse,
    ties: ExtremumTie,
) -> IndicatorResult:
    """Annual daily extrema, with explicit tied-date interpretation."""
    _check_assessment_samples(context, influenced)
    if indicator not in (Indicator.FLOOD_SEASONALITY, Indicator.LOW_FLOW_SEASONALITY):
        raise ValueError("seasonality indicator required")
    if not isinstance(reference, ReferenceEllipse):
        _check_reference_samples(context, reference)
    extremum = Extremum.MAXIMUM if indicator is Indicator.FLOOD_SEASONALITY else Extremum.MINIMUM
    point = seasonality_from_observations(influenced, extremum, ties)
    ref = (
        reference
        if isinstance(reference, ReferenceEllipse)
        else seasonality_from_observations(reference, extremum, ties)
    )
    result = assess_seasonality(context, indicator, point, ref)
    return _observation_window(
        replace(
            result,
            inputs=(influenced, reference, ties, *result.inputs),
            coverage=_input_coverage((influenced, reference)),
        ),
        influenced,
    )


def assess_duration_observations(
    context: AssessmentContext,
    influenced: tuple[FlowSample, ...],
    reference_q347: Flow | None,
) -> IndicatorResult:
    """Keep missing and censored daily evidence on the ordinary indicator result."""
    _check_assessment_samples(context, influenced)
    duration = low_flow_duration(influenced, reference_q347) if reference_q347 is not None else None
    result = assess_low_flow_duration(context, duration)
    return _observation_window(
        replace(result, inputs=(influenced, reference_q347, *result.inputs), coverage=_input_coverage((influenced,))),
        influenced,
    )


@dataclass(frozen=True)
class PardeCoefficients:
    monthly: tuple[Fraction | None, ...]
    source: str
    inputs: tuple[object, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.monthly, tuple) or len(self.monthly) != 12:
            raise ValueError("twelve monthly Parde coefficients required")
        values = tuple(finite_number(v) if v is not None else None for v in self.monthly)
        if any(v is not None and v < 0 for v in values):
            raise ValueError("negative Parde coefficient")
        object.__setattr__(self, "monthly", values)
        _source(self.source)


def parde_from_means(monthly: MonthlyRegime, annual_mean: Flow | None) -> PardeCoefficients:
    """§3.4.3: monthly/annual mean, without renormalising rounded source coefficients."""
    if annual_mean is None or annual_mean.value == 0:
        values = (None,) * 12
    else:
        values = tuple(v.value / annual_mean.value if v is not None else None for v in monthly.monthly_means)
    return PardeCoefficients(values, SOURCE + " §3.4.3", (monthly, annual_mean))


@dataclass(frozen=True)
class PardeEnvelope:
    """Supplied A2 monthly expectation zone inside its wider fluctuation zone."""

    regime: RegimeReference
    expectation_lower: tuple[Fraction, ...]
    expectation_upper: tuple[Fraction, ...]
    fluctuation_lower: tuple[Fraction, ...]
    fluctuation_upper: tuple[Fraction, ...]
    source: str

    def __post_init__(self) -> None:
        if not isinstance(self.regime, RegimeReference):
            raise TypeError("envelope requires attributable regime reference")
        for name in ("expectation_lower", "expectation_upper", "fluctuation_lower", "fluctuation_upper"):
            values = getattr(self, name)
            if not isinstance(values, tuple) or len(values) != 12:
                raise ValueError("envelope requires twelve monthly bounds")
            object.__setattr__(self, name, tuple(finite_number(v) for v in values))
        for fl, el, eu, fu in zip(
            self.fluctuation_lower, self.expectation_lower, self.expectation_upper, self.fluctuation_upper, strict=True
        ):
            if not 0 <= fl <= el <= eu <= fu:
                raise ValueError("expectation envelope must be nested in nonnegative fluctuation envelope")
        _source(self.source)


@dataclass(frozen=True)
class RegimeMatch:
    regime: RegimeReference | None
    hits: tuple[tuple[int, int, int], ...]
    inputs: tuple[object, ...]
    reasons: tuple[str, ...]


def match_parde_regime(coefficients: PardeCoefficients, envelopes: tuple[PardeEnvelope, ...]) -> RegimeMatch:
    """§3.3.1: both expectation and combined-band leads must be at least two months.

    All 16 supplied source envelopes are required for an unambiguous Swiss type.
    A hit on an envelope endpoint counts within that supplied closed interval.
    """
    ids = [e.regime.swiss_type for e in envelopes]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate regime envelope")
    inputs: tuple[object, ...] = (coefficients, envelopes)
    if set(ids) != set(range(1, 17)) or any(v is None for v in coefficients.monthly):
        return RegimeMatch(
            None, (), inputs, ("complete twelve-month coefficients and all sixteen candidate envelopes required",)
        )
    values = tuple(v for v in coefficients.monthly if v is not None)
    hits = tuple(
        (
            e.regime.swiss_type,
            sum(lo <= v <= hi for v, lo, hi in zip(values, e.expectation_lower, e.expectation_upper, strict=True)),
            sum(lo <= v <= hi for v, lo, hi in zip(values, e.fluctuation_lower, e.fluctuation_upper, strict=True)),
        )
        for e in envelopes
    )
    winners = [
        regime
        for regime, expected, total in hits
        if all(
            other == regime or (expected >= other_expected + 2 and total >= other_total + 2)
            for other, other_expected, other_total in hits
        )
    ]
    if not winners:
        return RegimeMatch(None, hits, inputs, ("no regime leads every other regime by two in both hit counts",))
    selected = next(e.regime for e in envelopes if e.regime.swiss_type == winners[0])
    return RegimeMatch(
        selected,
        hits,
        inputs,
        ("supplied Swiss A2 envelopes; numerical matching does not establish local applicability",),
    )
