"""zero_source_acceptance : ZeroOriginStudy × ActiveQualityUplift → FinalFloorChecks.

Complete synthetic years show that a ZERO result does not erase its actual
habitat/hydraulic sizing origin. No policy or ecological calibration is claimed.
"""

from dataclasses import replace
from datetime import date, timedelta
from fractions import Fraction

import pytest

from examples.alternative_requirements import family_basis, local_quality
from examples.requirement_chain import TARGET, accepted_evidence, samples
from examples.study_requirements import POTENTIAL
from fishy.evidence import CheckFinding, EvidenceScope, ReferenceKind
from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
from fishy.hydraulics import Comparison, HydraulicRelationEvidence, RelationDomain, StateBounds
from fishy.potential_requirements import (
    Applicability,
    AuthorityBasis,
    PotentialRoute,
    PotentialStudy,
    ServiceZeroDetermination,
    ZeroInterpretation,
    size_potential_floor,
)
from fishy.quality_activation import QualityRoute
from fishy.quantities import Flow, Volume
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_family import (
    FloorSeries,
    ReconstructionNeed,
    RequirementMember,
    SelectionSpecification,
    assess_selected_family,
    candidate_scope,
)
from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
from fishy.study_requirements import (
    FlowResponseRelation,
    Interpolation,
    ResponsePoint,
    ResponseVariable,
    StudyCondition,
    StudyCriterion,
    StudyNeed,
    StudyScope,
    StudySelection,
    StudyVariable,
)


def study(sample, route, *, relaxed=False, response_at10=20):
    scope = StudyScope(
        sample_subject(sample),
        sample.location,
        sample.interval,
        sample.provenance.scenario,
        sample.provenance.reference_member,
        "potential-sizing",
        "complete constant synthetic year",
    )
    evidence = accepted_evidence(
        EvidenceScope(
            scope.candidate,
            sample.location.reach.identifier,
            sample.provenance.reference_member,
            sample.interval,
            scope.purpose,
        ),
        sample.provenance,
    )
    metadata = HydraulicRelationEvidence(
        "zero-origin-v1",
        "synthetic geometry",
        "fixed boundary",
        "0<=Q<=10m3/s",
        "supported linear response",
        "exact hypothetical singleton states",
        "synthetic scenario only",
        RelationDomain.SUPPORTED,
    )
    variables = (
        ((StudyVariable.HABITAT, "m2"),)
        if route is PotentialRoute.HABITAT
        else ((StudyVariable.DEPTH, "m"), (StudyVariable.VELOCITY, "m/s"))
    )
    criteria, relations = [], []
    for variable, units in variables:
        response = ResponseVariable(variable, units, "synthetic reference datum", "synthetic section response")
        criteria.append(
            StudyCriterion(
                variable.value,
                response,
                StateBounds(Fraction(0 if relaxed else 40), Fraction(100)),
                Comparison.INCLUSIVE,
                Comparison.INCLUSIVE,
                "explicit hypothetical source objective40..100",
            )
        )
        relations.append(
            FlowResponseRelation(
                scope,
                response,
                (
                    ResponsePoint(Flow(0), StateBounds(Fraction(60), Fraction(60))),
                    ResponsePoint(Flow(10), StateBounds(Fraction(response_at10), Fraction(response_at10))),
                ),
                Interpolation.LINEAR,
                "synthetic declining response curve",
                metadata,
                evidence,
            )
        )
    ramp = StudyCondition(
        scope,
        "ramping",
        "daily mean flow change",
        "m3/s/day",
        "constant full-year scenario",
        "explicit zero daily change",
        "constant candidate with independently supplied same-flow predecessor",
        CheckFinding.PASS,
        evidence,
    )
    selected = StudySelection(
        scope,
        sample.value,
        "explicit source-selected candidate",
        "hypothetical habitat or joint hydraulics",
        evidence,
        tuple(criteria),
        ("ramping",),
        (ramp,),
    )
    return selected, tuple(relations)


def service_zero(sample):
    from fishy.service_conveyance import (
        Authentication,
        ConvergenceRule,
        ConveyanceRamp,
        ConveyanceRelation,
        ConveyanceState,
        DutySource,
        ServiceConveyanceRequest,
        ServiceDuty,
    )
    from fishy.time import Interval

    def evidence(product, period):
        return accepted_evidence(
            EvidenceScope(
                product,
                sample.location.reach.identifier,
                sample.provenance.reference_member,
                period,
                "service_conveyance",
            ),
            sample.provenance,
        )

    period = sample.interval
    relation = ConveyanceRelation(
        "zero-service",
        sample.location,
        period,
        Volume(0),
        sample.location,
        (ConveyanceState(Flow(0), Volume(0), ()), ConveyanceState(Flow(8), Volume(0), ())),
        "fixed geometry",
        "zero-loss fixed storage",
        "exact synthetic",
        evidence("zero-service", period),
    )
    duty = ServiceDuty(
        "zero-duty",
        sample.location,
        period,
        Volume(0),
        DutySource.OPERATING_RULE,
        Authentication.AUTHENTICATED,
        evidence("zero-duty", period),
        Flow(8),
    )
    transition = Interval(period.start - timedelta(days=1), period.start)
    ramp = ConveyanceRamp(Flow(0), transition, Flow(8), Flow(8), evidence("conveyance_ramp", transition))
    return ServiceConveyanceRequest(
        sample.location,
        period,
        (duty,),
        relation,
        (),
        Flow(0),
        ConvergenceRule(Volume(0), 2, "exact zero fixed-point, no tolerated deficit"),
        Flow(8),
        ramp,
    )


def zero_origin_year(route, final_study, *, response_at10=20, base_flow=0, with_service=False):
    missing = PotentialStudy(Applicability.NOT_APPLICABLE, "other route not applicable to this scenario", None, ())
    review = StudyNeed("hypothetical zero review", "synthetic review owner", date(2027, 1, 1))
    required = (FinalCondition.QUALITY,) if final_study == "omitted" else (FinalCondition.QUALITY, FinalCondition.STUDY)
    sources, components, finals, physical = [], [], [], []
    for raw in samples(TARGET, base_flow, "zero-origin", "R"):
        base = replace(raw, provenance=replace(raw.provenance, reference_kind=ReferenceKind.MANAGED))
        selected, relations = study(base, route, response_at10=response_at10)
        zero = ServiceZeroDetermination(
            selected.scope,
            ZeroInterpretation.SERVICE_DETERMINATION,
            AuthorityBasis.HYPOTHETICAL,
            selected.evidence,
            "explicit supported zero service determination",
            "hypothetical competent signoff",
            "retained audit right",
            "named dispute route",
            "accepted no service impact at sourceQ0",
            review,
        )
        applicable = PotentialStudy(
            Applicability.APPLICABLE, "source objective and relation accepted", selected, relations
        )
        habitat, hydraulic = (applicable, missing) if route is PotentialRoute.HABITAT else (missing, applicable)
        conveyance = service_zero(base) if with_service else None
        source = PotentialFloorSource(selected.scope, POTENTIAL, habitat, hydraulic, conveyance, review, zero=zero)
        native = size_potential_floor(selected.scope, POTENTIAL, habitat, hydraulic, conveyance, review, zero=zero)
        assert native.floor == Flow(base_flow)
        assert native.selected_route is (PotentialRoute.ZERO if base_flow == 0 else route)
        assert any(r.route is route and r.flow == Flow(base_flow) for r in native.routes)
        sources.append(native)
        q = local_quality(base, route=QualityRoute.FLOOR_ONLY, background_mg_l=10)
        composition = compose_requirement(base, base.provenance, quality=q)
        sample = composition.candidate
        assert sample is not None and sample.value == Flow(10)
        components.append(FloorComponent(source, composition))
        finals.append(sample)
        kwargs = {}
        if final_study != "omitted":
            selected, relations = study(sample, route, relaxed=final_study == "relaxed", response_at10=response_at10)
            kwargs = {"study_selection": selected, "study_relations": relations}
        physical.append(assess_requirement(sample, required, quality=q, **kwargs))
    series = FloorSeries(family_basis(finals[0], TARGET.interval, "potential-floor"), tuple(finals))
    member = RequirementMember(
        "zero-origin",
        "supported potential study, not a natural reconstruction",
        series,
        accepted_evidence(candidate_scope(series), finals[0].provenance),
        "single artificial reach",
    )
    selection = assess_selected_family(
        (member,),
        series,
        SelectionSpecification(
            (member.identifier,),
            (),
            Fraction(1, 5),
            ReconstructionNeed.NOT_REQUIRED,
            "potential route source-bound exemption",
        ),
    )
    result = finalize_floors(
        selection,
        required,
        tuple(physical),
        version="zero-origin-final-v1",
        constructions=(FloorConstruction(member.identifier, tuple(components)),),
        member_physical=tuple(FloorMemberAssessment(member.identifier, item) for item in physical),
    )
    return tuple(sources), result


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
@pytest.mark.parametrize("final_study", ["omitted", "relaxed"])
def test_zero_reconciliation_cannot_erase_study_origin_after_quality_uplift(route, final_study):
    sources, result = zero_origin_year(route, final_study)
    assert len(sources) == 365
    assert all(s.selected_route is PotentialRoute.ZERO and s.floor == Flow(0) for s in sources)
    assert len(result.physical) == len(result.member_physical) == 365
    assert all(p.checks.finding is CheckFinding.PASS for p in result.physical)
    assert result.checks.finding is CheckFinding.FAIL
    assert not result.floors
    assert result.source_conditions
    assert any(
        response.check.finding is CheckFinding.FAIL
        for condition in result.source_conditions
        for response in condition.responses
    )


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_zero_origin_study_can_pass_supported_final_uplift_inside_original_criteria(route):
    sources, result = zero_origin_year(route, "supported", response_at10=60)
    assert all(s.selected_route is PotentialRoute.ZERO for s in sources)
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.floors) == 365
    assert all(f.sample.value == Flow(10) for f in result.floors)
    assert result.source_conditions
    assert all(c.checks.finding is CheckFinding.PASS for c in result.source_conditions)


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_positive_study_does_not_acquire_unused_service_route_domain_gate(route):
    sources, result = zero_origin_year(route, "supported", response_at10=60, base_flow=5, with_service=True)
    assert all(s.selected_route is route for s in sources)
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.floors) == 365
    assert result.conveyance_conditions == ()


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_zero_study_keeps_its_actually_used_service_zero_domain_after_quality(route):
    sources, result = zero_origin_year(route, "supported", response_at10=60, with_service=True)
    assert all(s.selected_route is PotentialRoute.ZERO for s in sources)
    assert all(next(r for r in s.routes if r.route is PotentialRoute.ZERO).conveyance is not None for s in sources)
    assert result.checks.finding is CheckFinding.FAIL
    assert not result.floors
    assert result.conveyance_conditions
