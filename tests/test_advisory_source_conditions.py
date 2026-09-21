"""Advisory source quality remains diagnostic across a complete direct-floor year."""

from dataclasses import replace

from examples.alternative_requirements import family_basis, local_quality, single_selection
from examples.requirement_chain import TARGET, accepted_evidence, samples
from examples.study_requirements import NEED, POTENTIAL, relation, selection
from fishy.evidence import CheckFinding, EvidenceScope
from fishy.floor_construction import FloorComponent, FloorConstruction, PotentialFloorSource
from fishy.potential_requirements import Applicability, PotentialStudy
from fishy.quality_activation import ActivationMode, ComponentStatus, QualityRoute, apply_quality_component
from fishy.quantities import Flow
from fishy.requirement_checks import FinalCondition, assess_requirement, sample_subject
from fishy.requirement_composition import compose_requirement
from fishy.requirement_family import FloorSeries, ReconstructionNeed, assess_selected_family
from fishy.requirement_finalization import FloorMemberAssessment, finalize_floors
from fishy.study_requirements import StudyScope


def finalize_quality(mode, final_quality=None):
    rows, physical, finals = [], [], []
    required = (FinalCondition.STUDY,) if final_quality is None else (FinalCondition.STUDY, FinalCondition.QUALITY)
    for base in samples(TARGET, 5, "potential-direct"):
        p = base.provenance
        scope = StudyScope(
            sample_subject(base),
            base.location,
            base.interval,
            p.scenario,
            p.reference_member,
            "sizing",
            "whole-year supported daily habitat",
        )
        evidence = accepted_evidence(
            EvidenceScope(scope.candidate, base.location.reach.identifier, p.reference_member, base.interval, "sizing"),
            p,
        )
        original = selection(5)
        study = replace(
            original,
            scope=scope,
            evidence=evidence,
            conditions=tuple(replace(c, scope=scope, evidence=evidence) for c in original.conditions),
        )
        rel = replace(relation(), scope=scope, evidence=evidence)
        source = PotentialFloorSource(
            scope,
            POTENTIAL,
            PotentialStudy(Applicability.APPLICABLE, "supported habitat relation", study, (rel,)),
            PotentialStudy(Applicability.NOT_APPLICABLE, "habitat first", None, ()),
            None,
            NEED,
        )
        q = local_quality(
            base, route=QualityRoute.FLOOR_ONLY, background_mg_l=10 if mode is ActivationMode.ADVISORY else 5
        )
        q = apply_quality_component(
            q.base,
            q.quality.boundary,
            q.quality.targets,
            replace(q.activation, mode=mode),
            q.source_control,
            q.accounts,
            q.background_mapping,
        )
        assert q.combined == Flow(5)
        if mode is ActivationMode.ADVISORY:
            assert q.status is ComponentStatus.ADVISORY
        composition = compose_requirement(base, p, quality=q)
        final = composition.candidate
        assert final is not None and final.value == Flow(5)
        rows.append(FloorComponent(source, composition))
        finals.append(final)
        final_scope = replace(scope, candidate=sample_subject(final))
        fe = accepted_evidence(
            EvidenceScope(
                final_scope.candidate, base.location.reach.identifier, p.reference_member, base.interval, "sizing"
            ),
            p,
        )
        fs = replace(
            study,
            scope=final_scope,
            evidence=fe,
            conditions=tuple(replace(c, scope=final_scope, evidence=fe) for c in study.conditions),
        )
        fr = replace(rel, scope=final_scope, evidence=fe)
        final_q = (
            None if final_quality is None else local_quality(base, route=QualityRoute.FLOOR_ONLY, background_mg_l=5)
        )
        checked = assess_requirement(final, required, quality=final_q, study_selection=fs, study_relations=(fr,))
        assert checked.checks.finding is CheckFinding.PASS
        physical.append(checked)
    series = FloorSeries(family_basis(finals[0], TARGET.interval, "potential_floor"), tuple(finals))
    selected = single_selection(series)
    selected = assess_selected_family(
        selected.members,
        series,
        replace(
            selected.specification,
            reconstruction=ReconstructionNeed.NOT_REQUIRED,
            source="actual artificial potential route",
        ),
    )
    member = selected.members[0].identifier
    return finalize_floors(
        selected,
        required,
        tuple(physical),
        version="advisory-source-regression",
        constructions=(FloorConstruction(member, tuple(rows)),),
        member_physical=tuple(FloorMemberAssessment(member, checked) for checked in physical),
    )


def test_advisory_source_needs_no_final_quality_record_for_365_supported_floors():
    result = finalize_quality(ActivationMode.ADVISORY)
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.floors) == 365
    assert all(f.sample.value == Flow(5) for f in result.floors)
    assert all(
        c.quality is not None and c.quality.status is ComponentStatus.ADVISORY
        for construction in result.constructions
        for c in construction.compositions
    )


def test_binding_source_quality_still_requires_final_recheck():
    result = finalize_quality(ActivationMode.HYPOTHETICAL)
    assert result.checks.finding is not CheckFinding.PASS
    assert not result.floors
    assert any("source_quality" in c.check_id and c.finding is not CheckFinding.PASS for c in result.checks.checks)


def test_present_final_quality_cannot_change_advisory_activation():
    result = finalize_quality(ActivationMode.ADVISORY, final_quality="different activation")
    assert result.checks.finding is CheckFinding.FAIL
    assert not result.floors
    assert any("policy" in c.check_id and c.finding is CheckFinding.FAIL for c in result.checks.checks)


def test_forged_advisory_status_cannot_remove_binding_policy():
    from fishy.source_policy import quality_policy_matches

    base = samples(TARGET, 5, "potential-direct")[0]
    active = local_quality(base, route=QualityRoute.FLOOR_ONLY, background_mg_l=5)
    forged = replace(active, status=ComponentStatus.ADVISORY)
    assert not quality_policy_matches(forged, None)
    assert not quality_policy_matches(None, forged)
