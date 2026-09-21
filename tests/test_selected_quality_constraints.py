"""Selected-family aggregation changes ecological totals, not original quality limits."""

from dataclasses import replace
from fractions import Fraction

import pytest

import examples.requirement_chain as example
from fishy.evidence import CheckFinding
from fishy.quantities import Flow
from fishy.requirement_family import assess_selected_family
from fishy.requirement_finalization import ClassAssessment, finalize_regime


@pytest.fixture(scope="module")
def chain():
    return example.run_chain()


def median_attempt(chain):
    final = chain.final
    classes = []
    for cls in final.selection.supplied.classes:
        member_rows = tuple(m.candidate.samples(cls.design) for m in final.selection.members)
        rows = []
        for index, sample in enumerate(cls.samples):
            value = Flow(sum(member[index].value.value for member in member_rows) / len(member_rows))
            rows.append(replace(sample, value=value, uncertainty=example.singleton(value), components=()))
        classes.append(replace(cls, samples=tuple(rows)))
    family = replace(final.selection.supplied, classes=tuple(classes))
    selection = assess_selected_family(
        final.selection.members, family, replace(final.selection.specification, threshold=Fraction(1))
    )
    physical = tuple(
        ClassAssessment(cls.design, example.final_assessment(sample))
        for cls in family.classes
        for sample in cls.samples
    )
    return finalize_regime(
        selection,
        final.method,
        physical[0].result.required,
        physical,
        duration_tests=tuple(item.test for item in final.duration),
        expected_duration_tests=(("A", "annual7-T100"), ("B", "annual7-T100")),
        version="complete-median-quality-regression",
        provenance=final.floor.sample.provenance,
        constructions=tuple(item.construction for item in final.constructions),
        member_physical=final.member_physical,
        member_duration_tests=tuple(item.test for item in final.member_duration),
    )


def test_complete_median_preserves_members_without_reapplying_their_ecological_minima(chain):
    original = chain.final
    result = median_attempt(chain)
    assert result.selection.checks.finding is CheckFinding.PASS
    assert result.selection.branch.value == "median"
    assert all(item.checks.finding is CheckFinding.PASS for item in result.constructions)
    assert all(item.result.checks.finding is CheckFinding.PASS for item in result.physical)
    assert result.selection.members == original.selection.members
    assert tuple(item.construction for item in result.constructions) == tuple(
        item.construction for item in original.constructions
    )
    assert result.member_physical == original.member_physical
    assert (
        tuple(
            replace(item, result=replace(item.result, candidate_basis=prior.result.candidate_basis))
            for item, prior in zip(result.member_duration, original.member_duration, strict=True)
        )
        == original.member_duration
    )
    assert all(item.result.mapping.mapping.receptor == Flow(1) for item in result.physical)
    assert all(
        composition.result.mapping.mapping.receptor == Flow(1)
        for item in result.constructions
        for composition in item.compositions
    )
    assert result.checks.finding is CheckFinding.PASS
    assert result.requirement is not None
    assert result.floor is not None
    assert all(len(cls.samples) == 365 for cls in result.requirement.classes)


def test_selected_median_still_enforces_original_concentration_under_weaker_fresh_checks(chain):
    original_quality = example.quality

    def stronger_member_quality(base, interval, member, **kwargs):
        if member == "B":
            kwargs["background_concentration"] = Fraction(14, 1000)
        return original_quality(base, interval, member, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(example, "quality", stronger_member_quality)
        strong_chain = example.run_chain(prepared=chain.prepared)
    result = median_attempt(strong_chain)
    assert result.selection.checks.finding is CheckFinding.PASS
    assert all(item.checks.finding is CheckFinding.PASS for item in result.constructions)
    assert all(item.result.checks.finding is CheckFinding.PASS for item in result.physical)
    assert result.member_physical == strong_chain.final.member_physical
    assert result.checks.finding is CheckFinding.FAIL
    assert result.requirement is None and result.floor is None
    assert any(
        check.check_id.startswith("selected:source_final:B:")
        and check.check_id.endswith(":original_quality")
        and check.finding is CheckFinding.FAIL
        for check in result.checks.checks
    )
