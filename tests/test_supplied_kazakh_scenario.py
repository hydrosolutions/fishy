"""External acceptance of one supplied Kazakh scenario through public Fishy operations."""

from dataclasses import replace
from datetime import date
from fractions import Fraction

import pytest

from examples.supplied_ecological_studies import supplied_assessments
from examples.supplied_kazakh_scenario import (
    HISTORY,
    IDENTITY,
    LOCATION,
    MONTHS,
    PROVENANCE,
    YEAR,
    biological_timing,
    chemical_classification,
    corrected_design,
    natural_reference,
    review_inventory,
    scoped_support,
    selected_classification,
    source_bounds,
    support,
)
from fishy.basin import Basin, DonorReference, DonorRelation, PreparedTopology, River, RiverConnection, SectionContext
from fishy.design_conditions import DesignClass
from fishy.ecological_conditions import assess_floodplain
from fishy.evidence import CheckFinding, Completeness, OfficialAdmissibility
from fishy.flow_bounds import CandidateStatus, CorrectionOrder, correct_schedule
from fishy.flows import Presence
from fishy.kazakh_allocation import (
    AllocationRoute,
    AllocationStatus,
    DonorChoice,
    InitialCoefficient,
    ObservationRoute,
    initial_allocation,
    transfer_allocation,
)
from fishy.kazakh_review import (
    Applicability,
    BasinChange,
    ChangeState,
    RevisionState,
    assess_review,
    order179_applicability,
)
from fishy.quantities import Flow, Volume
from fishy.seasonal_allocation import ScheduleStage, appendix1_report, seasonal_schedule
from fishy.spatial import CalculationSection, Location, Reach, WaterBody
from fishy.spawning import (
    CoefficientInterpretation,
    EligibilityInterpretation,
    StarRelevance,
    TemporalBasis,
    coefficient_scope,
    spawning_schedule,
)
from fishy.water_classification import (
    UseFinding,
    UseInterpretation,
    UseMapping,
    WaterClass,
    WaterUse,
    assess_order111_use,
)


@pytest.mark.parametrize("observations", [ObservationRoute.ADEQUATE, ObservationRoute.INSUFFICIENT])
@pytest.mark.parametrize("route", [AllocationRoute.PROBABILITY_SHIFT, AllocationRoute.MEDIAN_NORMALISED])
@pytest.mark.parametrize("design,millions", zip(DesignClass, (100, 80, 60, 40), strict=True))
def test_complete_supplied_regime(design, millions, route, observations):
    initial = initial_allocation(natural_reference(observations), design, route)
    corrected, report = corrected_design(initial)
    expected_multiplier = Fraction(1) if design.value < 75 else Fraction(619, 610)
    expected = Volume(millions * 1_000_000 * expected_multiplier)
    assert initial.volume == Volume(millions * 1_000_000)
    assert corrected.actual_volume == expected == report.annual.volume
    assert corrected.annual_checks.finding is CheckFinding.PASS
    assert corrected.annual_checks.completeness is Completeness.COMPLETE
    assert all(c.finding is CheckFinding.PASS for c in corrected.annual_scientific_use)
    assert all(not item.conflicts for item in corrected.intervals)
    assert corrected.status is CandidateStatus.INTERPRETED  # numerical pass never reconciles law
    assert report.identity == IDENTITY
    assert report.annual.flow == Flow(expected.value / YEAR.seconds)
    assert report.monthly[1].annual_share_percent == Fraction(29 * 100, 366) / expected_multiplier
    assert sum(c.annual_share_percent for c in report.monthly) == 100
    assert sum(c.volume.value for c in report.monthly) == expected.value
    assert report.monthly[3].flow == Flow(
        Fraction(millions * 1_000_000, YEAR.seconds) * (Fraction(1) if design.value < 75 else Fraction(118, 100))
    )
    studies = supplied_assessments(corrected.samples)
    assert len(studies) == 80
    assert all(
        a.numerical.finding is CheckFinding.PASS and a.numerical.completeness is Completeness.COMPLETE for a in studies
    )
    assert all(a.scientific_use.finding is CheckFinding.PASS for a in studies)
    assert all(
        a.study is not None and a.study.findings.official_admissibility is OfficialAdmissibility.PENDING
        for a in studies
    )
    assert chemical_classification(PROVENANCE).classes[0].summary.finding is CheckFinding.PASS
    assert selected_classification(PROVENANCE).supported_matches == (WaterClass.FOUR,)
    assert review_inventory(PROVENANCE).state is RevisionState.NOT_DUE


def test_partial_annual_missing_shape_and_reconstruction():
    reference = natural_reference(ObservationRoute.ADEQUATE)
    initial = initial_allocation(reference, DesignClass.MEDIUM, AllocationRoute.PROBABILITY_SHIFT)
    seasonal = seasonal_schedule(initial, YEAR, None, None)
    report = appendix1_report(initial, YEAR, seasonal.samples, ScheduleStage.INITIAL, IDENTITY)
    assert report.initial.volume == Volume(80_000_000)
    assert report.annual.volume is None
    assert all(c.presence is Presence.MISSING for c in report.monthly)
    incomplete = replace(natural_reference(ObservationRoute.INSUFFICIENT), reconstruction=None)
    assert initial_allocation(incomplete, DesignClass.MEDIUM, AllocationRoute.PROBABILITY_SHIFT).volume is None


def test_unsupported_biology_and_infeasible_bounds_preserve_initial():
    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT
    )
    corrected, report = corrected_design(initial)
    unsupported = spawning_schedule(
        LOCATION,
        MONTHS,
        PROVENANCE,
        initial.design,
        EligibilityInterpretation.DRY_YEAR_WORDING,
        TemporalBasis.MONTHLY_AVERAGE,
        CoefficientInterpretation.LISTED_VALUE,
        StarRelevance.AFFECTS_ELIGIBILITY,
        biological_timing(PROVENANCE),
        tuple(support(coefficient_scope(LOCATION, m, PROVENANCE), PROVENANCE) for m in MONTHS),
        basin_row=2,
    )
    result = correct_schedule(
        tuple(c.original for c in corrected.intervals),
        source_bounds(PROVENANCE),
        unsupported,
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        report.samples[0].provenance,
    )
    assert result.actual_volume is None
    assert all(s.presence is Presence.UNSUPPORTED for s in result.samples)
    bounds = source_bounds(PROVENANCE)
    crossed = replace(bounds, natural_p99=tuple(replace(s, value=Flow(99)) for s in bounds.natural_p99))
    infeasible = correct_schedule(
        tuple(c.original for c in corrected.intervals),
        crossed,
        tuple(c.coefficient for c in corrected.intervals),
        CorrectionOrder.CORRECTION_THEN_BOUNDS,
        report.samples[0].provenance,
    )
    assert infeasible.status is CandidateStatus.UNRESOLVED
    assert infeasible.actual_volume is None
    assert report.initial.volume == Volume(40_000_000)


def test_required_failure_survives_missing_condition():
    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT
    )
    corrected, _ = corrected_design(initial)
    flood = next(
        a
        for a in supplied_assessments(corrected.samples)
        if "floodplain_depth" in tuple(c.check_id for c in a.numerical.checks)
    )
    from fishy.ecological_conditions import Duration
    from fishy.quantities import SignedState, StateVariable

    fail = assess_floodplain(
        flood.scope,
        flood.study,
        SignedState(StateVariable.STAGE, "0.05", "m", "depth"),
        SignedState(StateVariable.STAGE, "0.2", "m", "depth"),
        None,
        Duration(86400),
        None,
        None,
    )
    assert fail.numerical.finding is CheckFinding.FAIL
    assert fail.numerical.completeness is Completeness.INCOMPLETE
    unknown = assess_floodplain(flood.scope, None, None, None, None, None, None, None)
    assert unknown.numerical.finding is CheckFinding.UNKNOWN


def test_configuration_isolation_and_review_triggers():
    ref = natural_reference(ObservationRoute.ADEQUATE)
    initial = initial_allocation(ref, DesignClass.DRY, AllocationRoute.MEDIAN_NORMALISED)
    first, report = corrected_design(initial)
    other = replace(PROVENANCE, scenario="other", configuration_version="config-v2", data_version="data-v2")
    second, new_report = corrected_design(
        initial_allocation(
            natural_reference(ObservationRoute.ADEQUATE, other), DesignClass.DRY, AllocationRoute.MEDIAN_NORMALISED
        ),
        basin_row=3,
    )
    assert second.actual_volume == Volume(Fraction(40_000_000 * 309, 305))
    assert first.actual_volume != second.actual_volume
    assert report.samples[0].provenance.scenario != new_report.samples[0].provenance.scenario
    # The native scenario/configuration and listed-row override above changes results.
    # Re-running the original supplied configuration preserves its issued evidence.
    assert corrected_design(initial) == (first, report)
    review = review_inventory(PROVENANCE)
    changed = assess_review(
        review.applicability,
        review.last_study,
        BasinChange(ChangeState.CHANGED, PROVENANCE),
        BasinChange(ChangeState.UNKNOWN, None),
    )
    assert changed.state is RevisionState.REQUIRED
    assert changed.checks.completeness is Completeness.INCOMPLETE
    assert order179_applicability(date(2026, 12, 31), 11, PROVENANCE).status is Applicability.NOT_YET_IN_FORCE
    assert order179_applicability(date(2027, 1, 1), 11, PROVENANCE).status is Applicability.IN_FORCE
    assert review.applicability.status is Applicability.UNKNOWN  # publication evidence not invented


def test_use_mapping_keeps_conflict_and_replica_restrictions():
    results = tuple(
        assess_order111_use(
            WaterClass.FOUR,
            WaterUse.DRINKING_INTENSIVE,
            None if mapping is None else UseInterpretation(mapping, "synthetic mapping"),
        )
        for mapping in (None, UseMapping.DESCRIPTIVE, UseMapping.MATRIX)
    )
    assert tuple(r.finding for r in results) == (
        UseFinding.UNRESOLVED,
        UseFinding.CONDITIONAL,
        UseFinding.NOT_PERMITTED,
    )
    assert all(
        r.descriptive.finding is UseFinding.CONDITIONAL and r.matrix.finding is UseFinding.NOT_PERMITTED
        for r in results
    )
    assert all(r.limitations for r in results)


@pytest.mark.parametrize(
    "design,coefficient", zip(DesignClass, (Fraction(1), Fraction(4, 5), Fraction(3, 5), Fraction(2, 5)), strict=True)
)
def test_absent_observations_supported_parent_enters_same_complete_chain(design, coefficient):
    parent = River("receiving-parent", "v1", 0)
    recipient = River("ungauged-tributary", "v1", 1)
    donor = Location(
        Reach("donor-reach", "v1", WaterBody("donor-body", "v1")), CalculationSection("donor", "v1"), "map-v1"
    )
    topology = PreparedTopology(
        Basin("illustrative-basin", "v1"),
        "topology-v1",
        (parent, recipient),
        (RiverConnection(recipient, parent),),
        (SectionContext(parent, donor, None), SectionContext(recipient, LOCATION, donor)),
    )
    reference = natural_reference(ObservationRoute.ABSENT)
    relation = DonorRelation(
        recipient,
        parent,
        scoped_support("receiving_parent_transfer", HISTORY, "initial_allocation", PROVENANCE),
        DonorReference(PROVENANCE, HISTORY),
    )
    transfer = InitialCoefficient(
        design,
        coefficient,
        donor,
        scoped_support(
            f"initial_coefficient_P{design.value}", HISTORY, "initial_allocation_transfer", PROVENANCE, donor
        ),
    )
    initial = transfer_allocation(
        reference, design, topology, recipient, relation, transfer, DonorChoice.RECEIVING_PARENT
    )
    assert initial.status is AllocationStatus.SUPPORTED
    corrected, report = corrected_design(initial)
    assert corrected.annual_checks.finding is CheckFinding.PASS
    assert report.annual.volume == corrected.actual_volume
    missing = transfer_allocation(reference, design, topology, recipient, relation, None, DonorChoice.RECEIVING_PARENT)
    assert missing.status is AllocationStatus.FURTHER_STUDY
    assert missing.volume is None


def test_prepared_basin_context_and_attributed_account_do_not_sum_repeated_sections():
    from examples.supplied_basin_context import prepared_basin, supplied_tributary_account
    from fishy.basin import ContextKind, mouth_to_source, tributary_sum
    from fishy.evidence import permitted_use

    topology = prepared_basin(IDENTITY, YEAR, PROVENANCE)
    ordered = mouth_to_source(topology)
    assert tuple(s.location.section.identifier for s in ordered) == (
        "illustrative-section",
        "main-upstream",
        "left",
        "right",
    )
    for section in topology.sections:
        assert {e.kind for e in section.evidence} == set(ContextKind)
        assert all(permitted_use(e.findings, e.findings.scope).finding is CheckFinding.PASS for e in section.evidence)
    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT
    )
    _, report = corrected_design(initial)
    assert report.annual.volume is not None
    account = supplied_tributary_account(topology, IDENTITY, YEAR, PROVENANCE, report.annual.volume, report.design)
    assert account.volume == report.annual.volume
    assert tuple(a.volume.value for a in account.accounts) == (
        report.annual.volume.value * Fraction(3, 5),
        report.annual.volume.value * Fraction(2, 5),
    )
    missing = tributary_sum(topology, IDENTITY.river, LOCATION, account.scope, account.accounts, None)
    assert missing.volume is None
    with pytest.raises(ValueError, match="Repeated"):
        tributary_sum(topology, IDENTITY.river, LOCATION, account.scope, account.accounts * 2, account.evidence)


def test_historical_2024_leap_shape_keeps_volume_but_quality_cannot_backdate():
    from datetime import UTC, datetime

    from fishy.kazakh_allocation import NaturalExceedance
    from fishy.seasonal_allocation import SeasonalShape, ShapeChoice, ShapeOrdinate
    from fishy.time import Interval
    from fishy.water_classification import (
        ClassificationObservation,
        Order111Profile,
        SourceValue,
        WaterScope,
        assess_order111,
        source_row,
    )

    year = Interval(datetime(2024, 1, 1, tzinfo=UTC), datetime(2025, 1, 1, tzinfo=UTC))
    months = tuple(
        Interval(datetime(2024, m, 1, tzinfo=UTC), datetime(2024 + (m == 12), m % 12 + 1, 1, tzinfo=UTC))
        for m in range(1, 13)
    )
    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.WET, AllocationRoute.PROBABILITY_SHIFT
    )
    shape = SeasonalShape(
        LOCATION,
        year,
        NaturalExceedance.P50,
        tuple(ShapeOrdinate(m, Fraction(1)) for m in months),
        PROVENANCE,
        scoped_support("seasonal_shape_P50", year, "seasonal_allocation", PROVENANCE),
    )
    seasonal = seasonal_schedule(initial, year, ShapeChoice.SHIFTED_CLASS, shape)
    report = appendix1_report(initial, year, seasonal.samples, ScheduleStage.INITIAL, IDENTITY)
    assert report.annual.volume == Volume(100_000_000)
    assert report.monthly[1].annual_share_percent == Fraction(2900, 366)
    row = source_row("order111:02")
    profile = Order111Profile(
        "historical",
        "v1",
        PROVENANCE.scenario,
        LOCATION,
        year,
        WaterScope.RIVER,
        date(2029, 1, 1),
        (row.identifier,),
        "interval",
    )
    observation = ClassificationObservation(
        row.identifier,
        SourceValue(7, 7, row.unit, row.name),
        LOCATION,
        year,
        profile.basis,
        Presence.PRESENT,
        PROVENANCE,
    )
    result = assess_order111(profile, (observation,))
    assert result.unknown_classes == tuple(WaterClass)
    assert any("commencement" in reason for reason in result.classes[0].cells[0].check.reasons)


def test_supplied_hydraulic_relation_changes_actual_report_without_renormalising():
    from fishy.ecological_conditions import (
        CorrectionPosition,
        EcologicalScope,
        EcologicalStudy,
        StateSupport,
        apply_hydraulic_correction,
    )
    from fishy.quantities import SignedState, StateVariable

    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT
    )
    corrected, report = corrected_design(initial)
    april = corrected.intervals[3].original
    scope = EcologicalScope(
        LOCATION, april.interval, april.provenance, "hydraulic adjustment", "synthetic correction", "Order179-2025"
    )
    study = EcologicalStudy(
        scope,
        support(scope.evidence_scope, april.provenance),
        StateSupport.INTERVAL_ENVELOPE,
        "synthetic additive relation at this candidate flow",
        "supplied depth and velocity criteria",
    )
    hydraulic = apply_hydraulic_correction(
        scope,
        study,
        april,
        SignedState(StateVariable.EXCHANGE, "0.1", "m3/s", "additive hydraulic adjustment"),
        CorrectionPosition.BEFORE_SPAWNING,
    )
    assert hydraulic.corrected == Flow(april.value.value + Fraction(1, 10))
    originals = tuple(
        replace(item.original, value=hydraulic.corrected) if index == 3 else item.original
        for index, item in enumerate(corrected.intervals)
    )
    result = correct_schedule(
        originals,
        corrected.bounds,
        tuple(item.coefficient for item in corrected.intervals),
        corrected.order,
        report.samples[0].provenance,
    )
    assert result.actual_volume == Volume(corrected.actual_volume.value + Fraction(118, 1000) * 30 * 86400)
    actual = appendix1_report(initial, YEAR, result.samples, ScheduleStage.CORRECTED, IDENTITY)
    assert actual.annual.volume == result.actual_volume
    assert initial.volume == Volume(40_000_000)


def test_supplied_kazakh_duty_is_not_generated_or_capped_by_deliverability():
    from fishy.duties import (
        Availability,
        ComparisonKind,
        Deliverability,
        Delivery,
        DutyApplicability,
        Obligation,
        Requirement,
        SuppliedDuty,
        assess_duty,
        assess_feasibility,
    )

    initial = initial_allocation(
        natural_reference(ObservationRoute.ADEQUATE), DesignClass.DRY, AllocationRoute.PROBABILITY_SHIFT
    )
    corrected, report = corrected_design(initial)
    sample = corrected.samples[3]
    requirement = Requirement(sample, "candidate-v1")
    available = Availability(replace(sample, value=Flow(8)), "availability-v1")
    deliverable = Deliverability(replace(sample, value=Flow(6)), "capacity-v1")
    issued = Obligation(replace(sample, value=Flow(10)), "issued-v1")
    delivered = Delivery(replace(sample, value=Flow(5)), "delivery-v1")
    duty = SuppliedDuty(
        "independent supplied Kazakh duty",
        "issued-v1",
        "separately supplied illustrative duty, not derived from annual allocation",
        DutyApplicability.HYPOTHETICAL,
        (issued,),
        "synthetic instrument search",
        required_components=("discharge", "hydraulic"),
    )
    feasibility = assess_feasibility(duty, (deliverable,))
    result = assess_duty(duty, (delivered,))
    assert feasibility.intervals[0].shortfall == Flow(4)
    assert result.intervals[0].shortfall == Flow(5)
    assert result.known_shortfall_volume == Volume(5 * sample.interval.seconds)
    assert result.summary.finding is CheckFinding.FAIL
    assert result.summary.completeness is Completeness.INCOMPLETE
    assert result.interpretation is ComparisonKind.PREDICTION
    assert duty.schedule[0].sample.value == Flow(10)
    assert requirement.sample.value == report.monthly[3].flow
    assert available.sample.value == Flow(8)
    assert report.initial.volume == initial.volume
    later = assess_duty(duty, (Delivery(replace(delivered.sample, value=Flow(11)), "delivery-v2"),))
    assert later.intervals[0].shortfall == Flow(0)
    assert later.summary.finding is CheckFinding.UNKNOWN
    assert result.intervals[0].shortfall == Flow(5)
    assert duty.schedule[0].sample.value == Flow(10)
