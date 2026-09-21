"""pulse_condition : AttributedPulseObservations | OperatingPulseEstimates → IndicatorResult (pure).

BAFU 2011 §§3.7, 5.8–5.9. Figures 25/27 are digitised from the original
embedded raster. Classification refuses shared edges, transcription uncertainty,
and off-plot values. Linear quantiles use position (n-1)*p, a declared numerical
convention, not a source-mandated interpolation rule. No ecological certification.
"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from fractions import Fraction
from math import log10
from zoneinfo import ZoneInfo

from fishy.flow_events import InstantaneousDischarge
from fishy.flows import Presence
from fishy.hydrological_condition import (
    MANUAL,
    AssessmentContext,
    AssessmentState,
    HydrologyClass,
    Indicator,
    IndicatorResult,
    Metric,
)
from fishy.quantities import Area, Flow, SignedState, StateVariable, finite_number
from fishy.time import Interval


@dataclass(frozen=True)
class StageRate:
    """Magnitude of a stage rate in cm/min, never a discharge rate."""

    cm_per_minute: Fraction

    def __post_init__(self) -> None:
        object.__setattr__(self, "cm_per_minute", finite_number(self.cm_per_minute))
        if self.cm_per_minute < 0:
            raise ValueError("negative rate magnitude")


def _text(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("attributable source/evidence required")


@dataclass(frozen=True)
class HydropeakingMetrics:
    peak: InstantaneousDischarge
    trough: InstantaneousDischarge
    daily_ratio_quantile: Fraction | None
    rise: StageRate | None
    fall: StageRate | None
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        if not isinstance(self.peak, InstantaneousDischarge) or not isinstance(self.trough, InstantaneousDischarge):
            raise TypeError("peak/trough require instantaneous discharge")
        if self.peak.value < self.trough.value:
            raise ValueError("peak below trough")
        if self.daily_ratio_quantile is not None:
            object.__setattr__(self, "daily_ratio_quantile", finite_number(self.daily_ratio_quantile))
            if self.daily_ratio_quantile < 1:
                raise ValueError("daily maximum/minimum ratio below one")
        for rate in (self.rise, self.fall):
            if rate is not None and not isinstance(rate, StageRate):
                raise TypeError("stage rate required")


@dataclass(frozen=True)
class HydropeakingOperation:
    turbine_capacity: InstantaneousDischarge
    residual: InstantaneousDischarge
    rise: StageRate | None
    fall: StageRate | None
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        if not all(isinstance(x, InstantaneousDischarge) for x in (self.turbine_capacity, self.residual)):
            raise TypeError("operating discharges must be instantaneous")


@dataclass(frozen=True)
class PulseObservation:
    time: datetime
    discharge: InstantaneousDischarge | None
    stage: SignedState | None
    source: str
    presence: Presence | None = None

    def __post_init__(self) -> None:
        _text(self.source)
        # Compatibility for the original four-argument observation constructor.
        # Parsing occurs once; every constructed record has an explicit Presence.
        if self.presence is None:
            object.__setattr__(self, "presence", Presence.PRESENT if self.discharge is not None else Presence.MISSING)
        if not isinstance(self.presence, Presence):
            raise TypeError("discharge presence requires Presence")
        if self.presence is Presence.PRESENT and self.discharge is None:
            raise ValueError("present discharge requires a value")
        if (
            self.presence in (Presence.MISSING, Presence.ABSENT, Presence.OUTSIDE_HORIZON)
            and self.discharge is not None
        ):
            raise ValueError("missing/outside discharge cannot carry a value")
        if self.presence is Presence.DRY:
            raise ValueError("dry undefined is not a discharge state; use present zero")
        if self.time.tzinfo is None or self.time.utcoffset() is None:
            raise ValueError("observation requires timezone")
        if self.discharge is not None and not isinstance(self.discharge, InstantaneousDischarge):
            raise TypeError("interval mean cannot represent instantaneous discharge")
        if self.stage is not None and (
            not isinstance(self.stage, SignedState) or self.stage.variable is not StateVariable.STAGE
        ):
            raise TypeError("stage required, not discharge or velocity")


@dataclass(frozen=True)
class PulseSampling:
    """Ten Monday-starting calendar weeks in each of five representative years.

    Weeks need not be consecutive. The caller supplies low-flow and operating
    representativeness evidence. Resolution is explicit, never inferred from gaps.
    """

    week_starts: tuple[date, ...]
    timezone: ZoneInfo
    cadence: timedelta
    low_flow_evidence: str
    operating_regime_evidence: str

    def __post_init__(self) -> None:
        _text(self.low_flow_evidence)
        _text(self.operating_regime_evidence)
        if not isinstance(self.timezone, ZoneInfo):
            raise TypeError("calendar timezone requires ZoneInfo")
        if not isinstance(self.week_starts, tuple) or len(set(self.week_starts)) != len(self.week_starts):
            raise ValueError("unique calendar weeks required")
        if any(d.weekday() != 0 for d in self.week_starts):
            raise ValueError("calendar weeks start Monday")
        years = {d.isocalendar().year for d in self.week_starts}
        if len(years) != 5 or any(sum(d.isocalendar().year == y for d in self.week_starts) != 10 for y in years):
            raise ValueError("ten calendar weeks in each of five selected years required")
        seconds = self.cadence.total_seconds()
        if seconds <= 0 or seconds >= 86400 or 86400 % seconds:
            raise ValueError("explicit subdaily cadence dividing a day required")


def _interpolate(value: Fraction, knots: tuple[tuple[Fraction, Fraction], ...]) -> Fraction:
    if value <= knots[0][0]:
        return knots[0][1]
    for (x0, y0), (x1, y1) in zip(knots, knots[1:], strict=False):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return knots[-1][1]


def stage_correction(rate: StageRate) -> Fraction:
    return _interpolate(
        rate.cm_per_minute,
        (
            (Fraction(1, 2), Fraction(65, 100)),
            (Fraction(1), Fraction(3, 4)),
            (Fraction(2), Fraction(1)),
            (Fraction(4), Fraction(3, 2)),
        ),
    )


def catchment_correction(area: Area) -> Fraction:
    if not isinstance(area, Area) or area.value <= 0:
        raise ValueError("positive typed catchment area required")
    return _interpolate(
        area.value / 1_000_000,
        ((Fraction(250), Fraction(1, 2)), (Fraction(750), Fraction(3, 4)), (Fraction(1250), Fraction(1))),
    )


def _quantile(values: list[Fraction], p: Fraction) -> Fraction:
    values = sorted(values)
    pos = (len(values) - 1) * p
    i = pos.numerator // pos.denominator
    return values[i] if i == len(values) - 1 else values[i] + (values[i + 1] - values[i]) * (pos - i)


# Derived boundary ordinates, sampled every ten native raster pixels. No source
# image is distributed. Four upper class edges, left to right. Axis calibration:
# Fig25 x pixels 71..762 -> 0..3.25; y 423..9 -> 1..7.
# Fig27 x pixels 59..755 -> log10(x) -1..2; y 413..11 -> log10(f) -1..2.
# Fig27 coloured plot starts at y43 (about 60/year); gray is not a class.
# Explicit calibrated endpoint ordinates are transcribed from the adjacent
# interior colour pixels (within the same ±2-pixel precision); axes themselves
# are antialiased black/white. Interpolation spans endpoints without clamping.
_PEAK_EDGES = (
    (71.0, (353.5, 284.75, 198.0, 77.5)),
    (73.0, (353.5, 284.5, 198.0, 77.5)),
    (83.0, (354.0, 284.5, 198.0, 77.5)),
    (93.0, (353.5, 284.5, 198.0, 77.5)),
    (103.0, (354.0, 284.5, 198.0, 77.5)),
    (113.0, (353.5, 285.0, 198.0, 77.5)),
    (123.0, (353.5, 285.0, 198.0, 77.5)),
    (133.0, (354.5, 286.0, 200.5, 81.5)),
    (143.0, (356.0, 288.0, 203.0, 85.5)),
    (153.0, (357.5, 290.0, 205.5, 89.5)),
    (163.0, (358.5, 291.5, 208.5, 93.5)),
    (173.0, (360.0, 293.0, 211.0, 97.5)),
    (183.0, (361.5, 295.0, 213.5, 101.5)),
    (193.0, (362.5, 297.0, 216.0, 105.5)),
    (203.0, (364.0, 298.5, 219.0, 110.5)),
    (213.0, (365.5, 300.0, 221.5, 114.5)),
    (223.0, (366.5, 302.0, 224.5, 118.5)),
    (233.0, (367.5, 304.0, 227.0, 122.5)),
    (243.0, (369.0, 305.5, 229.5, 126.5)),
    (253.0, (370.5, 307.5, 232.5, 130.5)),
    (263.0, (371.5, 309.0, 235.0, 134.5)),
    (273.0, (373.0, 311.0, 237.5, 138.5)),
    (283.0, (374.5, 313.0, 240.0, 142.5)),
    (293.0, (375.5, 314.5, 243.0, 146.5)),
    (303.0, (377.0, 316.0, 245.5, 151.5)),
    (313.0, (378.0, 318.0, 248.5, 155.5)),
    (323.0, (379.5, 320.0, 251.0, 159.5)),
    (333.0, (380.5, 321.5, 254.0, 163.5)),
    (343.0, (382.0, 323.5, 256.5, 167.5)),
    (353.0, (383.5, 325.0, 259.5, 171.5)),
    (363.0, (384.5, 327.0, 262.0, 176.0)),
    (373.0, (386.0, 328.5, 264.5, 180.5)),
    (383.0, (387.5, 330.5, 267.5, 184.5)),
    (393.0, (388.5, 332.0, 270.0, 188.5)),
    (403.0, (390.5, 334.0, 272.5, 192.5)),
    (413.0, (392.0, 335.5, 275.5, 196.5)),
    (423.0, (393.5, 337.5, 278.0, 200.5)),
    (433.0, (395.0, 339.0, 280.5, 204.5)),
    (443.0, (396.5, 341.0, 283.5, 209.5)),
    (453.0, (397.0, 343.0, 285.5, 213.5)),
    (463.0, (397.5, 344.5, 288.5, 217.5)),
    (473.0, (397.5, 346.0, 291.0, 221.5)),
    (483.0, (398.0, 348.0, 293.5, 225.5)),
    (493.0, (398.5, 350.0, 296.5, 229.5)),
    (503.0, (398.5, 351.5, 299.0, 233.5)),
    (513.0, (399.0, 353.5, 301.5, 238.0)),
    (523.0, (399.5, 355.0, 304.5, 242.5)),
    (533.0, (399.5, 357.0, 307.0, 246.5)),
    (543.0, (400.0, 358.5, 309.5, 250.5)),
    (553.0, (400.5, 360.5, 312.5, 255.0)),
    (563.0, (400.5, 362.0, 315.0, 259.5)),
    (573.0, (401.0, 364.0, 317.5, 263.5)),
    (583.0, (401.5, 366.0, 320.5, 267.5)),
    (593.0, (401.5, 367.5, 323.0, 271.5)),
    (603.0, (402.0, 369.0, 325.5, 275.5)),
    (613.0, (402.5, 371.0, 328.5, 279.5)),
    (623.0, (402.5, 373.0, 331.0, 283.5)),
    (633.0, (403.0, 374.5, 333.5, 287.5)),
    (643.0, (403.5, 376.0, 336.5, 292.5)),
    (653.0, (403.5, 378.0, 339.0, 296.5)),
    (663.0, (404.0, 380.0, 341.5, 300.5)),
    (673.0, (404.5, 381.5, 344.5, 304.5)),
    (683.0, (404.5, 383.5, 347.0, 308.5)),
    (693.0, (405.0, 385.0, 349.5, 312.5)),
    (703.0, (405.0, 387.0, 352.0, 316.5)),
    (713.0, (405.5, 389.0, 354.0, 321.0)),
    (723.0, (405.5, 390.5, 357.5, 325.5)),
    (733.0, (405.5, 392.0, 360.0, 329.5)),
    (743.0, (405.5, 394.0, 362.5, 333.5)),
    (753.0, (405.5, 396.0, 365.5, 337.5)),
    (762.0, (405.5, 397.0, 367.5, 340.5)),
)
_FLUSH_EDGES = (
    (59.0, (76.5, 44.75, 43.0, 43.0)),
    (61.0, (76.5, 45.0, 43, 43)),
    (71.0, (79.5, 47.5, 43, 43)),
    (81.0, (82.5, 50.0, 43, 43)),
    (91.0, (85.5, 53.0, 43, 43)),
    (101.0, (88.5, 56.0, 43, 43)),
    (111.0, (91.5, 59.0, 43, 43)),
    (121.0, (93.5, 61.5, 43, 43)),
    (131.0, (96.75, 64.75, 43.0, 43.0)),
    (141.0, (99.5, 66.5, 43, 43)),
    (151.0, (102.5, 70.0, 43, 43)),
    (161.0, (105.5, 72.5, 43, 43)),
    (171.0, (109.0, 76.0, 43.5, 43)),
    (181.0, (111.5, 78.5, 46.0, 43)),
    (191.0, (114.5, 82.0, 48.5, 43)),
    (201.0, (117.75, 83.25, 50.75, 43.0)),
    (211.0, (120.5, 87.0, 53.0, 43)),
    (221.0, (123.5, 89.75, 56.0, 43.0)),
    (231.0, (129.0, 94.5, 61.0, 43)),
    (241.0, (135.0, 101.0, 66.5, 43)),
    (251.0, (140.0, 105.5, 71.5, 43)),
    (261.0, (146.0, 111.0, 77.0, 43)),
    (271.0, (152.0, 117.0, 82.0, 43)),
    (281.0, (157.25, 122.75, 87.75, 43.0)),
    (291.0, (163.0, 128.0, 93.0, 48.5)),
    (301.0, (167.5, 133.0, 97.5, 53.0)),
    (311.0, (173.5, 139.0, 102.5, 58.5)),
    (321.0, (179.0, 144.0, 107.5, 64.0)),
    (331.0, (184.5, 149.5, 112.5, 69.5)),
    (341.0, (190.0, 155.0, 118.5, 74.5)),
    (351.0, (195.5, 161.0, 123.5, 80.5)),
    (361.0, (201.5, 167.0, 129.0, 86.5)),
    (371.0, (206.5, 172.0, 134.0, 90.5)),
    (381.0, (212.0, 176.5, 139.0, 95.5)),
    (391.0, (217.5, 183.0, 144.5, 101.5)),
    (401.0, (222.5, 187.5, 149.0, 105.5)),
    (411.0, (228.5, 193.0, 154.5, 111.5)),
    (421.0, (234.5, 199.0, 159.0, 117.5)),
    (431.0, (240.75, 204.75, 166.0, 123.0)),
    (441.0, (251.0, 210.0, 170.5, 128.5)),
    (451.0, (261.0, 215.5, 176.0, 132.5)),
    (461.0, (272.5, 225.0, 181.0, 138.5)),
    (471.0, (282.5, 235.75, 186.5, 144.0)),
    (481.0, (292.5, 246.0, 196.5, 149.5)),
    (491.0, (304.0, 257.0, 207.5, 157.5)),
    (501.0, (315.5, 268.0, 220.0, 168.5)),
    (511.0, (324.0, 277.0, 228.5, 177.5)),
    (521.0, (337.25, 287.5, 240.75, 186.75)),
    (531.0, (354.0, 299.5, 252.5, 199.0)),
    (541.0, (370.0, 309.5, 263.5, 210.5)),
    (551.0, (386.0, 320.5, 274.5, 220.5)),
    (561.0, (402.0, 337.0, 285.0, 231.5)),
    (571.0, (413, 354.0, 296.0, 242.0)),
    (581.0, (413, 371.0, 309.5, 252.5)),
    (591.0, (413, 386.0, 325.0, 262.5)),
    (601.0, (413, 405.0, 344.0, 274.5)),
    (611.0, (413, 413, 360.0, 285.0)),
    (621.0, (413, 413, 376.0, 300.5)),
    (631.0, (413, 413, 392.5, 320.0)),
    (641.0, (413, 413, 409.0, 336.5)),
    (651.0, (413, 413, 413, 354.5)),
    (661.0, (413.0, 413.0, 413.0, 369.0)),
    (671.0, (413, 413, 413, 388.5)),
    (681.0, (413, 413, 413, 406.5)),
    (691.0, (413, 413, 413, 413)),
    (701.0, (413.0, 413.0, 413.0, 413.0)),
    (711.0, (413, 413, 413, 413)),
    (721.0, (413.0, 413.0, 413.0, 413.0)),
    (731.0, (413.0, 413.0, 413.0, 413.0)),
    (741.0, (413, 413, 413, 413)),
    (751.0, (413, 413, 413, 413)),
    (755.0, (413.0, 413.0, 413.0, 413.0)),
)


def _graph(x: float, y: float, indicator: Indicator) -> tuple[HydrologyClass | None, tuple[str, ...]]:
    if indicator is Indicator.HYDROPEAKING:
        if not (0 <= x <= 3.25 and 1 <= y <= 7):
            return None, ("outside Figure 25 graphical domain",)
        px, py = 71 + x * 691 / 3.25, 423 - (y - 1) * 414 / 6
        edges = _PEAK_EDGES
    else:
        if not (0.1 <= x <= 100 and 0.1 <= y < 60):
            return None, ("outside Figure 27 coloured graphical domain (0.1≤frequency<60/year)",)
        px, py = 59 + (log10(x) + 1) * 696 / 3, 413 - (log10(y) + 1) * 402 / 3
        edges = _FLUSH_EDGES

    def limits(pixel: float) -> tuple[float, ...]:
        if not edges[0][0] <= pixel <= edges[-1][0]:
            raise ValueError("boundary interpolation outside calibrated plot")
        for (x0, ys0), (x1, ys1) in zip(edges, edges[1:], strict=False):
            if pixel <= x1:
                t = (pixel - x0) / (x1 - x0)
                return tuple(a + (b - a) * t for a, b in zip(ys0, ys1, strict=True))
        raise AssertionError("calibrated endpoint missing")

    # Intersect the ±2-pixel transcription rectangle with the plotted domain.
    # This clips the uncertainty region, not the metric or boundary ordinates.
    low, high = max(edges[0][0], px - 2), min(edges[-1][0], px + 2)
    for left, right in zip(limits(low), limits(high), strict=True):
        if min(left, right) - 2 <= py <= max(left, right) + 2:
            return None, ("shared boundary or class ambiguity at ±2 native pixels transcription precision",)
    classification = HydrologyClass(1 + sum(py < edge for edge in limits(px)))
    return classification, ()


def _result(
    context: AssessmentContext,
    indicator: Indicator,
    metrics: tuple[Metric, ...],
    inputs: tuple[object, ...],
    classification: HydrologyClass | None = None,
    reasons: tuple[str, ...] = (),
) -> IndicatorResult:
    return IndicatorResult(
        indicator,
        context,
        AssessmentState.ASSESSED if classification is not None else AssessmentState.UNDETERMINED,
        classification,
        metrics,
        MANUAL + ", §§3.7,5.8–5.9; Figures25/27; ±2 native pixels; linear (n−1)p quantiles",
        reasons,
        inputs,
    )


def assess_hydropeaking(
    context: AssessmentContext, pulse: HydropeakingMetrics | None, reference_mean: Flow, area: Area
) -> IndicatorResult:
    inputs = (pulse, reference_mean, area)
    if reference_mean.value <= 0:
        return _result(
            context, Indicator.HYDROPEAKING, (), inputs, reasons=("zero reference mean: stress ratio undefined",)
        )
    if pulse is None:
        return _result(context, Indicator.HYDROPEAKING, (), inputs, reasons=("hydropeaking metrics missing",))
    k_area = catchment_correction(area)
    stress = pulse.peak.value / reference_mean.value * k_area
    metrics = (
        Metric("peak", pulse.peak.value, "m3/s"),
        Metric("trough", pulse.trough.value, "m3/s"),
        Metric("catchment_correction", k_area, "1"),
        Metric("hydraulic_stress", stress, "1"),
    )
    if pulse.daily_ratio_quantile is None or pulse.rise is None or pulse.fall is None:
        return _result(
            context,
            Indicator.HYDROPEAKING,
            metrics,
            inputs,
            reasons=("daily ratio or stage-rate evidence missing/undefined; discharge rate cannot substitute",),
        )
    k_rate = stage_correction(StageRate(max(pulse.rise.cm_per_minute, pulse.fall.cm_per_minute)))
    intensity = pulse.daily_ratio_quantile * k_rate
    metrics += (
        Metric("daily_ratio_quantile", pulse.daily_ratio_quantile, "1"),
        Metric("rise", pulse.rise.cm_per_minute, "cm/min"),
        Metric("fall", pulse.fall.cm_per_minute, "cm/min"),
        Metric("stage_correction", k_rate, "1"),
        Metric("pulse_intensity", intensity, "1"),
    )
    classification, reasons = _graph(float(stress), float(intensity), Indicator.HYDROPEAKING)
    return _result(context, Indicator.HYDROPEAKING, metrics, inputs, classification, reasons)


def estimate_hydropeaking(
    context: AssessmentContext, operation: HydropeakingOperation, reference_mean: Flow, area: Area
) -> IndicatorResult:
    peak = operation.turbine_capacity.value + operation.residual.value
    ratio = peak / operation.residual.value if operation.residual.value else None
    pulse = HydropeakingMetrics(
        InstantaneousDischarge(peak), operation.residual, ratio, operation.rise, operation.fall, operation.source
    )
    result = assess_hydropeaking(context, pulse, reference_mean, area)
    return replace(result, inputs=(operation,) + result.inputs)


def observe_hydropeaking(
    context: AssessmentContext,
    sampling: PulseSampling,
    observations: tuple[PulseObservation, ...],
    reference_mean: Flow,
    area: Area,
) -> IndicatorResult:
    inputs = (sampling, observations, reference_mean, area)
    if len({o.time for o in observations}) != len(observations):
        raise ValueError("duplicate pulse observation timestamps")
    lookup = {o.time: o for o in observations}
    maxima: list[Fraction] = []
    minima: list[Fraction] = []
    ratios: list[Fraction] = []
    rises: list[Fraction] = []
    falls: list[Fraction] = []
    flow_missing = stage_missing = False
    support_reasons: set[str] = set()
    excluded = context.provenance.excluded_warmup
    for week in sampling.week_starts:
        for offset in range(7):
            day = week + timedelta(days=offset)
            start = datetime.combine(day, datetime.min.time(), sampling.timezone).astimezone(UTC)
            end = datetime.combine(day + timedelta(days=1), datetime.min.time(), sampling.timezone).astimezone(UTC)
            if start < context.period.start or end > context.period.end:
                raise ValueError("sampling day outside assessment period")
            times = []
            current = start
            while current < end:
                times.append(current)
                current += sampling.cadence
            daily = [lookup.get(t) for t in times]
            flows = []
            for instant, observation in zip(times, daily, strict=True):
                if any(window.start <= instant < window.end for window in excluded):
                    support_reasons.add("instantaneous discharge intersects excluded warmup")
                elif observation is None:
                    support_reasons.add("missing instantaneous observation")
                elif observation.presence is not Presence.PRESENT:
                    assert observation.presence is not None
                    support_reasons.add("instantaneous discharge presence: " + observation.presence.value)
                else:
                    assert observation.discharge is not None
                    flows.append(observation.discharge.value)
            if len(flows) != len(times):
                flow_missing = True
            else:
                maxima.append(max(flows))
                minima.append(min(flows))
                if min(flows) > 0:
                    ratios.append(max(flows) / min(flows))
            rates = []
            for t in times:
                previous, now = lookup.get(t - sampling.cadence), lookup.get(t)
                if any(window.start <= t and t - sampling.cadence < window.end for window in excluded):
                    stage_missing = True
                    support_reasons.add("stage transition intersects excluded warmup")
                    continue
                if previous is None or now is None or previous.stage is None or now.stage is None:
                    stage_missing = True
                    continue
                if previous.stage.domain != now.stage.domain:
                    raise ValueError("stage datum/domain changed")
                rates.append(
                    (now.stage.value - previous.stage.value) * 6000 / finite_number(sampling.cadence.total_seconds())
                )
            if rates:
                rises.append(max(Fraction(0), max(rates)))
                falls.append(max(Fraction(0), -min(rates)))
    if flow_missing:
        return _result(
            context,
            Indicator.HYDROPEAKING,
            (),
            inputs,
            reasons=("missing instantaneous observations in selected calendar weeks",) + tuple(sorted(support_reasons)),
        )
    pulse = HydropeakingMetrics(
        InstantaneousDischarge(_quantile(maxima, Fraction(4, 5))),
        InstantaneousDischarge(_quantile(minima, Fraction(1, 5))),
        _quantile(ratios, Fraction(4, 5)) if len(ratios) == len(maxima) else None,
        StageRate(_quantile(rises, Fraction(1, 2))) if not stage_missing else None,
        StageRate(_quantile(falls, Fraction(1, 2))) if not stage_missing else None,
        sampling.operating_regime_evidence,
    )
    result = assess_hydropeaking(context, pulse, reference_mean, area)
    return replace(
        result,
        inputs=inputs + (pulse,),
        reasons=result.reasons
        + (("missing stage observation/predecessor",) if stage_missing else ())
        + tuple(sorted(support_reasons)),
    )


class FlushingTiming(StrEnum):
    HIGH_FLOW = "high_flow"
    MEAN_FLOW = "mean_flow"
    LOW_FLOW = "low_flow"


class HydropeakingApplicability(StrEnum):
    UNREVIEWED = "unreviewed"
    USE_HYDROPEAKING = "use_hydropeaking"
    RETAIN_FLUSHING = "retain_flushing"


@dataclass(frozen=True)
class HydropeakingReview:
    applicability: HydropeakingApplicability
    evidence: str

    def __post_init__(self) -> None:
        if not isinstance(self.applicability, HydropeakingApplicability):
            raise TypeError("typed applicability required")
        _text(self.evidence)


@dataclass(frozen=True)
class FlushingMetrics:
    excess: InstantaneousDischarge
    events_per_year: Fraction
    rise: StageRate | None
    timing: FlushingTiming | None
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        if not isinstance(self.excess, InstantaneousDischarge):
            raise TypeError("instantaneous excess required")
        object.__setattr__(self, "events_per_year", finite_number(self.events_per_year))
        if self.events_per_year < 0:
            raise ValueError("negative flushing frequency")
        if self.rise is not None and not isinstance(self.rise, StageRate):
            raise TypeError("stage rise rate required")
        if self.timing is not None and not isinstance(self.timing, FlushingTiming):
            raise TypeError("typed flushing timing required")


def assess_flushing(
    context: AssessmentContext,
    pulses: tuple[FlushingMetrics, ...],
    reference_mean: Flow,
    review: HydropeakingReview | None = None,
) -> IndicatorResult:
    inputs = (pulses, reference_mean, review)
    if not pulses or reference_mean.value == 0:
        return _result(
            context, Indicator.FLUSHING, (), inputs, reasons=("missing flushing types or zero reference mean",)
        )
    metrics: list[Metric] = []
    classes: list[HydrologyClass] = []
    reasons: list[str] = []
    for i, pulse in enumerate(pulses):
        prefix = f"type_{i}."
        metrics.extend(
            (
                Metric(prefix + "excess", pulse.excess.value, "m3/s"),
                Metric(prefix + "frequency", pulse.events_per_year, "1/year"),
            )
        )
        if pulse.events_per_year >= 60:
            reasons.append("frequency ≥60/year requires hydropeaking applicability review")
            if review is not None:
                reasons.append("supplied applicability: " + review.applicability.value + "; " + review.evidence)
        if pulse.rise is None or pulse.timing is None:
            reasons.append("missing flushing stage-rise/timing evidence")
            continue
        kt = {
            FlushingTiming.HIGH_FLOW: Fraction(3, 4),
            FlushingTiming.MEAN_FLOW: Fraction(1),
            FlushingTiming.LOW_FLOW: Fraction(3, 2),
        }[pulse.timing]
        kr = stage_correction(pulse.rise)
        stress = pulse.excess.value / reference_mean.value * kr * kt
        metrics.extend(
            (
                Metric(prefix + "stage_correction", kr, "1"),
                Metric(prefix + "timing_correction", kt, "1"),
                Metric(prefix + "hydraulic_stress", stress, "1"),
            )
        )
        classification, why = _graph(float(stress), float(pulse.events_per_year), Indicator.FLUSHING)
        reasons.extend(why)
        if classification is not None:
            classes.append(classification)
    # Unknown types cannot be averaged away. A known class5 fixes the worst class.
    classification = max(classes) if len(classes) == len(pulses) or HydrologyClass.BAD in classes else None
    if classification is None and not reasons:
        reasons.append("flushing classification unsupported")
    result = _result(context, Indicator.FLUSHING, tuple(metrics), inputs, classification, tuple(dict.fromkeys(reasons)))
    if len(classes) < len(pulses):
        from fishy.evidence import Completeness

        result = replace(result, coverage=Completeness.INCOMPLETE)
    return result


@dataclass(frozen=True)
class FlushingOperation:
    """Operating/concession estimate: peak minus base; mean stage rise to peak."""

    peak: InstantaneousDischarge
    base: InstantaneousDischarge
    base_stage: SignedState | None
    peak_stage: SignedState | None
    rise_duration: timedelta
    events_per_year: Fraction
    timing: FlushingTiming | None
    source: str

    def __post_init__(self) -> None:
        _text(self.source)
        if not all(isinstance(x, InstantaneousDischarge) for x in (self.peak, self.base)):
            raise TypeError("instantaneous operating discharges required")
        if self.peak.value < self.base.value or self.rise_duration <= timedelta(0):
            raise ValueError("invalid peak/base or rise duration")
        for stage in (self.base_stage, self.peak_stage):
            if stage is not None and (not isinstance(stage, SignedState) or stage.variable is not StateVariable.STAGE):
                raise TypeError("stage required")
        if (
            self.base_stage is not None
            and self.peak_stage is not None
            and self.base_stage.domain != self.peak_stage.domain
        ):
            raise ValueError("stage datum/domain changed")
        FlushingMetrics(
            InstantaneousDischarge(self.peak.value - self.base.value),
            self.events_per_year,
            None,
            self.timing,
            self.source,
        )


def estimate_flushing(
    context: AssessmentContext,
    operations: tuple[FlushingOperation, ...],
    reference_mean: Flow,
    review: HydropeakingReview | None = None,
) -> IndicatorResult:
    pulses = []
    for operation in operations:
        rate = None
        if operation.base_stage is not None and operation.peak_stage is not None:
            rate = StageRate(
                (operation.peak_stage.value - operation.base_stage.value)
                * 6000
                / finite_number(operation.rise_duration.total_seconds())
            )
        pulses.append(
            FlushingMetrics(
                InstantaneousDischarge(operation.peak.value - operation.base.value),
                operation.events_per_year,
                rate,
                operation.timing,
                operation.source,
            )
        )
    result = assess_flushing(context, tuple(pulses), reference_mean, review)
    return replace(result, inputs=(operations,) + result.inputs)


def observe_flushing(
    context: AssessmentContext,
    observations: tuple[PulseObservation, ...],
    events_per_year: Fraction,
    timing: FlushingTiming | None,
    reference_mean: Flow,
    source: str,
    review: HydropeakingReview | None = None,
) -> IndicatorResult:
    """One supplied typical event hydrograph; frequency from operating records.

    The first value is its pre-event base. Uses maximum positive stage change
    over actual elapsed time, not average rise and not discharge derivative.
    """
    _text(source)
    inputs = (observations, events_per_year, timing, reference_mean, source, review)
    if len(observations) < 2 or any(o.presence is not Presence.PRESENT for o in observations):
        unavailable = tuple(
            sorted(
                {
                    o.presence.value
                    for o in observations
                    if o.presence is not None and o.presence is not Presence.PRESENT
                }
            )
        )
        return _result(
            context,
            Indicator.FLUSHING,
            (),
            inputs,
            reasons=("missing/unsupported instantaneous flushing hydrograph",) + unavailable,
        )
    if any(b.time <= a.time for a, b in zip(observations, observations[1:], strict=False)):
        raise ValueError("event observations must be strictly time ordered")
    if any(not context.period.start <= o.time < context.period.end for o in observations):
        raise ValueError("event outside assessment period")
    if any(
        window.start <= observations[-1].time and observations[0].time < window.end
        for window in context.provenance.excluded_warmup
    ):
        return _result(
            context,
            Indicator.FLUSHING,
            (),
            inputs,
            reasons=("flushing observation/stage interval intersects excluded warmup",),
        )
    flows = [o.discharge.value for o in observations if o.discharge is not None]
    rates = []
    for a, b in zip(observations, observations[1:], strict=False):
        if a.stage is not None and b.stage is not None:
            if a.stage.domain != b.stage.domain:
                raise ValueError("stage datum/domain changed")
            rates.append(
                max(
                    Fraction(0),
                    (b.stage.value - a.stage.value) * 6000 / finite_number((b.time - a.time).total_seconds()),
                )
            )
    rate = StageRate(max(rates)) if len(rates) == len(observations) - 1 else None
    pulse = FlushingMetrics(InstantaneousDischarge(max(flows) - flows[0]), events_per_year, rate, timing, source)
    result = assess_flushing(context, (pulse,), reference_mean, review)
    return replace(result, inputs=inputs + (pulse,))


def estimate_hydropeaking_from_residuals(
    context: AssessmentContext,
    turbine_capacity: InstantaneousDischarge,
    concession_residuals: tuple[Flow, ...],
    intermediate_reference_q347: Flow,
    rise: StageRate | None,
    fall: StageRate | None,
    reference_mean: Flow,
    area: Area,
    source: str,
) -> IndicatorResult:
    """§3.7: QRest=sum(concession residuals)+intermediate reference Q347.

    Flow inputs retain their daily/reference-mean meaning; the estimated
    operating instantaneous residual is explicitly constructed, not relabelled
    as an observation.
    """
    if not isinstance(concession_residuals, tuple) or any(not isinstance(q, Flow) for q in concession_residuals):
        raise TypeError("immutable concession residual Flows required")
    if not isinstance(intermediate_reference_q347, Flow):
        raise TypeError("reference Q347 requires Flow")
    residual = sum((q.value for q in concession_residuals), intermediate_reference_q347.value)
    operation = HydropeakingOperation(turbine_capacity, InstantaneousDischarge(residual), rise, fall, source)
    result = estimate_hydropeaking(context, operation, reference_mean, area)
    return replace(result, inputs=(concession_residuals, intermediate_reference_q347) + result.inputs)


@dataclass(frozen=True)
class FlushingAnnualEvents:
    """Complete operating/concession event list for one calendar year.

    Each amount is peak minus pre-event base, not total peak. Completeness and
    site representativeness are supplied evidence, never inferred from count.
    """

    year: int
    excesses: tuple[InstantaneousDischarge, ...]
    source: str
    completeness_evidence: str
    event_type: str = "flushing"

    def __post_init__(self) -> None:
        _text(self.source)
        _text(self.completeness_evidence)
        _text(self.event_type)
        if isinstance(self.year, bool) or not isinstance(self.year, int) or not 1 <= self.year < 9999:
            raise ValueError("invalid calendar year")
        if not isinstance(self.excesses, tuple) or any(
            not isinstance(q, InstantaneousDischarge) for q in self.excesses
        ):
            raise TypeError("immutable instantaneous excesses required")

    @property
    def period(self) -> Interval:
        """Complete Gregorian operating year in explicitly declared UTC calendar."""
        return Interval(datetime(self.year, 1, 1, tzinfo=UTC), datetime(self.year + 1, 1, 1, tzinfo=UTC))


def assess_flushing_events(
    context: AssessmentContext,
    years: tuple[FlushingAnnualEvents, ...],
    selected_excess: InstantaneousDischarge,
    rise: StageRate | None,
    timing: FlushingTiming | None,
    reference_mean: Flow,
    source: str,
    review: HydropeakingReview | None = None,
) -> IndicatorResult:
    """§3.7.7: average annual count at or ABOVE selected extra discharge."""
    _text(source)
    if len({y.year for y in years}) != len(years):
        raise ValueError("duplicate operating years")
    if not years:
        return _result(
            context,
            Indicator.FLUSHING,
            (),
            (years, selected_excess, rise, timing, reference_mean, source, review),
            reasons=("annual operating event records missing",),
        )
    if len({year.event_type for year in years}) != 1:
        raise ValueError("one flushing event type per frequency/threshold combination required")
    for year in years:
        if year.period.start < context.period.start or year.period.end > context.period.end:
            raise ValueError("complete annual operating window outside assessment period")
    frequency = Fraction(sum(q.value >= selected_excess.value for year in years for q in year.excesses), len(years))
    pulse = FlushingMetrics(selected_excess, frequency, rise, timing, source)
    result = assess_flushing(context, (pulse,), reference_mean, review)
    return replace(result, inputs=(years,) + result.inputs)
