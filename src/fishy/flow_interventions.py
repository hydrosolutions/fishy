"""screen_intervention : Intervention × ReferenceDischarges → InterventionScreen (pure).

Inventory, reference eligibility and indicator selection implement HYDMOD-F §§2–4,
Tables 8–9 and §5.11. Screening is not ecological or official acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from hashlib import sha256

from fishy.evidence import (
    CheckFinding,
    CorrectionState,
    EvidenceFindings,
    EvidenceScope,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    permitted_use,
)
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
from fishy.time import Interval


class InterventionType(StrEnum):
    A1 = "A1"
    A2 = "A2"
    A3 = "A3"
    A4 = "A4"
    A5 = "A5"
    A6 = "A6"
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"
    B4 = "B4"
    B5 = "B5"
    B6 = "B6"
    B7 = "B7"
    B8 = "B8"
    C1 = "C1"
    C2 = "C2"
    C3 = "C3"
    C4 = "C4"
    D1 = "D1"
    D2 = "D2"
    D3 = "D3"
    E1 = "E1"
    E2 = "E2"
    IMPOUNDMENT = "impoundment"
    DIFFUSE = "diffuse"
    RIVER_ENGINEERING = "river_engineering"
    OTHER = "other_site_specific_intervention"


class MagnitudeUnit(StrEnum):
    DISCHARGE = "m3/s"
    AREA = "ha"
    VOLUME = "m3"
    POWER = "kW"
    POPULATION = "population_equivalent"
    FREQUENCY = "events/year"


@dataclass(frozen=True, init=False)
class InterventionMagnitude:
    """Maximum/concession discharge is not an interval-mean Flow."""

    value: Fraction
    unit: MagnitudeUnit

    def __init__(self, value: Number, unit: MagnitudeUnit) -> None:
        amount = finite_number(value)
        if amount < 0:
            raise ValueError("intervention magnitude cannot be negative")
        if not isinstance(unit, MagnitudeUnit):
            raise TypeError("magnitude requires a domain unit")
        object.__setattr__(self, "value", amount)
        object.__setattr__(self, "unit", unit)


@dataclass(frozen=True)
class Intervention:
    identifier: str
    kind: InterventionType
    context: AssessmentContext
    watercourse: str
    catchment_area: Area
    magnitude: InterventionMagnitude | None = None
    discharge: InterventionMagnitude | None = None
    frequency: InterventionMagnitude | None = None
    regulated_volume: InterventionMagnitude | None = None
    lake_area: InterventionMagnitude | None = None
    description: str = ""

    def __post_init__(self) -> None:
        if not self.identifier.strip() or not self.watercourse.strip():
            raise ValueError("inventory needs intervention and watercourse identities")
        if not isinstance(self.kind, InterventionType) or not isinstance(self.context, AssessmentContext):
            raise TypeError("inventory requires typed kind and context")
        if not isinstance(self.catchment_area, Area):
            raise TypeError("catchment requires Area")
        if self.catchment_area.value <= 0:
            raise ValueError("catchment area must be positive")
        for field, unit in (
            ("discharge", MagnitudeUnit.DISCHARGE),
            ("frequency", MagnitudeUnit.FREQUENCY),
            ("regulated_volume", MagnitudeUnit.VOLUME),
            ("lake_area", MagnitudeUnit.AREA),
        ):
            value = getattr(self, field)
            if value is not None and (not isinstance(value, InterventionMagnitude) or value.unit is not unit):
                raise ValueError(f"{field} has incompatible unit")
        if (
            self.magnitude is not None
            and self.kind in _THRESHOLDS
            and self.magnitude.unit is not _THRESHOLDS[self.kind][0]
        ):
            raise ValueError("characteristic magnitude has incompatible unit for intervention type")


class ScreenState(StrEnum):
    SIGNIFICANT = "significant"
    BELOW_THRESHOLD = "below_source_threshold"
    UNDETERMINED = "undetermined"
    EXCLUDED = "excluded_from_method"
    INVENTORY_ONLY = "inventory_only"


@dataclass(frozen=True)
class ReferenceDischarges:
    mean: Flow | None
    low: InterventionMagnitude | None
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.mean is not None and not isinstance(self.mean, Flow):
            raise TypeError("reference mean requires interval-mean Flow")
        if self.low is not None and self.low.unit is not MagnitudeUnit.DISCHARGE:
            raise ValueError("reference Q347 requires discharge units")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("reference needs provenance")


@dataclass(frozen=True)
class InterventionScreen:
    interventions: tuple[Intervention, ...]
    reference: ReferenceDischarges
    state: ScreenState
    metrics: tuple[Metric, ...]
    reasons: tuple[str, ...]
    source: str = "BAFU 2011 HYDMOD-F Table 8, §§4.2–4.4"
    combined_characteristics: Intervention | None = None

    @property
    def magnitude_screens(self) -> tuple[MagnitudeScreen, ...]:
        """Individual inventory screens; cumulative numerical magnitudes remain in metrics."""
        return tuple(screen_magnitude(item) for item in self.interventions)


# Literal Table 8 magnitudes. Relative significance comparisons are strictly >.
_THRESHOLDS = {
    **{
        kind: (MagnitudeUnit.DISCHARGE, Fraction(20, 1000))
        for kind in (
            InterventionType.A1,
            InterventionType.A2,
            InterventionType.A3,
            InterventionType.A4,
            InterventionType.A5,
            InterventionType.A6,
            InterventionType.B5,
            InterventionType.B6,
            InterventionType.B8,
        )
    },
    InterventionType.B1: (MagnitudeUnit.AREA, Fraction(5)),
    InterventionType.B2: (MagnitudeUnit.POPULATION, Fraction(500)),
    InterventionType.B3: (MagnitudeUnit.AREA, Fraction(15)),
    InterventionType.B4: (MagnitudeUnit.AREA, Fraction(25)),
    InterventionType.B7: (MagnitudeUnit.POWER, Fraction(50)),
    InterventionType.C1: (MagnitudeUnit.VOLUME, Fraction(15000)),
    InterventionType.C2: (MagnitudeUnit.VOLUME, Fraction(15000)),
    InterventionType.C3: (MagnitudeUnit.VOLUME, Fraction(25000)),
    InterventionType.C4: (MagnitudeUnit.VOLUME, Fraction(10000)),
    InterventionType.D1: (MagnitudeUnit.DISCHARGE, Fraction(15, 1000)),
    InterventionType.D2: (MagnitudeUnit.DISCHARGE, Fraction(40, 1000)),
    InterventionType.D3: (MagnitudeUnit.DISCHARGE, Fraction(50, 1000)),
    InterventionType.E1: (MagnitudeUnit.DISCHARGE, Fraction(150, 1000)),
    InterventionType.E2: (MagnitudeUnit.DISCHARGE, Fraction(150, 1000)),
}


def screen_intervention(intervention: Intervention, reference: ReferenceDischarges) -> InterventionScreen:
    """Preserve missing numbers and source exclusions, never call them measured absence."""
    if any(
        getattr(reference.provenance, field) != getattr(intervention.context.provenance, field)
        for field in ("scenario", "reference_member")
    ):
        raise ValueError("intervention and reference scenario/member identity differs")
    kind = intervention.kind
    metrics: list[Metric] = []

    def result(state: ScreenState, reason: str) -> InterventionScreen:
        return InterventionScreen((intervention,), reference, state, tuple(metrics), (reason,))

    if kind is InterventionType.IMPOUNDMENT:
        return result(ScreenState.INVENTORY_ONLY, "§4.2 impounded reaches are inventoried, not river-classified")
    if kind in (InterventionType.DIFFUSE, InterventionType.RIVER_ENGINEERING):
        return result(ScreenState.EXCLUDED, "§2.2 source scope exclusion, not evidence of no impact")
    if kind in (InterventionType.B5, InterventionType.D2, InterventionType.D3):
        return result(ScreenState.EXCLUDED, "§4.4 no significance criterion; not measured proof of no impact")
    if kind is InterventionType.OTHER:
        return result(ScreenState.UNDETERMINED, "§4.2 unlisted intervention requires supplied analogous assessment")
    magnitude = intervention.magnitude
    unit, threshold = _THRESHOLDS[kind]
    if magnitude is not None:
        metrics.append(Metric("characteristic_magnitude", magnitude.value, unit.value))
    if kind is InterventionType.C3:
        area = intervention.lake_area
        if area is not None:
            metrics.append(Metric("lake_area", area.value, "ha"))
        if not ((area is not None and area.value >= 10) or (magnitude is not None and magnitude.value >= threshold)):
            if area is None or magnitude is None:
                return result(ScreenState.UNDETERMINED, "missing lake area or volume needed for OR threshold")
            return result(ScreenState.BELOW_THRESHOLD, "below Table 8 absolute magnitude threshold")
    elif magnitude is None:
        return result(ScreenState.UNDETERMINED, "missing characteristic intervention magnitude")
    elif magnitude.value < threshold or (
        kind in (InterventionType.E1, InterventionType.E2) and magnitude.value == threshold
    ):
        return result(ScreenState.BELOW_THRESHOLD, "below Table 8 absolute magnitude threshold")
    low_reference = kind.value.startswith("A") or kind is InterventionType.D1
    denominator = (
        reference.low.value
        if low_reference and reference.low is not None
        else (reference.mean.value if not low_reference and reference.mean is not None else None)
    )
    if denominator is None or denominator == 0:
        return result(ScreenState.UNDETERMINED, "missing or zero reference denominator")
    if kind.value.startswith("C"):
        volume = intervention.regulated_volume if kind is InterventionType.C3 else magnitude
        if volume is None:
            return result(ScreenState.UNDETERMINED, "missing regulatable lake volume")
        ratio = volume.value / denominator / 3600
        limit = Fraction(3, 2) if kind is InterventionType.C4 else Fraction(12)
        metrics.append(Metric("storage_mean_flow_hours", ratio, "h"))
    else:
        discharge = magnitude if unit is MagnitudeUnit.DISCHARGE else intervention.discharge
        if discharge is None:
            return result(ScreenState.UNDETERMINED, "missing characteristic discharge")
        ratio = discharge.value / denominator
        limit = (
            Fraction(1, 5) if low_reference else (Fraction(1, 10) if kind is InterventionType.B6 else Fraction(1, 4))
        )
        metrics.append(Metric("discharge_reference_ratio", ratio, "1"))
        if kind in (InterventionType.E1, InterventionType.E2):
            frequency = intervention.frequency
            if frequency is None:
                return result(ScreenState.UNDETERMINED, "missing flushing frequency")
            metrics.append(Metric("flushing_frequency", frequency.value, "events/year"))
            if frequency.value == 40:
                return result(ScreenState.UNDETERMINED, "Table 8 frequency exactly 40 has no source band")
            limit = next(
                bound
                for top, bound in (
                    (10, Fraction(85, 100)),
                    (20, Fraction(65, 100)),
                    (40, Fraction(1, 2)),
                    (float("inf"), Fraction(1, 4)),
                )
                if frequency.value < top
            )
    metrics.append(Metric("significance_threshold", limit, "h" if kind.value.startswith("C") else "1"))
    return result(
        ScreenState.SIGNIFICANT if ratio > limit else ScreenState.BELOW_THRESHOLD,
        "Table 8 strict relative significance comparison",
    )


def screen_group(
    interventions: tuple[Intervention, ...],
    reference: ReferenceDischarges,
    *,
    combined_characteristics: Intervention | None = None,
) -> InterventionScreen:
    """Summarise an explicitly supplied nearby same-type group; refuse chain-expanded groups.

    Reference is supplied for the group assessment location, not averaged from sites.
    Flushing frequency and event discharge need a supplied combined-event analysis;
    their independent maxima cannot safely be summed.
    """
    if not interventions:
        raise ValueError("group must contain interventions")
    if len({item.identifier for item in interventions}) != len(interventions):
        raise ValueError("duplicate intervention in group")
    first = interventions[0]
    if any(
        item.context.period != first.context.period
        or any(
            getattr(item.context.provenance, field) != getattr(first.context.provenance, field)
            for field in ("scenario", "reference_member")
        )
        for item in interventions
    ):
        raise ValueError("grouped intervention context identity differs")
    if any(item.kind is not first.kind or item.watercourse != first.watercourse for item in interventions):
        raise ValueError("group requires same type and watercourse")
    if max(item.catchment_area.value for item in interventions) > min(
        item.catchment_area.value for item in interventions
    ) * Fraction(115, 100):
        raise ValueError("larger catchment exceeds source 15% grouping limit")
    if combined_characteristics is not None:
        if combined_characteristics.kind is not first.kind or combined_characteristics.watercourse != first.watercourse:
            raise ValueError("combined characteristics require matching intervention type and watercourse")
        screen = screen_intervention(combined_characteristics, reference)
        return InterventionScreen(
            interventions,
            reference,
            screen.state,
            screen.metrics,
            screen.reasons + ("supplied cumulative operating/event analysis",),
            combined_characteristics=combined_characteristics,
        )
    if first.kind in (InterventionType.E1, InterventionType.E2):
        return InterventionScreen(
            interventions,
            reference,
            ScreenState.UNDETERMINED,
            (),
            ("combined flushing-event characteristics require supplied analysis",),
        )

    def total(field: str) -> InterventionMagnitude | None:
        values = [getattr(item, field) for item in interventions]
        if any(value is None for value in values):
            return None
        return InterventionMagnitude(sum((value.value for value in values), Fraction()), values[0].unit)

    combined = Intervention(
        " + ".join(item.identifier for item in interventions),
        first.kind,
        first.context,
        first.watercourse,
        Area(max(item.catchment_area.value for item in interventions)),
        total("magnitude"),
        total("discharge"),
        None,
        total("regulated_volume"),
        total("lake_area"),
    )
    screen = screen_intervention(combined, reference)
    return InterventionScreen(
        interventions,
        reference,
        screen.state,
        screen.metrics,
        screen.reasons + ("§§4.3–4.4 cumulative same-type intervention group",),
    )


class SelectionAdvice(StrEnum):
    RECOMMENDED = "recommended"
    EXCEPTIONAL = "exceptional"
    INDIRECT_EXCLUSION = "indirect_exclusion"
    NOT_EXPECTED = "not_expected"
    UNSPECIFIED = "unspecified"


# Visually transcribed Table 9 rows; blanks differ from () and (x).
_RECOMMENDED = {
    Indicator.MEAN_FLOW: "A1 A2 A3 A4 A5 A6 B2 B6 B7 B8 C1 C2 D1",
    Indicator.FLOOD_FREQUENCY: "A1 A2 A3 B7 B8 C1 C2 C3 C4",
    Indicator.FLOOD_SEASONALITY: "A1 A2 A3 B7 B8 C1 C2 C3 C4 E1 E2",
    Indicator.LOW_FLOW_MAGNITUDE: "A1 A2 A3 A4 A5 A6 B2 B6 B7 B8 C1 C2 C3 D1",
    Indicator.LOW_FLOW_SEASONALITY: "A1 A2 A3 A4 A5 A6 B2 B6 B7 B8 C1 C2 C3 D1",
    Indicator.LOW_FLOW_DURATION: "A1 A2 A3 A4 A5 A6 B2 B6 B7 B8 C1 C2 C3 D1",
    Indicator.HYDROPEAKING: "B7",
    Indicator.FLUSHING: "A1 A2 A6 B2 B3 B4 C1 C2 E1 E2",
    Indicator.STORMWATER: "B1 B3 B4",
}


def selection_advice(kind: InterventionType, indicator: Indicator) -> SelectionAdvice:
    if kind is InterventionType.OTHER:
        return SelectionAdvice.UNSPECIFIED
    if kind.value in _RECOMMENDED[indicator].split():
        return SelectionAdvice.RECOMMENDED
    if (indicator is Indicator.FLOOD_FREQUENCY and kind is InterventionType.B6) or (
        indicator is Indicator.FLOOD_SEASONALITY
        and kind in (InterventionType.B1, InterventionType.B2, InterventionType.B3, InterventionType.B6)
    ):
        return SelectionAdvice.EXCEPTIONAL
    if kind in (InterventionType.D2, InterventionType.D3) and indicator in (
        Indicator.LOW_FLOW_MAGNITUDE,
        Indicator.LOW_FLOW_SEASONALITY,
        Indicator.LOW_FLOW_DURATION,
    ):
        return SelectionAdvice.INDIRECT_EXCLUSION
    return SelectionAdvice.NOT_EXPECTED


class SelectionAction(StrEnum):
    INCLUDE = "include"
    EXCLUDE = "exclude"


@dataclass(frozen=True)
class SiteSelection:
    indicator: Indicator
    action: SelectionAction
    reason: str
    provenance: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.indicator, Indicator) or not isinstance(self.action, SelectionAction):
            raise TypeError("site selection needs domain indicator and action")
        if not self.reason.strip() or not isinstance(self.provenance, Provenance):
            raise ValueError("site selection requires attributed reasoning")


def indicator_selection(
    context: AssessmentContext,
    local: tuple[InterventionScreen, ...],
    *,
    upstream: tuple[InterventionScreen, ...] = (),
    site: tuple[SiteSelection, ...] = (),
) -> tuple[IndicatorResult, ...]:
    """Return class 1 only for source screening; required calculations remain undetermined.

    Upstream screens must use reference discharges at this assessment location.
    Missing inventory is not a complete no-intervention survey.
    """
    if len({item.indicator for item in site}) != len(site):
        raise ValueError("duplicate site indicator selection")
    results = []
    screens = local + upstream
    for screen in screens:
        for item in screen.interventions:
            if item.context.period != context.period or any(
                getattr(item.context.provenance, field) != getattr(context.provenance, field)
                for field in ("scenario", "reference_member")
            ):
                raise ValueError("inventory selection context identity differs")
    for selection in site:
        if any(
            getattr(selection.provenance, field) != getattr(context.provenance, field)
            for field in ("scenario", "reference_member")
        ):
            raise ValueError("site selection context identity differs")
    for indicator in Indicator:
        override = next((item for item in site if item.indicator is indicator), None)
        reasons = []
        state, classification = AssessmentState.SCREENED, HydrologyClass.HIGH
        if not screens:
            state, classification = AssessmentState.UNDETERMINED, None
            reasons.append("missing intervention inventory")
        elif all(screen.state is ScreenState.INVENTORY_ONLY for screen in screens):
            state, classification = AssessmentState.NOT_APPLICABLE, None
            reasons.append("impoundments are inventoried without river class")
        else:
            for index, screen in enumerate(screens):
                origin = "upstream" if index >= len(local) else "local"
                advice = tuple(selection_advice(item.kind, indicator) for item in screen.interventions)
                reasons.append(
                    f"{origin}: {','.join(item.identifier for item in screen.interventions)}; "
                    f"{screen.state.value}; Table 9 {','.join(item.value for item in advice)}"
                )
                if screen.state in (ScreenState.UNDETERMINED, ScreenState.SIGNIFICANT) and any(
                    item in (SelectionAdvice.RECOMMENDED, SelectionAdvice.EXCEPTIONAL, SelectionAdvice.UNSPECIFIED)
                    for item in advice
                ):
                    state, classification = AssessmentState.UNDETERMINED, None
                if screen.state is ScreenState.EXCLUDED:
                    reasons.extend(screen.reasons)
        if override is not None:
            reasons.append(override.reason)
            if override.action is SelectionAction.INCLUDE:
                state, classification = AssessmentState.UNDETERMINED, None
            else:
                state, classification = AssessmentState.SCREENED, HydrologyClass.HIGH
        results.append(
            IndicatorResult(
                indicator,
                context,
                state,
                classification,
                (),
                "BAFU 2011 HYDMOD-F Table 9, §§5.1, 5.11",
                tuple(reasons),
                screens + site,
            )
        )
    return tuple(results)


class LandscapeBasis(StrEnum):
    CURRENT = "current_landscape_near_natural"
    PRISTINE = "original_natural_landscape"
    STRUCTURAL_NATURALISATION = "structural_naturalisation_only"


class ReferenceProfile(StrEnum):
    SWISS = "swiss_source"
    LOCAL_ADAPTATION = "explicit_local_adaptation"


class ReferenceSuitability(StrEnum):
    SUPPORTED = "supported"
    UNSUITABLE = "unsuitable"
    UNKNOWN = "unknown"


class WaterBodyKind(StrEnum):
    RIVER = "river"
    CANAL = "canal"
    DRAIN = "drain"
    LAKE = "lake"


@dataclass(frozen=True)
class ReferenceApplication:
    """A supplied scientific finding binds one exact source history to one assessment."""

    source: Provenance
    source_period: Interval
    target: AssessmentContext
    evidence: EvidenceFindings | None

    def __post_init__(self) -> None:
        for value, kind in (
            (self.source, Provenance),
            (self.source_period, Interval),
            (self.target, AssessmentContext),
        ):
            if not isinstance(value, kind):
                raise TypeError("reference application requires typed source, interval and target")
        if self.evidence is not None and not isinstance(self.evidence, EvidenceFindings):
            raise TypeError("reference application evidence requires EvidenceFindings")


@dataclass(frozen=True)
class ReferenceConditions:
    landscape: LandscapeBasis
    profile: ReferenceProfile
    water_body: WaterBodyKind
    suitability: ReferenceSuitability
    provenance: Provenance
    basis: str
    retained_influences: tuple[str, ...] = ()
    source_period: Interval | None = None
    application: ReferenceApplication | None = None

    def __post_init__(self) -> None:
        for value, cls in (
            (self.landscape, LandscapeBasis),
            (self.profile, ReferenceProfile),
            (self.water_body, WaterBodyKind),
            (self.suitability, ReferenceSuitability),
        ):
            if not isinstance(value, cls):
                raise TypeError("reference conditions require domain enums")
        if not self.basis.strip() or not isinstance(self.provenance, Provenance):
            raise ValueError("reference preparation requires attributable basis")
        if self.source_period is not None and not isinstance(self.source_period, Interval):
            raise TypeError("reference source period requires Interval")
        if self.application is not None and not isinstance(self.application, ReferenceApplication):
            raise TypeError("reference application requires ReferenceApplication")


def reference_application_scope(
    source: Provenance, source_period: Interval, target: AssessmentContext
) -> EvidenceScope:
    """Bind scientific permission to exact source history and receiving physical context."""
    if (
        not isinstance(source, Provenance)
        or not isinstance(source_period, Interval)
        or not isinstance(target, AssessmentContext)
    ):
        raise TypeError("reference scope requires typed source provenance, interval and target")
    digest = sha256(
        repr((source, source_period, target.location, target.period, target.provenance)).encode()
    ).hexdigest()
    return EvidenceScope(
        f"hydrological reference application:{digest}",
        target.location.reach.identifier,
        target.provenance.reference_member,
        target.period,
        "hydrological screening",
    )


def reference_limitations(context: AssessmentContext, conditions: ReferenceConditions) -> tuple[str, ...]:
    """Check exact source support and scoped permission without relabelling source history."""
    reasons = []
    identity = ("scenario", "reference_member", "data_version", "configuration_version", "reference_kind")
    source_period = conditions.source_period if conditions.source_period is not None else context.period
    application = conditions.application
    if application is None:
        for field in identity:
            if getattr(conditions.provenance, field) != getattr(context.provenance, field):
                reasons.append(f"reference {field} differs without an explicit assessment relationship")
        if source_period != context.period:
            reasons.append("distinct reference source_period requires scoped application evidence")
    else:
        if application.source != conditions.provenance:
            reasons.append("reference application source differs from exact source provenance")
        if conditions.source_period is None or application.source_period != conditions.source_period:
            reasons.append("reference application source_period differs from declared source period")
        if application.target != context:
            reasons.append("reference application target differs from requested assessment_context")
        if application.evidence is None:
            reasons.append("reference application evidence missing")
        else:
            evidence = application.evidence
            for field in identity:
                if getattr(evidence.provenance, field) != getattr(context.provenance, field):
                    reasons.append(f"reference application evidence {field} differs from target")
            if evidence.provenance.correction_state is CorrectionState.MISSING:
                reasons.append("reference application evidence correction state is missing")
            if any(
                period.start < context.period.end and context.period.start < period.end
                for period in evidence.provenance.excluded_warmup
            ):
                reasons.append("reference application evidence overlaps excluded warm-up")
            scope = reference_application_scope(conditions.provenance, source_period, context)
            permission = permitted_use(evidence, scope)
            if permission.finding is not CheckFinding.PASS:
                reasons.extend(permission.reasons or ("reference application permission unresolved",))
    if conditions.provenance.correction_state is CorrectionState.MISSING:
        reasons.append("reference source correction state is missing")
    if any(
        period.start < source_period.end and source_period.start < period.end
        for period in conditions.provenance.excluded_warmup
    ):
        reasons.append("reference source overlaps an excluded warm-up interval")
    return tuple(reasons)


def reference_eligibility(
    context: AssessmentContext, indicator: Indicator, conditions: ReferenceConditions
) -> IndicatorResult:
    """Assess supplied reference meaning, not infer scientific acceptance from naturalisation."""
    limitations = reference_limitations(context, conditions)
    if conditions.water_body is not WaterBodyKind.RIVER:
        state, reason = (
            AssessmentState.NOT_APPLICABLE,
            "natural-river condition does not apply automatically to canals, drains or lakes",
        )
    elif conditions.landscape is not LandscapeBasis.CURRENT:
        state, reason = (
            AssessmentState.UNDETERMINED,
            "§2.3.3 requires current-landscape near-natural reference, not pristine or merely structurally naturalised flows",
        )
    elif conditions.suitability is not ReferenceSuitability.SUPPORTED:
        state, reason = (
            AssessmentState.UNDETERMINED,
            "reference scientific suitability is not established by numerical preparation",
        )
    elif limitations:
        state, reason = AssessmentState.UNDETERMINED, "reference source support unresolved"
    else:
        state, reason = AssessmentState.UNDETERMINED, "reference eligible; indicator computation still required"
    return IndicatorResult(
        indicator,
        context,
        state,
        None,
        (),
        "BAFU 2011 HYDMOD-F §§2.1–2.3",
        (reason, conditions.profile.value, conditions.basis) + conditions.retained_influences + limitations,
        (conditions,),
    )


@dataclass(frozen=True)
class AbstractionConcession:
    capacity: InterventionMagnitude
    residual: Flow
    provenance: Provenance

    def __post_init__(self) -> None:
        if self.capacity.unit is not MagnitudeUnit.DISCHARGE or not isinstance(self.residual, Flow):
            raise ValueError("concession requires discharge capacity and interval residual flow")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("concession needs provenance")


def _estimate_identity(reference: Provenance, output: Provenance, operating: Provenance) -> None:
    if (
        output.scenario != reference.scenario
        or output.reference_member != reference.reference_member
        or operating.scenario != reference.scenario
        or (operating.reference_member is not None and operating.reference_member != reference.reference_member)
    ):
        raise ValueError("virtual series scenario/member identity differs")
    if output.reference_kind not in (reference.reference_kind, ReferenceKind.MANAGED):
        raise ValueError("virtual series reference identity may only become explicitly managed")


def estimate_abstracted_flows(
    reference: tuple[FlowSample, ...], concession: AbstractionConcession, provenance: Provenance
) -> tuple[FlowSample, ...]:
    """§3.2.3 virtual daily series: remove min(capacity, max(0, inflow-residual))."""
    check_flow_intervals(reference)
    _estimate_identity(reference[0].provenance, provenance, concession.provenance)
    if provenance.production_method is ProductionMethod.OBSERVED:
        raise ValueError("concession estimates cannot be labelled observed")
    results = []
    for sample in reference:
        if (
            sample.interval.seconds != 86400
            or sample.interval.start.hour != 0
            or sample.interval.start.minute != 0
            or sample.interval.start.second != 0
            or sample.interval.start.microsecond != 0
        ):
            raise ValueError("virtual daily route requires complete calendar-day mean intervals")
        presence = sample.presence
        reasons = sample.reasons
        value = sample.value
        if interval_use(sample) is IntervalUse.EXCLUDED_WARMUP:
            value, presence = None, Presence.UNSUPPORTED
            reasons += ("reference warm-up interval excluded",)
        if value is not None and presence is Presence.PRESENT:
            value = Flow(
                value.value - min(concession.capacity.value, max(Fraction(), value.value - concession.residual.value))
            )
        results.append(
            FlowSample(
                sample.location,
                sample.interval,
                value,
                presence,
                provenance,
                coverage=sample.coverage,
                reasons=reasons + ("HYDMOD-F §3.2.3 concession estimate", concession.provenance.source),
                components=(sample,),
            )
        )
    return tuple(results)


class MagnitudeState(StrEnum):
    QUALIFIES = "qualifies"
    BELOW_THRESHOLD = "below_threshold"
    UNDETERMINED = "undetermined"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class MagnitudeScreen:
    intervention: Intervention
    state: MagnitudeState
    thresholds: tuple[InterventionMagnitude, ...]
    source: str = "BAFU 2011 HYDMOD-F Table 8 absolute magnitude"


def screen_magnitude(intervention: Intervention) -> MagnitudeScreen:
    """Expose absolute eligibility independently, including excluded groundwater/cooling types."""
    kind = intervention.kind
    if kind not in _THRESHOLDS:
        return MagnitudeScreen(intervention, MagnitudeState.NOT_APPLICABLE, ())
    unit, threshold = _THRESHOLDS[kind]
    thresholds = (InterventionMagnitude(threshold, unit),)
    magnitude = intervention.magnitude
    if kind is InterventionType.C3:
        thresholds += (InterventionMagnitude(10, MagnitudeUnit.AREA),)
        area = intervention.lake_area
        if (magnitude is not None and magnitude.value >= threshold) or (area is not None and area.value >= 10):
            state = MagnitudeState.QUALIFIES
        elif magnitude is None or area is None:
            state = MagnitudeState.UNDETERMINED
        else:
            state = MagnitudeState.BELOW_THRESHOLD
    elif magnitude is None:
        state = MagnitudeState.UNDETERMINED
    elif magnitude.value > threshold or (
        magnitude.value == threshold and kind not in (InterventionType.E1, InterventionType.E2)
    ):
        state = MagnitudeState.QUALIFIES
    else:
        state = MagnitudeState.BELOW_THRESHOLD
    return MagnitudeScreen(intervention, state, thresholds)


def estimate_operated_flows(
    reference: tuple[FlowSample, ...], abstractions: tuple[FlowSample, ...], provenance: Provenance
) -> tuple[FlowSample, ...]:
    """§3.2.3 virtual daily series from actual operating abstractions, without silent clipping."""
    check_flow_intervals(reference)
    check_flow_intervals(abstractions)
    _estimate_identity(reference[0].provenance, provenance, abstractions[0].provenance)
    if provenance.production_method is ProductionMethod.OBSERVED:
        raise ValueError("constructed series cannot be labelled observed")
    if len(reference) != len(abstractions):
        raise ValueError("operating abstractions need matching reference intervals")
    references = sorted(reference, key=lambda sample: sample.interval.start)
    operations = sorted(abstractions, key=lambda sample: sample.interval.start)
    results = []
    for sample, abstraction in zip(references, operations, strict=True):
        if sample.interval != abstraction.interval or sample.location != abstraction.location:
            raise ValueError("operating abstractions need matching location and interval")
        if sample.provenance.scenario != abstraction.provenance.scenario:
            raise ValueError("operating abstraction scenario differs")
        if (
            sample.interval.seconds != 86400
            or sample.interval.start.hour != 0
            or sample.interval.start.minute != 0
            or sample.interval.start.second != 0
            or sample.interval.start.microsecond != 0
        ):
            raise ValueError("operating route requires complete calendar-day mean intervals")
        unavailable = next((item for item in (sample, abstraction) if item.presence is not Presence.PRESENT), None)
        value = None
        presence = unavailable.presence if unavailable is not None else Presence.PRESENT
        reasons = sample.reasons + abstraction.reasons
        excluded = any(interval_use(item) is IntervalUse.EXCLUDED_WARMUP for item in (sample, abstraction))
        if excluded:
            presence = Presence.UNSUPPORTED
            reasons += ("reference or operating warm-up interval excluded",)
        if unavailable is None and not excluded:
            assert sample.value is not None and abstraction.value is not None
            if abstraction.value.value > sample.value.value:
                raise ValueError("operating abstraction exceeds available reference flow")
            value = Flow(sample.value.value - abstraction.value.value)
        results.append(
            FlowSample(
                sample.location,
                sample.interval,
                value,
                presence,
                provenance,
                coverage=Coverage.PARTIAL
                if Coverage.PARTIAL in (sample.coverage, abstraction.coverage)
                else Coverage.COMPLETE,
                reasons=reasons + ("HYDMOD-F §3.2.3 actual operating abstraction estimate",),
                components=(sample, abstraction),
            )
        )
    return tuple(results)


class ReturnRelation(StrEnum):
    CLOSE_IN_SPACE_AND_TIME = "close_in_space_and_time"
    NOT_CLOSE = "not_close"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AbstractionReturn:
    relation: ReturnRelation
    provenance: Provenance
    basis: str

    def __post_init__(self) -> None:
        if not isinstance(self.relation, ReturnRelation) or not isinstance(self.provenance, Provenance):
            raise TypeError("abstraction-return relation requires typed evidence")
        if not self.basis.strip():
            raise ValueError("abstraction-return relation needs supplied site reasoning")


def reuse_pre_abstraction(
    context: AssessmentContext, findings: tuple[IndicatorResult, ...], relation: AbstractionReturn
) -> tuple[IndicatorResult, ...]:
    """§5.1 reuse supported findings in the same scenario/member/configuration and period.

    Upstream readings and the relationship study may have distinct source/data histories.
    Their original records remain in inputs; this operation does not relabel those histories.
    """
    if len({item.indicator for item in findings}) != len(findings):
        raise ValueError("duplicate pre-abstraction indicator")
    identity = ("scenario", "reference_member", "configuration_version", "reference_kind")
    if any(getattr(relation.provenance, field) != getattr(context.provenance, field) for field in identity):
        raise ValueError("abstraction-return relationship context identity differs")
    results = []
    for finding in findings:
        if finding.context.period != context.period or any(
            getattr(finding.context.provenance, field) != getattr(context.provenance, field) for field in identity
        ):
            raise ValueError("pre-abstraction findings need matching context identity and actual interval")
        limitations = []
        for label, provenance in (
            ("pre-abstraction finding", finding.context.provenance),
            ("return relationship", relation.provenance),
            ("receiving context", context.provenance),
        ):
            if provenance.correction_state is CorrectionState.MISSING:
                limitations.append(f"{label} correction state is missing")
            if any(
                period.start < context.period.end and context.period.start < period.end
                for period in provenance.excluded_warmup
            ):
                limitations.append(f"{label} overlaps excluded warm-up")
        supported = relation.relation is ReturnRelation.CLOSE_IN_SPACE_AND_TIME and not limitations
        results.append(
            IndicatorResult(
                finding.indicator,
                context,
                finding.state if supported else AssessmentState.UNDETERMINED,
                finding.classification if supported else None,
                finding.metrics,
                "BAFU 2011 HYDMOD-F §5.1 close abstraction/return",
                finding.reasons + (relation.relation.value, relation.basis) + tuple(limitations),
                (finding, relation),
                coverage=finding.coverage,
            )
        )
    return tuple(results)
