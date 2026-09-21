"""event_assessment : InstantaneousRecord × ReferenceFloodMagnitude → IndicatorResult (pure).

HYDMOD-F (BAFU 2011), sections 3.5, 3.7.9, 5.3 and 5.10.
Instantaneous discharges are deliberately distinct from interval-mean Flow.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from fractions import Fraction

from fishy.evidence import CorrectionState
from fishy.flows import Coverage, FlowSample, IntervalUse, Presence, check_flow_intervals, interval_use
from fishy.hydrological_condition import (
    AssessmentContext,
    AssessmentState,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    Metric,
)
from fishy.quantities import Area, Flow, Number, finite_number

SOURCE = "BAFU 2011 HYDMOD-F §§3.5, 3.7.9, 5.3 Fig.19, 5.10 Fig.28"


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attributable source/evidence is required")


@dataclass(frozen=True, init=False)
class InstantaneousDischarge:
    """Nonnegative point-in-time discharge, canonical m3/s; never an interval mean."""

    value: Fraction

    def __init__(self, value: Number, unit: str = "m3/s") -> None:
        if unit not in ("m3/s", "l/s"):
            raise ValueError("unsupported instantaneous discharge unit")
        amount = finite_number(value) / (1000 if unit == "l/s" else 1)
        if amount < 0:
            raise ValueError("instantaneous discharge cannot be negative")
        object.__setattr__(self, "value", amount)


class EventCause(StrEnum):
    NATURAL = "natural"
    FLUSHING = "flushing"
    ECOLOGICAL_FLOOD = "ecological_artificial_flood"


class EventSupport(StrEnum):
    COMPLETE = "complete_instantaneous_event_coverage"
    INCOMPLETE = "incomplete"
    DAILY_ONLY = "daily_only"


@dataclass(frozen=True)
class InstantaneousSample:
    at: datetime
    value: InstantaneousDischarge | None
    presence: Presence
    context: AssessmentContext
    cause: EventCause = EventCause.NATURAL

    def __post_init__(self) -> None:
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError("instantaneous timestamp requires timezone")
        object.__setattr__(self, "at", self.at.astimezone(UTC))
        if not isinstance(self.context, AssessmentContext):
            raise TypeError("sample requires assessment context")
        if not self.context.period.start <= self.at < self.context.period.end:
            raise ValueError("instantaneous reading lies outside attributed period")
        if not isinstance(self.presence, Presence) or not isinstance(self.cause, EventCause):
            raise TypeError("presence and cause require domain enums")
        if self.value is not None and not isinstance(self.value, InstantaneousDischarge):
            raise TypeError("instantaneous reading cannot use interval-mean Flow")
        if self.context.provenance.correction_state is CorrectionState.MISSING and self.value is not None:
            raise ValueError("missing correction status cannot carry an instantaneous value")
        if (self.presence is Presence.PRESENT) != (self.value is not None):
            raise ValueError("present readings require values; unavailable readings cannot carry values")


@dataclass(frozen=True)
class InstantaneousRecord:
    context: AssessmentContext
    samples: tuple[InstantaneousSample, ...]
    support: EventSupport
    evidence: str

    def __post_init__(self) -> None:
        _text(self.evidence)
        if not isinstance(self.support, EventSupport):
            raise TypeError("event coverage requires EventSupport")
        if not isinstance(self.samples, tuple):
            raise TypeError("samples require an immutable tuple")
        for sample in self.samples:
            if not isinstance(sample, InstantaneousSample):
                raise TypeError("record requires instantaneous samples, not daily means")
            if sample.context.location != self.context.location:
                raise ValueError("incompatible instantaneous locations")
            if not self.context.period.start <= sample.at < self.context.period.end:
                raise ValueError("sample outside record period")
            if any(
                getattr(sample.context.provenance, field) != getattr(self.context.provenance, field)
                for field in ("scenario", "reference_member", "reference_kind")
            ):
                raise ValueError("incompatible scenario/member/reference kind")
        if any(a.at >= b.at for a, b in zip(self.samples, self.samples[1:], strict=False)):
            raise ValueError("instantaneous timestamps must be unique and increasing")


@dataclass(frozen=True, init=False)
class EventFrequency:
    """Attributed long-term annual event frequency, in events/year."""

    value: Fraction
    source: str

    def __init__(self, value: Number, source: str) -> None:
        amount = finite_number(value)
        if amount < 0:
            raise ValueError("event frequency cannot be negative")
        _text(source)
        object.__setattr__(self, "value", amount)
        object.__setattr__(self, "source", source)


def _regime(regime_type: int) -> None:
    if isinstance(regime_type, bool) or not isinstance(regime_type, int) or not 1 <= regime_type <= 16:
        raise ValueError("Swiss regime type must be explicitly supplied in 1..16")


def _years(context: AssessmentContext) -> int | None:
    p = context.period
    if any((d.month, d.day, d.hour, d.minute, d.second, d.microsecond) != (1, 1, 0, 0, 0, 0) for d in (p.start, p.end)):
        return None
    return p.end.year - p.start.year


def _context_interval_use(context: AssessmentContext) -> IntervalUse:
    if any(
        context.period.start < excluded.end and excluded.start < context.period.end
        for excluded in context.provenance.excluded_warmup
    ):
        return IntervalUse.EXCLUDED_WARMUP
    return IntervalUse.ELIGIBLE


def _mhq_flow(reference: Flow | ReferenceFloodMagnitude | None) -> Flow | None:
    if isinstance(reference, ReferenceFloodMagnitude):
        return reference.flow
    if reference is not None and not isinstance(reference, Flow):
        raise TypeError("reference MHQ requires a daily-mean statistic, not instantaneous discharge")
    return reference


def _result(
    context: AssessmentContext,
    indicator: Indicator,
    classification: int | None,
    metrics: tuple[Metric, ...],
    inputs: tuple[object, ...],
    reasons: tuple[str, ...] = (),
) -> IndicatorResult:
    if _context_interval_use(context) is IntervalUse.EXCLUDED_WARMUP:
        classification = None
        reasons = (*reasons, "assessment interval overlaps excluded warmup")
    if context.provenance.correction_state is CorrectionState.MISSING:
        classification = None
        reasons = (*reasons, "assessment provenance marks input as missing")
    return IndicatorResult(
        indicator,
        context,
        AssessmentState.ASSESSED if classification is not None else AssessmentState.UNDETERMINED,
        HydrologyClass(classification) if classification is not None else None,
        metrics,
        SOURCE,
        reasons,
        inputs,
    )


def flood_frequency(
    context: AssessmentContext, frequency: EventFrequency | None, regime_type: int | None
) -> IndicatorResult:
    """Fig.19 absolute frequency; no seasonality or relative-frequency substitution."""
    if regime_type is not None:
        _regime(regime_type)
    if frequency is None:
        return _result(
            context, Indicator.FLOOD_FREQUENCY, None, (), (frequency, regime_type), ("flood frequency missing",)
        )
    f = frequency.value
    metrics = (Metric("flood_frequency", f, "events/year"),)
    if f < Fraction(1, 3):
        cls = 5
    elif f < Fraction(2, 3):
        cls = 4
    elif f < 1:
        cls = 3
    elif regime_type is None:
        return _result(
            context,
            Indicator.FLOOD_FREQUENCY,
            None,
            metrics,
            (frequency, regime_type),
            ("regime evidence required to distinguish classes 1 and 2",),
        )
    else:
        threshold = 2 if regime_type in (1, 2, 3, 4, 5, 13) else 6 if regime_type in (8, 9, 16) else Fraction(7, 2)
        cls = 1 if f >= threshold else 2
    return _result(context, Indicator.FLOOD_FREQUENCY, cls, metrics, (frequency, regime_type))


def flood_frequency_from_record(
    record: InstantaneousRecord, reference_mhq: Flow | ReferenceFloodMagnitude | None, regime_type: int | None
) -> IndicatorResult:
    """Count crossings above 0.6 MHQr; re-arm after a half-threshold drop and five days.

    Completeness is supplied event-resolution evidence, not inferred from sample count.
    Cross-year state is retained. The initial reading must be below the threshold.
    """
    if regime_type is not None:
        _regime(regime_type)
    inputs = (record, reference_mhq, regime_type)
    mhq = _mhq_flow(reference_mhq)
    years = _years(record.context)
    if (
        mhq is None
        or mhq.value <= 0
        or years is None
        or not record.samples
        or record.support is not EventSupport.COMPLETE
        or any(
            s.presence is not Presence.PRESENT or _context_interval_use(s.context) is IntervalUse.EXCLUDED_WARMUP
            for s in record.samples
        )
    ):
        return _result(
            record.context,
            Indicator.FLOOD_FREQUENCY,
            None,
            (),
            inputs,
            ("positive MHQr and complete calendar-year instantaneous event evidence required",),
        )
    threshold = mhq.value * Fraction(3, 5)
    if record.samples[0].value is None or record.samples[0].value.value > threshold:
        return _result(
            record.context,
            Indicator.FLOOD_FREQUENCY,
            None,
            (),
            inputs,
            ("initial flood requires predecessor crossing evidence",),
        )
    crossings: list[datetime] = []
    previous = record.samples[0].value.value
    seen_event = False
    drop: datetime | None = None
    for sample in record.samples[1:]:
        assert sample.value is not None
        q = sample.value.value
        if q <= threshold / 2 and seen_event and drop is None:
            drop = sample.at
        if previous <= threshold < q:
            independent = not seen_event or (drop is not None and sample.at - drop >= timedelta(days=5))
            if independent:
                if sample.cause is not EventCause.FLUSHING:
                    crossings.append(sample.at)
                seen_event = True
            # A premature crossing interrupts the required separation. A later
            # crossing must use a new qualifying drop, not an older trough.
            drop = None
        previous = q
    frequency = EventFrequency(Fraction(len(crossings), years), SOURCE + " §3.5.3")
    result = flood_frequency(record.context, frequency, regime_type)
    return replace(
        result,
        metrics=(
            *result.metrics,
            Metric("flood_threshold", threshold, "m3/s"),
            Metric("independent_events", len(crossings), "events"),
        ),
        inputs=(*inputs, tuple(crossings)),
    )


_MHQ_MQ = (
    "5.5",
    "5.2",
    "4.7",
    "5.4",
    "5.6",
    "5.1",
    "8.7",
    "9.9",
    "10.2",
    "9.2",
    "7.3",
    "9.7",
    "7.3",
    "14.9",
    "11.4",
    "8.7",
)
_MHQ_SPECIFIC = (291, 297, 259, 257, 253, 225, 456, 411, 272, 139, 161, 145, 348, 706, 418, 257)


@dataclass(frozen=True)
class ReferenceFloodMagnitude:
    flow: Flow
    source: str
    inputs: tuple[object, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.flow, Flow):
            raise TypeError("MHQ is an annual maximum daily-mean statistic")
        _text(self.source)


def estimate_mhq_from_mean(mean_flow: Flow, regime_type: int) -> ReferenceFloodMagnitude:
    if not isinstance(mean_flow, Flow):
        raise TypeError("mean discharge requires interval-mean Flow")
    _regime(regime_type)
    return ReferenceFloodMagnitude(
        Flow(mean_flow.value * Fraction(_MHQ_MQ[regime_type - 1])), SOURCE + " Table 4", (mean_flow, regime_type)
    )


def estimate_mhq_from_area(area: Area, regime_type: int) -> ReferenceFloodMagnitude:
    _regime(regime_type)
    return ReferenceFloodMagnitude(
        Flow(area.value / 1000000 * _MHQ_SPECIFIC[regime_type - 1], "l/s"), SOURCE + " Table 5", (area, regime_type)
    )


def observed_mhq(samples: tuple[FlowSample, ...]) -> ReferenceFloodMagnitude:
    """Arithmetic mean of annual daily maxima, complete calendar years only."""
    check_flow_intervals(samples)
    ordered = sorted(samples, key=lambda s: s.interval.start)
    maxima: dict[int, Fraction] = {}
    for s in ordered:
        if (
            s.presence is not Presence.PRESENT
            or s.coverage is not Coverage.COMPLETE
            or interval_use(s) is IntervalUse.EXCLUDED_WARMUP
            or s.value is None
            or s.interval.seconds != 86400
            or any(
                (s.interval.start.hour, s.interval.start.minute, s.interval.start.second, s.interval.start.microsecond)
            )
        ):
            raise ValueError("MHQ requires complete daily means")
        maxima[s.interval.start.year] = max(maxima.get(s.interval.start.year, Fraction()), s.value.value)
    if any(a.interval.end != b.interval.start for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError("MHQ refuses missing days")
    for d in (ordered[0].interval.start, ordered[-1].interval.end):
        if (d.month, d.day) != (1, 1):
            raise ValueError("MHQ requires complete calendar years")
    return ReferenceFloodMagnitude(Flow(sum(maxima.values(), Fraction()) / len(maxima)), SOURCE + " §3.5.1", samples)


def stormwater_frequency(context: AssessmentContext, frequency: EventFrequency | None) -> IndicatorResult:
    if frequency is None:
        return _result(
            context, Indicator.STORMWATER, None, (), (frequency,), ("additional stormwater event frequency missing",)
        )
    cls = next((i for i, bound in enumerate((Fraction(1, 5), 2, 4, 8), 1) if frequency.value < bound), 5)
    return _result(
        context,
        Indicator.STORMWATER,
        cls,
        (Metric("additional_stormwater_frequency", frequency.value, "events/year"),),
        (frequency,),
    )


@dataclass(frozen=True)
class StormwaterEvent:
    """One identified drainage discharge event, not a receiving-river natural flood."""

    identifier: str
    at: datetime
    peak: InstantaneousDischarge
    source: str

    def __post_init__(self) -> None:
        _text(self.identifier)
        _text(self.source)
        if not isinstance(self.peak, InstantaneousDischarge):
            raise TypeError("stormwater peak requires instantaneous discharge")
        if self.at.tzinfo is None or self.at.utcoffset() is None:
            raise ValueError("stormwater timestamp requires timezone")
        object.__setattr__(self, "at", self.at.astimezone(UTC))


def stormwater_events(
    context: AssessmentContext,
    events: tuple[StormwaterEvent, ...],
    receiving_mq: Flow | None,
    reference_mhq: Flow | ReferenceFloodMagnitude | None,
    support: EventSupport,
) -> IndicatorResult:
    """§3.7.9 counts drainage peaks with MQ_receiving + Q_E > Q*, not natural peaks."""
    if not isinstance(support, EventSupport):
        raise TypeError("stormwater coverage requires EventSupport")
    if receiving_mq is not None and not isinstance(receiving_mq, Flow):
        raise TypeError("receiving mean discharge requires interval-mean Flow")
    if len({e.identifier for e in events}) != len(events):
        raise ValueError("duplicate stormwater events")
    if any(not context.period.start <= e.at < context.period.end for e in events):
        raise ValueError("stormwater event outside calendar window")
    years = _years(context)
    inputs = (events, receiving_mq, reference_mhq, support)
    mhq = _mhq_flow(reference_mhq)
    if support is not EventSupport.COMPLETE or years is None or receiving_mq is None or mhq is None:
        return _result(
            context,
            Indicator.STORMWATER,
            None,
            (),
            inputs,
            ("complete annual drainage-event evidence and MQ/MHQ reference required",),
        )
    threshold = mhq.value * Fraction(3, 5)
    count = sum(receiving_mq.value + e.peak.value > threshold for e in events)
    result = stormwater_frequency(context, EventFrequency(Fraction(count, years), SOURCE + " §3.7.9"))
    return replace(
        result,
        inputs=inputs,
        metrics=(
            *result.metrics,
            Metric("additional_events", count, "events"),
            Metric("flood_threshold", threshold, "m3/s"),
        ),
    )


@dataclass(frozen=True)
class RainfallFrequency:
    """Specialist IDF relationship point at the supplied concentration duration."""

    intensity_m_s: Fraction
    duration_seconds: Fraction
    return_period_years: Fraction
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        for name in ("intensity_m_s", "duration_seconds", "return_period_years"):
            value = finite_number(getattr(self, name))
            if value <= 0:
                raise ValueError("rainfall intensity, duration and return period must be positive")
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class DrainageResponse:
    area: Area
    peak_coefficient: Fraction
    concentration_seconds: Fraction
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        if not isinstance(self.area, Area) or self.area.value <= 0:
            raise ValueError("drained area must be a positive Area")
        coefficient = finite_number(self.peak_coefficient)
        duration = finite_number(self.concentration_seconds)
        if not 0 < coefficient <= 1 or duration <= 0:
            raise ValueError("drainage coefficient must be in (0,1], concentration duration positive")
        object.__setattr__(self, "peak_coefficient", coefficient)
        object.__setattr__(self, "concentration_seconds", duration)


def stormwater_rainfall(
    context: AssessmentContext,
    receiving_mq: Flow,
    reference_mhq: Flow | ReferenceFloodMagnitude,
    drainage: DrainageResponse,
    rainfall: RainfallFrequency | None,
) -> IndicatorResult:
    """GEP inverse rainfall equation; supplied IDF point avoids inventing a rainfall curve."""
    if not isinstance(receiving_mq, Flow):
        raise TypeError("receiving mean discharge requires interval-mean Flow")
    mhq = _mhq_flow(reference_mhq)
    if mhq is None:
        raise TypeError("rainfall inversion requires a reference MHQ")
    intensity = (mhq.value * Fraction(3, 5) - receiving_mq.value) / (drainage.area.value * drainage.peak_coefficient)
    metrics = (Metric("critical_rainfall_intensity", intensity, "m/s"),)
    inputs = (receiving_mq, reference_mhq, drainage, rainfall)
    if (
        intensity <= 0
        or rainfall is None
        or rainfall.intensity_m_s != intensity
        or rainfall.duration_seconds != drainage.concentration_seconds
    ):
        return _result(
            context,
            Indicator.STORMWATER,
            None,
            metrics,
            inputs,
            ("positive critical intensity and matching specialist IDF intensity/duration required",),
        )
    result = stormwater_frequency(context, EventFrequency(1 / rainfall.return_period_years, rainfall.source))
    return replace(result, metrics=(*metrics, *result.metrics), inputs=inputs)
