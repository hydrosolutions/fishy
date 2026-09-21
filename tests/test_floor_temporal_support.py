"""floor_temporal_acceptance : PotentialFloorSource × DailyFloorSeries → FinalFloorAssertions."""

from dataclasses import replace

import pytest

from examples.alternative_requirements import family_basis, local_quality, single_selection
from examples.requirement_chain import TARGET, accepted_evidence, samples
from examples.study_requirements import NEED, POTENTIAL, relation, selection
from fishy.evidence import CheckFinding, EvidenceScope
from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
from fishy.potential_requirements import (
    Applicability,
    AuthorityBasis,
    PotentialRoute,
    PotentialStudy,
    ServiceZeroDetermination,
    ZeroInterpretation,
)
from fishy.quality_activation import QualityRoute
from fishy.quantities import Flow
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_family import FloorSeries, ReconstructionNeed
from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
from fishy.source_conditions import source_period_scope
from fishy.study_requirements import StudyScope, StudyVariable


def seasonal_floor(
    *, permission="supported", original_period=None, final_study="original", zero_route=None, annual_service=False
):
    from fractions import Fraction

    from fishy.hydraulics import StateBounds

    final_flow = 6 if final_study == "original" else 10
    required = (FinalCondition.QUALITY,) if final_study == "omitted" else (FinalCondition.QUALITY, FinalCondition.STUDY)
    base_flow = 5 if zero_route is None else 0
    bases = samples(TARGET, base_flow, "potential-direct")
    first = bases[0]
    p = first.provenance
    scope = StudyScope(
        sample_subject(first),
        first.location,
        original_period or TARGET.interval,
        p.scenario,
        p.reference_member,
        "sizing",
        "constant supported habitat floor",
    )
    evidence = accepted_evidence(
        EvidenceScope(scope.candidate, first.location.reach.identifier, p.reference_member, scope.period, "sizing"), p
    )
    old = selection(base_flow)
    study = replace(
        old,
        scope=scope,
        evidence=evidence,
        conditions=tuple(replace(c, scope=scope, evidence=evidence) for c in old.conditions),
    )
    rel = replace(relation(), scope=scope, evidence=evidence)
    relations = (rel,)
    zero = None
    if zero_route is not None:
        study = replace(
            study,
            criteria=tuple(replace(c, acceptable=StateBounds(Fraction(0), Fraction(100))) for c in study.criteria),
        )
        if zero_route is PotentialRoute.HYDRAULIC:
            variables = tuple(
                replace(rel.variable, variable=variable, units=units)
                for variable, units in ((StudyVariable.DEPTH, "m"), (StudyVariable.VELOCITY, "m/s"))
            )
            criteria = tuple(
                replace(study.criteria[0], identifier=variable.variable.value, variable=variable)
                for variable in variables
            )
            study = replace(study, criteria=criteria)
            relations = tuple(replace(rel, variable=variable) for variable in variables)
        zero = ServiceZeroDetermination(
            scope,
            ZeroInterpretation.SERVICE_DETERMINATION,
            AuthorityBasis.HYPOTHETICAL,
            evidence,
            "supported seasonal no-service need",
            "explicit hypothetical signoff",
            "independent audit",
            "named dispute route",
            "no adverse service effect at source0",
            NEED,
        )
    support = accepted_evidence(source_period_scope(study, relations), p)
    if permission == "foreign":
        support = replace(support, scope=replace(support.scope, product="unrelated-threshold"))
    applicable = PotentialStudy(Applicability.APPLICABLE, "supported original study relation", study, relations)
    unused = PotentialStudy(Applicability.NOT_APPLICABLE, "other route not selected", None, ())
    habitat, hydraulic = (unused, applicable) if zero_route is PotentialRoute.HYDRAULIC else (applicable, unused)
    conveyance = None
    if annual_service:
        from test_zero_source_conditions import service_zero

        # The native service account is deliberately annual, like the source
        # study. Study-only constant-threshold permission cannot disaggregate it.
        conveyance = service_zero(replace(first, interval=scope.period))
    source = PotentialFloorSource(
        scope,
        POTENTIAL,
        habitat,
        hydraulic,
        conveyance,
        NEED,
        zero=zero,
        constant_thresholds=() if permission == "missing" else (support,),
    )
    rows, physical, finals = [], [], []
    for base in bases:
        quality = local_quality(base, route=QualityRoute.FLOOR_ONLY, background_mg_l=final_flow)
        composition = compose_requirement(base, p, quality=quality)
        final = composition.candidate
        assert final is not None and final.value == Flow(final_flow)
        rows.append(FloorComponent(source, composition))
        finals.append(final)
        fscope = replace(scope, candidate=sample_subject(final), period=final.interval)
        fe = accepted_evidence(
            EvidenceScope(
                fscope.candidate, final.location.reach.identifier, p.reference_member, final.interval, "sizing"
            ),
            p,
        )
        fresh = replace(
            study,
            scope=fscope,
            selected_flow=final.value,
            evidence=fe,
            conditions=tuple(replace(c, scope=fscope, evidence=fe) for c in study.conditions),
        )
        frels = tuple(replace(r, scope=fscope, evidence=fe) for r in relations)
        if final_study == "relaxed":
            fresh = replace(
                fresh,
                criteria=tuple(
                    replace(c, acceptable=StateBounds(Fraction(10), Fraction(100)), source="relaxed final target")
                    for c in fresh.criteria
                ),
            )
        physical.append(
            assess_requirement(
                final,
                required,
                quality=quality,
                study_selection=None if final_study == "omitted" else fresh,
                study_relations=() if final_study == "omitted" else frels,
            )
        )
    series = FloorSeries(family_basis(finals[0], TARGET.interval, "potential_floor"), tuple(finals))
    selected = single_selection(series)
    selected = replace(
        selected, specification=replace(selected.specification, reconstruction=ReconstructionNeed.NOT_REQUIRED)
    )
    member = selected.members[0].identifier
    return finalize_floors(
        selected,
        required,
        tuple(physical),
        version="constant-season-floor",
        constructions=(FloorConstruction(member, tuple(rows)),),
        member_physical=tuple(FloorMemberAssessment(member, p) for p in physical),
    )


def test_supported_seasonal_threshold_maps_to_all365_daily_quality_adjusted_floors():
    result = seasonal_floor()
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.floors) == 365
    assert {f.sample.value for f in result.floors} == {Flow(6)}
    assert len(result.constructions[0].sources) == 1
    assert len(result.source_conditions) == 730


@pytest.mark.parametrize("permission", ("missing", "foreign"))
def test_seasonal_scope_alone_never_disaggregates_interval_mean(permission):
    result = seasonal_floor(permission=permission)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.floors == ()
    assert result.selection.supplied is not None


def test_daily_floor_outside_supported_season_fails_without_clipping():
    from fishy.pattern_calendar import AccountingYear

    result = seasonal_floor(original_period=AccountingYear(2002, 1, 0).interval)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.floors == ()


@pytest.mark.parametrize("final_study", ("omitted", "relaxed"))
def test_original_source_habitat_policy_survives_daily_quality_uplift(final_study):
    result = seasonal_floor(final_study=final_study)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.floors == ()
    assert len(result.source_conditions) == 730
    assert all(r.checks.finding is CheckFinding.FAIL for r in result.source_conditions)
    assert all(p.checks.finding is CheckFinding.PASS for p in result.physical)


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_zero_seasonal_study_maps_with_exact_supported_whole_source_permission(route):
    result = seasonal_floor(zero_route=route)
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.floors) == 365
    assert {f.sample.value for f in result.floors} == {Flow(6)}
    native = result.constructions[0].sources[0]
    assert native.selected_route is PotentialRoute.ZERO and native.floor == Flow(0)
    assert any(r.route is route and r.flow == Flow(0) for r in native.routes)
    assert len(result.source_conditions) == 730
    assert all(c.checks.finding is CheckFinding.PASS for c in result.source_conditions)


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
@pytest.mark.parametrize("permission", ["missing", "foreign"])
def test_zero_seasonal_study_does_not_infer_daily_equivalence_without_exact_permission(route, permission):
    result = seasonal_floor(zero_route=route, permission=permission)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.floors == ()
    assert result.selection.supplied is not None


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_zero_seasonal_study_permission_does_not_extend_outside_original_period(route):
    from fishy.pattern_calendar import AccountingYear

    result = seasonal_floor(zero_route=route, original_period=AccountingYear(2002, 1, 0).interval)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.floors == ()


@pytest.mark.parametrize("route", [PotentialRoute.HABITAT, PotentialRoute.HYDRAULIC])
def test_zero_seasonal_study_permission_never_disaggregates_annual_service_account(route):
    result = seasonal_floor(zero_route=route, annual_service=True)
    native = result.constructions[0].sources[0]
    assert native.selected_route is PotentialRoute.ZERO
    assert native.floor == Flow(0)
    assert next(r for r in native.routes if r.route is PotentialRoute.ZERO).conveyance is not None
    assert len(result.source_conditions) == 730
    assert all(c.checks.finding is CheckFinding.PASS for c in result.source_conditions)
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.floors == ()
    assert len(result.conveyance_conditions) == 730
    assert all(c.checks.finding is CheckFinding.UNKNOWN for c in result.conveyance_conditions)
