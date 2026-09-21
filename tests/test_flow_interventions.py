"""HYDMOD-F Tables 8–9 and reference/estimate acceptance, exact rational thresholds."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from fractions import Fraction

import pytest

from fishy.evidence import (
    Computability,
    CorrectionState,
    Disclosure,
    EvidenceFindings,
    NumericalValidity,
    OfficialAdmissibility,
    ProductionMethod,
    Provenance,
    ReferenceKind,
    ScientificAdequacy,
)
from fishy.flow_interventions import (
    AbstractionConcession,
    AbstractionReturn,
    Intervention,
    InterventionMagnitude,
    InterventionType,
    LandscapeBasis,
    MagnitudeState,
    MagnitudeUnit,
    ReferenceApplication,
    ReferenceConditions,
    ReferenceDischarges,
    ReferenceProfile,
    ReferenceSuitability,
    ReturnRelation,
    ScreenState,
    SelectionAction,
    SelectionAdvice,
    SiteSelection,
    WaterBodyKind,
    estimate_abstracted_flows,
    estimate_operated_flows,
    indicator_selection,
    reference_application_scope,
    reference_eligibility,
    reference_limitations,
    reuse_pre_abstraction,
    screen_group,
    screen_intervention,
    screen_magnitude,
    selection_advice,
)
from fishy.flows import FlowSample, Presence
from fishy.hydrological_condition import AssessmentContext, AssessmentState, HydrologyClass, Indicator
from fishy.quantities import Area, Flow
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.time import Interval


@pytest.fixture
def context():
    provenance = Provenance(
        "synthetic inventory",
        "scenario",
        "reference",
        "test",
        "v1",
        "v1",
        ProductionMethod.ILLUSTRATIVE,
        CorrectionState.ORIGINAL,
    )
    location = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "v1")
    return AssessmentContext(
        location, Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1, tzinfo=UTC)), provenance
    )


def magnitude(value, unit=MagnitudeUnit.DISCHARGE):
    return InterventionMagnitude(value, unit)


def intervention(context, kind=InterventionType.A1, value="0.1", unit=MagnitudeUnit.DISCHARGE, **kwargs):
    return Intervention("intake", kind, context, "river", Area(100, "km2"), magnitude(value, unit), **kwargs)


def reference(context, mean=1, low="0.1"):
    return ReferenceDischarges(Flow(mean), magnitude(low), context.provenance)


@pytest.mark.parametrize("kind", [InterventionType[f"A{i}"] for i in range(1, 7)] + [InterventionType.D1])
def test_abstraction_relative_strict_boundary(context, kind):
    item = intervention(context, kind, "0.02")
    assert screen_intervention(item, reference(context)).state is ScreenState.BELOW_THRESHOLD
    assert (
        screen_intervention(replace(item, magnitude=magnitude("0.020001")), reference(context)).state
        is ScreenState.SIGNIFICANT
    )


@pytest.mark.parametrize(
    "kind,value,unit",
    [
        (InterventionType.B1, 5, MagnitudeUnit.AREA),
        (InterventionType.B2, 500, MagnitudeUnit.POPULATION),
        (InterventionType.B3, 15, MagnitudeUnit.AREA),
        (InterventionType.B4, 25, MagnitudeUnit.AREA),
        (InterventionType.B7, 50, MagnitudeUnit.POWER),
    ],
)
def test_supply_absolute_and_relative_boundaries(context, kind, value, unit):
    item = intervention(context, kind, value, unit, discharge=magnitude("0.25"))
    assert screen_intervention(item, reference(context)).state is ScreenState.BELOW_THRESHOLD
    assert (
        screen_intervention(replace(item, discharge=magnitude("0.250001")), reference(context)).state
        is ScreenState.SIGNIFICANT
    )
    below = replace(item, magnitude=magnitude(Fraction(value) - Fraction(1, 1000), unit), discharge=magnitude(100))
    assert screen_intervention(below, reference(context)).state is ScreenState.BELOW_THRESHOLD


@pytest.mark.parametrize("kind,limit", [(InterventionType.B6, "0.1"), (InterventionType.B8, "0.25")])
def test_transfer_and_turbine_returns(context, kind, limit):
    item = intervention(context, kind, limit)
    assert screen_intervention(item, reference(context)).state is ScreenState.BELOW_THRESHOLD
    assert (
        screen_intervention(
            replace(item, magnitude=magnitude(Fraction(limit) + Fraction(1, 1000))), reference(context)
        ).state
        is ScreenState.SIGNIFICANT
    )


@pytest.mark.parametrize(
    "kind,hours", [(InterventionType.C1, 12), (InterventionType.C2, 12), (InterventionType.C4, Fraction(3, 2))]
)
def test_storage_hours_strict_threshold(context, kind, hours):
    item = intervention(context, kind, hours * 3600 * 10, MagnitudeUnit.VOLUME)
    assert screen_intervention(item, reference(context, mean=10)).state is ScreenState.BELOW_THRESHOLD
    result = screen_intervention(
        replace(item, magnitude=magnitude(item.magnitude.value + 1, MagnitudeUnit.VOLUME)), reference(context, mean=10)
    )
    assert result.state is ScreenState.SIGNIFICANT
    assert result.metrics[1].value == hours + Fraction(1, 36000)


def test_lake_or_threshold_and_regulated_not_total_volume(context):
    item = intervention(
        context,
        InterventionType.C3,
        100,
        MagnitudeUnit.VOLUME,
        lake_area=magnitude(10, MagnitudeUnit.AREA),
        regulated_volume=magnitude(43200, MagnitudeUnit.VOLUME),
    )
    assert screen_intervention(item, reference(context)).state is ScreenState.BELOW_THRESHOLD
    assert (
        screen_intervention(
            replace(item, regulated_volume=magnitude(43201, MagnitudeUnit.VOLUME)), reference(context)
        ).state
        is ScreenState.SIGNIFICANT
    )
    missing = replace(item, magnitude=None, lake_area=magnitude(9, MagnitudeUnit.AREA))
    assert screen_intervention(missing, reference(context)).state is ScreenState.UNDETERMINED


@pytest.mark.parametrize(
    "frequency,limit", [(0, "0.85"), (9, "0.85"), (10, "0.65"), (19, "0.65"), (20, "0.5"), (39, "0.5"), (41, "0.25")]
)
@pytest.mark.parametrize("kind", [InterventionType.E1, InterventionType.E2])
def test_flushing_bands_and_strict_ratio(context, frequency, limit, kind):
    item = intervention(context, kind, limit, frequency=magnitude(frequency, MagnitudeUnit.FREQUENCY))
    assert screen_intervention(item, reference(context)).state is ScreenState.BELOW_THRESHOLD
    assert (
        screen_intervention(
            replace(item, magnitude=magnitude(Fraction(limit) + Fraction(1, 1000))), reference(context)
        ).state
        is ScreenState.SIGNIFICANT
    )


def test_flushing_absolute_strict_and_40_unresolved(context):
    item = intervention(context, InterventionType.E1, "0.15", frequency=magnitude(41, MagnitudeUnit.FREQUENCY))
    assert screen_intervention(item, reference(context, mean="0.1")).state is ScreenState.BELOW_THRESHOLD
    item = replace(item, magnitude=magnitude("0.4"), frequency=magnitude(40, MagnitudeUnit.FREQUENCY))
    result = screen_intervention(item, reference(context))
    assert result.state is ScreenState.UNDETERMINED
    assert result.metrics[1].value == Fraction(2, 5)
    assert "40" in result.reasons[0]


@pytest.mark.parametrize(
    "kind",
    [
        InterventionType.B5,
        InterventionType.D2,
        InterventionType.D3,
        InterventionType.DIFFUSE,
        InterventionType.RIVER_ENGINEERING,
    ],
)
def test_source_exclusions_not_measured_absence(context, kind):
    item = Intervention("excluded", kind, context, "river", Area(100, "km2"))
    result = screen_intervention(item, reference(context))
    assert result.state is ScreenState.EXCLUDED
    assert "no impact" in result.reasons[0]


def test_impoundment_inventory_not_river_class(context):
    item = Intervention("pool", InterventionType.IMPOUNDMENT, context, "river", Area(100, "km2"))
    result = screen_intervention(item, reference(context))
    assert result.state is ScreenState.INVENTORY_ONLY
    assert all(
        r.state is AssessmentState.NOT_APPLICABLE and r.classification is None
        for r in indicator_selection(context, (result,))
    )


def test_cumulative_small_abstractions_and_15_percent_equality(context):
    first = intervention(context, value="0.012")
    second = replace(first, identifier="second", catchment_area=Area(115, "km2"))
    assert screen_intervention(first, reference(context)).state is ScreenState.BELOW_THRESHOLD
    result = screen_group((first, second), reference(context))
    assert result.state is ScreenState.SIGNIFICANT
    assert result.interventions == (first, second)
    assert result.metrics[0].value == Fraction(24, 1000)
    with pytest.raises(ValueError, match="15%"):
        screen_group((first, replace(second, catchment_area=Area("115.000001", "km2"))), reference(context))
    for invalid in (replace(second, watercourse="other"), replace(second, kind=InterventionType.A2), first):
        with pytest.raises(ValueError):
            screen_group((first, invalid), reference(context))


def test_missing_cumulative_component_is_not_zero(context):
    first = intervention(context)
    second = replace(first, identifier="unknown", magnitude=None)
    assert screen_group((first, second), reference(context)).state is ScreenState.UNDETERMINED


def test_screened_one_differs_missing_affected_indicator(context):
    screened = screen_intervention(intervention(context, value="0.001"), reference(context))
    assert all(
        r.state is AssessmentState.SCREENED and r.classification is HydrologyClass.HIGH
        for r in indicator_selection(context, (screened,))
    )
    missing = screen_intervention(replace(intervention(context), magnitude=None), reference(context))
    results = {r.indicator: r for r in indicator_selection(context, (missing,))}
    assert results[Indicator.MEAN_FLOW].state is AssessmentState.UNDETERMINED
    assert results[Indicator.STORMWATER].state is AssessmentState.SCREENED
    assert all(r.classification is None for r in indicator_selection(context, ()))


def test_selection_upstream_exceptional_and_site_attribution(context):
    local = screen_intervention(intervention(context, InterventionType.B5), reference(context))
    upstream = screen_intervention(intervention(context, InterventionType.B6, "0.2"), reference(context))
    results = {r.indicator: r for r in indicator_selection(context, (local,), upstream=(upstream,))}
    assert results[Indicator.MEAN_FLOW].state is AssessmentState.UNDETERMINED
    assert results[Indicator.FLOOD_FREQUENCY].state is AssessmentState.UNDETERMINED
    assert "upstream" in " ".join(results[Indicator.MEAN_FLOW].reasons)
    exclusion = SiteSelection(
        Indicator.FLOOD_FREQUENCY,
        SelectionAction.EXCLUDE,
        "groundwater-dominated: no distinct floods",
        context.provenance,
    )
    addition = SiteSelection(
        Indicator.STORMWATER, SelectionAction.INCLUDE, "site drainage inflow study", context.provenance
    )
    selected = {
        r.indicator: r for r in indicator_selection(context, (local,), upstream=(upstream,), site=(exclusion, addition))
    }
    assert selected[Indicator.FLOOD_FREQUENCY].state is AssessmentState.SCREENED
    assert selected[Indicator.STORMWATER].state is AssessmentState.UNDETERMINED
    assert exclusion in selected[Indicator.FLOOD_FREQUENCY].inputs
    assert upstream in selected[Indicator.MEAN_FLOW].inputs


def test_table9_distinct_recommendation_symbols():
    assert selection_advice(InterventionType.B7, Indicator.HYDROPEAKING) is SelectionAdvice.RECOMMENDED
    assert selection_advice(InterventionType.B1, Indicator.FLOOD_SEASONALITY) is SelectionAdvice.EXCEPTIONAL
    assert selection_advice(InterventionType.D2, Indicator.LOW_FLOW_DURATION) is SelectionAdvice.INDIRECT_EXCLUSION
    assert selection_advice(InterventionType.B4, Indicator.FLOOD_SEASONALITY) is SelectionAdvice.NOT_EXPECTED


@pytest.mark.parametrize("body", [WaterBodyKind.CANAL, WaterBodyKind.DRAIN, WaterBodyKind.LAKE])
def test_reference_excludes_artificial_and_lake_class(context, body):
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        body,
        ReferenceSuitability.SUPPORTED,
        context.provenance,
        "study",
    )
    assert reference_eligibility(context, Indicator.MEAN_FLOW, conditions).state is AssessmentState.NOT_APPLICABLE


def test_reference_naturalisation_not_scientific_acceptance(context):
    conditions = ReferenceConditions(
        LandscapeBasis.STRUCTURAL_NATURALISATION,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        context.provenance,
        "structural preparation",
    )
    result = reference_eligibility(context, Indicator.MEAN_FLOW, conditions)
    assert result.classification is None
    assert "current-landscape" in result.reasons[0]
    supported = replace(
        conditions,
        landscape=LandscapeBasis.CURRENT,
        profile=ReferenceProfile.LOCAL_ADAPTATION,
        basis="explicit local study",
        retained_influences=("historical lake regulation retained",),
    )
    result = reference_eligibility(context, Indicator.MEAN_FLOW, supported)
    assert "reference eligible" in result.reasons[0]
    assert "explicit_local_adaptation" in result.reasons
    assert result.inputs == (supported,)
    assert (
        reference_eligibility(
            context, Indicator.MEAN_FLOW, replace(supported, suitability=ReferenceSuitability.UNKNOWN)
        ).classification
        is None
    )


def test_daily_concession_estimate_preserves_inflow_floor_and_missing(context):
    start = datetime(2000, 2, 28, tzinfo=UTC)
    samples = tuple(
        FlowSample(
            context.location,
            Interval(start + timedelta(days=i), start + timedelta(days=i + 1)),
            Flow(q) if q is not None else None,
            Presence.PRESENT if q is not None else Presence.MISSING,
            context.provenance,
            reasons=() if q is not None else ("missing reading",),
        )
        for i, q in enumerate((10, 5, 1, 0, None))
    )
    concession = AbstractionConcession(magnitude(6), Flow(2), context.provenance)
    results = estimate_abstracted_flows(samples, concession, context.provenance)
    assert tuple(s.value.value if s.value is not None else None for s in results) == (4, 2, 1, 0, None)
    assert results[1].interval.start.day == 29
    assert results[-1].presence is Presence.MISSING
    assert results[0].components == (samples[0],)
    with pytest.raises(ValueError, match="observed"):
        estimate_abstracted_flows(
            samples, concession, replace(context.provenance, production_method=ProductionMethod.OBSERVED)
        )
    with pytest.raises(ValueError, match="calendar-day"):
        estimate_abstracted_flows(
            (replace(samples[0], interval=Interval(start, start + timedelta(hours=1))),), concession, context.provenance
        )


def test_invalid_units_nonfinite_negative_and_missing_reference(context):
    for invalid in ("NaN", "inf", -1):
        with pytest.raises(ValueError):
            magnitude(invalid)
    with pytest.raises(ValueError, match="incompatible"):
        intervention(context, unit=MagnitudeUnit.VOLUME)
    assert screen_intervention(intervention(context), reference(context, low=0)).state is ScreenState.UNDETERMINED
    assert (
        screen_intervention(intervention(context), ReferenceDischarges(None, None, context.provenance)).state
        is ScreenState.UNDETERMINED
    )


def test_combined_flushing_operating_analysis_retained(context):
    first = intervention(context, InterventionType.E1, "0.1", frequency=magnitude(5, MagnitudeUnit.FREQUENCY))
    second = replace(first, identifier="second")
    assert screen_group((first, second), reference(context)).state is ScreenState.UNDETERMINED
    combined = replace(
        first,
        identifier="combined event study",
        magnitude=magnitude(1),
        frequency=magnitude(15, MagnitudeUnit.FREQUENCY),
    )
    result = screen_group((first, second), reference(context), combined_characteristics=combined)
    assert result.state is ScreenState.SIGNIFICANT
    assert result.interventions == (first, second)
    assert result.combined_characteristics == combined
    assert result.metrics[1].value == 1
    with pytest.raises(ValueError, match="matching"):
        screen_group(
            (first, second), reference(context), combined_characteristics=replace(combined, watercourse="other")
        )


@pytest.mark.parametrize(
    "kind, value", [(InterventionType.B5, "0.02"), (InterventionType.D2, "0.04"), (InterventionType.D3, "0.05")]
)
def test_excluded_types_still_have_absolute_inventory_screen(context, kind, value):
    item = intervention(context, kind, value)
    result = screen_intervention(item, reference(context))
    assert result.state is ScreenState.EXCLUDED
    assert result.magnitude_screens[0].state is MagnitudeState.QUALIFIES
    assert (
        screen_magnitude(replace(item, magnitude=magnitude(Fraction(value) - Fraction(1, 100000)))).state
        is MagnitudeState.BELOW_THRESHOLD
    )


@pytest.mark.parametrize(
    "kind,threshold,unit",
    [
        *[(InterventionType[f"A{i}"], "0.02", MagnitudeUnit.DISCHARGE) for i in range(1, 7)],
        (InterventionType.D1, "0.015", MagnitudeUnit.DISCHARGE),
        (InterventionType.C1, 15000, MagnitudeUnit.VOLUME),
        (InterventionType.C2, 15000, MagnitudeUnit.VOLUME),
        (InterventionType.C4, 10000, MagnitudeUnit.VOLUME),
    ],
)
def test_absolute_inventory_equality_independent_of_reference(context, kind, threshold, unit):
    item = intervention(context, kind, threshold, unit)
    assert screen_magnitude(item).state is MagnitudeState.QUALIFIES
    assert (
        screen_magnitude(replace(item, magnitude=magnitude(Fraction(threshold) - Fraction(1, 100000), unit))).state
        is MagnitudeState.BELOW_THRESHOLD
    )
    assert screen_magnitude(replace(item, magnitude=None)).state is MagnitudeState.UNDETERMINED


def test_actual_operating_abstraction_success_gap_and_infeasible(context):
    interval = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 2, tzinfo=UTC))
    sample = FlowSample(context.location, interval, Flow(10), Presence.PRESENT, context.provenance)
    operation = replace(sample, value=Flow(3))
    result = estimate_operated_flows((sample,), (operation,), context.provenance)[0]
    assert result.value == Flow(7)
    assert result.components == (sample, operation)
    missing = replace(operation, value=None, presence=Presence.MISSING, reasons=("operation unknown",))
    assert estimate_operated_flows((sample,), (missing,), context.provenance)[0].presence is Presence.MISSING
    with pytest.raises(ValueError, match="exceeds"):
        estimate_operated_flows((sample,), (replace(operation, value=Flow(11)),), context.provenance)
    with pytest.raises(ValueError, match="matching"):
        estimate_operated_flows(
            (sample,),
            (
                replace(
                    operation, interval=Interval(interval.start + timedelta(days=1), interval.end + timedelta(days=1))
                ),
            ),
            context.provenance,
        )


def test_close_abstraction_return_reuses_attributed_prior_findings(context):
    screened = screen_intervention(intervention(context, value="0.001"), reference(context))
    original = indicator_selection(context, (screened,))
    relation = AbstractionReturn(
        ReturnRelation.CLOSE_IN_SPACE_AND_TIME,
        context.provenance,
        "site study confirms nearby simultaneous full return",
    )
    downstream = replace(context, location=replace(context.location, section=CalculationSection("return", "v1")))
    results = reuse_pre_abstraction(downstream, original, relation)
    assert all(r.classification is HydrologyClass.HIGH and r.context == downstream for r in results)
    assert results[0].inputs == (original[0], relation)
    unknown = reuse_pre_abstraction(downstream, original, replace(relation, relation=ReturnRelation.UNKNOWN))
    assert all(r.classification is None for r in unknown)


def test_all_table9_cells_match_primary_grid():
    types = tuple(
        InterventionType(code)
        for code in [
            "A1",
            "A2",
            "A3",
            "A4",
            "A5",
            "A6",
            "B1",
            "B2",
            "B3",
            "B4",
            "B5",
            "B6",
            "B7",
            "B8",
            "C1",
            "C2",
            "C3",
            "C4",
            "D1",
            "D2",
            "D3",
            "E1",
            "E2",
        ]
    )
    # 23 source columns; x recommended, e exceptional, i indirect, - blank.
    # Build independent row assertions as source column-index sets, including every blank.
    expected = (
        ({0, 1, 2, 3, 4, 5, 7, 11, 12, 13, 14, 15, 18}, set(), set()),
        ({0, 1, 2, 12, 13, 14, 15, 16, 17}, {11}, set()),
        ({0, 1, 2, 12, 13, 14, 15, 16, 17, 21, 22}, {6, 7, 8, 11}, set()),
        ({0, 1, 2, 3, 4, 5, 7, 11, 12, 13, 14, 15, 16, 18}, set(), {19, 20}),
        ({0, 1, 2, 3, 4, 5, 7, 11, 12, 13, 14, 15, 16, 18}, set(), {19, 20}),
        ({0, 1, 2, 3, 4, 5, 7, 11, 12, 13, 14, 15, 16, 18}, set(), {19, 20}),
        ({12}, set(), set()),
        ({0, 1, 5, 7, 8, 9, 14, 15, 21, 22}, set(), set()),
        ({6, 8, 9}, set(), set()),
    )
    for indicator, (recommended, exceptional, indirect) in zip(Indicator, expected, strict=True):
        for index, kind in enumerate(types):
            advice = (
                SelectionAdvice.RECOMMENDED
                if index in recommended
                else SelectionAdvice.EXCEPTIONAL
                if index in exceptional
                else SelectionAdvice.INDIRECT_EXCLUSION
                if index in indirect
                else SelectionAdvice.NOT_EXPECTED
            )
            assert selection_advice(kind, indicator) is advice


def test_virtual_series_refuses_identity_relabelling(context):
    day = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 2, tzinfo=UTC))
    sample = FlowSample(context.location, day, Flow(10), Presence.PRESENT, context.provenance)
    concession = AbstractionConcession(magnitude(6), Flow(2), context.provenance)
    for field, value in (("scenario", "other"), ("reference_member", "other")):
        foreign = replace(context.provenance, **{field: value})
        with pytest.raises(ValueError, match="identity"):
            estimate_abstracted_flows((sample,), concession, foreign)
        with pytest.raises(ValueError, match="identity"):
            estimate_operated_flows((sample,), (replace(sample, value=Flow(1)),), foreign)
    with pytest.raises(ValueError, match="identity"):
        estimate_abstracted_flows(
            (sample,), replace(concession, provenance=replace(context.provenance, scenario="other")), context.provenance
        )


def test_virtual_series_warmup_cannot_become_supported(context):
    day = Interval(datetime(2000, 1, 1, tzinfo=UTC), datetime(2000, 1, 2, tzinfo=UTC))
    sample = FlowSample(
        context.location, day, Flow(10), Presence.PRESENT, replace(context.provenance, excluded_warmup=(day,))
    )
    concession = AbstractionConcession(magnitude(6), Flow(2), context.provenance)
    estimated = estimate_abstracted_flows((sample,), concession, context.provenance)[0]
    assert estimated.value is None and estimated.presence is Presence.UNSUPPORTED
    operation = replace(sample, value=Flow(1))
    estimated = estimate_operated_flows((sample,), (operation,), context.provenance)[0]
    assert estimated.value is None and estimated.presence is Presence.UNSUPPORTED
    assert "warm-up" in " ".join(estimated.reasons)


@pytest.mark.parametrize("field", ["scenario", "reference_member"])
def test_inventory_refuses_foreign_reference_and_selection_context(context, field):
    item = intervention(context)
    foreign = replace(context.provenance, **{field: "foreign"})
    with pytest.raises(ValueError, match="identity"):
        screen_intervention(item, replace(reference(context), provenance=foreign))
    screened = screen_intervention(item, reference(context))
    with pytest.raises(ValueError, match="identity"):
        indicator_selection(replace(context, provenance=foreign), (screened,))


def test_unlisted_intervention_keeps_inventory_without_guessed_exclusion(context):
    item = Intervention(
        "special operation",
        InterventionType.OTHER,
        context,
        "river",
        Area(100, "km2"),
        description="site-specific operator evidence",
    )
    screen = screen_intervention(item, reference(context))
    assert screen.state is ScreenState.UNDETERMINED
    assert all(result.classification is None for result in indicator_selection(context, (screen,)))
    assert screen.interventions == (item,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("scenario", "other"),
        ("reference_member", "other"),
        ("data_version", "other"),
        ("configuration_version", "other"),
        ("reference_kind", ReferenceKind.FUTURE_CLIMATE_STRESS),
    ],
)
def test_reference_eligibility_binds_source_identity(context, field, value):
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        replace(context.provenance, **{field: value}),
        "study",
    )
    result = reference_eligibility(context, Indicator.MEAN_FLOW, conditions)
    assert "reference eligible" not in " ".join(result.reasons)
    assert field in " ".join(result.reasons)


@pytest.mark.parametrize("restriction", ["missing", "warmup"])
def test_reference_eligibility_honours_unavailable_source(context, restriction):
    provenance = (
        replace(context.provenance, correction_state=CorrectionState.MISSING)
        if restriction == "missing"
        else replace(context.provenance, excluded_warmup=(context.period,))
    )
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        provenance,
        "study",
    )
    result = reference_eligibility(context, Indicator.MEAN_FLOW, conditions)
    assert "reference eligible" not in " ".join(result.reasons)
    assert ("missing" if restriction == "missing" else "warm-up") in " ".join(result.reasons)


def test_explicit_reference_relationship_preserves_distinct_source_history(context):
    source = replace(
        context.provenance,
        scenario="historic source",
        reference_member="donor",
        data_version="archive",
        configuration_version="source",
        reference_kind=ReferenceKind.NATURALISED_HISTORICAL,
    )
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "study transfers historic observations to current assessment",
        source_period=context.period,
        application=application(context, source),
    )
    assert reference_limitations(context, conditions) == ()
    result = reference_eligibility(context, Indicator.MEAN_FLOW, conditions)
    assert "reference eligible" in result.reasons[0]
    assert result.inputs == (conditions,) and conditions.provenance == source
    other = replace(context, location=replace(context.location, section=CalculationSection("other", "v1")))
    assert "assessment_context" in " ".join(reference_limitations(other, conditions))
    assert "reference eligible" not in " ".join(reference_eligibility(other, Indicator.MEAN_FLOW, conditions).reasons)
    for provenance in (
        replace(source, correction_state=CorrectionState.MISSING),
        replace(source, excluded_warmup=(context.period,)),
    ):
        restricted = replace(conditions, provenance=provenance)
        assert reference_limitations(context, restricted)
        assert "reference eligible" not in " ".join(
            reference_eligibility(context, Indicator.MEAN_FLOW, restricted).reasons
        )


def test_nonoverlapping_reference_warmup_does_not_block(context):
    preceding = Interval(context.period.start - timedelta(days=1), context.period.start)
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        replace(context.provenance, excluded_warmup=(preceding,)),
        "study",
    )
    assert reference_limitations(context, conditions) == ()


def test_reference_application_cannot_reuse_relationship_after_source_mutation(context):
    source = replace(context.provenance, scenario="historic source", data_version="archive")
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "transfer study",
        source_period=context.period,
        application=application(context, source),
    )
    stale = replace(conditions, provenance=replace(source, data_version="different archive"))
    assert reference_limitations(context, stale)


def application(context, source, source_period=None):
    period = source_period or context.period
    scope = reference_application_scope(source, period, context)
    evidence = EvidenceFindings(
        scope,
        replace(context.provenance, source="independent specialist"),
        Computability.COMPUTABLE,
        NumericalValidity.VALID,
        Disclosure.COMPLETE,
        ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
        OfficialAdmissibility.PENDING,
        ("reference-transfer study",),
    )
    return ReferenceApplication(source, period, context, evidence)


@pytest.mark.parametrize("change", ["target", "period", "unknown", "failed", "scope", "missing", "evidence_identity"])
def test_reference_application_rejects_unbound_or_failed_evidence(context, change):
    source = replace(context.provenance, scenario="historical", data_version="archive")
    relation = application(context, source)
    assert relation.evidence is not None
    if change == "target":
        relation = replace(relation, target=replace(context, provenance=replace(context.provenance, scenario="other")))
    elif change == "period":
        relation = replace(
            relation, source_period=Interval(context.period.start - timedelta(days=1), context.period.start)
        )
    elif change == "unknown":
        relation = replace(
            relation, evidence=replace(relation.evidence, scientific_adequacy=ScientificAdequacy.UNKNOWN)
        )
    elif change == "failed":
        relation = replace(
            relation, evidence=replace(relation.evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
        )
    elif change == "scope":
        relation = replace(
            relation, evidence=replace(relation.evidence, scope=replace(relation.evidence.scope, reach="other"))
        )
    elif change == "missing":
        relation = replace(relation, evidence=None)
    else:
        relation = replace(
            relation, evidence=replace(relation.evidence, provenance=replace(context.provenance, data_version="other"))
        )
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "transfer study",
        source_period=context.period,
        application=relation,
    )
    assert reference_limitations(context, conditions)
    assert "reference eligible" not in " ".join(reference_eligibility(context, Indicator.MEAN_FLOW, conditions).reasons)


def test_historical_source_period_controls_warmup_scope(context):
    historical = Interval(datetime(1980, 1, 1, tzinfo=UTC), datetime(1990, 1, 1, tzinfo=UTC))
    source = replace(context.provenance, scenario="historic", data_version="archive", excluded_warmup=(context.period,))
    relation = application(context, source, historical)
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "historic reference transfer",
        source_period=historical,
        application=relation,
    )
    assert reference_limitations(context, conditions) == ()
    assert "reference eligible" in reference_eligibility(context, Indicator.MEAN_FLOW, conditions).reasons[0]
    invalid_source = replace(source, excluded_warmup=(historical,))
    restricted = replace(
        conditions, provenance=invalid_source, application=application(context, invalid_source, historical)
    )
    assert "warm-up" in " ".join(reference_limitations(context, restricted))


def test_reference_permission_cannot_move_when_source_and_relation_both_change(context):
    source = replace(context.provenance, scenario="historic", data_version="archive")
    relation = application(context, source)
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "study",
        source_period=context.period,
        application=relation,
    )
    other_source = replace(source, data_version="unreviewed archive")
    mutated = replace(conditions, provenance=other_source, application=replace(relation, source=other_source))
    assert reference_limitations(context, mutated)


@pytest.mark.parametrize("restriction", ["missing", "warmup"])
def test_application_evidence_provenance_restrictions_survive_positive_flags(context, restriction):
    source = replace(context.provenance, scenario="historic")
    relation = application(context, source)
    assert relation.evidence is not None
    provenance = (
        replace(relation.evidence.provenance, correction_state=CorrectionState.MISSING)
        if restriction == "missing"
        else replace(relation.evidence.provenance, excluded_warmup=(context.period,))
    )
    relation = replace(relation, evidence=replace(relation.evidence, provenance=provenance))
    conditions = ReferenceConditions(
        LandscapeBasis.CURRENT,
        ReferenceProfile.SWISS,
        WaterBodyKind.RIVER,
        ReferenceSuitability.SUPPORTED,
        source,
        "study",
        source_period=context.period,
        application=relation,
    )
    assert reference_limitations(context, conditions)
