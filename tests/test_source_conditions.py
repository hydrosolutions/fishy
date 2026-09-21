"""source_condition_witnesses : StudySelection × FlowSample → CheckSummary.

Supported synthetic habitat Q5→100m2, Q10→20m2 exposes post-quality failure.
No criterion or numerical value is a policy default or ecological validation.
"""

from dataclasses import replace
from fractions import Fraction

import pytest

from examples.study_requirements import condition, relation, selection
from fishy.evidence import CheckFinding, Completeness, EvidenceScope, ScientificAdequacy
from fishy.flows import FlowSample, Presence
from fishy.hydraulics import StateBounds
from fishy.quantities import Flow
from fishy.receptor_delivery import (
    ControlMapping,
    DeliveryContext,
    WaterRelationship,
    control_equivalent,
    delivery_scope,
)
from fishy.requirement_checks import sample_subject
from fishy.source_conditions import assess_source_conditions
from fishy.study_requirements import ResponsePoint, assess_study


def candidate(flow=10):
    source = selection()
    return FlowSample(
        source.scope.location, source.scope.period, Flow(flow), Presence.PRESENT, source.evidence.provenance
    )


def fresh(source, relations, final, *, local_flow=None):
    """Explicit fresh synthetic review at the actual final subject, not transferred permission."""
    scope = replace(
        source.scope,
        candidate=sample_subject(final),
        period=final.interval,
        scenario=final.provenance.scenario,
        reference_member=final.provenance.reference_member,
    )
    evidence = replace(
        source.evidence,
        scope=EvidenceScope(
            scope.candidate, scope.location.reach.identifier, scope.reference_member, scope.period, scope.purpose
        ),
        provenance=replace(final.provenance, source="fresh independently supplied synthetic final review"),
    )
    conditions = tuple(
        replace(c, scope=scope, evidence=evidence, assessed_value="fresh final-candidate synthetic assessment")
        for c in source.conditions
    )
    holistic = (
        None
        if source.holistic_assessment is None
        else replace(source.holistic_assessment, scope=scope, evidence=evidence)
    )
    chosen = replace(
        source,
        scope=scope,
        selected_flow=final.value if local_flow is None else local_flow,
        evidence=evidence,
        conditions=conditions,
        holistic_assessment=holistic,
    )
    new_relations = tuple(replace(r, scope=scope, evidence=evidence) for r in relations)
    return assess_study(chosen, new_relations)


def test_nonmonotonic_source_failure_survives_omitted_final_study_and_temporal_coverage():
    source, relations = selection(5), (relation(),)
    assert assess_study(source, relations).checks.finding is CheckFinding.PASS
    final = candidate(10)
    result = assess_source_conditions(source, relations, final)
    assert result.local_flow == Flow(10)
    assert result.responses[0].value == StateBounds(Fraction(20), Fraction(20))
    assert result.responses[0].check.finding is CheckFinding.FAIL
    assert result.checks.finding is CheckFinding.FAIL
    assert result.checks.completeness is Completeness.INCOMPLETE
    assert source.selected_flow == Flow(5) and source.scope.candidate == "candidate1"
    assert result.supplied is None


def test_numerical_pass_without_fresh_final_support_is_not_final_permission():
    source, relations = selection(), (relation(),)
    final = candidate(5)
    missing = assess_source_conditions(source, relations, final)
    assert missing.responses[0].check.finding is CheckFinding.PASS
    assert missing.checks.finding is CheckFinding.UNKNOWN
    supplied = fresh(source, relations, final)
    assert assess_source_conditions(source, relations, final, supplied=supplied).checks.finding is CheckFinding.PASS
    stale = assess_study(source, relations)
    assert assess_source_conditions(source, relations, final, supplied=stale).checks.finding is CheckFinding.FAIL


@pytest.mark.parametrize("launder", ("criterion", "relation", "both"))
def test_relaxed_final_criterion_or_flattering_relation_cannot_hide_original_failure(launder):
    source, relations = selection(), (relation(),)
    final = candidate(10)
    supplied = fresh(source, relations, final)
    chosen = supplied.selection
    models = tuple(r.relation for r in supplied.responses)
    if launder in ("criterion", "both"):
        chosen = replace(
            chosen, criteria=(replace(chosen.criteria[0], acceptable=StateBounds(Fraction(10), Fraction(100))),)
        )
    if launder in ("relation", "both"):
        models = tuple(
            replace(r, points=tuple(ResponsePoint(p.flow, StateBounds(Fraction(100), Fraction(100))) for p in r.points))
            for r in models
        )
    flattering = assess_study(chosen, models)
    assert flattering.checks.finding is CheckFinding.PASS
    result = assess_source_conditions(source, relations, final, supplied=flattering)
    assert result.checks.finding is CheckFinding.FAIL
    assert result.responses[0].value is not None
    assert result.responses[0].value.lower == 20
    assert result.responses[0].check.finding is CheckFinding.FAIL
    assert any(
        c.check_id.startswith(("criterion_policy:", "relation_policy:")) and c.finding is CheckFinding.FAIL
        for c in result.checks.checks
    )


@pytest.mark.parametrize("missing", ("sediment", "hydraulic", "flood_safety", "ramping"))
def test_natural_top_source_required_conditions_cannot_be_removed_from_final_manifest(missing):
    source = selection(8, required=("sediment", "hydraulic", "flood_safety", "ramping"))
    final = candidate(8)
    supplied = fresh(source, (relation(),), final)
    chosen = replace(
        supplied.selection,
        required_conditions=tuple(n for n in source.required_conditions if n != missing),
        conditions=tuple(c for c in supplied.selection.conditions if c.component != missing),
    )
    incomplete = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert incomplete.checks.finding is CheckFinding.PASS
    result = assess_source_conditions(source, (relation(),), final, supplied=incomplete)
    assert result.responses[0].value is not None
    assert result.responses[0].value.lower == 52
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert any(
        c.check_id == "condition_policy:" + missing and c.finding is CheckFinding.UNKNOWN for c in result.checks.checks
    )


def test_temporal_limit_change_and_holistic_omission_cannot_pass():
    source = selection()
    final = candidate(5)
    supplied = fresh(source, (relation(),), final)
    chosen = replace(
        supplied.selection, conditions=(replace(supplied.selection.conditions[0], criterion="no ramp limit"),)
    )
    changed = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert assess_source_conditions(source, (relation(),), final, supplied=changed).checks.finding is CheckFinding.FAIL
    holistic = replace(condition("holistic_objective"), criterion="mandatory holistic objective")
    source = replace(source, holistic_assessment=holistic)
    supplied = fresh(source, (relation(),), final)
    chosen = replace(supplied.selection, holistic_assessment=None)
    omitted = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert (
        assess_source_conditions(source, (relation(),), final, supplied=omitted).checks.finding is CheckFinding.UNKNOWN
    )


def mapped_final(relationship):
    original = candidate(10 if relationship is WaterRelationship.SAME_WATER else 8)
    upstream = replace(original.location, section=replace(original.location.section, identifier="upstream"))
    final = replace(original, location=upstream)
    ctx = DeliveryContext(
        original.location, final.interval, sample_subject(final), "supported final mapping", final.provenance
    )
    mapping = ControlMapping(
        ctx,
        upstream,
        original.location,
        Flow(5),
        Flow(10 if relationship is WaterRelationship.SAME_WATER else 3),
        relationship,
        "explicit zero-loss no-delay mapping",
    )
    source = selection()
    evidence = replace(source.evidence, scope=delivery_scope(ctx, mapping), provenance=final.provenance)
    return final, control_equivalent(mapping, evidence)


def test_same_water_evaluates_actual_shared_flow_not_smaller_continuing_lower_bound():
    final, mapping = mapped_final(WaterRelationship.SAME_WATER)
    result = assess_source_conditions(selection(), (relation(),), final, mapping=mapping)
    assert mapping.mapping.continuing == Flow(5)
    assert result.local_flow == Flow(10)
    assert result.responses[0].value is not None
    assert result.responses[0].value.lower == 20
    assert result.checks.finding is CheckFinding.FAIL


def test_lateral_evaluates_continuing_flow_with_supported_exact_mapping():
    final, mapping = mapped_final(WaterRelationship.LATERAL)
    source = selection()
    supplied = fresh(source, (relation(),), final, local_flow=Flow(5))
    result = assess_source_conditions(source, (relation(),), final, mapping=mapping, supplied=supplied)
    assert result.local_flow == Flow(5)
    assert result.checks.finding is CheckFinding.PASS
    assert (
        assess_source_conditions(source, (relation(),), final, supplied=supplied).checks.finding is CheckFinding.UNKNOWN
    )
    missing = replace(mapping, evidence=None)
    assert (
        assess_source_conditions(source, (relation(),), final, mapping=missing).checks.finding is CheckFinding.UNKNOWN
    )
    changed = replace(final, value=Flow(9))
    assert assess_source_conditions(source, (relation(),), changed, mapping=mapping).checks.finding is CheckFinding.FAIL


def test_unsupported_original_relation_cannot_promote_exploratory_violation_to_supported_failure():
    unsupported = replace(
        relation(), evidence=replace(relation().evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED)
    )
    result = assess_source_conditions(selection(), (unsupported,), candidate(10))
    assert result.responses[0].numerical_finding is CheckFinding.FAIL
    assert result.responses[0].check.finding is CheckFinding.UNKNOWN
    assert result.checks.finding is CheckFinding.UNKNOWN


def test_supplemental_process_constraints_are_required_without_fabricated_study_evidence():
    from fishy.source_conditions import assess_process_conditions

    source = selection(required=("temperature", "salinity"))
    final = candidate(5)
    supplied = fresh(source, (relation(),), final)
    assert assess_process_conditions(source.conditions, final, supplied=supplied).checks.finding is CheckFinding.PASS
    assert assess_process_conditions(source.conditions, final).checks.finding is CheckFinding.UNKNOWN
    chosen = replace(
        supplied.selection, required_conditions=("temperature",), conditions=supplied.selection.conditions[:1]
    )
    missing = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert assess_process_conditions(source.conditions, final, supplied=missing).checks.finding is CheckFinding.UNKNOWN
    failed_condition = replace(supplied.selection.conditions[0], finding=CheckFinding.FAIL)
    chosen = replace(supplied.selection, conditions=(failed_condition, supplied.selection.conditions[1]))
    failed = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert assess_process_conditions(source.conditions, final, supplied=failed).checks.finding is CheckFinding.FAIL
    changed = replace(failed_condition, criterion="relaxed temperature", finding=CheckFinding.PASS)
    chosen = replace(supplied.selection, conditions=(changed, supplied.selection.conditions[1]))
    relaxed = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert assess_process_conditions(source.conditions, final, supplied=relaxed).checks.finding is CheckFinding.FAIL


def test_seasonal_daily_source_application_requires_separate_full_source_permission():
    from datetime import timedelta

    from fishy.source_conditions import SourcePeriodMapping, source_period_scope
    from fishy.time import Interval

    original = selection()
    scope = replace(
        original.scope, period=Interval(original.scope.period.start, original.scope.period.end + timedelta(days=1))
    )
    evidence = replace(original.evidence, scope=replace(original.evidence.scope, period=scope.period))
    source = replace(
        original,
        scope=scope,
        evidence=evidence,
        conditions=tuple(replace(c, scope=scope, evidence=evidence) for c in original.conditions),
    )
    model = replace(relation(), scope=scope, evidence=evidence)
    final = candidate(5)
    supplied = fresh(source, (model,), final)
    assert assess_source_conditions(source, (model,), final, supplied=supplied).checks.finding is CheckFinding.FAIL
    missing = assess_source_conditions(
        source, (model,), final, supplied=supplied, period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD
    )
    assert missing.checks.finding is CheckFinding.UNKNOWN
    permission = replace(source.evidence, scope=source_period_scope(source, (model,)))
    accepted = assess_source_conditions(
        source,
        (model,),
        final,
        supplied=supplied,
        period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
        period_permission=permission,
    )
    assert accepted.checks.finding is CheckFinding.PASS
    assert permission.scope.period == source.scope.period
    second = replace(final, interval=Interval(final.interval.end, source.scope.period.end))
    assert (
        assess_source_conditions(
            source,
            (model,),
            second,
            supplied=fresh(source, (model,), second),
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permission=permission,
        ).checks.finding
        is CheckFinding.PASS
    )
    wrong = replace(permission, scope=replace(permission.scope, product="unrelated-source"))
    assert (
        assess_source_conditions(
            source,
            (model,),
            final,
            supplied=supplied,
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permission=wrong,
        ).checks.finding
        is CheckFinding.UNKNOWN
    )
    changed = replace(model, survey="another geometry")
    assert (
        assess_source_conditions(
            source,
            (changed,),
            final,
            supplied=fresh(source, (changed,), final),
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permission=permission,
        ).checks.finding
        is CheckFinding.UNKNOWN
    )
    outside = replace(final, interval=Interval(source.scope.period.end, source.scope.period.end + timedelta(days=1)))
    assert (
        assess_source_conditions(
            source,
            (model,),
            outside,
            supplied=fresh(source, (model,), outside),
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permission=permission,
        ).checks.finding
        is CheckFinding.FAIL
    )


def test_supplemental_conditions_use_independent_full_source_temporal_permissions():
    from datetime import timedelta

    from fishy.source_conditions import SourcePeriodMapping, assess_process_conditions, source_period_scope
    from fishy.time import Interval

    original = selection(required=("temperature",))
    scope = replace(
        original.scope, period=Interval(original.scope.period.start, original.scope.period.end + timedelta(days=1))
    )
    ev = replace(original.evidence, scope=replace(original.evidence.scope, period=scope.period))
    source = replace(
        original,
        scope=scope,
        evidence=ev,
        conditions=tuple(replace(c, scope=scope, evidence=ev) for c in original.conditions),
    )
    model = replace(relation(), scope=scope, evidence=ev)
    final = candidate(5)
    supplied = fresh(source, (model,), final)
    missing = assess_process_conditions(
        source.conditions, final, supplied=supplied, period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD
    )
    assert missing.checks.finding is CheckFinding.UNKNOWN
    permission = replace(ev, scope=source_period_scope(source.conditions[0]))
    accepted = assess_process_conditions(
        source.conditions,
        final,
        supplied=supplied,
        period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
        period_permissions=(permission,),
    )
    assert accepted.checks.finding is CheckFinding.PASS
    wrong = replace(permission, provenance=replace(permission.provenance, configuration_version="another-policy"))
    assert (
        assess_process_conditions(
            source.conditions,
            final,
            supplied=supplied,
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permissions=(wrong,),
        ).checks.finding
        is CheckFinding.FAIL
    )
    unaccepted = replace(
        supplied.selection.conditions[0],
        evidence=replace(
            supplied.selection.conditions[0].evidence, scientific_adequacy=ScientificAdequacy.NOT_ACCEPTED
        ),
    )
    chosen = replace(supplied.selection, conditions=(unaccepted,))
    unsupported = assess_study(chosen, tuple(r.relation for r in supplied.responses))
    assert (
        assess_process_conditions(
            source.conditions,
            final,
            supplied=unsupported,
            period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
            period_permissions=(permission,),
        ).checks.finding
        is CheckFinding.UNKNOWN
    )


@pytest.mark.parametrize("relationship,local", ((WaterRelationship.LATERAL, 5), (WaterRelationship.SAME_WATER, 10)))
def test_public_requirement_boundary_accepts_exact_mapped_local_study_then_rechecks_source(relationship, local):
    from fishy.requirement_checks import FinalCondition, assess_requirement

    final, mapping = mapped_final(relationship)
    source = selection()
    supplied = fresh(source, (relation(),), final, local_flow=Flow(local))
    relations = tuple(r.relation for r in supplied.responses)
    assessed = assess_requirement(
        final,
        (FinalCondition.MAPPING, FinalCondition.STUDY),
        mapping=mapping,
        study_selection=supplied.selection,
        study_relations=relations,
    )
    assert assessed.study is not None
    assert assessed.study.selection.scope.location == source.scope.location
    assert assessed.study.selection.selected_flow == Flow(local)
    result = assess_source_conditions(source, (relation(),), final, mapping=mapping, supplied=assessed.study)
    expected = CheckFinding.PASS if relationship is WaterRelationship.LATERAL else CheckFinding.FAIL
    assert assessed.checks.finding is result.checks.finding is expected
    wrong = replace(supplied.selection, selected_flow=Flow(local + 1))
    with pytest.raises(ValueError, match="discharge|flow"):
        assess_requirement(
            final,
            (FinalCondition.MAPPING, FinalCondition.STUDY),
            mapping=mapping,
            study_selection=wrong,
            study_relations=relations,
        )


@pytest.mark.parametrize("hours", (12, 48))
def test_constant_threshold_daily_permission_does_not_infer_subdaily_or_aggregate_applicability(hours):
    from datetime import timedelta

    from fishy.source_conditions import SourcePeriodMapping, source_period_scope
    from fishy.time import Interval

    original = selection()
    scope = replace(
        original.scope, period=Interval(original.scope.period.start, original.scope.period.end + timedelta(days=1))
    )
    ev = replace(original.evidence, scope=replace(original.evidence.scope, period=scope.period))
    source = replace(
        original,
        scope=scope,
        evidence=ev,
        conditions=tuple(replace(c, scope=scope, evidence=ev) for c in original.conditions),
    )
    model = replace(relation(), scope=scope, evidence=ev)
    final = replace(candidate(5), interval=Interval(scope.period.start, scope.period.start + timedelta(hours=hours)))
    permission = replace(ev, scope=source_period_scope(source, (model,)))
    supplied = fresh(source, (model,), final)
    result = assess_source_conditions(
        source,
        (model,),
        final,
        supplied=supplied,
        period_mapping=SourcePeriodMapping.CONSTANT_THRESHOLD,
        period_permission=permission,
    )
    assert result.checks.finding is CheckFinding.UNKNOWN
    assert result.local_flow is None
    assert any(c.check_id == "period_application" and "daily" in " ".join(c.reasons) for c in result.checks.checks)
    if hours == 48:
        # Exact original non-daily domains remain legitimate; only conversion is constrained.
        assert assess_source_conditions(source, (model,), final, supplied=supplied).checks.finding is CheckFinding.PASS
