"""Supported constant potential threshold × real daily calendar → direct floors."""

from dataclasses import replace

import pytest

from examples.alternative_requirements import family_basis, local_quality, single_selection
from examples.requirement_chain import TARGET, accepted_evidence, samples
from examples.study_requirements import NEED, POTENTIAL, relation, selection
from fishy.evidence import CheckFinding, EvidenceScope
from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
from fishy.potential_requirements import Applicability, PotentialStudy
from fishy.quality_activation import QualityRoute
from fishy.quantities import Flow
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_family import FloorSeries, ReconstructionNeed
from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
from fishy.source_conditions import source_period_scope
from fishy.study_requirements import StudyScope


def seasonal_floor(*, permission="supported", original_period=None, final_study="original"):
    from fractions import Fraction

    from fishy.hydraulics import StateBounds

    final_flow = 6 if final_study == "original" else 10
    required = (FinalCondition.QUALITY,) if final_study == "omitted" else (FinalCondition.QUALITY, FinalCondition.STUDY)
    bases = samples(TARGET, 5, "potential-direct")
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
    old = selection(5)
    study = replace(
        old,
        scope=scope,
        evidence=evidence,
        conditions=tuple(replace(c, scope=scope, evidence=evidence) for c in old.conditions),
    )
    rel = replace(relation(), scope=scope, evidence=evidence)
    support = accepted_evidence(source_period_scope(study, (rel,)), p)
    if permission == "foreign":
        support = replace(support, scope=replace(support.scope, product="unrelated-threshold"))
    source = PotentialFloorSource(
        scope,
        POTENTIAL,
        PotentialStudy(Applicability.APPLICABLE, "supported habitat relation", study, (rel,)),
        PotentialStudy(Applicability.NOT_APPLICABLE, "habitat selected", None, ()),
        None,
        NEED,
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
        frel = replace(rel, scope=fscope, evidence=fe)
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
                study_relations=() if final_study == "omitted" else (frel,),
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
