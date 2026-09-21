"""Pre-quality diagnostics bind actual sources and never borrow final context."""

from dataclasses import replace
from datetime import timedelta

import pytest
from test_requirement_finalization import inputs

from fishy.design_conditions import DesignClass
from fishy.evidence import CheckFinding
from fishy.low_flow_safeguard import AssessmentStage
from fishy.provisional_duration import recompute_provisional_duration
from fishy.quality_activation import ActivationMode
from fishy.requirement_construction import assess_construction
from fishy.time import Interval


@pytest.fixture(scope="module")
def prepared():
    selection, _, tests, constructions = inputs(ActivationMode.HYPOTHETICAL)
    sources = tuple(assess_construction(m, c) for m, c in zip(selection.members, constructions, strict=True))
    return selection.members, sources, tests


def run(prepared, **kwargs):
    members, sources, tests = prepared
    return recompute_provisional_duration(members, sources, tests, (("A", "annual7"), ("B", "annual7")), **kwargs)


def test_actual_bases_are_assessed_without_caller_summaries(prepared):
    records = run(prepared)
    assert len(records) == 2 * len(DesignClass)
    for record in records:
        assert record.result.stage is AssessmentStage.PROVISIONAL
        assert record.result.point.finding is CheckFinding.FAIL
        assert all(s.value.value == 8 for s in record.source)
        assert record.result.candidate == record.source
        assert record.result.comparisons[0].point is CheckFinding.UNKNOWN
        assert any(c.finding is CheckFinding.UNKNOWN for c in record.checks.checks)


def test_missing_test_and_source_remain_explicit(prepared):
    members, _, _ = prepared
    records = run((members, (), ()))
    assert len(records) == 2 * len(DesignClass)
    assert all(r.result is None and r.checks.finding is CheckFinding.UNKNOWN for r in records)
    assert all(r.source == () for r in records)


def test_missing_test_retains_source(prepared):
    members, sources, _ = prepared
    records = run((members, sources, ()))
    assert all(r.source and r.result is None and r.checks.finding is CheckFinding.UNKNOWN for r in records)


def test_explicit_prequality_context_used_not_final_context(prepared):
    _, _, tests = prepared
    context = []
    for record, test in zip(
        run(prepared), sorted(tests, key=lambda t: (t.member, t.identifier, t.design.value)), strict=True
    ):
        first = record.source[0]
        prefix = tuple(
            replace(
                first,
                interval=Interval(
                    first.interval.start - timedelta(days=i), first.interval.start - timedelta(days=i - 1)
                ),
            )
            for i in range(6, 0, -1)
        )
        context.append(replace(test, predecessors=prefix, reference_relation=None))
    records = run(prepared, provisional_duration_tests=tuple(context))
    assert all(r.result.comparisons[0].point is CheckFinding.FAIL for r in records)
    assert all(r.result.candidate[:6] == c.predecessors for r, c in zip(records, context, strict=True))


def test_context_cannot_change_test_threshold(prepared):
    _, _, tests = prepared
    changed = replace(tests[0], threshold=replace(tests[0].threshold, profile_version="changed"))
    with pytest.raises(ValueError, match="threshold"):
        run(prepared, provisional_duration_tests=(changed,))


def test_missing_source_with_configured_test_remains_unknown(prepared):
    members, _, tests = prepared
    records = run((members, (), tests))
    assert len(records) == 2 * len(DesignClass)
    assert all(r.result is None and r.checks.finding is CheckFinding.UNKNOWN for r in records)


def test_context_must_identify_declared_member_and_class(prepared):
    _, _, tests = prepared
    with pytest.raises(ValueError, match="undeclared or duplicate"):
        run(prepared, provisional_duration_tests=(tests[0], tests[0]))
    with pytest.raises(ValueError, match="undeclared or duplicate"):
        run(prepared, provisional_duration_tests=(replace(tests[0], identifier="unconfigured"),))


def altered_sources(prepared, transform):
    members, sources, tests = prepared
    return (
        members,
        tuple(
            replace(
                a,
                compositions=tuple(
                    replace(c, result=replace(c.result, base=transform(c.result.base))) for c in a.compositions
                ),
            )
            for a in sources
        ),
        tests,
    )


def altered_native_sources(prepared, transform):
    members, sources, tests = prepared
    changed = []
    for assessment in sources:
        native = assessment.recomputed_source
        family = native.candidate
        classes = tuple(replace(c, samples=tuple(transform(s) for s in c.samples)) for c in family.classes)
        first = classes[0].samples[0]
        calendar = replace(family.calendar, year=first.interval.start.year)
        changed.append(
            replace(
                assessment,
                recomputed_source=replace(
                    native, candidate=replace(family, location=first.location, calendar=calendar, classes=classes)
                ),
            )
        )
    return members, tuple(changed), tests


def test_source_reference_location_mismatch_retains_unknown(prepared):
    changed = altered_native_sources(
        prepared,
        lambda s: replace(
            s, location=replace(s.location, section=replace(s.location.section, identifier="actual-upstream-source"))
        ),
    )
    records = run(changed)
    assert all(r.result is None and r.checks.finding is CheckFinding.UNKNOWN for r in records)
    assert all(r.source[0].location.section.identifier == "actual-upstream-source" for r in records)
    assert all(any(c.check_id == "reference_location" for c in r.checks.checks) for r in records)


def test_source_outside_assessment_period_retains_native_unknown(prepared):
    changed = altered_native_sources(
        prepared,
        lambda s: replace(
            s, interval=Interval(s.interval.start - timedelta(days=365), s.interval.end - timedelta(days=365))
        ),
    )
    records = run(changed)
    assert all(r.result.point.finding is CheckFinding.UNKNOWN for r in records)
    assert all(all(c.window.mean is None for c in r.result.comparisons) for r in records)


def test_changed_composition_cannot_replace_native_source(prepared):
    from fishy.quantities import Flow

    changed = altered_sources(prepared, lambda s: replace(s, value=Flow(999), uncertainty=None))
    records = run(changed)
    assert all(all(s.value == Flow(8) for s in r.source) for r in records)
    assert all(r.result.point.finding is CheckFinding.FAIL for r in records)


def test_recomputed_rejected_composition_still_assesses_native_source(prepared):
    from fishy.quantities import Flow

    members, sources, tests = prepared
    changed = []
    for member, assessment in zip(members, sources, strict=True):
        construction = assessment.construction
        forged = replace(
            construction,
            compositions=tuple(
                replace(c, result=replace(c.result, base=replace(c.result.base, value=Flow(999), uncertainty=None)))
                for c in construction.compositions
            ),
        )
        result = assess_construction(member, forged)
        assert result.checks.finding is CheckFinding.FAIL
        assert not result.compositions
        changed.append(result)
    records = run((members, tuple(changed), tests))
    assert all(all(s.value == Flow(8) for s in r.source) for r in records)
    assert all(r.result.point.finding is CheckFinding.FAIL for r in records)


@pytest.fixture(scope="module")
def mapped_chain():
    from examples.requirement_chain import run_chain

    chain = run_chain()
    final = chain.final
    contexts = []
    for item in final.duration:
        test = item.test
        classes = chain.families[test.member].classes
        index = next(i for i, cls in enumerate(classes) if cls.design is test.design)
        local = chain.provisional[test.member][index]
        prefix = tuple(s for s in local.candidate if s.interval.end <= final.selection.supplied.basis.period.start)
        contexts.append(
            replace(
                test,
                threshold=local.threshold,
                predecessors=prefix,
                predecessor_basis=local.windows.predecessor_basis,
                scientific_assessment=local.scientific_assessment,
                uncertainty_support=local.windows.uncertainty_support,
                reference_relation=local.reference_relation,
                candidate_support=tuple(
                    s for s in local.candidate if s.interval.start >= final.selection.supplied.basis.period.start
                ),
            )
        )
    return chain, tuple(contexts)


def test_u9_public_finalization_retains_actual_local_source_tests(mapped_chain):
    from fishy.requirement_finalization import finalize_regime

    chain, contexts = mapped_chain
    final = chain.final
    assert len(final.provisional) == 8
    assert all(local.checks.finding is CheckFinding.PASS for local in final.provisional)
    result = finalize_regime(
        final.selection,
        final.method,
        final.physical[0].result.required,
        final.physical,
        duration_tests=tuple(d.test for d in final.duration),
        expected_duration_tests=(("A", "annual7-T100"), ("B", "annual7-T100")),
        version="U9-local-provisional-regression",
        provenance=final.floor.sample.provenance,
        constructions=tuple(c.construction for c in final.constructions),
        member_physical=final.member_physical,
        member_duration_tests=tuple(d.test for d in final.member_duration),
        provisional_duration_tests=contexts,
    )
    assert result.checks.finding is CheckFinding.PASS
    assert len(result.provisional_diagnostics) == len(result.provisional) == 8
    assert result.requirement is not None
    local_tests = {(t.member, t.identifier, t.design): t for t in contexts}
    for diagnostic in result.provisional_diagnostics:
        test = local_tests[diagnostic.member, diagnostic.identifier, diagnostic.design]
        assert diagnostic.result is not None
        assert diagnostic.result.threshold == test.threshold
        assert diagnostic.result.scientific_assessment == test.scientific_assessment
        assert diagnostic.result.permission.finding is CheckFinding.PASS
        assert diagnostic.result.point.finding is CheckFinding.PASS
        assert diagnostic.result.checks.finding is CheckFinding.PASS
        assert diagnostic.result.stage is AssessmentStage.PROVISIONAL
        assert all(s.location == test.threshold.reference.location for s in diagnostic.source)
        assert diagnostic.source[0].location != result.requirement.basis.location


def test_u9_local_threshold_never_borrows_final_scientific_permission(mapped_chain):
    chain, contexts = mapped_chain
    final = chain.final
    results = recompute_provisional_duration(
        final.selection.members,
        final.constructions,
        tuple(d.test for d in final.duration),
        (("A", "annual7-T100"), ("B", "annual7-T100")),
        provisional_duration_tests=tuple(replace(t, scientific_assessment=None) for t in contexts),
    )
    for record in results:
        assert record.result is not None
        assert record.result.permission.finding is CheckFinding.UNKNOWN
        assert record.result.scientific_assessment is None


@pytest.mark.parametrize("changed_policy", ("return_period", "purpose"))
def test_explicit_local_reference_cannot_change_configured_policy(prepared, changed_policy):
    from fishy.low_flow_frequency import LowFlowReturnPeriod
    from fishy.scientific_acceptance import UsePurpose

    _, _, tests = prepared
    test = tests[0]
    if changed_policy == "return_period":
        changed = replace(test, threshold=replace(test.threshold, return_period=LowFlowReturnPeriod(3)))
    else:
        changed = replace(test, purpose=UsePurpose.SCREENING)
    with pytest.raises(ValueError, match="threshold policy or purpose"):
        run(prepared, provisional_duration_tests=(changed,))


def test_local_reference_rejects_final_location_scientific_permission(mapped_chain):
    chain, contexts = mapped_chain
    final = chain.final
    final_tests = {(d.test.member, d.test.identifier, d.test.design): d.test for d in final.duration}
    results = recompute_provisional_duration(
        final.selection.members,
        final.constructions,
        tuple(d.test for d in final.duration),
        (("A", "annual7-T100"), ("B", "annual7-T100")),
        provisional_duration_tests=tuple(
            replace(t, scientific_assessment=final_tests[t.member, t.identifier, t.design].scientific_assessment)
            for t in contexts
        ),
    )
    for record in results:
        assert record.result is not None
        assert record.result.permission.finding is not CheckFinding.PASS


@pytest.mark.parametrize("mutation", ("value", "location", "interval", "provenance", "duplicate"))
def test_candidate_uncertainty_support_cannot_replace_native_source(prepared, mutation):
    from fishy.quantities import Flow

    _, _, tests = prepared
    source = run(prepared)[0].source[0]
    if mutation == "value":
        changed = replace(source, value=Flow(999), uncertainty=None)
    elif mutation == "location":
        changed = replace(source, location=replace(source.location, mapping_version="wrong-scope"))
    elif mutation == "interval":
        changed = replace(
            source,
            interval=Interval(source.interval.start - timedelta(days=1), source.interval.end - timedelta(days=1)),
        )
    elif mutation == "provenance":
        changed = replace(source, provenance=replace(source.provenance, configuration_version="wrong-source"))
    else:
        changed = source
    support = (changed, changed) if mutation == "duplicate" else (changed,)
    context = replace(tests[0], candidate_support=support)
    with pytest.raises(ValueError, match="candidate support"):
        run(prepared, provisional_duration_tests=(context,))


def test_u9_missing_local_candidate_support_remains_unknown(mapped_chain):
    chain, contexts = mapped_chain
    final = chain.final
    records = recompute_provisional_duration(
        final.selection.members,
        final.constructions,
        tuple(d.test for d in final.duration),
        (("A", "annual7-T100"), ("B", "annual7-T100")),
        provisional_duration_tests=tuple(replace(t, candidate_support=()) for t in contexts),
    )
    for record in records:
        assert record.result is not None
        assert record.result.point.finding is CheckFinding.PASS
        assert record.result.uncertainty.finding is CheckFinding.UNKNOWN
        assert record.result.checks.finding is CheckFinding.UNKNOWN
