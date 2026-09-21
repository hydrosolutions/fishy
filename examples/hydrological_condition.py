"""scenario : SuppliedInventory × HydrologicalRecords → PointAndReachCondition.

Synthetic HYDMOD-F calculations. No simulator, HYDMOD-FIT, private files,
national adaptation, prescribed-release change or official admission is needed.
"""

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from fractions import Fraction

from fishy.catchment_conditions import (
    CatchmentNode,
    DrainageNetwork,
    IntermediateCondition,
    ReachCondition,
    propagate_hydrology,
)
from fishy.evidence import (
    Completeness,
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    EvidenceScope,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ScientificAdequacy,
)
from fishy.flow_events import (
    EventSupport,
    InstantaneousDischarge,
    InstantaneousRecord,
    InstantaneousSample,
    StormwaterEvent,
    estimate_mhq_from_mean,
    flood_frequency_from_record,
    stormwater_events,
)
from fishy.flow_interventions import (
    Intervention,
    InterventionMagnitude,
    InterventionType,
    LandscapeBasis,
    MagnitudeUnit,
    ReferenceConditions,
    ReferenceDischarges,
    ReferenceProfile,
    ReferenceSuitability,
    SelectionAction,
    SiteSelection,
    WaterBodyKind,
    screen_intervention,
)
from fishy.flow_pulses import (
    FlushingMetrics,
    FlushingTiming,
    HydropeakingOperation,
    StageRate,
    assess_flushing,
    estimate_hydropeaking,
)
from fishy.flow_regime import (
    LowFlowStatistics,
    MonthlyRegime,
    RegimeReference,
    TroughApplicability,
    assess_duration_observations,
    assess_low_flow_magnitude,
    assess_mean_flow,
    assess_seasonality,
    circular_timing,
    regime_low_flow,
    regime_mean_flow,
)
from fishy.flows import FlowSample, Presence
from fishy.hydrological_assessment import HydrologicalAssessment, InventorySurvey, assess_river_hydrology
from fishy.hydrological_condition import AssessmentContext, HydrologicalCondition, Indicator, assess_hydrology
from fishy.quantities import Area, Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


@dataclass(frozen=True)
class Scenario:
    point: HydrologicalAssessment
    reaches: tuple[ReachCondition, ...]
    overall: HydrologicalCondition
    partial_point: HydrologicalAssessment
    partial_overall: HydrologicalCondition


def scenario() -> Scenario:
    provenance = Provenance(
        "synthetic hydrological example",
        "illustration",
        "reference-1",
        "example-v1",
        "synthetic-v1",
        "configuration-v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    river = WaterBody("example river", "1")
    location = Location(Reach("intervention reach", "1", river), CalculationSection("upstream end", "1"), "map-1")
    period = Interval(datetime(2010, 1, 1, tzinfo=UTC), datetime(2015, 1, 1, tzinfo=UTC))
    evidence = EvidenceFindings(
        EvidenceScope(
            "hydrological condition",
            location.reach.identifier,
            provenance.reference_member,
            period,
            "illustrative screening",
        ),
        provenance,
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("synthetic demonstration only; no site certification",),
    )
    ctx = AssessmentContext(location, period, provenance, (evidence,))
    area = Area(50, "km2")
    regime = RegimeReference(3, "explicit Swiss type for this synthetic example; not inferred from geography")
    monthly = regime_mean_flow(regime, area)
    mean = Flow(Fraction(54, 1000) * 50)  # Table 2, type 3: 54 l/s/km².
    low = regime_low_flow(regime, area)
    assert low.q347 is not None
    abstraction = Intervention(
        "intake",
        InterventionType.A1,
        ctx,
        "example river",
        area,
        InterventionMagnitude("0.2", MagnitudeUnit.DISCHARGE),
        description="supplied hypothetical authorised maximum",
    )
    screen = screen_intervention(
        abstraction,
        ReferenceDischarges(mean, InterventionMagnitude(low.q347.value, MagnitudeUnit.DISCHARGE), provenance),
    )
    inventory = InventorySurvey(
        (screen,), (), Completeness.COMPLETE, "complete synthetic intervention survey", "survey-1"
    )
    reference = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        provenance,
        "prepared near-natural current-landscape reference",
    )
    altered = MonthlyRegime(
        tuple(Flow(q.value * Fraction(64, 100)) for q in monthly.monthly_means if q is not None),
        "synthetic altered monthly means",
        (monthly,),
    )
    mean_result = assess_mean_flow(ctx, monthly, altered, regime)

    # Complete prepared instantaneous crossing catalogue; support is supplied,
    # not inferred from daily means or the number of listed knots.
    mhq = estimate_mhq_from_mean(mean, regime.swiss_type)
    readings = []
    for year in range(2010, 2015):
        for month, day, q in ((1, 1, 0), (1, 2, 8), (1, 3, 0), (2, 1, 8), (2, 2, 0)):
            readings.append(
                InstantaneousSample(
                    datetime(year, month, day, tzinfo=UTC), InstantaneousDischarge(q), Presence.PRESENT, ctx
                )
            )
    floods = flood_frequency_from_record(
        InstantaneousRecord(
            ctx,
            tuple(readings),
            EventSupport.COMPLETE,
            "synthetic complete event catalogue, baseline zero between listed events",
        ),
        mhq,
        regime.swiss_type,
    )
    natural_timing = circular_timing(tuple(date(y, 1, 2) for y in range(2010, 2015)), "synthetic annual dates")
    flood_timing = assess_seasonality(ctx, Indicator.FLOOD_SEASONALITY, natural_timing, natural_timing)
    low_timing = assess_seasonality(ctx, Indicator.LOW_FLOW_SEASONALITY, natural_timing, natural_timing)
    low_result = assess_low_flow_magnitude(
        ctx,
        low,
        LowFlowStatistics(Flow(low.q347.value * Fraction(3, 5)), None, "synthetic altered Q347"),
        TroughApplicability.ABSENT,
    )
    daily = []
    at = period.start
    while at < period.end:
        # Twenty consecutive equality days each year; not total low-flow days.
        q = low.q347 if at.month == 1 and 2 <= at.day <= 21 else Flow(low.q347.value * 2)
        daily.append(FlowSample(location, Interval(at, at + timedelta(days=1)), q, Presence.PRESENT, provenance))
        at += timedelta(days=1)
    duration = assess_duration_observations(ctx, tuple(daily), low.q347)
    operation = HydropeakingOperation(
        InstantaneousDischarge("1.62"),
        InstantaneousDischarge("1.08"),
        StageRate(Fraction(2)),
        StageRate(Fraction(2)),
        "supported synthetic operating estimate",
    )
    peaking = estimate_hydropeaking(ctx, operation, mean, area)
    flushing = assess_flushing(
        ctx,
        (
            FlushingMetrics(
                InstantaneousDischarge(mean.value),
                Fraction(10),
                StageRate(Fraction(2)),
                FlushingTiming.MEAN_FLOW,
                "synthetic flushing operation",
            ),
        ),
        mean,
    )
    storms = stormwater_events(
        ctx,
        tuple(
            StormwaterEvent(
                f"storm-{y}",
                datetime(y, 3, 1, tzinfo=UTC),
                InstantaneousDischarge(6),
                "synthetic additional drainage event",
            )
            for y in (2010, 2012)
        ),
        mean,
        mhq,
        EventSupport.COMPLETE,
    )
    calculations = (mean_result, floods, flood_timing, low_result, low_timing, duration, peaking, flushing, storms)
    additions = tuple(
        SiteSelection(i, SelectionAction.INCLUDE, "supplied situational indicator addition", provenance)
        for i in (Indicator.HYDROPEAKING, Indicator.STORMWATER)
    )
    point = assess_river_hydrology(ctx, reference, inventory, calculations, additions)

    downstream = Location(
        Reach("downstream reach", "1", river), CalculationSection("downstream upstream end", "1"), "map-1"
    )
    downstream_ctx = replace(ctx, location=downstream, evidence=())

    def transfer(results):
        upstream = CatchmentNode(
            "intake", ctx, area, (), tuple(Indicator), results, IntermediateCondition.UNAFFECTED, "surveyed point"
        )
        outlet = CatchmentNode(
            "outlet",
            downstream_ctx,
            Area(100, "km2"),
            ("intake",),
            (),
            (),
            IntermediateCondition.UNAFFECTED,
            "surveyed unaffected 50 km2 intermediate area",
        )
        network = DrainageNetwork((upstream, outlet), "network-1", "prepared disjoint drainage topology")
        reaches = propagate_hydrology(network, "outlet")
        return reaches, assess_hydrology(downstream_ctx, tuple(r.result for r in reaches))

    reaches, overall = transfer(point.condition.indicators)
    # A missing stage rate preserves other supported calculations, not a fake
    # no-hydropeaking class inferred from daily data.
    partial_peaking = estimate_hydropeaking(ctx, replace(operation, rise=None), mean, area)
    partial_calculations = tuple(partial_peaking if r.indicator is Indicator.HYDROPEAKING else r for r in calculations)
    partial = assess_river_hydrology(ctx, reference, inventory, partial_calculations, additions)
    _, partial_overall = transfer(partial.condition.indicators)
    return Scenario(point, reaches, overall, partial, partial_overall)


if __name__ == "__main__":
    result = scenario()
    print(
        "Point classes:",
        [r.classification.value if r.classification else None for r in result.point.condition.indicators],
    )
    print("Point overall:", result.point.condition.classification, "points:", result.point.condition.points)
    print("Downstream overall:", result.overall.classification, "coverage:", result.overall.completeness.value)
    print(
        "Missing stage rate:",
        result.partial_overall.classification,
        "coverage:",
        result.partial_overall.completeness.value,
    )
