"""Synthetic study selections exercise public relations, route descent and history."""

from dataclasses import replace
from datetime import UTC, date, datetime
from fractions import Fraction

import pytest

from fishy.evidence import (
    CheckFinding,
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
    ReferenceKind,
    ScientificAdequacy,
    UseRestriction,
)
from fishy.hydraulics import Comparison, HydraulicRelationEvidence, RelationDomain, StateBounds
from fishy.quantities import Flow
from fishy.spatial import (
    CalculationSection,
    DesignationState,
    Eligibility,
    Location,
    Origin,
    PreparedClassification,
    Reach,
    UseCategory,
    WaterBody,
)
from fishy.study_requirements import (
    FlowResponseRelation,
    HighFlowTrigger,
    Interpolation,
    NaturalStudyComponent,
    ResponsePoint,
    ResponseVariable,
    StudyCondition,
    StudyCriterion,
    StudyNeed,
    StudyScope,
    StudySelection,
    StudyVariable,
    TopTierEligibility,
    assess_natural_study,
    assess_study,
)
from fishy.time import Interval

PERIOD = Interval(datetime(2026, 6, 1, tzinfo=UTC), datetime(2026, 6, 2, tzinfo=UTC))
LOCATION = Location(Reach("reach", "v1", WaterBody("river", "v1")), CalculationSection("section", "v1"), "mapping1")
SCOPE = StudyScope("candidate1", LOCATION, PERIOD, "hypothetical", "natural1", "sizing", "summer")
PROVENANCE = Provenance(
    "synthetic selected study",
    "hypothetical",
    "natural1",
    "test",
    "survey1",
    "criteria1",
    ProductionMethod.ILLUSTRATIVE,
    CorrectionState.ORIGINAL,
    ReferenceKind.PRESENT_CLIMATE_NATURAL,
)
EVIDENCE = EvidenceFindings(
    EvidenceScope("candidate1", "reach", "natural1", PERIOD, "sizing"),
    PROVENANCE,
    Computability.COMPUTABLE,
    NumericalValidity.VALID,
    Disclosure.COMPLETE,
    ScientificAdequacy.ACCEPTED_AS_INDICATIVE,
    OfficialAdmissibility.PENDING,
    ("synthetic only",),
)
HABITAT = ResponseVariable(StudyVariable.HABITAT, "m2", "survey bed", "surveyed wetted area")
DEPTH = ResponseVariable(StudyVariable.DEPTH, "m", "survey bed", "section mean")
VELOCITY = ResponseVariable(StudyVariable.VELOCITY, "m/s", "positive downstream", "section mean")
METADATA = HydraulicRelationEvidence(
    "relation1",
    "geometry1",
    "fixed downstream boundary",
    "0 to 10 m3/s",
    "linear envelopes accepted",
    "supplied bounds",
    "hypothetical sizing",
    RelationDomain.SUPPORTED,
)
NEED = StudyNeed("study and review", "basin reviewer", date(2027, 1, 1))
NATURAL = PreparedClassification(
    Origin.NATURAL,
    DesignationState.NONE,
    Eligibility.NOT_APPLICABLE,
    UseCategory.AGRICULTURE_IRRIGATION,
    ("irrigation",),
    "origin survey",
    "v1",
)
POTENTIAL = replace(NATURAL, origin=Origin.ARTIFICIAL)


def relation(variable=HABITAT, values=(0, 100, 20)):
    return FlowResponseRelation(
        SCOPE,
        variable,
        tuple(
            ResponsePoint(Flow(q), StateBounds(Fraction(v), Fraction(v)))
            for q, v in zip((0, 5, 10), values, strict=True)
        ),
        Interpolation.LINEAR,
        "channel survey1",
        METADATA,
        EVIDENCE,
    )


def criterion(variable=HABITAT, low=40, high=100):
    return StudyCriterion(
        variable.variable.value,
        variable,
        StateBounds(Fraction(low), Fraction(high)),
        Comparison.INCLUSIVE,
        Comparison.INCLUSIVE,
        "ecologist selected threshold",
    )


def condition(name, finding=CheckFinding.PASS):
    return StudyCondition(
        SCOPE,
        name,
        "study process",
        "declared study units",
        "reach and event",
        "specialist criterion v1",
        "supplied assessed process state",
        finding,
        EVIDENCE,
    )


def selection(flow=5, criteria=None, required=("ramping",)):
    return StudySelection(
        SCOPE,
        Flow(flow),
        "specialist selection v1",
        "selected potential habitat objective",
        EVIDENCE,
        (criterion(),) if criteria is None else criteria,
        required,
        tuple(condition(n) for n in required),
    )


def test_selected_nonmonotone_habitat_and_interpolation_are_computed_not_inverted():
    result = assess_study(selection(2.5), (relation(),))
    assert result.responses[0].value == StateBounds(Fraction(50), Fraction(50))
    assert result.supported_flow == Flow(2.5)
    assert result.selection.evidence.official_admissibility is OfficialAdmissibility.PENDING
    assert assess_study(selection(10), (relation(),)).checks.finding is CheckFinding.FAIL
    assert assess_study(selection(11), (relation(),)).supported_flow is None
    assert (
        assess_study(selection(2.5), (replace(relation(), interpolation=Interpolation.EXACT),)).supported_flow is None
    )


def test_missing_criterion_relation_ramping_and_restricted_evidence():
    assert assess_study(selection(criteria=()), (relation(),)).checks.finding is CheckFinding.UNKNOWN
    assert assess_study(selection(), ()).supported_flow is None
    assert (
        assess_study(replace(selection(), conditions=()), (relation(),)).checks.completeness is Completeness.INCOMPLETE
    )
    restricted = replace(EVIDENCE, restrictions=(UseRestriction("rating extrapolation", ("sizing",)),))
    result = assess_study(selection(), (replace(relation(), evidence=restricted),))
    assert result.responses[0].value == StateBounds(Fraction(100), Fraction(100))
    assert result.supported_flow is None


def test_joint_velocity_failure_survives_missing_depth_same_candidate():
    candidate = selection(criteria=(criterion(DEPTH, 1, 2), criterion(VELOCITY, 0, 1)))
    result = assess_study(candidate, (relation(VELOCITY, (0, 2, 3)),))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_scope_duplicates_and_negative_depth_rejected():
    with pytest.raises(ValueError, match="same candidate"):
        assess_study(selection(), (replace(relation(), scope=replace(SCOPE, season="winter")),))
    with pytest.raises(ValueError, match="duplicate"):
        assess_study(selection(), (relation(), relation()))
    with pytest.raises(ValueError, match="nonnegative"):
        relation(DEPTH, (0, -1, 2))
    with pytest.raises(ValueError, match="incompatible"):
        replace(selection(), evidence=replace(EVIDENCE, provenance=replace(PROVENANCE, scenario="other")))
    with pytest.raises(ValueError, match="strictly increasing"):
        replace(relation(), points=(relation().points[0], relation().points[0]))


def natural(component=None, **kwargs):
    supplied = component or NaturalStudyComponent(
        "pulse", selection(8, required=("sediment", "hydraulic", "flood_safety", "ramping")), (relation(),), "pulse"
    )
    return assess_natural_study(
        NATURAL,
        TopTierEligibility.TRIGGERED,
        ("pulse",),
        (supplied,),
        HighFlowTrigger.SEDIMENT_TRAPPING,
        NEED,
        "eligible_baseline_then_fallback",
        baseline_median_cap=Flow(3),
        **kwargs,
    )


def test_natural_pulse_exceeds_baseline_cap_with_supported_selected_study():
    result = natural()
    assert result.components[0].responses[0].value == StateBounds(Fraction(52), Fraction(52))
    assert result.supported_components == (("pulse", Flow(8)),)
    assert result.checks.finding is CheckFinding.PASS
    assert result.baseline_median_cap == Flow(3)
    assert result.next_route is None
    assert result.release_permission == "not_granted_by_calculation"


def test_natural_missing_relation_ramping_and_owner_deadline_descent():
    component = NaturalStudyComponent("pulse", selection(8), (), "pulse")
    result = natural(component)
    assert result.next_route == "eligible_baseline_then_fallback"
    assert result.supported_components == ()
    result = assess_natural_study(
        NATURAL,
        TopTierEligibility.TRIGGERED,
        ("pulse",),
        (),
        HighFlowTrigger.SEDIMENT_TRAPPING,
        StudyNeed("mandatory sediment assessment", None, None),
        "fallback",
    )
    assert {c.check_id for c in result.checks.checks} >= {"trigger_assignment", "high_flow_assessment", "pulse"}
    assert result.study_need.owner is None
    assert result.next_route == "fallback"


def test_natural_failed_ramping_and_out_of_domain_descent():
    candidate = selection(8, required=("sediment", "hydraulic", "flood_safety", "ramping"))
    candidate = replace(
        candidate,
        conditions=tuple(
            condition(n, CheckFinding.FAIL if n == "ramping" else CheckFinding.PASS)
            for n in candidate.required_conditions
        ),
    )
    result = natural(NaturalStudyComponent("pulse", candidate, (relation(),), "pulse"))
    assert result.checks.finding is CheckFinding.FAIL
    assert result.next_route is not None
    assert (
        natural(
            NaturalStudyComponent("pulse", replace(candidate, selected_flow=Flow(12)), (relation(),), "pulse")
        ).supported_components
        == ()
    )


def test_valid_designation_stops_new_natural_calculation():
    designated = replace(NATURAL, designation=DesignationState.DESIGNATED, designation_eligibility=Eligibility.ACCEPTED)
    with pytest.raises(ValueError, match="natural track"):
        assess_natural_study(designated, TopTierEligibility.PRIORITY, (), (), HighFlowTrigger.NONE, NEED, "fallback")


def test_public_study_example():
    from examples.study_requirements import main

    result = main()
    assert result.supported_components == (("pulse", Flow(8)),)
    assert result.components[0].responses[0].value == StateBounds(Fraction(52), Fraction(52))


@pytest.mark.parametrize(
    "kind", [ReferenceKind.OBSERVED, ReferenceKind.MANAGED, ReferenceKind.NATURALISED_HISTORICAL, None]
)
def test_wrong_reference_kind_cannot_supply_natural_requirement(kind):
    evidence = replace(EVIDENCE, provenance=replace(PROVENANCE, reference_kind=kind))
    candidate = replace(selection(), evidence=evidence)
    component = NaturalStudyComponent("seasonal", candidate, (relation(),), "seasonal")
    result = assess_natural_study(
        NATURAL, TopTierEligibility.PRIORITY, ("seasonal",), (component,), HighFlowTrigger.NONE, NEED, "fallback"
    )
    assert result.supported_components == ()
    assert result.next_route == "fallback"
    assert result.components[0].responses[0].value is not None


@pytest.mark.parametrize("eligibility", [TopTierEligibility.NOT_SELECTED, TopTierEligibility.UNRESOURCED])
def test_ineligible_study_retains_arithmetic_not_supported_requirement(eligibility):
    component = NaturalStudyComponent("seasonal", selection(), (relation(),), "seasonal")
    result = assess_natural_study(
        NATURAL, eligibility, ("seasonal",), (component,), HighFlowTrigger.NONE, NEED, "fallback"
    )
    assert result.supported_components == ()
    assert result.next_route == "fallback"
    assert result.components[0].supported_flow == Flow(5)


def test_supported_imported_holistic_objective_can_supply_selected_requirement():
    candidate = replace(selection(criteria=()), holistic_assessment=condition("holistic_objective"))
    component = NaturalStudyComponent("seasonal", candidate, (), "seasonal")
    result = assess_natural_study(
        NATURAL, TopTierEligibility.PRIORITY, ("seasonal",), (component,), HighFlowTrigger.NONE, NEED, "fallback"
    )
    assert result.supported_components == (("seasonal", Flow(5)),)
    assert result.checks.finding is CheckFinding.PASS
    unsupported = replace(
        candidate.holistic_assessment, evidence=replace(EVIDENCE, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    assert assess_study(replace(candidate, holistic_assessment=unsupported), ()).supported_flow is None


@pytest.mark.parametrize("component", ["relation", "condition"])
def test_mixed_study_configuration_versions_rejected(component):
    evidence = replace(EVIDENCE, provenance=replace(PROVENANCE, configuration_version="different-policy"))
    candidate = selection()
    relations = (relation(),)
    if component == "relation":
        relations = (replace(relation(), evidence=evidence),)
    else:
        candidate = replace(candidate, conditions=(replace(condition("ramping"), evidence=evidence),))
    with pytest.raises(ValueError, match="configuration"):
        assess_study(candidate, relations)


def test_unsupported_selected_threshold_failure_stays_exploratory():
    candidate = replace(selection(10), evidence=replace(EVIDENCE, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED))
    result = assess_study(candidate, (relation(),))
    assert result.responses[0].value == StateBounds(Fraction(20), Fraction(20))
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.responses[0].numerical_finding is CheckFinding.FAIL
    assert result.supported_flow is None


def test_unsupported_selection_does_not_hide_independent_supported_failure():
    candidate = replace(
        selection(10),
        evidence=replace(EVIDENCE, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED),
        conditions=(condition("ramping", CheckFinding.FAIL),),
    )
    result = assess_study(candidate, (relation(),))
    assert result.responses[0].check.finding is CheckFinding.UNKNOWN
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE


def test_natural_components_cannot_mix_policy_configurations():
    first = NaturalStudyComponent("summer", selection(), (relation(),), "seasonal")
    evidence = replace(EVIDENCE, provenance=replace(PROVENANCE, configuration_version="other-policy"))
    candidate = replace(selection(), evidence=evidence, conditions=(replace(condition("ramping"), evidence=evidence),))
    second = NaturalStudyComponent("winter", candidate, (replace(relation(), evidence=evidence),), "seasonal")
    with pytest.raises(ValueError, match="configuration"):
        assess_natural_study(
            NATURAL,
            TopTierEligibility.PRIORITY,
            ("summer", "winter"),
            (first, second),
            HighFlowTrigger.NONE,
            NEED,
            "fallback",
        )
