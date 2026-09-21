"""assess_hydrology : LocatedIndicatorResults → HydrologicalCondition (pure).

HYDMOD-F (BAFU 2011) is a hydrological screening method, not a prescribed
release, ecological certification, or legal compliance finding.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from fractions import Fraction

from fishy.evidence import Completeness, EvidenceFindings, Provenance
from fishy.quantities import finite_number
from fishy.spatial import Location
from fishy.time import Interval

MANUAL = "BAFU 2011, Methoden zur Untersuchung und Beurteilung der Fliessgewässer: Hydrologie – Abflussregime Stufe F"
MANUAL_SHA256 = "1fddd85c31265a7474d566bb7faab6bbacf571a6428f8702942b1ee1ec987bc2"


class Indicator(StrEnum):
    MEAN_FLOW = "mean_flow"
    FLOOD_FREQUENCY = "flood_frequency"
    FLOOD_SEASONALITY = "flood_seasonality"
    LOW_FLOW_MAGNITUDE = "low_flow_magnitude"
    LOW_FLOW_SEASONALITY = "low_flow_seasonality"
    LOW_FLOW_DURATION = "low_flow_duration"
    HYDROPEAKING = "hydropeaking"
    FLUSHING = "flushing"
    STORMWATER = "stormwater"


class HydrologyClass(IntEnum):
    HIGH = 1
    GOOD = 2
    MODERATE = 3
    POOR = 4
    BAD = 5


class AssessmentState(StrEnum):
    ASSESSED = "assessed"
    SCREENED = "screened"
    UNDETERMINED = "undetermined"
    NOT_APPLICABLE = "not_applicable"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} requires nonempty text")


@dataclass(frozen=True)
class AssessmentContext:
    location: Location
    period: Interval
    provenance: Provenance
    evidence: tuple[EvidenceFindings, ...] = ()

    def __post_init__(self) -> None:
        for name, kind in (("location", Location), ("period", Interval), ("provenance", Provenance)):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"{name} requires {kind.__name__}")
        if not isinstance(self.evidence, tuple) or any(not isinstance(e, EvidenceFindings) for e in self.evidence):
            raise TypeError("evidence requires immutable EvidenceFindings")


@dataclass(frozen=True)
class Metric:
    name: str
    value: Fraction | float | int
    unit: str

    def __post_init__(self) -> None:
        _text(self.name, "metric name")
        _text(self.unit, "metric unit")
        finite_number(self.value)


@dataclass(frozen=True)
class IndicatorResult:
    indicator: Indicator
    context: AssessmentContext
    state: AssessmentState
    classification: HydrologyClass | None
    metrics: tuple[Metric, ...]
    source: str
    reasons: tuple[str, ...] = ()
    inputs: tuple[object, ...] = ()
    coverage: Completeness = Completeness.COMPLETE

    def __post_init__(self) -> None:
        for name, kind in (("indicator", Indicator), ("context", AssessmentContext), ("state", AssessmentState)):
            if not isinstance(getattr(self, name), kind):
                raise TypeError(f"{name} requires {kind.__name__}")
        if self.classification is not None and not isinstance(self.classification, HydrologyClass):
            raise TypeError("classification requires HydrologyClass")
        if not isinstance(self.coverage, Completeness):
            raise TypeError("coverage requires Completeness")
        if self.classification is None:
            object.__setattr__(self, "coverage", Completeness.INCOMPLETE)
        if self.state in (AssessmentState.ASSESSED, AssessmentState.SCREENED):
            if self.classification is None:
                raise ValueError("assessed/screened result requires a class")
        elif self.classification is not None:
            raise ValueError("unassessed results cannot assert a class")
        if self.state is AssessmentState.SCREENED and self.classification is not HydrologyClass.HIGH:
            raise ValueError("source screening supplies only class 1")
        if not isinstance(self.metrics, tuple) or any(not isinstance(m, Metric) for m in self.metrics):
            raise TypeError("metrics requires immutable Metric records")
        if len({m.name for m in self.metrics}) != len(self.metrics):
            raise ValueError("duplicate metric names")
        _text(self.source, "method source")
        if not isinstance(self.reasons, tuple) or not isinstance(self.inputs, tuple):
            raise TypeError("reasons and inputs require tuples")
        for reason in self.reasons:
            _text(reason, "reason")
        if self.state is not AssessmentState.ASSESSED and not self.reasons:
            raise ValueError("screened/unassessed results require an attributable reason")


@dataclass(frozen=True)
class HydrologicalCondition:
    context: AssessmentContext
    indicators: tuple[IndicatorResult, ...]
    classification: HydrologyClass | None
    points: int
    worst: HydrologyClass | None
    completeness: Completeness
    reasons: tuple[str, ...]
    source: str = MANUAL + ", §6.4, Figure 33"


def overall_class(worst: HydrologyClass, points: int) -> HydrologyClass:
    """The Figure 33 matrix; this low-level operation does not imply coverage."""
    if not isinstance(worst, HydrologyClass):
        raise TypeError("worst requires HydrologyClass")
    if not isinstance(points, int) or isinstance(points, bool) or points < 9:
        raise ValueError("nine indicators contribute at least nine points")
    if worst is HydrologyClass.HIGH:
        if points != 9:
            raise ValueError("nine class-1 indicators total nine points")
        return HydrologyClass.HIGH
    worst_points = {HydrologyClass.GOOD: 2, HydrologyClass.MODERATE: 4, HydrologyClass.POOR: 8, HydrologyClass.BAD: 12}[
        worst
    ]
    if not 8 + worst_points <= points <= 9 * worst_points:
        raise ValueError("point total incompatible with nine indicators and supplied worst class")
    bounds = {
        HydrologyClass.GOOD: ((11, HydrologyClass.HIGH),),
        HydrologyClass.MODERATE: ((13, HydrologyClass.HIGH), (15, HydrologyClass.GOOD)),
        HydrologyClass.POOR: ((17, HydrologyClass.GOOD), (23, HydrologyClass.MODERATE)),
        HydrologyClass.BAD: ((25, HydrologyClass.MODERATE), (31, HydrologyClass.POOR)),
    }
    for threshold, result in bounds[worst]:
        if points < threshold:
            return result
    return worst


def assess_hydrology(context: AssessmentContext, indicators: tuple[IndicatorResult, ...]) -> HydrologicalCondition:
    """Combine nine classes without hiding omitted/undetermined indicators.

    Supplied evidence remains separate; numerical classification never changes
    scientific adequacy or official admissibility. Missing inputs are materialised.
    """
    if not isinstance(context, AssessmentContext):
        raise TypeError("assessment requires AssessmentContext")
    if not isinstance(indicators, tuple) or any(not isinstance(r, IndicatorResult) for r in indicators):
        raise TypeError("indicators requires immutable IndicatorResult records")
    if len({r.indicator for r in indicators}) != len(indicators):
        raise ValueError("duplicate indicator results")
    for result in indicators:
        if result.context != context:
            raise ValueError("indicator context differs: location, period, scenario/member, version or evidence")
    supplied = {r.indicator: r for r in indicators}
    complete = tuple(
        supplied[i]
        if i in supplied
        else IndicatorResult(
            i,
            context,
            AssessmentState.UNDETERMINED,
            None,
            (),
            MANUAL + ", §6.4",
            ("required indicator not supplied",),
        )
        for i in Indicator
    )
    classes = tuple(r.classification for r in complete if r.classification is not None)
    point_values = {
        HydrologyClass.HIGH: 1,
        HydrologyClass.GOOD: 2,
        HydrologyClass.MODERATE: 4,
        HydrologyClass.POOR: 8,
        HydrologyClass.BAD: 12,
    }
    points = sum(point_values[c] for c in classes)
    worst = max(classes) if classes else None
    all_classes = len(classes) == len(Indicator)
    coverage = (
        Completeness.COMPLETE
        if all_classes and all(r.coverage is Completeness.COMPLETE for r in complete)
        else Completeness.INCOMPLETE
    )
    reasons: tuple[str, ...] = ()
    classification = None
    if all_classes:
        if coverage is Completeness.INCOMPLETE:
            reasons = ("assessed classes retain incomplete input coverage",)
        assert worst is not None
        classification = overall_class(worst, points)
        pulse = supplied[Indicator.HYDROPEAKING].classification
        if pulse is not None and pulse > classification:
            classification = pulse
            reasons += ("hydropeaking overrides Figure 33 matrix class",)
    elif classes.count(HydrologyClass.BAD) >= 2:
        classification = HydrologyClass.BAD
        reasons = ("two known class-5 indicators determine class 5 despite incomplete coverage",)
    else:
        reasons = ("required indicator coverage incomplete",)
    return HydrologicalCondition(context, complete, classification, points, worst, coverage, reasons)
