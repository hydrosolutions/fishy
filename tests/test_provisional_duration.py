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
